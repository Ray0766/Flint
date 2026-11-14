"""markdown 渲染（M3-033，D3：block 树唯一真相，渲染不回写）。

- 树序 (section_id, order) 排序后逐块渲染；八类 content 判别分派，未知
  kind 由类型系统封死（BlockContent 联合穷尽）。
- 引用/图表/质量卡/缺口以占位语法（{{kind:ref}}）渲染——解引用（fact
  文本、图表绘制）归各消费端；disputed claim 带 ⚠ 标记（审10）。
- 纯函数：输入树不被触碰（副本都不做，只读遍历）。
"""
from __future__ import annotations

from flint.domain.models import (
    Block,
    BlockContent,
    InlineSpan,
    TableCell,
)


def _span_text(span: InlineSpan) -> str:
    if span.kind == "text":
        return span.text
    if span.kind == "claim":
        mark = "⚠" if span.disputed_mark else ""
        return f"{span.text}{mark}"
    if span.kind == "cite":
        return f"[{span.citation_id}]"
    return f"{{{{profile:{span.field_path}}}}}"


def cell_text(cell: TableCell) -> str:
    """表格单元文本化（docx 线复用同一占位口径）。"""
    return _cell_text(cell)


def _cell_text(cell: TableCell) -> str:
    if cell.kind == "text":
        return cell.text
    if cell.kind == "fact":
        return f"{{{{fact:{cell.fact_id}}}}}"
    return f"{{{{price:{cell.price_entry_id}×{cell.quantity}}}}}"


def _content_markdown(content: BlockContent) -> str:
    if content.kind == "heading":
        return f"{'#' * content.level} {content.text}"
    if content.kind == "paragraph":
        return "".join(_span_text(s) for s in content.spans)
    if content.kind == "table":
        header = "| " + " | ".join(content.header) + " |"
        divider = "|" + "---|" * len(content.header)
        rows = [
            "| " + " | ".join(_cell_text(c) for c in row) + " |"
            for row in content.rows
        ]
        return "\n".join([header, divider, *rows])
    if content.kind == "chart":
        return f"{{{{chart:{content.chart_id}}}}}"
    if content.kind == "declaration":
        return f"> {content.text}"
    if content.kind == "quality_card":
        return f"{{{{quality_card:{content.card_ref}}}}}"
    if content.kind == "citation_list":
        return "\n".join(f"- [{cid}]" for cid in content.citation_ids)
    return f"{{{{gaps:{content.hints_ref}}}}}"


def render_markdown_ordered(ordered: list[Block]) -> str:
    """按给定序渲染（排序策略由调用方决定——html 线用 pin_order）。"""
    return "\n\n".join(_content_markdown(b.content) for b in ordered) + "\n"


def render_markdown(blocks: list[Block]) -> str:
    ordered = sorted(blocks, key=lambda b: (b.section_id, b.order))
    return render_markdown_ordered(ordered)
