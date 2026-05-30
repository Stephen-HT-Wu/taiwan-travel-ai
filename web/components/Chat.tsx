"use client";

import { useState, useRef, useEffect, useMemo, FormEvent, KeyboardEvent } from "react";
import dynamic from "next/dynamic";
import styles from "./Chat.module.css";
import MarkdownContent from "./MarkdownContent";
import type { MapFocusTarget, MapPlace, MapPlaceInput } from "./mapTypes";
import { filterPlacesMentionedInText, mergeMapPlaces, resolveDisplayPlaces } from "./mapTypes";
import { getOrCreateSessionId } from "../lib/sessionId";
import { openGoogleMaps } from "../lib/googleMaps";

const MapPanel = dynamic(() => import("./MapPanel"), { ssr: false });

type Message = {
  role: "user" | "assistant";
  content: string;
  activities?: ActivityItem[];
  places?: MapPlace[];
};

type Phase = "thinking" | "tool" | "writing" | "done";

type ActivityItem = {
  id: string;
  type: "status" | "tool";
  phase?: Phase;
  message?: string;
  name?: string;
  label?: string;
  source?: string;
  provider?: string;
  status?: "running" | "done" | "error";
  input?: Record<string, unknown>;
  summary?: string;
  preview?: string[];
  count?: number;
};

const SUGGESTIONS = [
  "我想去台南玩兩天，有什麼景點推薦？",
  "台北明天天氣如何？適合出門嗎？",
  "高雄有什麼必吃美食？",
  "從台北到台南，台鐵有哪些班次？",
];

const PHASE_LABELS: Record<Phase, string> = {
  thinking: "理解問題",
  tool: "查詢資料",
  writing: "生成回答",
  done: "完成",
};

