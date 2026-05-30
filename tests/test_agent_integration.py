from agent import (
    compact_tool_result_for_model,
    execute_tool,
    extract_map_places,
    stream_agent,
    summarize_tool_result,
    _should_require_place_tools,
)
from providers.base import TextBlock, ToolUseBlock, TurnResult
from tests.conftest import tdx_get_handler
from tests.fake_provider import make_fake_provider


def test_execute_tool_unknown_name():
    result = execute_tool("not_a_tool", {})

    assert result["error"] == "未知工具 not_a_tool"


def test_execute_tool_search_attractions_via_mock(mock_httpx):
    mock_httpx["get_handlers"].append(
        tdx_get_handler(
            "/v2/Tourism/ScenicSpot/Tainan",
            [{"ScenicSpotName": "安平古堡", "Picture": {}, "Position": {"PositionLat": 23.0, "PositionLon": 120.16}}],
        )
    )

    result = execute_tool("search_attractions", {"city": "Tainan", "limit": 1})

    assert result[0]["name"] == "安平古堡"


def test_summarize_tool_result_for_list():
    summary = summarize_tool_result(
        "search_attractions",
        [{"name": "赤崁樓"}, {"name": "孔廟"}],
    )

    assert summary["ok"] is True
    assert summary["count"] == 2
    assert "赤崁樓" in summary["preview"]


def test_summarize_tool_result_for_weather():
    summary = summarize_tool_result(
        "get_weather_forecast",
        {
            "location": "臺北市",
            "forecast": [{"weather": "晴", "min_temp": "25", "max_temp": "32"}],
        },
    )

    assert summary["ok"] is True
    assert "臺北市" in summary["summary"]


def test_summarize_tool_result_for_travel_route():
    summary = summarize_tool_result(
        "get_travel_route",
        {
            "mode_label": "步行",
            "duration_minutes": 25,
            "distance_km": 2.1,
            "origin": {"query": "捷運中山站"},
            "destination": {"query": "雙城街觀光夜市"},
        },
    )

    assert summary["ok"] is True
    assert "25" in summary["summary"]
    assert "步行" in summary["summary"]


def test_extract_map_places_from_attractions():
    places = extract_map_places(
        "search_attractions",
        [{"name": "赤崁樓", "lat": 22.997, "lng": 120.202, "address": "臺南市"}],
    )

    assert len(places) == 1
    assert places[0]["type"] == "attraction"
    assert places[0]["name"] == "赤崁樓"


def test_extract_map_places_skips_items_without_coordinates():
    places = extract_map_places("search_restaurants", [{"name": "無座標"}])

    assert places == []


def test_compact_tool_result_for_model_strips_verbose_fields():
    compact = compact_tool_result_for_model(
        "search_attractions",
        [{
            "name": "赤崁樓",
            "description": "x" * 200,
            "address": "臺南市",
            "image": "https://example.com/photo.jpg",
            "lat": 22.997,
            "lng": 120.202,
        }],
    )

    assert compact[0]["name"] == "赤崁樓"
    assert len(compact[0]["description"]) <= 121
    assert "image" not in compact[0]


def test_compact_tool_result_for_model_keeps_route_warnings():
    compact = compact_tool_result_for_model(
        "get_travel_route",
        {
            "origin": {"query": "捷運中山站", "name": "中山站", "lat": 25.05, "lng": 121.52},
            "destination": {"query": "雙城街夜市", "name": "晴光市場", "lat": 25.06, "lng": 121.53},
            "mode_label": "步行",
            "duration_minutes": 28,
            "distance_km": 2.3,
            "geocode_warnings": ["終點「雙城街夜市」已對應至：晴光市場"],
            "note": "測試",
        },
    )

    assert compact["geocode_warnings"]
    assert compact["duration_minutes"] == 28
    assert "image" not in compact


def test_compact_tool_result_for_model_empty_list():
    compact = compact_tool_result_for_model("search_restaurants", [])

    assert compact["count"] == 0
    assert compact["items"] == []
    assert "查無結果" in compact["note"]


def test_summarize_tool_result_empty_restaurants():
    summary = summarize_tool_result("search_restaurants", [])

    assert summary["count"] == 0
    assert "餐飲資料庫查無結果" in summary["summary"]


def test_extract_map_places_from_search_places():
    places = extract_map_places(
        "search_places",
        [{"name": "赤崁樓", "lat": 22.997, "lng": 120.202, "type": "attraction"}],
    )

    assert len(places) == 1
    assert places[0]["type"] == "attraction"


