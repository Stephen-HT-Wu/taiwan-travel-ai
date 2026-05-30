import json
import os
from typing import Generator

from dotenv import load_dotenv
import anthropic

from tdx import search_attractions, search_restaurants, search_bus_routes, search_train_schedule
from cwa import get_weather_forecast
from routing import get_travel_route

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
        "description": "查詢台鐵兩站之間的列車時刻表。支援所有台鐵正式站名（約 245 站，台北/臺北等別名皆可）",
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
    {
        "name": "get_travel_route",
        "description": (
            "查詢兩地之間的步行、開車或騎車路線時間與距離。"
            "使用者問「A 到 B 要多久、多遠」時必須使用此工具，不可自行估算。"
            "地點請用中文具體名稱（例如 捷運中山站 中山區、雙城街夜市）。"
            "若先前工具已回傳 lat/lng，可一併傳入以提升準確度。"
            "回傳含 origin/destination 的 name、query、lat/lng；若 query 與 name 不符代表 geocoding 可能對錯點，回答時須向使用者說明。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "origin": {
                    "type": "string",
                    "description": "起點中文名稱，例如 捷運中山站",
                },
                "destination": {
                    "type": "string",
                    "description": "終點中文名稱，例如 雙城街觀光夜市",
                },
                "mode": {
                    "type": "string",
                    "description": "交通方式：walking（步行，預設）、driving（開車）、cycling（騎車）",
                },
                "near": {
                    "type": "string",
                    "description": "地點所在區域提示，預設 台北市，例如 台北市、臺南市",
                },
                "origin_lat": {"type": "number", "description": "起點緯度（可選）"},
                "origin_lng": {"type": "number", "description": "起點經度（可選）"},
                "destination_lat": {"type": "number", "description": "終點緯度（可選）"},
                "destination_lng": {"type": "number", "description": "終點經度（可選）"},
            },
            "required": ["origin", "destination"],
        },
    },
]

SYSTEM_PROMPT = """你是一個台灣旅遊規劃助理。
當使用者詢問景點、美食、天氣或交通時，使用對應工具查詢真實資料，再根據資料給出建議。
規劃行程時，可綜合天氣、景點、餐廳與交通資訊。

交通時間與距離規則：
- 使用者問兩地之間「多久、多遠、怎麼走」時，必須呼叫 get_travel_route，不可憑記憶估算分鐘數。
- 沒有工具資料時，明確告知無法提供精確時間，不要猜測。
- 回覆時說明交通方式（步行/開車/騎車），並提及 OSRM 估算不含等車或轉乘。
- 捷運、公車轉乘請另外說明需另行查詢，不要與步行時間混淆。

工具結果驗證規則（尤其 get_travel_route）：
- 回答前必須閱讀工具回傳的 origin、destination 的 name、query、lat、lng，確認系統實際使用的起終點。
- 若 query（你輸入的地名）與 name（geocoding 解析結果）明顯不同，必須在回答中清楚告知，例如：「您問的是雙城街夜市，但系統對應到晴光市場（農安街一巷），以下時間依此座標計算。」
- 禁止用「名字相似」推論地理位置（例如：雙城街≠雙連站、中山≠中山國中），禁止用直覺覆蓋或「修正」工具回傳的座標、距離、時間。
- 不可自行推薦「最近的捷運站」或「應該搭到哪一站」除非另有工具資料支持；無法確認時，請依 name／座標描述所在區域，並建議使用者用 Google Maps 確認。
- 若 geocode_warnings 非空，必須優先向使用者說明地點可能對得不準，並建議提供更精確地址後再查。
- 時間與距離只能引用工具數字；可補充「也可考慮搭公車／捷運」但不可改寫數字，也不可腦補轉乘站名或站距。

回答時用繁體中文，口吻親切自然。"""

TOOL_HANDLERS = {
    "search_attractions": search_attractions,
    "search_restaurants": search_restaurants,
    "get_weather_forecast": get_weather_forecast,
    "search_bus_routes": search_bus_routes,
    "search_train_schedule": search_train_schedule,
    "get_travel_route": get_travel_route,
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
    "get_travel_route": {
        "label": "規劃路線",
        "source": "OSRM 路線估算",
        "provider": "OpenStreetMap",
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
        if name == "get_travel_route":
            origin = result.get("origin", {})
            dest = result.get("destination", {})
            origin_label = origin.get("query") or origin.get("name", "")[:40]
            dest_label = dest.get("query") or dest.get("name", "")[:40]
            preview = [f"{origin_label} → {dest_label}"]
            for warning in result.get("geocode_warnings") or []:
                preview.append(warning[:80])
            return {
                "ok": True,
                "count": 1,
                "summary": (
                    f"{result.get('mode_label', '路線')} 約 "
                    f"{result.get('duration_minutes')} 分鐘（"
                    f"{result.get('distance_km')} 公里）"
                ),
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


MAP_TOOL_NAMES = {"search_attractions", "search_restaurants"}


def extract_map_places(name: str, result) -> list:
    if name not in MAP_TOOL_NAMES or not isinstance(result, list):
        return []

    places = []
    for item in result:
        if not isinstance(item, dict) or item.get("error"):
            continue
        lat, lng = item.get("lat"), item.get("lng")
        if lat is None or lng is None:
            continue
        places.append({
            "name": item.get("name", ""),
            "lat": lat,
            "lng": lng,
            "address": item.get("address", ""),
            "type": "attraction" if name == "search_attractions" else "restaurant",
        })
    return places


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
                    "places": extract_map_places(block.name, result),
                    **summary,
                },
            }

        messages.append({"role": "user", "content": tool_results})
