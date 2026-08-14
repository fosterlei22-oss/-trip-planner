from __future__ import annotations

import json
import os
import threading
import time

# 命名空间前缀：跨功能防碰撞，也让 clear_cache / 命中率统计可分类
RAG_PREFIX = "rag:"
LLM_PREFIX = "llm:json:"
SESSION_PREFIX = "session:"

_CACHE_PREFIXES = (RAG_PREFIX, LLM_PREFIX)

DEFAULT_REDIS_URL = "redis://localhost:6379"
_REDIS_CONNECT_TIMEOUT = 1.0
_REDIS_SOCKET_TIMEOUT = 1.0

# 内存后端键数上限（防御性），防止异常下无界增长
_MEMORY_MAX_KEYS = 5000


def _feature_of(key: str) -> str:
    """从 key 前缀推出所属功能（用于命中率分类统计）。"""
    if key.startswith(RAG_PREFIX):
        return "rag"
    if key.startswith(LLM_PREFIX):
        return "llm"
    if key.startswith(SESSION_PREFIX):
        return "session"
    return "other"


class KVStore:
    """KV 缓存/会话存储的抽象接口。get 失败一律按 miss 处理（优雅降级）。"""

    backend: str  # "redis" | "memory"

    def get(self, key: str):  # noqa: ANN201
        raise NotImplementedError

    def set(self, key: str, value, ttl: int | None = None) -> None:  # noqa: ANN001
        raise NotImplementedError

    def clear_cache(self) -> None:
        raise NotImplementedError

    def clear_all(self) -> None:
        raise NotImplementedError

    def snapshot(self) -> dict:
        raise NotImplementedError


class InMemoryKVStore(KVStore):
    """进程内字典后端：TTL 惰性过期 + 键数上限。行为与 Redis 后端等价。"""

    def __init__(self) -> None:
        self.backend = "memory"
        self._lock = threading.Lock()
        # key -> (json_str, expires_at_monotonic | None)
        self._data: dict[str, tuple[str, float | None]] = {}
        self._hits: dict[str, int] = {}
        self._misses: dict[str, int] = {}
        self._errors = 0

    def get(self, key: str):
        now = time.monotonic()
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                self._misses[_feature_of(key)] = self._misses.get(_feature_of(key), 0) + 1
                return None
            value, expires_at = entry
            if expires_at is not None and now > expires_at:
                del self._data[key]
                self._misses[_feature_of(key)] = self._misses.get(_feature_of(key), 0) + 1
                return None
            self._hits[_feature_of(key)] = self._hits.get(_feature_of(key), 0) + 1
            return json.loads(value)

    def set(self, key: str, value, ttl: int | None = None) -> None:
        encoded = json.dumps(value, ensure_ascii=False)
        expires_at = time.monotonic() + ttl if ttl else None
        with self._lock:
            if key not in self._data and len(self._data) >= _MEMORY_MAX_KEYS:
                return  # 超上限静默丢弃新键，避免内存失控
            self._data[key] = (encoded, expires_at)

    def clear_cache(self) -> None:
        with self._lock:
            for key in [k for k in self._data if k.startswith(_CACHE_PREFIXES)]:
                del self._data[key]

    def clear_all(self) -> None:
        with self._lock:
            self._data.clear()

    def snapshot(self) -> dict:
        with self._lock:
            hits, misses = dict(self._hits), dict(self._misses)
            errors = self._errors
            size = len(self._data)
        return _build_snapshot(self.backend, hits, misses, errors, size)


