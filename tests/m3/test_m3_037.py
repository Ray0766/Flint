"""M3-037 acceptance tests: export gatekeeper (audit 11).

Acceptance (tasks.json M3-037):
  - blocking_reviews_open > 0 -> export refused (EXPORT_BLOCKED error body)
  - advisory does not block but the quality card lists "N pending"
"""
from __future__ import annotations

import pytest

from flint.domain.models import Block, HeadingContent
from flint.render.gatekeeper import (
    ExportBlocked,
    check_export,
    guarded_render,
    pending_note,
)
from flint.render.markdown import render_markdown


def block(block_id: str, *, reason: str | None = None,
          severity: str | None = None) -> Block:
    return Block(
        block_id=block_id, deliverable_id="d-1", section_id="s-1", order=0,
        type="heading", content=HeadingContent(kind="heading", level=1, text="t"),
        claim_ids=[], fact_ids=[], author="system", revision=1, locked=False,
        needs_review=reason is not None,
        review_reason=reason,  # type: ignore[arg-type]
        review_severity=severity,  # type: ignore[arg-type]
    )


def test_blocking_refuses_export() -> None:
    blocks = [
        block("b-1"),
        block("b-2", reason="fact_removed", severity="blocking"),
    ]
    check = check_export(blocks)
    assert check.blocking_open == 1 and check.exportable is False
    with pytest.raises(ExportBlocked, match="EXPORT_BLOCKED") as err:
        guarded_render(blocks, render_markdown)
    assert err.value.blocking_block_ids == ["b-2"]


def test_advisory_passes_with_pending_note() -> None:
    blocks = [
        block("b-1"),
        block("b-2", reason="fact_changed", severity="advisory"),
        block("b-3", reason="fact_disputed", severity="advisory"),
    ]
    check = check_export(blocks)
    assert check.exportable is True and check.advisory_open == 2
    rendered = guarded_render(blocks, render_markdown)
    assert isinstance(rendered, str)
    assert pending_note(blocks) == "2 项待处理（advisory）"


def test_clean_tree_no_note() -> None:
    blocks = [block("b-1")]
    assert check_export(blocks).exportable is True
    assert pending_note(blocks) is None
