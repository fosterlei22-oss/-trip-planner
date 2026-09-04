from __future__ import annotations

import hashlib
import json
import os
import time

from dotenv import load_dotenv
from openai import OpenAI

from .metrics import metrics
from .store import LLM_PREFIX, get_store

# 读取 backend/.env 里的配置（如 DEEPSEEK_API_KEY）
load_dotenv()

# DeepSeek 兼容 OpenAI 接口，所以可以直接用 openai SDK
BASE_URL = "https://api.deepseek.com"
MODEL = "deepseek-chat"

# chat_json 响应缓存时长（秒）：相同 (system, user, temperature) 命中，跳过真实调用
LLM_CACHE_TTL = 7 * 24 * 3600

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.environ.get("DEEPSEEK_API_KEY")
        if not api_key:
            raise RuntimeError("未设置 DEEPSEEK_API_KEY（请在 backend/.env 中配置）")
        _client = OpenAI(api_key=api_key, base_url=BASE_URL)
    return _client


def _json_cache_key(system: str, user: str, temperature: float) -> str:
    """chat_json 缓存键：整元组序列化哈希，规避字段边界歧义。"""
    payload = json.dumps([system, user, temperature], ensure_ascii=False).encode("utf-8")
    return LLM_PREFIX + hashlib.sha256(payload).hexdigest()


def chat_json(system: str, user: str, temperature: float = 0.3, use_cache: bool = True) -> str:
    """调用 DeepSeek，要求以 JSON 对象格式返回，返回 JSON 字符串。

    核心点：response_format={"type": "json_object"} 强制模型输出合法 JSON，
    这样下游可以解析后用 Pydantic 校验。

    use_cache=True（默认）：相同 (system, user, temperature) 命中缓存，跳过真实调用；
    只缓存成功响应。use_cache=False 供评估冷启动测真实延迟。
    """
    key = _json_cache_key(system, user, temperature) if use_cache else None
    if key is not None:
        cached = get_store().get(key)
        if cached is not None:
            return cached

    start = time.perf_counter()
    try:
        resp = _get_client().chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
            temperature=temperature,
        )
    finally:
        metrics.inc("llm_calls")
        metrics.observe("llm", time.perf_counter() - start)

    content = resp.choices[0].message.content or "{}"
    if key is not None:
        get_store().set(key, content, ttl=LLM_CACHE_TTL)
    return content


def chat_with_tools(
    system: str,
    user: str,
    tools: list[dict],
    executor,
    max_rounds: int = 5,
    temperature: float = 0.3,
) -> str:
    """ReAct 工具调用循环：LLM 决定调工具 → 代码执行 → 结果喂回 → 直到输出最终答案。

    - tools: OpenAI 兼容的 function 定义列表
    - executor: 回调函数 `(tool_name: str, args: dict) -> dict`，由调用方实现真正逻辑
    """
    client = _get_client()
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    # 注意：chat_with_tools 不做响应缓存——保住 travel_minutes 真实执行
    # 的 ReAct 循环，工具成功率度量才有意义。只做耗时/次数埋点。
    for _ in range(max_rounds):
        start = time.perf_counter()
        try:
            resp = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                temperature=temperature,
            )
        finally:
            metrics.inc("llm_calls")
            metrics.observe("llm", time.perf_counter() - start)
        msg = resp.choices[0].message

        # 没有 tool_calls 说明 LLM 想收尾了，返回最终内容
        if not msg.tool_calls:
            return msg.content or ""

        # 把"assistant 想调工具"这条消息存进历史
        messages.append(msg.model_dump(exclude_none=True))
        for tc in msg.tool_calls:
            try:
                args = json.loads(tc.function.arguments)
                result = executor(tc.function.name, args)
            except Exception as exc:  # noqa: BLE001
                result = {"error": str(exc)}
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result, ensure_ascii=False),
                }
            )

    raise RuntimeError(f"工具调用超过 {max_rounds} 轮仍未结束")


def extract_json(text: str) -> dict:
    """从模型输出中稳健地解析出 JSON 对象。

    模型经常把 JSON 包在 markdown 代码块里，或前面写一大段思考文字，
    所以不能直接 json.loads。依次尝试：直接解析 → 去掉代码块围栏 → 定位首个完整 JSON 对象。
    """
    text = text.strip()

    # 去掉 ```json ... ``` 代码块围栏
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 兜底：从每个左花括号开始尝试，读取第一个完整 JSON 对象。
    # raw_decode 会在对象结束处停止，因此能容忍 JSON 后面附带文字或第二段内容。
    decoder = json.JSONDecoder()
    for start, char in enumerate(text):
        if char != "{":
            continue
        try:
            data, _ = decoder.raw_decode(text[start:])
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            return data

    raise ValueError(f"无法从模型输出解析 JSON：{text[:100]!r}")
