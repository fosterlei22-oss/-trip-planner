from __future__ import annotations

import math
import threading
import time

# 每个 stage 最多保留最近 N 条耗时样本，防止无界增长。
MAX_SAMPLES = 1000


def percentiles(values: list[float], ps: tuple[int, ...] = (50, 95)) -> list[float | None]:
    """最近秩百分位数：n 个样本里第 ceil(p/100*n) 个（1 起）。空列表返回 [None, ...]。"""
    if not values:
        return [None] * len(ps)
    ordered = sorted(values)
    out: list[float | None] = []
    for p in ps:
        idx = math.ceil(p / 100 * len(ordered)) - 1
        idx = max(0, min(idx, len(ordered) - 1))
        out.append(ordered[idx])
    return out


class Metrics:
    """进程内轻量度量：计数 + 各阶段耗时分位数 + 降级/工具/缓存计数。

    全部状态由一把锁保护；synchronized 的 snapshot 返回深拷贝，
    /api/metrics 端点与 eval 套件读取的都是同一份数据。
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._start = time.monotonic()
        self._counters: dict[str, int] = {}
        self._fallbacks: dict[str, int] = {}
        self._stages: dict[str, list[float]] = {}

    def reset(self) -> None:
        """清空所有计数与样本（测试 / eval 隔离用）。uptime 也归零。"""
        with self._lock:
            self._start = time.monotonic()
            self._counters = {}
            self._fallbacks = {}
            self._stages = {}

    def inc(self, name: str, n: int = 1) -> None:
        with self._lock:
            self._counters[name] = self._counters.get(name, 0) + n

    def record_fallback(self, agent: str) -> None:
        """记录某个 Agent 走了降级路径（LLM 不可用退回规则版）。"""
        with self._lock:
            self._fallbacks[agent] = self._fallbacks.get(agent, 0) + 1

    def observe(self, stage: str, seconds: float) -> None:
        """记录某个阶段的一次耗时（秒），环形缓冲只留最近 MAX_SAMPLES 条。"""
        with self._lock:
            bucket = self._stages.setdefault(stage, [])
            bucket.append(seconds)
            if len(bucket) > MAX_SAMPLES:
                del bucket[: len(bucket) - MAX_SAMPLES]

    def _stage_stats(self, stage: str) -> dict | None:
        bucket = self._stages.get(stage) or []
        if not bucket:
            return None
        p50, p95 = percentiles(bucket)
        return {
            "count": len(bucket),
            "mean": round(sum(bucket) / len(bucket), 4),
            "p50": round(p50, 4) if p50 is not None else None,
            "p95": round(p95, 4) if p95 is not None else None,
        }

    def snapshot(self) -> dict:
        """返回可序列化的完整度量快照。锁内拷贝，锁外计算分位数。"""
        with self._lock:
            counters = dict(self._counters)
            fallbacks = dict(self._fallbacks)
            stages = {k: list(v) for k, v in self._stages.items()}
            uptime = time.monotonic() - self._start
        return {
            "requests_total": counters.get("requests_total", 0),
            "llm_calls": counters.get("llm_calls", 0),
            "tool_calls": counters.get("tool_calls", 0),
            "tool_errors": counters.get("tool_errors", 0),
            "rag_errors": counters.get("rag_errors", 0),
            "fallbacks": {
                "research": fallbacks.get("research", 0),
                "itinerary": fallbacks.get("itinerary", 0),
            },
            "stages": {
                stage: self._stage_stats(stage)
                for stage in sorted(stages)
                if self._stages.get(stage)
            },
            "uptime_seconds": round(uptime, 2),
        }


# 模块级单例：所有模块共享同一份度量
metrics = Metrics()
