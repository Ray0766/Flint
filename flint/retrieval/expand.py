"""同义/上下位扩展步（M2-018，PDD v0.2 §4.1 第二步）。

- 同义 / 上位 / 下位各 1~2 条（结构化输出 schema 校验 + 每族截断 2）。
- 扩展失败（结构化耗尽）降级为原词继续——检索不因扩展环节阻塞。
- judgment 类：同词扩展入内容 hash 缓存。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final

from flint.domain.models import JSON
from flint.domain.protocols import LLMProvider
from flint.llm.cache import LLMJudgmentCache
from flint.llm.structured import StructuredOutputExhausted

EXPANSION_SCHEMA: Final[JSON] = {
    "type": "object",
    "properties": {
        "synonyms": {"type": "array", "items": {"type": "string", "minLength": 1}},
        "broader": {"type": "array", "items": {"type": "string", "minLength": 1}},
        "narrower": {"type": "array", "items": {"type": "string", "minLength": 1}},
    },
    "required": ["synonyms", "broader", "narrower"],
    "additionalProperties": False,
}

_PROMPT = (
    "给出以下英文学术检索术语的扩展：synonyms（同义）、broader（上位）、"
    "narrower（下位）各 1~2 条，用于文献检索。只输出符合 schema 的 JSON。\n"
    "术语：{term}"
)


@dataclass(frozen=True)
class Expansion:
    term: str
    synonyms: list[str] = field(default_factory=list)
    broader: list[str] = field(default_factory=list)
    narrower: list[str] = field(default_factory=list)
    degraded: bool = False

    def all_terms(self) -> list[str]:
        return [self.term, *self.synonyms, *self.broader, *self.narrower]


def expand_term(
    term: str,
    provider: LLMProvider,
    cache: LLMJudgmentCache,
    max_retries: int = 2,
) -> Expansion:
    def compute() -> JSON:
        return provider.generate_structured(
            _PROMPT.format(term=term), EXPANSION_SCHEMA, max_retries
        )

    try:
        payload = cache.cached("judgment", f"expand|{term}", compute)
    except StructuredOutputExhausted:
        return Expansion(term=term, degraded=True)  # 原词降级，不阻塞
    return Expansion(
        term=term,
        synonyms=[str(s) for s in payload["synonyms"]][:2],
        broader=[str(s) for s in payload["broader"]][:2],
        narrower=[str(s) for s in payload["narrower"]][:2],
    )