def test_compact_tool_result_for_model_empty_search_places():
    compact = compact_tool_result_for_model("search_places", [])

    assert compact["count"] == 0
    assert "OpenStreetMap" in compact["note"]


def test_should_require_place_tools_for_itinerary_queries():
    assert _should_require_place_tools(
        "幫我規劃明天早上8:00後坐高鐵或台鐵從台北到嘉義一日遊行程，考慮到天氣。"
    )
    assert not _should_require_place_tools("明天台北會下雨嗎？")


def test_stream_agent_nudges_place_tools_after_transport_weather(monkeypatch, mock_httpx):
    from tests.test_routing_integration import osrm_handler

    mock_httpx["get_handlers"].append(osrm_handler(800, 600))
    weather_block = ToolUseBlock(
        type="tool_use",
        id="toolu_w",
        name="get_weather_forecast",
        input={"city": "Chiayi"},
    )
    train_block = ToolUseBlock(
        type="tool_use",
        id="toolu_t",
        name="search_train_schedule",
        input={"origin": "台北", "destination": "嘉義", "travel_date": "2026-05-31"},
    )
    places_block = ToolUseBlock(
        type="tool_use",
        id="toolu_p",
        name="search_places",
        input={"city": "Chiayi", "place_type": "attraction", "limit": 1},
    )

    monkeypatch.setattr(
        "agent.get_llm_provider",
        lambda: make_fake_provider([
            {
                "events": [{"event": "tool_use_start"}],
                "result": TurnResult(stop_reason="tool_use", content=[weather_block, train_block]),
            },
            {
                "events": [{"event": "tool_use_start"}],
                "result": TurnResult(stop_reason="tool_use", content=[places_block]),
            },
            {
                "events": [{"event": "tool_use_start"}],
                "result": TurnResult(
                    stop_reason="tool_use",
                    content=[
                        ToolUseBlock(
                            type="tool_use",
                            id="toolu_l",
                            name="get_itinerary_legs",
                            input={"stops": [{"name": "高鐵嘉義站"}, {"name": "噴水雞肉飯"}]},
                        )
                    ],
                ),
            },
            {
                "events": [{"event": "text_delta", "text": "嘉義"}],
                "result": TurnResult(
                    stop_reason="end_turn",
                    content=[TextBlock(type="text", text="嘉義一日遊")],
                ),
            },
        ]),
    )

    messages = []
    query = "幫我規劃嘉義一日遊行程，考慮到天氣。"
    list(stream_agent(query, messages))

    user_texts = [
        block if isinstance(block, str) else block
        for msg in messages
        if msg["role"] == "user"
        for block in ([msg["content"]] if isinstance(msg["content"], str) else msg["content"])
    ]
    assert any("search_places" in text for text in user_texts if isinstance(text, str))
    tool_names = [
        block["name"]
        for msg in messages
        if msg["role"] == "assistant"
        for block in msg["content"]
        if block.get("type") == "tool_use"
    ]
    assert "search_places" in tool_names


def test_stream_agent_nudges_itinerary_legs_after_places(monkeypatch, mock_httpx):
    from tests.test_routing_integration import osrm_handler

    mock_httpx["get_handlers"].append(osrm_handler(800, 600))
    places_block = ToolUseBlock(
        type="tool_use",
        id="toolu_p",
        name="search_places",
        input={"city": "Chiayi", "place_type": "attraction", "limit": 1},
    )
    legs_block = ToolUseBlock(
        type="tool_use",
        id="toolu_l",
        name="get_itinerary_legs",
        input={
            "stops": [
                {"name": "高鐵嘉義站", "lat": 23.459, "lng": 120.323},
                {"name": "噴水雞肉飯", "lat": 23.480, "lng": 120.449},
            ]
        },
    )

    monkeypatch.setattr(
        "agent.get_llm_provider",
        lambda: make_fake_provider([
            {
                "events": [{"event": "tool_use_start"}],
                "result": TurnResult(stop_reason="tool_use", content=[places_block]),
            },
            {
                "events": [{"event": "tool_use_start"}],
                "result": TurnResult(stop_reason="tool_use", content=[legs_block]),
            },
            {
                "events": [{"event": "text_delta", "text": "嘉義"}],
                "result": TurnResult(
                    stop_reason="end_turn",
                    content=[TextBlock(type="text", text="嘉義一日遊")],
                ),
            },
        ]),
    )

    messages = []
    list(stream_agent("幫我規劃嘉義一日遊行程", messages))

    user_texts = [
        msg["content"]
        for msg in messages
        if msg["role"] == "user" and isinstance(msg["content"], str)
    ]
    assert any("get_itinerary_legs" in text for text in user_texts)
    tool_names = [
        block["name"]
        for msg in messages
        if msg["role"] == "assistant"
        for block in msg["content"]
        if block.get("type") == "tool_use"
    ]
    assert "get_itinerary_legs" in tool_names


