"""GET /api/metrics：快照结构 + 内存后端标记。"""

from fastapi.testclient import TestClient

from app.main import app


def test_metrics_endpoint_shape():
    client = TestClient(app)
    resp = client.get("/api/metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert data["requests_total"] >= 1  # 本次请求已被中间件计数
    assert data["cache"]["backend"] == "memory"  # 无 REDIS_URL → 内存后端
    assert isinstance(data["stages"], dict)
    assert "uptime_seconds" in data
