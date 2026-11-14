"""查询术语标准化步（M2-017，PDD v0.2 §4.1 第一步）。

- 中→英学术术语优先走映射表（M1-018；命中率钩子 term_map.stats() 即观测面）；
- 映射缺失 → LLM 提案（judgment 类，入内容 hash 缓存——同词第二次零调用）；
- 非直译：LLM 提案 prompt 要求学术检索用语形态。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

from flint.domain.models import JSON
from flint.domain.protocols import LLMProvider
from flint.llm.cache import LLMJudgmentCache
from flint.norm.terms import TermMap

TERM_SCHEMA: Final[JSON] = {
    "type": "object",
    "properties": {"english": {"type": "string", "minLength": 1}},
    "required": ["english"],
    "additionalProperties": False,
}

_PROMPT = (
    "把以下中文关键词转成英文学术检索术语（非逐字直译，用文献中实际使用的"
    "表述）。只输出符合 schema 的 JSON。\n关键词：{term}"
)


@dataclass(frozen=True)
class StandardizedTerm:
    original: str
    english: str
    source: Literal["term_map", "llm"]


def standardize_terms(
    keywords: list[str],
    term_map: TermMap,
    provider: LLMProvider,
    cache: LLMJudgmentCache,
    max_retries: int = 2,
) -> list[StandardizedTerm]:
    results: list[StandardizedTerm] = []
    for keyword in keywords:
        mapped = term_map.lookup(keyword)
        if mapped is not None:
            results.append(
                StandardizedTerm(original=keyword, english=mapped, source="term_map")
            )
            continue

        def compute(term: str = keyword) -> JSON:
            return provider.generate_structured(
                _PROMPT.format(term=term), TERM_SCHEMA, max_retries
            )

        payload = cache.cached("judgment", f"term-std|{keyword}", compute)
        results.append(
            StandardizedTerm(
                original=keyword, english=str(payload["english"]), source="llm"
            )
        )
    return results