def test_stream_agent_end_turn_emits_sse_events(monkeypatch):
    monkeypatch.setattr(
        "agent.get_llm_provider",
        lambda: make_fake_provider([
            {
                "events": [{"event": "text_delta", "text": "台南"}],
                "result": TurnResult(
                    stop_reason="end_turn",
                    content=[TextBlock(type="text", text="台南很好玩")],
                ),
            }
        ]),
    )

    events = list(stream_agent("你好，請簡短回覆。", []))

    event_names = [e["event"] for e in events]
    assert "status" in event_names
    assert "text_delta" in event_names
    assert "done" in event_names
    assert any(e["data"].get("text") == "台南" for e in events if e["event"] == "text_delta")


def test_stream_agent_tool_use_emits_tool_events(monkeypatch, mock_httpx):
    mock_httpx["get_handlers"].append(
        tdx_get_handler(
            "/v2/Tourism/ScenicSpot/Tainan",
            [{"ScenicSpotName": "赤崁樓", "Picture": {}, "Position": {"PositionLat": 22.997, "PositionLon": 120.202}}],
        )
    )

    tool_block = ToolUseBlock(
        type="tool_use",
        id="toolu_123",
        name="search_attractions",
        input={"city": "Tainan", "limit": 1},
    )

    monkeypatch.setattr(
        "agent.get_llm_provider",
        lambda: make_fake_provider([
            {
                "events": [{"event": "tool_use_start"}],
                "result": TurnResult(stop_reason="tool_use", content=[tool_block]),
            },
            {
                "events": [],
                "result": TurnResult(
                    stop_reason="end_turn",
                    content=[TextBlock(type="text", text="推薦赤崁樓")],
                ),
            },
        ]),
    )

    events = list(stream_agent("台南有什麼古蹟？", []))

    assert "tool_start" in [e["event"] for e in events]
    tool_end = next(e for e in events if e["event"] == "tool_end")
    assert tool_end["data"]["ok"] is True
    assert tool_end["data"]["count"] == 1
    assert "赤崁樓" in tool_end["data"]["preview"]
    assert len(tool_end["data"]["places"]) == 1
    assert tool_end["data"]["places"][0]["lat"] == 22.997


def test_run_tool_calls_uses_anthropic_tool_result_shape():
    from providers.base import ToolUseBlock
    from agent import run_tool_calls

    tool_results, _full_results = run_tool_calls([
        ToolUseBlock(
            type="tool_use",
            id="toolu_123",
            name="search_places",
            input={"city": "Tainan", "limit": 1},
        )
    ])

    assert len(tool_results) == 1
    assert set(tool_results[0].keys()) == {"type", "tool_use_id", "content"}
    assert tool_results[0]["type"] == "tool_result"


def test_stream_agent_stores_serializable_assistant_messages(monkeypatch, mock_httpx):
    mock_httpx["get_handlers"].append(
        tdx_get_handler(
            "/v2/Tourism/ScenicSpot/Tainan",
            [{"ScenicSpotName": "赤崁樓", "Picture": {}, "Position": {"PositionLat": 22.997, "PositionLon": 120.202}}],
        )
    )

    tool_block = ToolUseBlock(
        type="tool_use",
        id="toolu_123",
        name="search_attractions",
        input={"city": "Tainan", "limit": 1},
    )

    monkeypatch.setattr(
        "agent.get_llm_provider",
        lambda: make_fake_provider([
            {
                "events": [{"event": "tool_use_start"}],
                "result": TurnResult(stop_reason="tool_use", content=[tool_block]),
            },
            {
                "events": [{"event": "text_delta", "text": "推薦"}],
                "result": TurnResult(
                    stop_reason="end_turn",
                    content=[TextBlock(type="text", text="推薦赤崁樓")],
                ),
            },
        ]),
    )

    messages = []
    list(stream_agent("台南有什麼古蹟？", messages))

    assistant_messages = [msg for msg in messages if msg["role"] == "assistant"]
    assert len(assistant_messages) == 2
    for msg in assistant_messages:
        for block in msg["content"]:
            assert isinstance(block, dict)
            assert block["type"] in {"text", "tool_use"}
    assert assistant_messages[0]["content"][0]["type"] == "tool_use"
    assert assistant_messages[1]["content"][0]["type"] == "text"
