"""M3-002 acceptance tests: Claim/Fact serialization (discriminated JSONB).

Acceptance (tasks.json M3-002):
  - Claim confidence/alignment and Fact status/origin discriminators round
    trip losslessly (review-16: no naked dicts)
  - promoted_claim must carry source_claim_id (validated)
"""
from __future__ import annotations

import pytest

from flint.domain.models import Claim, Fact
from flint.ledger.entities import (
    claim_from_row,
    claim_to_row,
    fact_from_row,
    fact_to_row,
)


def make_fact(**overrides: object) -> Fact:
    base: dict = {
        "fact_id": "f-1", "statement": "市场规模 12 亿", "value": 12.0,
        "unit": "亿元", "citation_ids": ["cit-1"], "status": "frozen",
        "origin": "promoted_claim", "created_in_version": 3,
        "source_claim_id": "c-9", "promoted_from": "d-1",
    }
    base.update(overrides)
    return Fact(**base)  # type: ignore[arg-type]


def make_claim(**overrides: object) -> Claim:
    base: dict = {
        "claim_id": "c-1", "deliverable_id": "d-1", "block_id": "b-1",
        "text_span": "需求增速 30%", "confidence": "cited",
        "citation_ids": ["cit-2"], "alignment": "supports",
        "promoted_fact_id": None,
    }
    base.update(overrides)
    return Claim(**base)  # type: ignore[arg-type]


def test_fact_round_trip_lossless() -> None:
    for fact in (
        make_fact(),
        make_fact(value="约束条件描述", unit=None, origin="injected",
                  source_claim_id=None, promoted_from=None, status="disputed"),
        make_fact(value=None, status="retired"),
    ):
        assert fact_from_row(fact_to_row(fact)) == fact


def test_claim_round_trip_lossless() -> None:
    for claim in (
        make_claim(),
        make_claim(confidence="speculative", alignment="unsupported",
                   citation_ids=[], promoted_fact_id="f-1"),
        make_claim(alignment="pending"),
    ):
        assert claim_from_row(claim_to_row(claim)) == claim


def test_promoted_claim_requires_source_claim_id() -> None:
    with pytest.raises(ValueError, match="source_claim_id"):
        fact_to_row(make_fact(source_claim_id=None))
    row = fact_to_row(make_fact())
    row["source_claim_id"] = None
    with pytest.raises(ValueError, match="source_claim_id"):
        fact_from_row(row)


def test_bad_discriminators_rejected_on_read() -> None:
    fact_row = fact_to_row(make_fact())
    fact_row["status"] = "melted"
    with pytest.raises(ValueError, match="status"):
        fact_from_row(fact_row)

    claim_row = claim_to_row(make_claim())
    claim_row["alignment"] = "maybe"
    with pytest.raises(ValueError, match="alignment"):
        claim_from_row(claim_row)


def test_row_shape_matches_migration_columns() -> None:
    fact_row = fact_to_row(make_fact())
    assert set(fact_row) == {
        "fact_id", "statement", "value", "unit", "citation_ids", "status",
        "origin", "created_in_version", "source_claim_id", "promoted_from",
    }
    claim_row = claim_to_row(make_claim())
    assert set(claim_row) == {
        "claim_id", "deliverable_id", "block_id", "text_span", "confidence",
        "citation_ids", "alignment", "promoted_fact_id",
    }
