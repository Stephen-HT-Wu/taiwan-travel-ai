from fastapi.testclient import TestClient

import api


def test_health_endpoint():
    client = TestClient(api.app)
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_chat_endpoint_streams_sse(monkeypatch):
    api.sessions.clear()

    def fake_stream_agent(message, messages):
        yield {"event": "status", "data": {"phase": "thinking", "message": "test"}}
        yield {"event": "text_delta", "data": {"text": "你好"}}
        yield {"event": "done", "data": {}}

    monkeypatch.setattr(api, "stream_agent", fake_stream_agent)

    client = TestClient(api.app)
    response = client.post(
        "/api/chat",
        json={"message": "你好", "session_id": "test-session"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    body = response.text
    assert "event: status" in body
    assert "event: text_delta" in body
    assert "你好" in body
    assert "event: done" in body


def test_format_sse_encodes_unicode():
    line = api.format_sse("text_delta", {"text": "臺南"})
    assert "臺南" in line
    assert line.startswith("event: text_delta")


def test_chat_endpoint_hides_internal_errors(monkeypatch):
    api.sessions.clear()

    def failing_stream_agent(message, messages):
        raise RuntimeError("429 RESOURCE_EXHAUSTED secret internal detail")
        yield  # pragma: no cover

    monkeypatch.setattr(api, "stream_agent", failing_stream_agent)

    client = TestClient(api.app)
    response = client.post(
        "/api/chat",
        json={"message": "你好", "session_id": "error-session"},
    )

    assert response.status_code == 200
    body = response.text
    assert "event: error" in body
    assert api.USER_FACING_ERROR in body
    assert "429" not in body
    assert "RESOURCE_EXHAUSTED" not in body
    assert "secret internal detail" not in body
