"""共享 fixture：所有测试无 API key 也能跑（强制走降级路径）+ 状态隔离。"""

import pytest

from app.metrics import metrics
from app.store import reset_store


@pytest.fixture(autouse=True)
def _clean_state():
    """每个测试前清空存储单例与度量，保证互不污染。"""
    reset_store()
    metrics.reset()
    yield


@pytest.fixture
def force_llm_fallback(monkeypatch):
    """强制 LLM 不可用：chat_json / chat_with_tools 直接抛错 → 规则引擎兜底。"""

    def boom(*args, **kwargs):
        raise RuntimeError("forced LLM fallback (no key)")

    monkeypatch.setattr("app.agents.chat_json", boom)
    monkeypatch.setattr("app.agents.chat_with_tools", boom)
