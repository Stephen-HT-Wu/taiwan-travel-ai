from types import SimpleNamespace
from unittest.mock import MagicMock

from agent import execute_tool, stream_agent, summarize_tool_result
from tests.conftest import FakeAnthropicStream, tdx_get_handler


def test_execute_tool_unknown_name():
    result = execute_tool("not_a_tool", {})

    assert result["error"] == "未知工具 not_a_tool"


def test_execute_tool_search_attractions_via_mock(mock_httpx):
    mock_httpx["get_handlers"].append(
        tdx_get_handler(
            "/v2/Tourism/ScenicSpot/Tainan",
            [{"ScenicSpotName": "安平古堡", "Picture": {}}],
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


def test_stream_agent_end_turn_emits_sse_events(monkeypatch):
    text_block = SimpleNamespace(type="text", text="台南很好玩")
    final_message = SimpleNamespace(
        stop_reason="end_turn",
        content=[text_block],
    )

    delta = SimpleNamespace(type="text_delta", text="台南")
    stream_event = SimpleNamespace(type="content_block_delta", delta=delta)

    messages_mock = MagicMock()
    messages_mock.stream.return_value = FakeAnthropicStream([stream_event], final_message)
    monkeypatch.setattr("agent.client.messages", messages_mock)

    events = list(stream_agent("台南有什麼景點？", []))

    event_names = [e["event"] for e in events]
    assert "status" in event_names
    assert "text_delta" in event_names
    assert "done" in event_names
    assert any(e["data"].get("text") == "台南" for e in events if e["event"] == "text_delta")


def test_stream_agent_tool_use_emits_tool_events(monkeypatch, mock_httpx):
    mock_httpx["get_handlers"].append(
        tdx_get_handler(
            "/v2/Tourism/ScenicSpot/Tainan",
            [{"ScenicSpotName": "赤崁樓", "Picture": {}}],
        )
    )

    tool_block = SimpleNamespace(
        type="tool_use",
        id="toolu_123",
        name="search_attractions",
        input={"city": "Tainan", "limit": 1},
    )
    text_block = SimpleNamespace(type="text", text="推薦赤崁樓")
    tool_response = SimpleNamespace(stop_reason="tool_use", content=[tool_block])
    final_response = SimpleNamespace(stop_reason="end_turn", content=[text_block])

    call_count = {"n": 0}

    def make_stream(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return FakeAnthropicStream([], tool_response)
        return FakeAnthropicStream([], final_response)

    messages_mock = MagicMock()
    messages_mock.stream.side_effect = make_stream
    monkeypatch.setattr("agent.client.messages", messages_mock)

    events = list(stream_agent("台南景點", []))

    assert "tool_start" in [e["event"] for e in events]
    tool_end = next(e for e in events if e["event"] == "tool_end")
    assert tool_end["data"]["ok"] is True
    assert tool_end["data"]["count"] == 1
    assert "赤崁樓" in tool_end["data"]["preview"]
