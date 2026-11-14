"""draft claim 抽取（M3-021，D9 章节类 / v0.3.2 Claim 作用域）。

- 章节草稿 → 结构化 claim 全量（text_span + citation_ids 绑定，stage2
  对齐输入面）；alignment 初值 "pending"（对齐归 M3-024）。
- confidence 初值：有引用 → "cited"，无引用 → "speculative"（v0.2 §4.4）。
- D9 章节类降级：结构化耗尽 → degraded + GapHint（该章标缺口继续），
  NEVER 阻塞组稿。
- claim_id 确定性（sha256(deliverable|block|text_span)）。
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Final

from flint.domain.models import JSON, Claim, GapHint
from flint.domain.protocols import LLMProvider
from flint.llm.structured import StructuredOutputExhausted

CLAIM_SCHEMA: Final[JSON] = {
    "type": "object",
    "properties": {
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text_span": {"type": "string", "minLength": 1},
                    "citation_ids": {
                        "type": "array", "items": {"type": "string"},
                    },
                },
                "required": ["text_span", "citation_ids"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["claims"],
    "additionalProperties": False,
}

_PROMPT = (
    "从以下章节草稿中抽取全部结论句（claim）。每条给出 text_span（原文句）与"
    " citation_ids（句内引用标记的 doc/citation id，无则空列表）。"
    "只输出符合 schema 的 JSON。\n草稿：\n{text}"
)


@dataclass
class ClaimExtraction:
    claims: list[Claim] = field(default_factory=list)
    degraded: bool = False
    gap: GapHint | None = None


def claim_id_for(deliverable_id: str, block_id: str, text_span: str) -> str:
    digest = hashlib.sha256(
        f"{deliverable_id}|{block_id}|{text_span}".encode()
    ).hexdigest()
    return f"claim-{digest[:12]}"


def extract_draft_claims(
    provider: LLMProvider,
    deliverable_id: str,
    block_id: str,
    section_text: str,
    max_retries: int = 2,
) -> ClaimExtraction:
    try:
        payload = provider.generate_structured(
            _PROMPT.format(text=section_text), CLAIM_SCHEMA, max_retries
        )
    except (StructuredOutputExhausted, RuntimeError):
        return ClaimExtraction(
            degraded=True,
            gap=GapHint(
                missing_what="本章 claim 抽取未完成（结构化输出耗尽）",
                cause="missing_data",
                suggested_sources=["重试本章生成", "人工标注结论句"],
                action="search",
            ),
        )
    claims: list[Claim] = []
    for item in payload["claims"]:
        text_span = str(item["text_span"])
        citation_ids = [str(c) for c in item["citation_ids"]]
        claims.append(
            Claim(
                claim_id=claim_id_for(deliverable_id, block_id, text_span),
                deliverable_id=deliverable_id,
                block_id=block_id,
                text_span=text_span,
                confidence="cited" if citation_ids else "speculative",
                citation_ids=citation_ids,
                alignment="pending",
            )
        )
    return ClaimExtraction(claims=claims)
