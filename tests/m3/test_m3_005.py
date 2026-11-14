"""M3-005 acceptance tests: FactDiff + needs_review mapping.

Acceptance (tasks.json M3-005):
  - changed->advisory / removed->blocking / disputed->advisory, each mapped
    (audit 11)
  - only blocks referencing changed facts get needs_review (zero pollution)
"""
from __future__ import annotations

from flint.domain.models import Block, Fact, FactDiff, HeadingContent
from flint.ledger.diff import apply_review_marks, compute_diff


def fact(fact_id: str, statement: str = "s", status: str = "frozen",
         value: float | None = None) -> Fact:
    return Fact(
        fact_id=fact_id, statement=statement, value=value, unit=None,
        citation_ids=[], status=status,  # type: ignore[arg-type]
        origin="injected", created_in_version=1,
    )


def block(block_id: str, fact_ids: list[str]) -> Block:
    return Block(
        block_id=block_id, deliverable_id="d-1", section_id="s-1", order=0,
        type="heading", content=HeadingContent(kind="heading", level=1, text="t"),
        claim_ids=[], fact_ids=fact_ids, author="system", revision=1, locked=False,
    )


def test_compute_diff_three_categories() -> None:
    old = [fact("f-1"), fact("f-2"), fact("f-3"), fact("f-4"), fact("f-5")]
    new = [
        fact("f-1", statement="改了"),          # changed
        fact("f-2", status="retired"),          # removed (retired)
        fact("f-3", status="disputed"),         # disputed (newly)
        fact("f-4"),                            # unchanged
        # f-5 absent -> removed
    ]
    diff = compute_diff(old, new)
    assert isinstance(diff, FactDiff)
    assert diff.changed == ["f-1"]
    assert sorted(diff.removed) == ["f-2", "f-5"]
    assert diff.disputed == ["f-3"]


def test_mapping_and_zero_pollution() -> None:
    diff = FactDiff(changed=["f-c"], removed=["f-r"], disputed=["f-d"])
    blocks = [
        block("b-changed", ["f-c"]),
        block("b-removed", ["f-r"]),
        block("b-disputed", ["f-d"]),
        block("b-clean", ["f-other"]),
    ]
    marked = {b.block_id: b for b in apply_review_marks(blocks, diff)}
    assert marked["b-changed"].review_reason == "fact_changed"
    assert marked["b-changed"].review_severity == "advisory"
    assert marked["b-removed"].review_reason == "fact_removed"
    assert marked["b-removed"].review_severity == "blocking"
    assert marked["b-disputed"].review_reason == "fact_disputed"
    assert marked["b-disputed"].review_severity == "advisory"
    assert marked["b-clean"].needs_review is False, "zero pollution"


def test_blocking_takes_precedence_when_block_hits_multiple() -> None:
    diff = FactDiff(changed=["f-c"], removed=["f-r"], disputed=[])
    blocks = [block("b-both", ["f-c", "f-r"])]
    marked = apply_review_marks(blocks, diff)
    assert marked[0].review_reason == "fact_removed"
    assert marked[0].review_severity == "blocking", "strongest mark wins"


def test_inputs_not_mutated() -> None:
    diff = FactDiff(changed=["f-c"], removed=[], disputed=[])
    original = block("b-1", ["f-c"])
    apply_review_marks([original], diff)
    assert original.needs_review is False
