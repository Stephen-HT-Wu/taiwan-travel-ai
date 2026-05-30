import json
import os
from typing import Generator

from dotenv import load_dotenv
import anthropic

from tdx import search_attractions, search_restaurants, search_bus_routes, search_train_schedule
from cwa import get_weather_forecast

load_dotenv(override=True)

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
MODEL = "claude-sonnet-4-5"

tools = [
    {
        "name": "search_attractions",
        "description": "搜尋台灣各縣市的觀光景點",
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "縣市英文名，例如 Tainan、Taipei、Taichung、HualienCounty",
                },
                "keyword": {"type": "string", "description": "景點名稱關鍵字（可選）"},
                "limit": {"type": "integer", "description": "回傳幾筆資料，預設 5"},
            },
            "required": ["city"],
        },
    },
    {
        "name": "search_restaurants",
        "description": "搜尋台灣各縣市的餐廳、小吃",
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "縣市英文名，例如 Tainan、Taipei、Taichung",
                },
                "keyword": {"type": "string", "description": "餐廳名稱或料理關鍵字（可選）"},
                "limit": {"type": "integer", "description": "回傳幾筆資料，預設 5"},
            },
            "required": ["city"],
        },
    },
    {
        "name": "get_weather_forecast",
        "description": "查詢台灣縣市未來 36 小時天氣預報",
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "縣市英文名，例如 Tainan、Taipei、HualienCounty",
                },
                "location_name": {
                    "type": "string",
                    "description": "中文縣市名（可選，例如 臺南市）",
                },
            },
            "required": ["city"],
        },
    },
    {
        "name": "search_bus_routes",
        "description": "搜尋指定縣市的市區公車路線",
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "縣市英文名，例如 Tainan、Taipei、Kaohsiung",
                },
                "keyword": {"type": "string", "description": "路線名稱關鍵字（可選）"},
                "limit": {"type": "integer", "description": "回傳幾筆資料，預設 5"},
            },
            "required": ["city"],
        },
    },
    {
        "name": "search_train_schedule",
        "description": "查詢台鐵兩站之間的列車時刻表",
        "input_schema": {
            "type": "object",
            "properties": {
                "origin": {
                    "type": "string",
                    "description": "出發站中文名，例如 台北、台南、高雄、台中",
                },
                "destination": {
                    "type": "string",
                    "description": "目的站中文名，例如 台北、台南、高雄、台中",
                },
                "travel_date": {
                    "type": "string",
                    "description": "日期 YYYY-MM-DD（可選，預設今天）",
                },
                "limit": {"type": "integer", "description": "回傳幾班車，預設 5"},
            },
            "required": ["origin", "destination"],
        },
    },
]

SYSTEM_PROMPT = """你是一個台灣旅遊規劃助理。
當使用者詢問景點、美食、天氣或交通時，使用對應工具查詢真實資料，再根據資料給出建議。
規劃行程時，可綜合天氣、景點、餐廳與交通資訊。
回答時用繁體中文，口吻親切自然。"""

TOOL_HANDLERS = {
    "search_attractions": search_attractions,
    "search_restaurants": search_restaurants,
    "get_weather_forecast": get_weather_forecast,
    "search_bus_routes": search_bus_routes,
    "search_train_schedule": search_train_schedule,
}

TOOL_META = {
    "search_attractions": {
        "label": "查詢景點",
        "source": "TDX 觀光景點",
        "provider": "交通部 TDX",
    },
    "search_restaurants": {
        "label": "查詢餐廳",
        "source": "TDX 觀光餐飲",
        "provider": "交通部 TDX",
    },
    "get_weather_forecast": {
        "label": "查詢天氣",
        "source": "36 小時天氣預報",
        "provider": "中央氣象署 CWA",
    },
    "search_bus_routes": {
        "label": "查詢公車路線",
        "source": "TDX 市區公車",
        "provider": "交通部 TDX",
    },
    "search_train_schedule": {
        "label": "查詢台鐵時刻",
        "source": "TDX 台鐵時刻表",
        "provider": "交通部 TDX",
    },
}


