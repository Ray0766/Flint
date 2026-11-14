"""M3-007 acceptance tests: disputed exclusion surface.

Acceptance (tasks.json M3-007):
  - status==disputed facts excluded from the generation pool (S2-4)
  - blocks referencing them marked advisory, never blocking
"""
from __future__ import annotations

from flint.domain.models import Block, Fact, HeadingContent
from flint.ledger.disputed import mark_advisory_for_disputed, usable_fact_pool


def fact(fact_id: str, status: str) -> Fact:
    return Fact(
        fact_id=fact_id, statement=f"s-{fact_id}", value=None, unit=None,
        citation_ids=[], status=status,  # type: ignore[arg-type]
        origin="injected", created_in_version=1,
    )


def block(block_id: str, fact_ids: list[str]) -> Block:
    return Block(
        block_id=block_id, deliverable_id="d-1", section_id="s-1", order=0,
        type="heading", content=HeadingContent(kind="heading", level=1, text="t"),
        claim_ids=[], fact_ids=fact_ids, author="system", revision=1, locked=False,
    )


def test_pool_keeps_frozen_only() -> None:
    facts = [fact("f-1", "frozen"), fact("f-2", "disputed"), fact("f-3", "retired")]
    pool = usable_fact_pool(facts)
    assert [f.fact_id for f in pool] == ["f-1"], "disputed and retired both excluded"


def test_referencing_blocks_marked_advisory() -> None:
    blocks = [
        block("b-1", ["f-1", "f-2"]),
        block("b-2", ["f-1"]),
    ]
    marked = mark_advisory_for_disputed(blocks, disputed_ids={"f-2"})
    hit = marked[0]
    assert hit.needs_review is True
    assert hit.review_reason == "fact_disputed"
    assert hit.review_severity == "advisory", "disputed never blocks (audit 11)"
    untouched = marked[1]
    assert untouched.needs_review is False, "unrelated blocks zero pollution"


def test_marking_returns_copies() -> None:
    original = block("b-1", ["f-2"])
    marked = mark_advisory_for_disputed([original], disputed_ids={"f-2"})
    assert original.needs_review is False, "input blocks not mutated"
    assert marked[0] is not original


def test_already_reviewed_block_keeps_stronger_severity() -> None:
    stronger = block("b-1", ["f-2"])
    stronger.needs_review = True
    stronger.review_reason = "fact_removed"
    stronger.review_severity = "blocking"
    marked = mark_advisory_for_disputed([stronger], disputed_ids={"f-2"})
    assert marked[0].review_severity == "blocking", "advisory never downgrades blocking"
    assert marked[0].review_reason == "fact_removed"
