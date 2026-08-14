"""评估器：跑 golden case → 不变式校验 → 聚合成可量化的指标。

关键设计：**缓存命中率按"本轮运行"算 delta**——cold 跑完填充缓存后，
全局累计命中率会永远停在 0.5，只有看"本轮内 hits/misses 增量"才能
区分 cold（0%）和 warm（100%）。run_all 在跑前/跑后各取一次 store
快照，报告这一轮的 per-feature hit_rate。
"""

from __future__ import annotations

from math import ceil
from time import perf_counter

from app.agents import TravelPlanner
from app.data import CITY_PLACES, DEFAULT_PLACES
from app.metrics import metrics, percentiles
from app.models import TripPlan, TripRequest
from app.store import get_store

_planner = TravelPlanner()


# ---------- 不变式校验 ----------

def _known_names(destination: str) -> set[str]:
    """该目的地的合法景点名集合：CITY_PLACES 优先，未知城市用 DEFAULT_PLACES。"""
    places = CITY_PLACES.get(destination) or DEFAULT_PLACES
    return {p.name for p in places}


def validate(plan: TripPlan, case: dict) -> list[str]:
    """校验一份计划的硬性不变式，返回违规清单（空 = 通过）。

    覆盖：天数匹配 / 每天 3 个互异非空景点 / 景点名在知识库内（防幻觉）/
    预算 total 恒等式 / per_person == ceil(total/people) /
    transport/meals/packing_list/tips 非空 / route_points 与去重景点一致。
    """
    violations: list[str] = []
    destination = case["destination"]
    days = case["days"]
    people = case["people"]
    known = _known_names(destination)

    if len(plan.days) != days:
        violations.append(f"天数不符：期望 {days}，实际 {len(plan.days)}")

    day_names: list[str] = []
    for day in plan.days:
        names = [day.morning.name, day.afternoon.name, day.evening.name]
        day_names.extend(names)
        if any(not name for name in names):
            violations.append(f"Day {day.day} 存在空景点名")
        if len(set(names)) != 3:
            violations.append(f"Day {day.day} 三个景点不互异：{names}")
        for name in names:
            if name not in known:
                violations.append(f"Day {day.day} 含知识库外景点（幻觉）：{name}")
        if not day.transport or not day.meals:
            violations.append(f"Day {day.day} 缺交通或餐饮信息")

    b = plan.budget
    if b.total != b.lodging + b.food + b.transport + b.tickets + b.misc:
        violations.append("预算 total 与分项不一致")
    expected = ceil(b.total / people)
    if b.per_person != expected:
        violations.append(f"per_person 应为 ceil(total/people)={expected}，实际 {b.per_person}")

    if not plan.route_points:
        violations.append("route_points 为空")
    if not plan.packing_list:
        violations.append("packing_list 为空")
    if not plan.tips:
        violations.append("tips 为空")

    route_names = [p.name for p in plan.route_points]
    if sorted(route_names) != sorted(dict.fromkeys(day_names)):
        violations.append("route_points 与行程景点（去重）不一致")

    return violations


# ---------- 单用例 / 整批运行 ----------

def run_case(case: dict) -> dict:
    """跑一个 golden case，返回结构化结果（含耗时、违规、幻觉明细）。"""
    payload = {k: v for k, v in case.items() if k != "id"}
    request = TripRequest(**payload)
    start = perf_counter()
    plan = _planner.plan(request)
    elapsed = perf_counter() - start

    violations = validate(plan, case)
    return {
        "case_id": case["id"],
        "destination": case["destination"],
        "days": len(plan.days),
        "ok": not violations,
        "violations": violations,
        "hallucinations": [v for v in violations if "幻觉" in v],
        "latency_s": round(elapsed, 4),
    }


def _cache_delta(before: dict, after: dict) -> dict:
    """本轮运行内各功能的命中/未命中增量与命中率。"""
    features = set(before["hits"]) | set(after["hits"]) | set(before["misses"]) | set(after["misses"])
    out: dict[str, dict] = {}
    for feature in sorted(features):
        hits = after["hits"].get(feature, 0) - before["hits"].get(feature, 0)
        misses = after["misses"].get(feature, 0) - before["misses"].get(feature, 0)
        total = hits + misses
        out[feature] = {
            "hits": hits,
            "misses": misses,
            "hit_rate": round(hits / total, 4) if total else None,
        }
    return out


def run_all(cases: list[dict]) -> dict:
    """批量跑完一组 case 并聚合指标。

    返回：pass_rate / hallucination_rate / latency mean·p50·p95 /
    tool_success_rate（读当前 metrics 计数，0 调用则为 None）/
    cache_delta（本轮 per-feature hit_rate）。
    """
    cache_before = get_store().snapshot()
    snap_before = metrics.snapshot()
    results = [run_case(c) for c in cases]
    cache_after = get_store().snapshot()
    snap_after = metrics.snapshot()

    passed = sum(1 for r in results if r["ok"])
    hallucinated = sum(len(r["hallucinations"]) for r in results)
    total_slots = sum(r["days"] * 3 for r in results)
    latencies = [r["latency_s"] for r in results]

    # 工具计数按"本轮增量"报（与 cache_delta 一致）：cold / warm 各自独立
    tool_total = snap_after["tool_calls"] - snap_before["tool_calls"]
    tool_errors = snap_after["tool_errors"] - snap_before["tool_errors"]
    p50, p95 = percentiles(latencies)

    return {
        "cases_total": len(cases),
        "passed": passed,
        "pass_rate": round(passed / len(cases), 4) if cases else None,
        "hallucination_rate": round(hallucinated / total_slots, 4) if total_slots else None,
        "latency_s": {
            "mean": round(sum(latencies) / len(latencies), 4) if latencies else None,
            "p50": round(p50, 4) if p50 is not None else None,
            "p95": round(p95, 4) if p95 is not None else None,
        },
        "tool_calls": tool_total,
        "tool_errors": tool_errors,
        "tool_success_rate": round((tool_total - tool_errors) / tool_total, 4) if tool_total else None,
        "cache_backend": cache_after["backend"],
        "cache_delta": _cache_delta(cache_before, cache_after),
        "cases": results,
    }
