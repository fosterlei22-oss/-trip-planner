"""评估 CLI：双轨。

- 缺省（无 --with-llm）：把 app.agents.chat_json / chat_with_tools 强制抛错，
  三 Agent 全部走确定性降级路径 → CI 安全、秒级、结果可复现。
- --with-llm：真实 DeepSeek（需 DEEPSEEK_API_KEY），报告真实 LLM 指标；
  没配 key 时自动退回规则引擎。

无论哪一轨都跑 **cold → warm 两遍**：cold 前清缓存（测真实延迟），
cold→warm 之间不清（warm 测缓存命中率与收益）。warm 命中率依赖
「同一批 case 的查询完全相同」这一前提，因此必须连跑。
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys

from app.metrics import metrics
from app.store import get_store, store_note
from eval.evaluator import run_all
from eval.golden_cases import CASES

MODE_RULE = "rule_engine"
MODE_LLM = "llm"


def _force_rule_engine():
    """把两个 LLM 入口替换成抛错函数，让所有 Agent 走降级路径。"""
    import app.agents as agents

    def boom(*args, **kwargs):  # noqa: ARG001
        raise RuntimeError("eval: LLM 被禁用，强制规则引擎")

    original = (agents.chat_json, agents.chat_with_tools)
    agents.chat_json = boom
    agents.chat_with_tools = boom
    return original


def _restore_agents(original) -> None:
    import app.agents as agents

    agents.chat_json, agents.chat_with_tools = original


def _print_summary(tag: str, result: dict) -> None:
    lat = result["latency_s"]
    print(f"\n## {tag}")
    print(f"  通过率     : {result['passed']}/{result['cases_total']} (pass_rate={result['pass_rate']})")
    print(f"  幻觉率     : {result['hallucination_rate']}（未知景点名 / 总 slot 数）")
    print(f"  耗时(s)    : mean={lat['mean']}  p50={lat['p50']}  p95={lat['p95']}")
    if result["tool_success_rate"] is None:
        print("  工具成功率 : 无（规则引擎路径，0 次工具调用）")
    else:
        print(
            f"  工具成功率 : {result['tool_success_rate']} "
            f"（{result['tool_calls']} 次调用 / {result['tool_errors']} 次失败）"
        )
    for feature, delta in sorted(result["cache_delta"].items()):
        rate = delta["hit_rate"] if delta["hit_rate"] is not None else "n/a"
        print(f"  缓存[{feature}]   : hits={delta['hits']} misses={delta['misses']} hit_rate={rate}")


def _select_mode(args: argparse.Namespace) -> str:
    if args.with_llm and not os.environ.get("DEEPSEEK_API_KEY"):
        print("[eval] 警告：--with-llm 但未设置 DEEPSEEK_API_KEY，退回规则引擎", file=sys.stderr)
        return MODE_RULE
    return MODE_LLM if args.with_llm else MODE_RULE


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="评估 LLM 多 Agent 旅行助手（golden cases 不变式校验）")
    parser.add_argument(
        "--with-llm",
        action="store_true",
        help="调用真实 DeepSeek（需 DEEPSEEK_API_KEY）；缺省强制规则引擎",
    )
    parser.add_argument("--json", action="store_true", help="输出机器可读 JSON 而非表格")
    parser.add_argument("--cases", type=int, default=0, help="只跑前 N 个用例（0 = 全部）")
    args = parser.parse_args(argv)

    cases = CASES[: args.cases] if args.cases > 0 else CASES
    mode = _select_mode(args)

    if args.json:
        # 重定向时 Windows 会用系统编码（GBK）写 stdout，污染 JSON 里的中文 →
        # 固定 UTF-8，保证 --json 输出任何平台/管道下都是合法 UTF-8。
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass  # 个别环境不支持 reconfigure，忽略

    get_store()  # 初始化并记忆化存储（探测 Redis 或回退内存），拿到真实 note
    store = store_note() or "memory"

    original = None
    try:
        if mode == MODE_RULE:
            original = _force_rule_engine()

        # cold → warm：只清一次缓存。cold 测真实延迟，warm 测缓存收益 + 命中率。
        # Agent 的调试 print 是诊断噪音，JSON 模式下把它赶到 stderr，别污染 stdout。
        quiet = sys.stderr if args.json else sys.stdout
        metrics.reset()
        get_store().clear_cache()
        with contextlib.redirect_stdout(quiet):
            cold = run_all(cases)
            warm = run_all(cases)

        if args.json:
            print(
                json.dumps(
                    {
                        "mode": mode,
                        "cases": len(cases),
                        "store_backend": cold["cache_backend"],
                        "store_note": store,
                        "cold": cold,
                        "warm": warm,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
        else:
            print(f"评估模式：{'真实 DeepSeek' if mode == MODE_LLM else '规则引擎（无 key）'}")
            print(f"存储后端：{store}（backend={cold['cache_backend']}）")
            _print_summary("cold（清缓存后首跑）", cold)
            _print_summary("warm（紧接着二跑，缓存已热）", warm)
        return 0
    finally:
        if original is not None:
            _restore_agents(original)


if __name__ == "__main__":
    sys.exit(main())
