"""回归测试：评估套件抓到的真实 bug——LLM 精排返回重复景点，候选列表带重。

问题：真实 LLM 轨评估时 `sh-foodie-1` 失败，violation = 「Day 1 三个景点不互异」
（外滩 / 豫园 / 外滩）。根因是 `_llm_select` 把 LLM 返回的重复景点原样放进候选，
单日行程（或规则版兜底）就出现同名景点。

修复：`_llm_select` 保序去重；去重后不足 3 个时用规则版候选补齐，
保证「任意一天 3 个互异景点」这个不变式在结构上成立。
"""

import json

from app.agents import DestinationResearchAgent, TravelPlanner
from app.data import CITY_PLACES
from app.models import TripRequest

# LLM 返回了重复的「外滩」（真实 case 的形态），去重后应剩 外滩/豫园/田子坊 3 个
DUPS_JSON = json.dumps({"places": [{"name": "外滩"}, {"name": "豫园"}, {"name": "外滩"}, {"name": "田子坊"}]})
# LLM 只给了 2 个去重景点 → 需要规则版补齐到 3 个
FEW_JSON = json.dumps({"places": [{"name": "外滩"}, {"name": "外滩"}]})


def test_llm_select_dedupes_places(monkeypatch):
    monkeypatch.setattr("app.agents.chat_json", lambda *a, **k: DUPS_JSON)
    agent = DestinationResearchAgent()
    request = TripRequest(destination="上海", days=1, people=2, interests=["美食"])
    picked = agent._llm_select(request, CITY_PLACES["上海"])
    names = [p.name for p in picked]
    assert names == ["外滩", "豫园", "田子坊"]  # 保序去重


def test_llm_select_pads_to_three_when_few_distinct(monkeypatch):
    monkeypatch.setattr("app.agents.chat_json", lambda *a, **k: FEW_JSON)
    agent = DestinationResearchAgent()
    request = TripRequest(destination="上海", days=1, people=2, interests=["美食"])
    picked = agent._llm_select(request, CITY_PLACES["上海"])
    assert len(picked) >= 3  # 不足 3 个时用规则版候选补齐
    assert len({p.name for p in picked}) == len(picked)  # 仍无重复


def test_plan_no_same_day_duplicates_when_llm_returns_dups(force_llm_fallback, monkeypatch):
    """集成：LLM 返回重复景点时，最终行程同一天三个景点仍互异。"""
    monkeypatch.setattr("app.agents.chat_json", lambda *a, **k: DUPS_JSON)
    planner = TravelPlanner()
    request = TripRequest(destination="上海", days=1, people=2, interests=["美食"])
    plan = planner.plan(request)
    for day in plan.days:
        names = {day.morning.name, day.afternoon.name, day.evening.name}
        assert len(names) == 3
