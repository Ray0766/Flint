"""M3-040 acceptance tests: decision-boundary declaration block.

Acceptance (tasks.json M3-040):
  - system disclaimer (locked=true, author=system) pinned above the quality
    card
  - not editable/deletable (protection enforcer reused)
"""
from __future__ import annotations

import pytest

from flint.compose.disclaimer import DISCLAIMER_TEXT, build_disclaimer_block, pin_order
from flint.compose.protect import ProtectedBlockViolation, guard_rewrite
from flint.domain.models import Block, DeclarationContent, QualityCardContent


def test_disclaimer_block_shape() -> None:
    block = build_disclaimer_block(
        deliverable_id="d-1", section_id="s-quality",
        retrieved_at="2026-07-26",
    )
    assert isinstance(block, Block)
    assert block.type == "declaration"
    assert isinstance(block.content, DeclarationContent)
    assert "2026-07-26" in block.content.text
    assert "不构成" in block.content.text, "non-advice clause present"
    assert block.locked is True and block.author == "system"


def test_pinned_above_quality_card() -> None:
    disclaimer = build_disclaimer_block("d-1", "s-quality", "2026-07-26")
    quality = Block(
        block_id="b-qc", deliverable_id="d-1", section_id="s-quality", order=5,
        type="quality_card",
        content=QualityCardContent(kind="quality_card", card_ref="qc-1"),
        claim_ids=[], fact_ids=[], author="system", revision=1, locked=True,
    )
    ordered = pin_order([quality, disclaimer])
    assert [b.type for b in ordered[:2]] == ["declaration", "quality_card"], (
        "declaration always immediately above the quality card"
    )


def test_not_editable_or_deletable() -> None:
    disclaimer = build_disclaimer_block("d-1", "s-quality", "2026-07-26")
    altered = Block(
        **{**disclaimer.__dict__,
           "content": DeclarationContent(kind="declaration", text="改掉")},
    )
    with pytest.raises(ProtectedBlockViolation):
        guard_rewrite([disclaimer], [altered])
    with pytest.raises(ProtectedBlockViolation):
        guard_rewrite([disclaimer], [])


def test_template_text_fixed() -> None:
    assert "{检索时点}" in DISCLAIMER_TEXT or "{retrieved_at}" in DISCLAIMER_TEXT
