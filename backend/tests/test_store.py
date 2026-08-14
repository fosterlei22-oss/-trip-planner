"""KVStore 存储抽象：内存后端读写 / TTL / 清空 / 命中率。Redis 后端不在此测（无服务器）。"""

from app.store import InMemoryKVStore, get_store, reset_store


def test_memory_set_get_roundtrip():
    store = InMemoryKVStore()
    store.set("rag:k", ["西湖", "灵隐寺"])
    assert store.get("rag:k") == ["西湖", "灵隐寺"]
    assert store.get("missing") is None


def test_memory_ttl_lazy_expiry():
    store = InMemoryKVStore()
    store.set("k", "v", ttl=-1)  # 已过期
    assert store.get("k") is None


def test_clear_cache_only_prefixed_keys():
    store = InMemoryKVStore()
    store.set("rag:x", ["a"])
    store.set("llm:json:y", "{}")
    store.set("session:s", {"interests": []})
    store.clear_cache()
    assert store.get("rag:x") is None
    assert store.get("llm:json:y") is None
    assert store.get("session:s") is not None


def test_clear_all():
    store = InMemoryKVStore()
    store.set("session:s", {})
    store.clear_all()
    assert store.get("session:s") is None


def test_get_store_defaults_to_memory_when_no_url(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    reset_store()
    assert get_store().backend == "memory"


def test_snapshot_hit_rate():
    store = InMemoryKVStore()
    store.set("rag:k", ["a"])
    store.get("rag:k")  # hit
    store.get("rag:k")  # hit
    store.get("rag:nope")  # miss
    snap = store.snapshot()
    assert snap["backend"] == "memory"
    assert snap["hits"]["rag"] == 2
    assert snap["misses"]["rag"] == 1
    assert abs(snap["rag_hit_rate"] - 2 / 3) < 1e-4  # snapshot 里四舍五入到 4 位
