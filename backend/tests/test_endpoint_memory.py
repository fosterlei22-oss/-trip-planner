"""端到端会话记忆：同 session_id 二次请求合并历史偏好并回显 memory_notes。"""

from fastapi.testclient import TestClient

from app.main import app


def test_second_request_merges_memory(force_llm_fallback):
    client = TestClient(app)
    first = client.post(
        "/api/trip/plan",
        json={"destination": "杭州", "days": 2, "interests": ["历史", "美食"], "session_id": "sess-abc"},
    )
    assert first.status_code == 200
    first_data = first.json()
    # 首轮也会回显：系统刚记住了偏好
    assert any("已记住你的偏好" in note for note in first_data["memory_notes"])
    assert any("第 1 次规划" in note for note in first_data["memory_notes"])

    second = client.post(
        "/api/trip/plan",
        json={"destination": "成都", "days": 2, "session_id": "sess-abc"},
    )
    assert second.status_code == 200
    second_data = second.json()
    assert any("已记住你的偏好" in note for note in second_data["memory_notes"])
    assert any("此前规划过" in note for note in second_data["memory_notes"])
    # 历史兴趣合并进了本次请求（影响 RAG 检索）
    assert "历史" in second_data["request"]["interests"]
    assert "美食" in second_data["request"]["interests"]


def test_session_id_excluded_from_response(force_llm_fallback):
    client = TestClient(app)
    resp = client.post(
        "/api/trip/plan",
        json={"destination": "杭州", "days": 2, "session_id": "sess-hide"},
    )
    data = resp.json()
    assert "session_id" not in data["request"]  # Field(exclude=True) 生效


def test_different_session_has_no_history(force_llm_fallback):
    client = TestClient(app)
    resp = client.post(
        "/api/trip/plan",
        json={"destination": "杭州", "days": 2, "session_id": "sess-fresh"},
    )
    data = resp.json()
    # 无兴趣输入 → 不记偏好；只记录目的地与次数
    assert data["memory_notes"] == ["此前规划过：杭州", "这是你的第 1 次规划"]
    assert all("已记住" not in note for note in data["memory_notes"])