class RedisKVStore(KVStore):
    """Redis 后端：所有网络操作失败都退化为 miss / no-op，绝不抛给上层。"""

    def __init__(self, url: str) -> None:
        import redis  # 可选导入：未装 redis 时上层回退内存后端

        self.backend = "redis"
        self._lock = threading.Lock()
        self._client = redis.Redis.from_url(
            url,
            socket_connect_timeout=_REDIS_CONNECT_TIMEOUT,
            socket_timeout=_REDIS_SOCKET_TIMEOUT,
            decode_responses=True,
        )
        self._hits: dict[str, int] = {}
        self._misses: dict[str, int] = {}
        self._errors = 0

    def ping(self) -> bool:
        try:
            return bool(self._client.ping())
        except Exception:  # noqa: BLE001
            return False

    def get(self, key: str):
        feature = _feature_of(key)
        try:
            raw = self._client.get(key)
        except Exception:  # noqa: BLE001
            with self._lock:
                self._errors += 1
                self._misses[feature] = self._misses.get(feature, 0) + 1
            return None
        if raw is None:
            with self._lock:
                self._misses[feature] = self._misses.get(feature, 0) + 1
            return None
        with self._lock:
            self._hits[feature] = self._hits.get(feature, 0) + 1
        return json.loads(raw)

    def set(self, key: str, value, ttl: int | None = None) -> None:
        try:
            self._client.set(key, json.dumps(value, ensure_ascii=False), ex=ttl)
        except Exception:  # noqa: BLE001
            with self._lock:
                self._errors += 1

    def _scan_prefix(self, prefix: str) -> None:
        for key in self._client.scan_iter(match=prefix + "*", count=1000):
            self._client.delete(key)

    def clear_cache(self) -> None:
        try:
            for prefix in _CACHE_PREFIXES:
                self._scan_prefix(prefix)
        except Exception:  # noqa: BLE001
            with self._lock:
                self._errors += 1

    def clear_all(self) -> None:
        try:
            for prefix in _CACHE_PREFIXES + (SESSION_PREFIX,):
                self._scan_prefix(prefix)
        except Exception:  # noqa: BLE001
            with self._lock:
                self._errors += 1

    def snapshot(self) -> dict:
        with self._lock:
            hits, misses = dict(self._hits), dict(self._misses)
            errors = self._errors
        return _build_snapshot(self.backend, hits, misses, errors, None)


def _build_snapshot(
    backend: str,
    hits: dict[str, int],
    misses: dict[str, int],
    errors: int,
    size: int | None,
) -> dict:
    out: dict = {
        "backend": backend,
        "errors": errors,
        "hits": hits,
        "misses": misses,
    }
    if size is not None:
        out["keys"] = size
    for feature in sorted(set(hits) | set(misses)):
        h, m = hits.get(feature, 0), misses.get(feature, 0)
        out[f"{feature}_hit_rate"] = round(h / (h + m), 4) if (h + m) else None
    return out


_store: KVStore | None = None
_store_lock = threading.Lock()
_store_note: str | None = None


def get_store() -> KVStore:
    """进程内单例：首次调用惰性初始化并记忆化。

    - 未配置 REDIS_URL：直接内存后端，零网络（本地开发 / CI / Render）。
    - 配置了 REDIS_URL：探测 redis，失败则回退内存并记录原因。
    """
    global _store, _store_note
    with _store_lock:
        if _store is not None:
            return _store

        url = os.environ.get("REDIS_URL")
        if not url:
            _store = InMemoryKVStore()
            _store_note = "REDIS_URL 未配置，使用进程内内存后端"
            return _store

        try:
            candidate = RedisKVStore(url)
            if candidate.ping():
                _store = candidate
                _store_note = f"已连接 Redis：{url}"
            else:
                _store = InMemoryKVStore()
                _store_note = f"Redis 不可达（{url}），自动回退内存后端"
        except Exception as exc:  # noqa: BLE001 —— import 失败或连接异常都回退
            _store = InMemoryKVStore()
            _store_note = f"Redis 初始化失败（{exc}），自动回退内存后端"
        return _store


def reset_store() -> None:
    """清空单例（测试 / eval 重新探测用）。"""
    global _store, _store_note
    with _store_lock:
        _store = None
        _store_note = None


def store_note() -> str | None:
    return _store_note
