"""RelevanceJudge：小模型判相关率（M2-022，PDD v0.2 §4.1 第四步）。

- 采样 top-k（默认 5）文摘逐条判「相关/不相关」（judgment 类，走小模型档 +
  内容 hash 缓存），hit_rate = 相关数 / 采样数；空集 = 0.0。
- θ_rel 初值 0.6（S4 Open Question，金标集调参前不动）；低于阈值的处置
  （改写重检 ≤R 轮）归 M2-023。
"""
from __future__ import annotations

from typing import Final

from flint.domain.models import JSON, Doc, Query
from flint.domain.protocols import LLMProvider
from flint.llm.cache import LLMJudgmentCache

THETA_REL: Final[float] = 0.6

RELEVANCE_SCHEMA: Final[JSON] = {
    "type": "object",
    "properties": {"relevant": {"type": "boolean"}},
    "required": ["relevant"],
    "additionalProperties": False,
}

_PROMPT = (
    "判定检索相关性：文摘须直接讨论查询主题本身；仅提及同领域周边话题判"
    "不相关。只输出符合 schema 的 JSON。\n查询：{query}\n"
    "文摘（doc_id={doc_id}）：{title}"
)


class LLMRelevanceJudge:
    """冻结协议 RelevanceJudge 实现。"""

    def __init__(
        self,
        provider: LLMProvider,
        cache: LLMJudgmentCache,
        top_k: int = 5,
        max_retries: int = 2,
    ) -> None:
        self._provider = provider
        self._cache = cache
        self._top_k = top_k
        self._max_retries = max_retries

    def hit_rate(self, q: Query, docs: list[Doc]) -> float:
        sample = docs[: self._top_k]
        if not sample:
            return 0.0
        relevant = 0
        for doc in sample:
            prompt = _PROMPT.format(query=q.text, doc_id=doc.doc_id, title=doc.title)

            def compute(p: str = prompt) -> JSON:
                return self._provider.generate_structured(
                    p, RELEVANCE_SCHEMA, self._max_retries
                )

            payload = self._cache.cached(
                "judgment", f"relevance|{q.text}|{doc.doc_id}", compute
            )
            if payload["relevant"] is True:
                relevant += 1
        return relevant / len(sample)
