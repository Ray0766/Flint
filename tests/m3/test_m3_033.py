"""M3-033 acceptance tests: markdown renderer.

Acceptance (tasks.json M3-033):
  - block tree -> deterministic markdown; rendering never writes back
    (tree unchanged)
  - citations/charts rendered by discriminated kind
"""
from __future__ import annotations

import copy

from flint.domain.models import (
    Block,
    ChartContent,
    CitationListContent,
    CitationMark,
    ClaimSpan,
    DeclarationContent,
    FactCell,
    GapNoticeContent,
    HeadingContent,
    ParagraphContent,
    PriceCell,
    ProfileRef,
    QualityCardContent,
    TableContent,
    TextCell,
    TextSpan,
)
from flint.render.markdown import render_markdown


def block(block_id: str, order: int, btype: str, content: object) -> Block:
    return Block(
        block_id=block_id, deliverable_id="d-1", section_id="s-1", order=order,
        type=btype, content=content,  # type: ignore[arg-type]
        claim_ids=[], fact_ids=[], author="system", revision=1, locked=False,
    )


TREE = [
    block("b-1", 0, "heading", HeadingContent(kind="heading", level=2, text="市场")),
    block("b-2", 1, "paragraph", ParagraphContent(kind="paragraph", spans=[
        TextSpan(kind="text", text="增速 "),
        ClaimSpan(kind="claim", claim_id="c-1", text="30%", disputed_mark=True),
        CitationMark(kind="cite", citation_id="cit-1"),
        ProfileRef(kind="profile", field_path="identity.org"),
    ])),
    block("b-3", 2, "table", TableContent(kind="table", header=["项", "值"], rows=[
        [TextCell(kind="text", text="规模"), FactCell(kind="fact", fact_id="f-1")],
        [TextCell(kind="text", text="服务器"),
         PriceCell(kind="price", price_entry_id="pe-1", quantity=2.0)],
    ])),
    block("b-4", 3, "chart", ChartContent(kind="chart", chart_id="ch-1")),
    block("b-5", 4, "declaration",
          DeclarationContent(kind="declaration", text="边界声明")),
    block("b-6", 5, "quality_card",
          QualityCardContent(kind="quality_card", card_ref="qc-1")),
    block("b-7", 6, "citation_list",
          CitationListContent(kind="citation_list", citation_ids=["cit-1", "cit-2"])),
    block("b-8", 7, "gap_notice",
          GapNoticeContent(kind="gap_notice", hints_ref="ss-1")),
]


def test_deterministic_and_all_kinds_rendered() -> None:
    first = render_markdown(TREE)
    second = render_markdown(TREE)
    assert first == second, "byte-stable"
    assert "## 市场" in first
    assert "30%" in first and "⚠" in first, "disputed claim carries the mark"
    assert "[cit-1]" in first
    assert "{{profile:identity.org}}" in first
    assert "| 项 | 值 |" in first
    assert "{{fact:f-1}}" in first and "{{price:pe-1×2.0}}" in first
    assert "{{chart:ch-1}}" in first
    assert "> 边界声明" in first
    assert "{{quality_card:qc-1}}" in first
    assert "- [cit-1]" in first and "- [cit-2]" in first
    assert "{{gaps:ss-1}}" in first


def test_render_never_writes_back() -> None:
    snapshot = copy.deepcopy(TREE)
    render_markdown(TREE)
    assert TREE == snapshot, "tree is the single truth; render is read-only"


def test_section_order_respected() -> None:
    shuffled = [TREE[3], TREE[0], TREE[1], TREE[2]]
    text = render_markdown(shuffled)
    assert text.index("## 市场") < text.index("{{chart:ch-1}}"), (
        "render sorts by (section, order), not input order"
    )
