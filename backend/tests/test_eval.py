"""评估套件的 keyless 测试：无 API key 验证通过率 / 幻觉率 / 缓存收益。

两个测试都强制走规则引擎（conftest 的 force_llm_fallback），
验证的是「确定性降级路径本身是否满足不变式」+「cold/warm 缓存语义」。

warm 命中率依赖「同一批 case 查询完全相同」：先 run_all 预热填充缓存，
再 run_all 全部命中 → 本轮 delta hit_rate == 1.0。
"""

from eval import evaluator
from eval.golden_cases import CASES


def test_fallback_eval_pass_rate(force_llm_fallback):
    """规则引擎路径：全部 15 个 golden case 通过，零幻觉，冷启动 RAG 全未命中。"""
    cold = evaluator.run_all(CASES)

    assert cold["cases_total"] == len(CASES) == 15
    assert cold["passed"] == 15
    assert cold["pass_rate"] == 1.0
    assert cold["hallucination_rate"] == 0.0
    # 规则引擎不调用工具 → 工具成功率应为 None（不要断言具体值）
    assert cold["tool_success_rate"] is None
    # 冷启动首轮：RAG 全未命中（每个 case 一次 retrieve）
    assert cold["cache_delta"]["rag"]["hits"] == 0
    assert cold["cache_delta"]["rag"]["misses"] == len(CASES)
    assert cold["cache_delta"]["rag"]["hit_rate"] == 0.0


def test_warm_rag_cache_hit(force_llm_fallback):
    """先冷后暖连跑：第二遍同查询全部命中 → 本轮 RAG 命中率 1.0。"""
    evaluator.run_all(CASES)  # cold：预热填充 RAG 缓存
    warm = evaluator.run_all(CASES)  # warm：同一批 case 全命中

    assert warm["cache_delta"]["rag"]["hits"] == len(CASES)
    assert warm["cache_delta"]["rag"]["misses"] == 0
    assert warm["cache_delta"]["rag"]["hit_rate"] == 1.0
