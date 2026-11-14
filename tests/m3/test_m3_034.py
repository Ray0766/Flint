"""M3-034 acceptance tests: html renderer.

Acceptance (tasks.json M3-034):
  - markdown-it pipeline yields html; quality card and declaration blocks
    positioned correctly
  - re-render of the same tree is byte-stable
"""
from __future__ import annotations

from flint.compose.disclaimer import build_disclaimer_block
from flint.domain.models import (
    Block,
    HeadingContent,
    QualityCardContent,
)
from flint.render.html import render_html


def block(block_id: str, order: int, btype: str, content: object,
          section: str = "s-1") -> Block:
    return Block(
        block_id=block_id, deliverable_id="d-1", section_id=section, order=order,
        type=btype, content=content,  # type: ignore[arg-type]
        claim_ids=[], fact_ids=[], author="system", revision=1, locked=False,
    )


TREE = [
    block("b-h", 0, "heading", HeadingContent(kind="heading", level=2, text="市场")),
    build_disclaimer_block("d-1", "s-0", "2026-07-26"),
    block("b-qc", 1, "quality_card",
          QualityCardContent(kind="quality_card", card_ref="qc-1"), section="s-0"),
]


def test_html_pipeline_and_positioning() -> None:
    html = render_html(TREE)
    assert "<h2>市场</h2>" in html
    assert "blockquote" in html, "declaration renders as quote"
    declaration_at = html.index("本报告基于截至")
    quality_at = html.index("quality_card:qc-1")
    heading_at = html.index("<h2>市场</h2>")
    assert declaration_at < quality_at < heading_at, (
        "declaration pinned immediately above the quality card, both first"
    )


def test_byte_stable() -> None:
    assert render_html(TREE) == render_html(TREE)
