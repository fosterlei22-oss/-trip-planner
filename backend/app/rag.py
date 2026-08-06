from __future__ import annotations

import math

from .data import CITY_PLACES

# 向量维度。特征哈希把文本映射到固定维度空间，纯 Python 实现、零依赖。
DIM = 512

# 缓存：city, name, 向量
_docs: list[tuple[str, str, list[float]]] | None = None


def _hash_token(token: str) -> int:
    """把任意文本 token 稳定映射成一个整数（特征哈希）。"""
    h = 0
    for ch in token:
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    return h


def _embed(text: str) -> list[float]:
    """把文本向量化：字符 + 字符二元组 作为特征，特征哈希后累加，再做 L2 归一化。

    说明：这是轻量自研 embedding（零下载）。生产环境应换成神经 embedding 模型
    （如 OpenAI / 智谱 embedding API），本函数的输入输出接口保持兼容。
    """
    chars = text.strip().replace(" ", "")
    tokens = list(chars)
    tokens += [chars[i : i + 2] for i in range(len(chars) - 1)]

    vec = [0.0] * DIM
    for token in tokens:
        vec[_hash_token(token) % DIM] += 1.0

    norm = math.sqrt(sum(v * v for v in vec))
    if norm:
        vec = [v / norm for v in vec]
    return vec


def _build_docs() -> list[tuple[str, str, list[float]]]:
    """把每个景点拼成文档并向量化，进程内缓存。"""
    global _docs
    if _docs is None:
        _docs = []
        for city, places in CITY_PLACES.items():
            for p in places:
                doc = (
                    f"{city} {p.name}。分类：{p.category}。{p.description}"
                    f"门票约{p.ticket}元，建议游玩{p.estimated_hours}小时。"
                )
                _docs.append((city, p.name, _embed(doc)))
    return _docs


def retrieve(query: str, city: str | None = None, top_k: int = 5) -> list[str]:
    """语义检索：把查询向量化，按余弦相似度返回最相关的景点名列表。

    where 思路：city 非空时先按城市过滤，再在候选里排序。
    余弦相似度 = 归一化向量的点积。
    """
    qv = _embed(query)
    docs = _build_docs()

    scored: list[tuple[float, str]] = []
    for doc_city, name, dv in docs:
        if city and doc_city != city:
            continue
        score = sum(a * b for a, b in zip(qv, dv))  # 点积 = 余弦相似度
        scored.append((score, name))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [name for _, name in scored[:top_k]]