export default function Chat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [phase, setPhase] = useState<Phase | null>(null);
  const [phaseProgress, setPhaseProgress] = useState(-1);
  const [phaseMessage, setPhaseMessage] = useState("");
  const [activities, setActivities] = useState<ActivityItem[]>([]);
  const [streamingText, setStreamingText] = useState("");
  const [streamingPlacePool, setStreamingPlacePool] = useState<MapPlace[]>([]);
  const [selectedPlaceId, setSelectedPlaceId] = useState<string | null>(null);
  const [mapFocus, setMapFocus] = useState<MapFocusTarget | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const composingRef = useRef(false);
  const enterToConfirmImeRef = useRef(false);
  const activityCounter = useRef(0);
  const sessionIdRef = useRef<string>();

  if (!sessionIdRef.current) {
    sessionIdRef.current = getOrCreateSessionId();
  }

  const streamingVisiblePlaces = useMemo(
    () => filterPlacesMentionedInText(streamingText, streamingPlacePool),
    [streamingText, streamingPlacePool]
  );

  const mapPlaces = useMemo(() => {
    const fromMessages = messages.flatMap((msg) =>
      msg.role === "assistant"
        ? resolveDisplayPlaces(msg.content, msg.places ?? [])
        : []
    );
    if (loading) {
      return mergeMapPlaces(fromMessages, streamingVisiblePlaces);
    }
    return mergeMapPlaces([], fromMessages);
  }, [messages, loading, streamingVisiblePlaces]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingText, activities, phase]);

  useEffect(() => {
    if (!selectedPlaceId) return;
    document
      .querySelector(`[data-place-id="${selectedPlaceId}"]`)
      ?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [selectedPlaceId]);

  function nextActivityId(prefix: string) {
    activityCounter.current += 1;
    return `${prefix}-${activityCounter.current}`;
  }

  function focusPlace(place: MapPlace) {
    setSelectedPlaceId(place.id);
    setMapFocus({
      lat: place.lat,
      lng: place.lng,
      nonce: Date.now(),
    });
  }

  function handleTextPlaceSelect(place: MapPlace) {
    focusPlace(place);
  }

  function handleMapPlaceSelect(place: MapPlace) {
    focusPlace(place);
    openGoogleMaps(place);
  }

  function updatePhase(next: Phase, message?: string) {
    const order: Phase[] = ["thinking", "tool", "writing", "done"];
    const nextIdx = order.indexOf(next);
    setPhase(next);
    setPhaseProgress((prev) => Math.max(prev, nextIdx));
    if (message) {
      setPhaseMessage(message);
    } else {
      setPhaseMessage(PHASE_LABELS[next] || "");
    }
  }

  async function sendMessage(text: string) {
    if (!text.trim() || loading) return;

    const userMessage = text.trim();
    setInput("");
    setLoading(true);
    setPhase("thinking");
    setPhaseProgress(0);
    setPhaseMessage("正在理解你的問題...");
    setActivities([]);
    setStreamingText("");
    setStreamingPlacePool([]);
    setSelectedPlaceId(null);
    setMapFocus(null);
    setMessages((prev) => [...prev, { role: "user", content: userMessage }]);

    const currentActivities: ActivityItem[] = [];
    let currentPlaces: MapPlace[] = [];
    let accumulated = "";
    let committed = false;

    function commitAssistantMessage(content: string, places: MapPlace[]) {
      if (committed) return;
      const hasToolActivity = currentActivities.some((item) => item.type === "tool");
      if (!content && places.length === 0 && !hasToolActivity) return;
      committed = true;
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content,
          activities: [...currentActivities],
          places: [...places],
        },
      ]);
    }

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: userMessage,
          session_id: sessionIdRef.current,
        }),
      });

      if (!res.ok || !res.body) {
        throw new Error(
          `API 請求失敗 (${res.status})，請確認後端已啟動：uvicorn api:app --reload --port 8000`
        );
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n");
        buffer = parts.pop() || "";

        for (const part of parts) {
          const lines = part.split("\n");
          let event = "";
          let data = "";

          for (const line of lines) {
            if (line.startsWith("event: ")) event = line.slice(7);
            if (line.startsWith("data: ")) data = line.slice(6);
          }

          if (!event || !data) continue;
          const parsed = JSON.parse(data);

          if (event === "status") {
            updatePhase(parsed.phase as Phase, parsed.message);

            const statusItem: ActivityItem = {
              id: nextActivityId("status"),
              type: "status",
              phase: parsed.phase,
              message: parsed.message,
            };
            currentActivities.push(statusItem);
            setActivities([...currentActivities]);
          } else if (event === "text_delta") {
            updatePhase("writing", "正在整理回答...");
            accumulated += parsed.text;
            setStreamingText(accumulated);
          } else if (event === "tool_start") {
            updatePhase("tool", "正在查詢政府開放資料...");
            const toolItem: ActivityItem = {
              id: parsed.id || nextActivityId("tool"),
              type: "tool",
              name: parsed.name,
              label: parsed.label,
              source: parsed.source,
              provider: parsed.provider,
              input: parsed.input,
              status: "running",
            };
            currentActivities.push(toolItem);
            setActivities([...currentActivities]);
          } else if (event === "tool_end") {
            const idx = currentActivities.findIndex(
              (item) => item.type === "tool" && item.id === parsed.id
            );
            if (idx >= 0) {
              currentActivities[idx] = {
                ...currentActivities[idx],
                status: parsed.ok === false ? "error" : "done",
                summary: parsed.summary,
                preview: parsed.preview,
                count: parsed.count,
              };
              setActivities([...currentActivities]);
            }
            if (parsed.places?.length) {
              currentPlaces = mergeMapPlaces(currentPlaces, parsed.places as MapPlaceInput[]);
              setStreamingPlacePool([...currentPlaces]);
            }
          } else if (event === "done") {
            commitAssistantMessage(accumulated, currentPlaces);
            setStreamingText("");
            setStreamingPlacePool([]);
            setPhase(null);
            setPhaseProgress(-1);
            setPhaseMessage("");
            setActivities([]);
          } else if (event === "error") {
            const errorText = parsed.message
              ? `發生錯誤：${parsed.message}`
              : "發生錯誤，請稍後再試。";
            commitAssistantMessage(accumulated || errorText, currentPlaces);
            setStreamingText("");
            setStreamingPlacePool([]);
            setPhase(null);
            setPhaseProgress(-1);
            setPhaseMessage("");
            setActivities([]);
          }
        }
      }

      if (!committed && (accumulated || currentActivities.length > 0)) {
        commitAssistantMessage(accumulated, currentPlaces);
      }
      setStreamingText("");
      setStreamingPlacePool([]);
      setPhase(null);
      setPhaseProgress(-1);
      setPhaseMessage("");
      setActivities([]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: `發生錯誤：${err instanceof Error ? err.message : "未知錯誤"}`,
        },
      ]);
      setStreamingText("");
      setActivities([]);
      setPhase(null);
      setPhaseProgress(-1);
      setPhaseMessage("");
    } finally {
      setLoading(false);
    }
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    sendMessage(input);
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key !== "Enter" || e.shiftKey) return;

    // IME 組字中：Enter 用來選字，不送出
    if (e.nativeEvent.isComposing || composingRef.current) return;

    // 剛用 Enter 確認選字：略過這次 Enter，避免誤送或無法再按
    if (enterToConfirmImeRef.current) {
      enterToConfirmImeRef.current = false;
      return;
    }

    e.preventDefault();
    sendMessage(input);
  }

  return (
    <div className={styles.pageLayout}>
      <div className={styles.container}>
        <header className={styles.header}>
        <div className={styles.logo}>🗺️</div>
        <div>
          <h1 className={styles.title}>台灣旅遊 AI 助理</h1>
          <p className={styles.subtitle}>串接 TDX 景點・餐廳・交通 & 中央氣象署天氣</p>
        </div>
      </header>

      <main className={styles.chat}>
        {messages.length === 0 && !loading && (
          <div className={styles.welcome}>
            <p>問我任何台灣旅遊相關問題，我會查真實資料幫你規劃！</p>
            <div className={styles.suggestions}>
              {SUGGESTIONS.map((s) => (
                <button key={s} className={styles.suggestion} onClick={() => sendMessage(s)}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i}>
            <div className={`${styles.message} ${styles[msg.role]}`}>
              <div className={styles.bubble}>
                {msg.role === "assistant" ? (
                  <MarkdownContent
                    content={msg.content}
                    places={msg.places ?? []}
                    mapPlaces={mapPlaces}
                    selectedPlaceId={selectedPlaceId}
                    onPlaceSelect={handleTextPlaceSelect}
                  />
                ) : (
                  msg.content
                )}
              </div>
            </div>
            {msg.activities && msg.activities.length > 0 && (
              <ActivityPanel items={msg.activities} compact />
            )}
          </div>
        ))}

        {loading && (
          <div className={styles.progressPanel}>
            <div className={styles.progressHeader}>
              <span className={styles.progressSpinner} />
              <span>{phaseMessage || "處理中..."}</span>
            </div>

            <div className={styles.phaseBar}>
              {(["thinking", "tool", "writing"] as Phase[]).map((step) => (
                <div
                  key={step}
                  className={`${styles.phaseStep} ${
                    phase === step
                      ? styles.phaseActive
                      : isPhaseDone(step, phaseProgress)
                        ? styles.phaseDone
                        : ""
                  }`}
                >
                  {PHASE_LABELS[step]}
                </div>
              ))}
            </div>

            {activities.length > 0 && <ActivityPanel items={activities} />}
          </div>
        )}

        {streamingText && (
          <div className={`${styles.message} ${styles.assistant}`}>
            <div className={styles.bubble}>
              <MarkdownContent
                content={streamingText}
                places={streamingPlacePool}
                mapPlaces={mapPlaces}
                selectedPlaceId={selectedPlaceId}
                onPlaceSelect={handleTextPlaceSelect}
              />
              <span className={styles.cursor}>▊</span>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </main>

      <form className={styles.inputArea} onSubmit={handleSubmit}>
        <textarea
          className={styles.input}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onCompositionStart={() => {
            composingRef.current = true;
          }}
          onCompositionEnd={() => {
            composingRef.current = false;
            enterToConfirmImeRef.current = true;
          }}
          onBlur={() => {
            composingRef.current = false;
          }}
          onKeyDown={handleKeyDown}
          placeholder="例如：台南有什麼古蹟？明天會下雨嗎？"
          rows={2}
          disabled={loading}
        />
        <div className={styles.inputActions}>
          <span className={styles.inputHint}>Enter 送出 · Shift+Enter 換行</span>
          <button type="submit" className={styles.sendBtn} disabled={loading || !input.trim()}>
            送出
          </button>
        </div>
      </form>
      </div>

      <aside className={styles.mapColumn}>
        <MapPanel
          places={mapPlaces}
          selectedPlaceId={selectedPlaceId}
          focusTarget={mapFocus}
          onPlaceSelect={handleMapPlaceSelect}
        />
      </aside>
    </div>
  );
}

function ActivityPanel({
  items,
  compact = false,
}: {
  items: ActivityItem[];
  compact?: boolean;
}) {
  const toolItems = items.filter((item) => item.type === "tool");
  if (toolItems.length === 0 && compact) return null;

  return (
    <div className={`${styles.activityPanel} ${compact ? styles.activityCompact : ""}`}>
      {!compact && <div className={styles.activityTitle}>資料來源</div>}
      {toolItems.map((tool) => (
        <div
          key={tool.id}
          className={`${styles.activityItem} ${styles[tool.status || "running"]}`}
        >
          <div className={styles.activityTop}>
            <span className={styles.activityIcon}>
              {tool.status === "done" ? "✓" : tool.status === "error" ? "!" : "↻"}
            </span>
            <span className={styles.activityLabel}>{tool.label || tool.name}</span>
            {tool.provider && <span className={styles.sourceBadge}>{tool.provider}</span>}
          </div>

          {tool.source && <div className={styles.activitySource}>{tool.source}</div>}

          {tool.input && (
            <div className={styles.activityInput}>
              {Object.entries(tool.input)
                .map(([k, v]) => `${k}: ${v}`)
                .join(" · ")}
            </div>
          )}

          {tool.status === "running" && (
            <div className={styles.activityPending}>查詢中...</div>
          )}

          {tool.status === "done" && (
            <div className={styles.activityResult}>
              <span>{tool.summary}</span>
              {tool.preview && tool.preview.length > 0 && (
                <span className={styles.activityPreview}>｜{tool.preview.join("、")}</span>
              )}
            </div>
          )}

          {tool.status === "error" && (
            <div className={styles.activityError}>{tool.summary || "查詢失敗"}</div>
          )}
        </div>
      ))}
    </div>
  );
}

function isPhaseDone(step: Phase, progress: number) {
  const order: Phase[] = ["thinking", "tool", "writing", "done"];
  const stepIdx = order.indexOf(step);
  return progress > stepIdx;
}
