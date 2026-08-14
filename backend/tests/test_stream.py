"""SSE 流式端点：事件齐全 + 记忆接线。TestClient 会把整个流缓冲进 resp.text。"""

import json

from fastapi.testclient import TestClient

from app.main import app


def test_stream_events_and_memory_notes(force_llm_fallback):
    client = TestClient(app)
    resp = client.post(
        "/api/trip/plan/stream",
        json={"destination": "杭州", "days": 2, "session_id": "sess-stream"},
    )
    assert resp.status_code == 200
    text = resp.text
    assert "event: start" in text
    assert "event: stage" in text
    assert "event: result" in text

    # 解析 result 事件里的 plan JSON
    events = [e for e in text.split("\n\n") if e.strip()]
    result_event = next(e for e in events if e.startswith("event: result"))
    data_line = next(line for line in result_event.splitlines() if line.startswith("data: "))
    plan = json.loads(data_line[len("data: "):])
    assert plan["destination"] == "杭州"
    assert "memory_notes" in plan
