"""Claim/Fact 序列化装配（M3-002；审16 判别不留裸 dict）。

- to_row / from_row 与迁移 0008 列面一一对应（value 走 JSON 标量，
  str|float|None 三态无损）；
- 读写两侧都执行判别校验与提升不变量的字段面（promoted_claim 必带
  source_claim_id）——存储 CHECK 是兜底，这里是第一道门。
"""
from __future__ import annotations

from typing import Any, Final, Literal, cast

from flint.domain.models import Alignment, Claim, Fact, FactStatus

# 域以 contracts/models.py#Fact.origin / #Claim.confidence 为准；冻结 Literal
# 变更时 mypy 在构造点报错（S3：strict 是冻结边界执行器；先例 Strength 别名）
FactOrigin = Literal["promoted_claim", "injected"]
Confidence = Literal["cited", "speculative"]

_FACT_STATUSES: Final[frozenset[str]] = frozenset({"frozen", "disputed", "retired"})
_FACT_ORIGINS: Final[frozenset[str]] = frozenset({"promoted_claim", "injected"})
_CONFIDENCES: Final[frozenset[str]] = frozenset({"cited", "speculative"})
_ALIGNMENTS: Final[frozenset[str]] = frozenset(
    {"pending", "supports", "partial", "unsupported"}
)


def _require_promotion_source(origin: str, source_claim_id: str | None) -> None:
    if origin == "promoted_claim" and not source_claim_id:
        raise ValueError(
            "promoted_claim fact requires source_claim_id (promotion invariant)"
        )


def fact_to_row(fact: Fact) -> dict[str, Any]:
    _require_promotion_source(fact.origin, fact.source_claim_id)
    return {
        "fact_id": fact.fact_id,
        "statement": fact.statement,
        "value": fact.value,
        "unit": fact.unit,
        "citation_ids": list(fact.citation_ids),
        "status": fact.status,
        "origin": fact.origin,
        "created_in_version": fact.created_in_version,
        "source_claim_id": fact.source_claim_id,
        "promoted_from": fact.promoted_from,
    }


def fact_from_row(row: dict[str, Any]) -> Fact:
    status = str(row["status"])
    origin = str(row["origin"])
    if status not in _FACT_STATUSES:
        raise ValueError(f"unknown fact status: {status!r}")
    if origin not in _FACT_ORIGINS:
        raise ValueError(f"unknown fact origin: {origin!r}")
    source_claim_id = cast("str | None", row["source_claim_id"])
    _require_promotion_source(origin, source_claim_id)
    return Fact(
        fact_id=str(row["fact_id"]),
        statement=str(row["statement"]),
        value=cast("str | float | None", row["value"]),
        unit=cast("str | None", row["unit"]),
        citation_ids=[str(c) for c in row["citation_ids"]],
        status=cast(FactStatus, status),
        origin=cast(FactOrigin, origin),
        created_in_version=int(row["created_in_version"]),
        source_claim_id=source_claim_id,
        promoted_from=cast("str | None", row["promoted_from"]),
    )


def claim_to_row(claim: Claim) -> dict[str, Any]:
    return {
        "claim_id": claim.claim_id,
        "deliverable_id": claim.deliverable_id,
        "block_id": claim.block_id,
        "text_span": claim.text_span,
        "confidence": claim.confidence,
        "citation_ids": list(claim.citation_ids),
        "alignment": claim.alignment,
        "promoted_fact_id": claim.promoted_fact_id,
    }


def claim_from_row(row: dict[str, Any]) -> Claim:
    confidence = str(row["confidence"])
    alignment = str(row["alignment"])
    if confidence not in _CONFIDENCES:
        raise ValueError(f"unknown claim confidence: {confidence!r}")
    if alignment not in _ALIGNMENTS:
        raise ValueError(f"unknown claim alignment: {alignment!r}")
    return Claim(
        claim_id=str(row["claim_id"]),
        deliverable_id=str(row["deliverable_id"]),
        block_id=str(row["block_id"]),
        text_span=str(row["text_span"]),
        confidence=cast(Confidence, confidence),
        citation_ids=[str(c) for c in row["citation_ids"]],
        alignment=cast(Alignment, alignment),
        promoted_fact_id=cast("str | None", row["promoted_fact_id"]),
    )
