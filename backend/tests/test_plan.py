"""多 Agent 编排的降级路径测试。

把 LLM 两个入口（chat_json / chat_with_tools）都强制抛异常，验证系统在
无 API key / LLM 失败时自动退回规则引擎，仍产出结构完整的 TripPlan。
CI 里本来就没有 DEEPSEEK_API_KEY，这里显式 patch 保证测试确定性且秒级完成。
"""
import pytest
from fastapi.testclient import TestClient

from app.agents import TravelPlanner
from app.main import app
from app.models import TripRequest


@pytest.fixture()
def force_llm_fallback(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("测试：强制降级")

    monkeypatch.setattr("app.agents.chat_json", boom)
    monkeypatch.setattr("app.agents.chat_with_tools", boom)


def test_planner_fallback_produces_full_structure(force_llm_fallback):
    request = TripRequest(destination="杭州", days=2, people=2, interests=["文化"])
    plan = TravelPlanner().plan(request)

    assert len(plan.days) == 2
    assert plan.budget.total > 0
    assert plan.budget.per_person > 0
    assert plan.route_points  # 去重后的路线点非空
    assert plan.packing_list
    assert plan.tips

    for day in plan.days:
        assert day.morning and day.afternoon and day.evening
        assert day.estimated_cost > 0


def test_api_plan_endpoint_fallback(force_llm_fallback):
    client = TestClient(app)
    resp = client.post(
        "/api/trip/plan",
        json={"destination": "北京", "days": 1, "people": 1},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["destination"] == "北京"
    assert len(body["days"]) == 1
    assert body["budget"]["total"] > 0
    assert body["route_points"]
