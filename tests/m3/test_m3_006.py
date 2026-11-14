"""M3-006 acceptance tests: ClaimPromoter promotion invariant.

Acceptance (tasks.json M3-006):
  - only confidence==cited AND alignment==supports promotes; partial NEVER
    (test_partial_never_promoted)
  - source_claim_id / promoted_from / promoted_fact_id three-field backfill
"""
from __future__ import annotations

import pytest

from flint.domain.models import Claim
from flint.ledger.promoter import promote_claims


def claim(cid: str, confidence: str = "cited", alignment: str = "supports") -> Claim:
    return Claim(
        claim_id=cid, deliverable_id="d-1", block_id="b-1",
        text_span=f"结论 {cid}", confidence=confidence,  # type: ignore[arg-type]
        citation_ids=[f"cit-{cid}"], alignment=alignment,  # type: ignore[arg-type]
    )


def test_cited_supports_promotes_with_three_field_backfill() -> None:
    result = promote_claims([claim("c-1")], deliverable_id="d-1", next_version=4)
    assert len(result.facts) == 1
    fact = result.facts[0]
    assert fact.origin == "promoted_claim"
    assert fact.status == "frozen"
    assert fact.source_claim_id == "c-1"
    assert fact.promoted_from == "d-1"
    assert fact.created_in_version == 4
    assert fact.statement == "结论 c-1"
    assert fact.citation_ids == ["cit-c-1"]

    updated = result.claims[0]
    assert updated.promoted_fact_id == fact.fact_id, "third field backfilled"


def test_partial_never_promoted() -> None:
    """E9 点名不变量：partial 绝不提升（S2-4）。"""
    result = promote_claims(
        [claim("c-2", alignment="partial")], deliverable_id="d-1", next_version=1
    )
    assert result.facts == []
    assert result.claims[0].promoted_fact_id is None


@pytest.mark.parametrize(
    ("confidence", "alignment"),
    [
        ("speculative", "supports"),
        ("cited", "pending"),
        ("cited", "unsupported"),
        ("speculative", "partial"),
    ],
)
def test_every_other_combination_never_promotes(
    confidence: str, alignment: str
) -> None:
    result = promote_claims(
        [claim("c-3", confidence=confidence, alignment=alignment)],
        deliverable_id="d-1", next_version=1,
    )
    assert result.facts == []


def test_mixed_batch_promotes_only_eligible() -> None:
    claims = [
        claim("c-a"),
        claim("c-b", alignment="partial"),
        claim("c-c"),
        claim("c-d", confidence="speculative"),
    ]
    result = promote_claims(claims, deliverable_id="d-1", next_version=2)
    assert [f.source_claim_id for f in result.facts] == ["c-a", "c-c"]
    assert result.claims[1].promoted_fact_id is None
    assert result.claims[3].promoted_fact_id is None


def test_fact_ids_deterministic_and_originals_untouched() -> None:
    claims = [claim("c-1")]
    first = promote_claims(claims, deliverable_id="d-1", next_version=1)
    second = promote_claims(claims, deliverable_id="d-1", next_version=1)
    assert [f.fact_id for f in first.facts] == [f.fact_id for f in second.facts]
    assert claims[0].promoted_fact_id is None, "input claims are not mutated"
