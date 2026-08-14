"""chat_json 响应缓存：相同入参命中、use_cache=False 绕过、chat_with_tools 永不缓存。"""

from types import SimpleNamespace

import app.llm as llm


class _Msg:
    """模拟 message：tool_calls 为 None 让 chat_with_tools 一轮即收尾。"""

    tool_calls = None

    def __init__(self, content: str) -> None:
        self.content = content


class FakeClient:
    """模拟 OpenAI 客户端：记录 create 调用次数，返回固定内容。"""

    def __init__(self, content: str = "{}") -> None:
        self._content = content
        self.calls = 0

    @property
    def chat(self):
        return self

    @property
    def completions(self):
        return self

    def create(self, **kwargs):
        self.calls += 1
        return SimpleNamespace(choices=[SimpleNamespace(message=_Msg(self._content))])


def test_chat_json_cache_hit(monkeypatch):
    fake = FakeClient('{"places": [{"name": "西湖"}]}')
    monkeypatch.setattr(llm, "_get_client", lambda: fake)
    first = llm.chat_json("system", "user")
    second = llm.chat_json("system", "user")
    assert first == second
    assert fake.calls == 1  # 第二次命中缓存，不再调 API


def test_chat_json_use_cache_false_bypasses(monkeypatch):
    fake = FakeClient("{}")
    monkeypatch.setattr(llm, "_get_client", lambda: fake)
    llm.chat_json("system", "user", use_cache=False)
    llm.chat_json("system", "user", use_cache=False)
    assert fake.calls == 2


def test_chat_json_different_input_misses(monkeypatch):
    fake = FakeClient("{}")
    monkeypatch.setattr(llm, "_get_client", lambda: fake)
    llm.chat_json("system A", "user")
    llm.chat_json("system B", "user")
    assert fake.calls == 2


def test_chat_with_tools_never_cached(monkeypatch):
    fake = FakeClient('{"days": []}')
    monkeypatch.setattr(llm, "_get_client", lambda: fake)
    out1 = llm.chat_with_tools("system", "user", [], lambda name, args: {})
    out2 = llm.chat_with_tools("system", "user", [], lambda name, args: {})
    assert out1 == out2
    assert fake.calls == 2  # 工具循环每次真实调用，不读缓存