def summarize_tool_result(name: str, result) -> dict:
    if isinstance(result, dict):
        if result.get("error"):
            return {"ok": False, "count": 0, "summary": result["error"], "preview": []}
        if name == "get_weather_forecast":
            location = result.get("location", "")
            periods = result.get("forecast", [])
            preview = [
                f"{p.get('weather', '')} {p.get('min_temp', '')}~{p.get('max_temp', '')}°C"
                for p in periods[:2]
            ]
            return {
                "ok": True,
                "count": len(periods),
                "summary": f"取得 {location} 未來 {len(periods)} 段預報",
                "preview": preview,
            }

    if isinstance(result, list):
        if not result:
            return {"ok": True, "count": 0, "summary": "查無資料", "preview": []}
        if isinstance(result[0], dict) and result[0].get("error"):
            return {"ok": False, "count": 0, "summary": result[0]["error"], "preview": []}

        preview = []
        for item in result[:3]:
            label = (
                item.get("name")
                or item.get("route_name")
                or item.get("train_no")
                or item.get("location")
                or ""
            )
            if label:
                preview.append(str(label))

        return {
            "ok": True,
            "count": len(result),
            "summary": f"取得 {len(result)} 筆資料",
            "preview": preview,
        }

    return {"ok": True, "count": 0, "summary": "查詢完成", "preview": []}


def execute_tool(name: str, tool_input: dict):
    handler = TOOL_HANDLERS.get(name)
    if not handler:
        return {"error": f"未知工具 {name}"}
    try:
        return handler(**tool_input)
    except Exception as e:
        return {"error": str(e)}


def run_tool_calls(content_blocks) -> list[dict]:
    tool_results = []
    for block in content_blocks:
        if block.type != "tool_use":
            continue
        result = execute_tool(block.name, block.input)
        tool_results.append({
            "type": "tool_result",
            "tool_use_id": block.id,
            "content": json.dumps(result, ensure_ascii=False),
        })
    return tool_results


def run_agent(user_message: str, messages: list):
    """CLI 版 agent（非串流）"""
    print("-" * 40)
    messages.append({"role": "user", "content": user_message})

    while True:
        response = client.messages.create(
            model=MODEL,
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            tools=tools,
            messages=messages,
        )

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            for block in response.content:
                if hasattr(block, "text"):
                    print(block.text)
            break

        for block in response.content:
            if block.type == "tool_use":
                print(f"[呼叫工具] {block.name}({block.input})")

        tool_results = run_tool_calls(response.content)
        messages.append({"role": "user", "content": tool_results})


def stream_agent(user_message: str, messages: list) -> Generator[dict, None, None]:
    """串流版 agent，yield SSE 事件 dict"""
    messages.append({"role": "user", "content": user_message})

    while True:
        yield {
            "event": "status",
            "data": {"phase": "thinking", "message": "正在理解你的問題..."},
        }

        writing_started = False
        with client.messages.stream(
            model=MODEL,
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            tools=tools,
            messages=messages,
        ) as stream:
            for event in stream:
                if event.type == "content_block_delta" and event.delta.type == "text_delta":
                    if not writing_started:
                        writing_started = True
                        yield {
                            "event": "status",
                            "data": {"phase": "writing", "message": "正在整理回答..."},
                        }
                    yield {"event": "text_delta", "data": {"text": event.delta.text}}
            response = stream.get_final_message()

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            yield {"event": "status", "data": {"phase": "done", "message": "完成"}}
            yield {"event": "done", "data": {}}
            break

        tool_blocks = [block for block in response.content if block.type == "tool_use"]
        if tool_blocks:
            yield {
                "event": "status",
                "data": {"phase": "tool", "message": "正在查詢政府開放資料..."},
            }

        for block in tool_blocks:
            meta = TOOL_META.get(block.name, {})
            yield {
                "event": "tool_start",
                "data": {
                    "id": block.id,
                    "name": block.name,
                    "label": meta.get("label", block.name),
                    "source": meta.get("source", ""),
                    "provider": meta.get("provider", ""),
                    "input": block.input,
                },
            }

        tool_results = run_tool_calls(response.content)

        for block in tool_blocks:
            result_content = next(
                (r["content"] for r in tool_results if r["tool_use_id"] == block.id),
                "{}",
            )
            result = json.loads(result_content)
            summary = summarize_tool_result(block.name, result)
            meta = TOOL_META.get(block.name, {})
            yield {
                "event": "tool_end",
                "data": {
                    "id": block.id,
                    "name": block.name,
                    "label": meta.get("label", block.name),
                    "source": meta.get("source", ""),
                    "provider": meta.get("provider", ""),
                    "result": result_content,
                    **summary,
                },
            }

        messages.append({"role": "user", "content": tool_results})
