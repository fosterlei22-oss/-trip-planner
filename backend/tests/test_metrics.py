"""Metrics 单例：计数 / 分位数 / 快照 / 重置。"""

from app.metrics import Metrics, percentiles


def test_inc_and_snapshot():
    m = Metrics()
    m.inc("requests_total")
    m.inc("requests_total", 2)
    m.record_fallback("research")
    for value in (0.1, 0.2, 0.3, 0.4):
        m.observe("llm", value)
    snap = m.snapshot()
    assert snap["requests_total"] == 3
    assert snap["fallbacks"]["research"] == 1
    assert snap["stages"]["llm"]["count"] == 4
    assert snap["stages"]["llm"]["p50"] == 0.2  # 最近秩：ceil(0.5*4)=2 → 0.2


def test_percentiles_nearest_rank():
    p50, p95 = percentiles([1, 2, 3, 4])
    assert p50 == 2  # ceil(0.5*4)=2 → 第 2 个
    assert p95 == 4  # ceil(0.95*4)=4 → 第 4 个


def test_percentiles_empty():
    assert percentiles([]) == [None, None]


def test_reset_clears_state():
    m = Metrics()
    m.inc("x")
    m.observe("llm", 0.5)
    m.reset()
    snap = m.snapshot()
    assert snap["requests_total"] == 0
    assert "llm" not in snap["stages"]
