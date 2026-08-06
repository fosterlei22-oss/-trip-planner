from __future__ import annotations

import json
import os

from dotenv import load_dotenv
from openai import OpenAI

# 读取 backend/.env 里的配置（如 DEEPSEEK_API_KEY）
load_dotenv()

# DeepSeek 兼容 OpenAI 接口，所以可以直接用 openai SDK
BASE_URL = "https://api.deepseek.com"
MODEL = "deepseek-chat"

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.environ.get("DEEPSEEK_API_KEY")
        if not api_key:
            raise RuntimeError("未设置 DEEPSEEK_API_KEY（请在 backend/.env 中配置）")
        _client = OpenAI(api_key=api_key, base_url=BASE_URL)
    return _client


def chat_json(system: str, user: str, temperature: float = 0.3) -> str:
    """调用 DeepSeek，要求以 JSON 对象格式返回，返回 JSON 字符串。

    核心点：response_format={"type": "json_object"} 强制模型输出合法 JSON，
    这样下游可以解析后用 Pydantic 校验。
    """
    resp = _get_client().chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        response_format={"type": "json_object"},
        temperature=temperature,
    )
    return resp.choices[0].message.content or "{}"


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
    for _ in range(max_rounds):
        resp = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            temperature=temperature,
        )
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
    所以不能直接 json.loads。依次尝试：直接解析 → 去掉代码块围栏 → 截取 {} 区间。
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

    # 兜底：截取第一个 { 到最后一个 } 之间的内容
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(text[start : end + 1])

    raise ValueError(f"无法从模型输出解析 JSON：{text[:100]!r}")
