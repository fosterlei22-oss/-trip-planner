"""Agent 评估套件：golden cases + 不变式校验 + cold/warm 缓存收益量化。

用法（在 backend/ 目录下运行，保证 `app` / `eval` 可导入）：

    python -m eval.run_eval               # 规则引擎（无 API key，CI 安全、秒级）
    python -m eval.run_eval --with-llm    # 真实 DeepSeek（需 DEEPSEEK_API_KEY）
    python -m eval.run_eval --json        # 机器可读输出
    python -m eval.run_eval --cases 5     # 只跑前 5 个用例

输出指标：通过率 pass_rate、幻觉率 hallucination_rate、耗时 mean/p50/p95、
工具成功率 tool_success_rate、cold→warm 缓存命中率（RAG / LLM）。
"""
