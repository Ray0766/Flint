"""BlockContent 判别联合序列化（M3-008；审16 不留裸 dict）。

- 八类 content × 嵌套联合（InlineSpan 四类 / TableCell 三类）kind 分派，
  from_json 恢复精确类型；未知 kind 抛错（绝不静默降级为 dict）。
- dataclasses.asdict 足以出 JSON（全树皆 dataclass + 标量）；恢复侧逐类
  显式构造（不用反射，字段错位在构造点即爆）。
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Any

from flint.domain.models import (
    BlockContent,
    ChartContent,
    CitationListContent,
    CitationMark,
    ClaimSpan,
    DeclarationContent,
    FactCell,
    GapNoticeContent,
    HeadingContent,
    InlineSpan,
    ParagraphContent,
    PriceCell,
    ProfileRef,
    QualityCardContent,
    TableCell,
    TableContent,
    TextCell,
    TextSpan,
)


def block_content_to_json(content: BlockContent) -> dict[str, Any]:
    return asdict(content)


def _span_from(data: dict[str, Any]) -> InlineSpan:
    kind = data.get("kind")
    if kind == "text":
        return TextSpan(kind="text", text=str(data["text"]))
    if kind == "claim":
        return ClaimSpan(
            kind="claim", claim_id=str(data["claim_id"]), text=str(data["text"]),
            disputed_mark=bool(data.get("disputed_mark", False)),
        )
    if kind == "cite":
        return CitationMark(kind="cite", citation_id=str(data["citation_id"]))
    if kind == "profile":
        return ProfileRef(kind="profile", field_path=str(data["field_path"]))
    raise ValueError(f"unknown inline span kind: {kind!r}")


def _cell_from(data: dict[str, Any]) -> TableCell:
    kind = data.get("kind")
    if kind == "text":
        return TextCell(kind="text", text=str(data["text"]))
    if kind == "fact":
        return FactCell(kind="fact", fact_id=str(data["fact_id"]))
    if kind == "price":
        return PriceCell(
            kind="price", price_entry_id=str(data["price_entry_id"]),
            quantity=float(data["quantity"]),
        )
    raise ValueError(f"unknown table cell kind: {kind!r}")


def block_content_from_json(data: dict[str, Any]) -> BlockContent:
    kind = data.get("kind")
    if kind == "heading":
        return HeadingContent(
            kind="heading", level=int(data["level"]), text=str(data["text"])
        )
    if kind == "paragraph":
        return ParagraphContent(
            kind="paragraph", spans=[_span_from(s) for s in data["spans"]]
        )
    if kind == "table":
        return TableContent(
            kind="table",
            header=[str(h) for h in data["header"]],
            rows=[[_cell_from(c) for c in row] for row in data["rows"]],
        )
    if kind == "chart":
        return ChartContent(kind="chart", chart_id=str(data["chart_id"]))
    if kind == "declaration":
        return DeclarationContent(kind="declaration", text=str(data["text"]))
    if kind == "quality_card":
        return QualityCardContent(kind="quality_card", card_ref=str(data["card_ref"]))
    if kind == "citation_list":
        return CitationListContent(
            kind="citation_list",
            citation_ids=[str(c) for c in data["citation_ids"]],
        )
    if kind == "gap_notice":
        return GapNoticeContent(kind="gap_notice", hints_ref=str(data["hints_ref"]))
    raise ValueError(f"unknown block content kind: {kind!r}")
