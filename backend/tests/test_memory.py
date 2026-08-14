"""会话记忆：prepare 合并 / remember 回写 / 兴趣上限 / 显式偏好记录。"""

from app.memory import MemoryStore
from app.models import TripRequest


def _req(**kw) -> TripRequest:
    defaults: dict = {"destination": "杭州", "days": 2}
    defaults.update(kw)
    return TripRequest(**defaults)


def test_prepare_noop_without_session():
    store = MemoryStore()
    req = _req(interests=["历史"])
    assert store.prepare(req) is req  # 无 session_id 原样返回同一对象


def test_prepare_noop_without_profile():
    store = MemoryStore()
    req = _req(session_id="brand-new", interests=["历史"])
    assert store.prepare(req) is req  # 无档案 → 原样返回


def test_remember_then_prepare_roundtrip():
    store = MemoryStore()
    store.remember(_req(session_id="s1", interests=["历史", "美食"], travel_style="foodie"))

    req2 = _req(session_id="s1", interests=["摄影"], destination="成都")
    merged = store.prepare(req2)
    assert merged.interests[:1] == ["摄影"]  # 本次在前
    assert "历史" in merged.interests and "美食" in merged.interests
    assert merged.travel_style == "foodie"  # 默认 classic → 沿用档案 foodie


def test_interests_capped_at_8():
    store = MemoryStore()
    store.remember(_req(session_id="s2", interests=["a", "b", "c", "d", "e", "f", "g", "h"]))
    merged = store.prepare(_req(session_id="s2", interests=["x", "y"]))
    assert len(merged.interests) <= 8
    assert merged.interests[:2] == ["x", "y"]


def test_remember_increments_visits_and_destinations():
    store = MemoryStore()
    store.remember(_req(session_id="s3", destination="北京"))
    store.remember(_req(session_id="s3", destination="上海"))
    profile = store.get_profile("s3")
    assert profile is not None
    assert profile.visits == 2
    assert profile.destinations == ["北京", "上海"]


def test_style_budget_only_recorded_when_explicit():
    store = MemoryStore()
    store.remember(_req(session_id="s4"))  # 全默认
    profile = store.get_profile("s4")
    assert profile.travel_style is None
    assert profile.budget_level is None

    store.remember(_req(session_id="s4", travel_style="deep", budget_level="comfort"))
    profile = store.get_profile("s4")
    assert profile.travel_style == "deep"
    assert profile.budget_level == "comfort"
