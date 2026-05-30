"use client";

import { useState, useRef, useEffect, FormEvent, KeyboardEvent } from "react";
import styles from "./Chat.module.css";

type Message = {
  role: "user" | "assistant";
  content: string;
};

type ToolEvent = {
  name: string;
  input?: Record<string, unknown>;
  status: "running" | "done";
};

const SUGGESTIONS = [
  "我想去台南玩兩天，有什麼景點推薦？",
  "台北明天天氣如何？適合出門嗎？",
  "高雄有什麼必吃美食？",
  "從台北到台南，台鐵有哪些班次？",
];

export default function Chat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [tools, setTools] = useState<ToolEvent[]>([]);
  const [streamingText, setStreamingText] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingText, tools]);

  async function sendMessage(text: string) {
    if (!text.trim() || loading) return;

    const userMessage = text.trim();
    setInput("");
    setLoading(true);
    setTools([]);
    setStreamingText("");
    setMessages((prev) => [...prev, { role: "user", content: userMessage }]);

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: userMessage, session_id: "web" }),
      });

      if (!res.ok || !res.body) {
        throw new Error(`API 請求失敗 (${res.status})，請確認後端已啟動：uvicorn api:app --reload --port 8000`);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let accumulated = "";

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

          if (event === "text_delta") {
            accumulated += parsed.text;
            setStreamingText(accumulated);
          } else if (event === "tool_start") {
            setTools((prev) => [
              ...prev,
              { name: parsed.name, input: parsed.input, status: "running" },
            ]);
          } else if (event === "tool_end") {
            setTools((prev) =>
              prev.map((t) =>
                t.name === parsed.name && t.status === "running"
                  ? { ...t, status: "done" }
                  : t
              )
            );
          } else if (event === "done") {
            if (accumulated) {
              setMessages((prev) => [
                ...prev,
                { role: "assistant", content: accumulated },
              ]);
            }
            setStreamingText("");
            setTools([]);
          }
        }
      }
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: `發生錯誤：${err instanceof Error ? err.message : "未知錯誤"}` },
      ]);
      setStreamingText("");
      setTools([]);
    } finally {
      setLoading(false);
    }
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    sendMessage(input);
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  }

  return (
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
          <div key={i} className={`${styles.message} ${styles[msg.role]}`}>
            <div className={styles.bubble}>{msg.content}</div>
          </div>
        ))}

        {tools.length > 0 && (
          <div className={styles.toolPanel}>
            {tools.map((tool, i) => (
              <div key={i} className={`${styles.toolItem} ${styles[tool.status]}`}>
                <span className={styles.toolIcon}>{tool.status === "running" ? "⚙️" : "✓"}</span>
                <span className={styles.toolName}>{toolLabel(tool.name)}</span>
                {tool.input && (
                  <span className={styles.toolInput}>
                    {Object.entries(tool.input)
                      .map(([k, v]) => `${k}: ${v}`)
                      .join(", ")}
                  </span>
                )}
              </div>
            ))}
          </div>
        )}

        {streamingText && (
          <div className={`${styles.message} ${styles.assistant}`}>
            <div className={styles.bubble}>
              {streamingText}
              <span className={styles.cursor}>▊</span>
            </div>
          </div>
        )}

        {loading && !streamingText && tools.length === 0 && (
          <div className={styles.thinking}>
            <span className={styles.dot} />
            <span className={styles.dot} />
            <span className={styles.dot} />
          </div>
        )}

        <div ref={bottomRef} />
      </main>

      <form className={styles.inputArea} onSubmit={handleSubmit}>
        <textarea
          className={styles.input}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="例如：台南有什麼古蹟？明天會下雨嗎？"
          rows={1}
          disabled={loading}
        />
        <button type="submit" className={styles.sendBtn} disabled={loading || !input.trim()}>
          送出
        </button>
      </form>
    </div>
  );
}

function toolLabel(name: string): string {
  const labels: Record<string, string> = {
    search_attractions: "查詢景點",
    search_restaurants: "查詢餐廳",
    get_weather_forecast: "查詢天氣",
    search_bus_routes: "查詢公車路線",
    search_train_schedule: "查詢台鐵時刻",
  };
  return labels[name] || name;
}
