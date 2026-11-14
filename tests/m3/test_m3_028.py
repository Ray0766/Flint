"""M3-028 acceptance tests: protection enforcer (S2-5).

Acceptance (tasks.json M3-028):
  - locked / author==user / user_modified, individually and combined:
    regenerate/shrink/expand ALL never rewrite
    (test_protected_block_never_rewritten)
  - rejected rewrite attempts leave no half-write (original tree untouched)
"""
from __future__ import annotations

import pytest

from flint.compose.expand import expand_section
from flint.compose.protect import ProtectedBlockViolation, guard_rewrite
from flint.compose.shrink import shrink_section
from flint.domain.models import Block, ParagraphContent, TextSpan


def para(block_id: str, text: str, order: int = 0, *, locked: bool = False,
         author: str = "system", user_modified: bool = False) -> Block:
    return Block(
        block_id=block_id, deliverable_id="d-1", section_id="s-1", order=order,
        type="paragraph",
        content=ParagraphContent(kind="paragraph",
                                 spans=[TextSpan(kind="text", text=text)]),
        claim_ids=[], fact_ids=[], author=author,  # type: ignore[arg-type]
        revision=1, locked=locked, user_modified=user_modified,
    )


PROTECTED_VARIANTS = [
    {"locked": True},
    {"author": "user"},
    {"user_modified": True},
    {"locked": True, "author": "user", "user_modified": True},
]


@pytest.mark.parametrize("flags", PROTECTED_VARIANTS)
def test_protected_block_never_rewritten(flags: dict) -> None:
    """E9 点名不变量：三保护条件逐一 + 组合，改写一律被拒。"""
    original = [para("b-1", "原文", 0, **flags), para("b-2", "普通", 1)]

    altered = [para("b-1", "被改写", 0, **flags), para("b-2", "普通", 1)]
    with pytest.raises(ProtectedBlockViolation, match="b-1"):
        guard_rewrite(original, altered)

    dropped = [para("b-2", "普通", 1)]
    with pytest.raises(ProtectedBlockViolation, match="b-1"):
        guard_rewrite(original, dropped)


def test_unprotected_rewrite_passes_and_order_move_allowed() -> None:
    original = [para("b-1", "原文", 0, locked=True), para("b-2", "普通", 1)]
    proposal = [para("b-2", "改写普通", 0), para("b-1", "原文", 1, locked=True)]
    merged = guard_rewrite(original, proposal)
    assert [b.block_id for b in merged] == ["b-2", "b-1"], (
        "order moves are structural, not rewrites"
    )


def test_rejection_leaves_no_half_write() -> None:
    original = [para("b-1", "原文", 0, locked=True), para("b-2", "普通", 1)]
    snapshot = [para("b-1", "原文", 0, locked=True), para("b-2", "普通", 1)]
    with pytest.raises(ProtectedBlockViolation):
        guard_rewrite(original, [para("b-1", "改", 0, locked=True)])
    assert original == snapshot, "guard never mutates the current tree"


def test_shrink_path_honors_protection() -> None:
    blocks = [para("b-1", "user 写的", 0, author="user"),
              para("b-2", "冗余", 1)]
    result = shrink_section(blocks, lambda unprotected: [])
    assert [b.block_id for b in result] == ["b-1"], "shrink cannot drop protected"
    assert result[0].content == blocks[0].content


def test_expand_path_is_additive_never_touches_existing() -> None:
    from datetime import UTC, datetime

    from flint.domain.models import Fact, FactsLedger, SectionSpec

    led = FactsLedger(
        ledger_id="led-1", project_id="p-1", version=1, parent_version=None,
        derivation_reason="initial",
        facts=[Fact(fact_id="f-new", statement="s", value=None, unit=None,
                    citation_ids=[], status="frozen", origin="injected",
                    created_in_version=1)],
        created_from=[], created_at=datetime(2026, 7, 29, tzinfo=UTC),
        actor="u-1",
    )
    spec = SectionSpec(section_id="s-1", inputs=[], check_questions=["q"],
                       charts=[])
    existing = [para("b-1", "用户改过", 0, user_modified=True)]
    outcome = expand_section(
        spec, led, cited_fact_ids=set(),
        generator=lambda pool: [para("b-new", "新增")],
        missing_scopes=[],
    )
    merged = guard_rewrite(existing, existing + list(outcome))  # type: ignore[arg-type]
    assert [b.block_id for b in merged] == ["b-1", "b-new"]
    assert merged[0] == existing[0], "expand adds, never rewrites"
