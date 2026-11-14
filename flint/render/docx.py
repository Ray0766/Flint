"""docx 渲染（M3-036，python-docx；D3 渲染目标不回写）。

块级映射：heading → Heading N 样式；table → docx 表格（单元文本走
markdown 线同一占位口径）；declaration → Quote 样式段；其余 kind
（paragraph/chart/quality_card/citation_list/gap_notice）以 markdown 单块
文本入正文段。
"""
from __future__ import annotations

import io

from docx import Document

from flint.compose.disclaimer import pin_order
from flint.domain.models import Block
from flint.render.markdown import cell_text, render_markdown_ordered


def render_docx(blocks: list[Block]) -> bytes:
    document = Document()
    for block in pin_order(blocks):
        content = block.content
        if content.kind == "heading":
            document.add_heading(content.text, level=content.level)
        elif content.kind == "table":
            table = document.add_table(
                rows=len(content.rows) + 1, cols=len(content.header)
            )
            for column, title in enumerate(content.header):
                table.rows[0].cells[column].text = title
            for row_index, row in enumerate(content.rows, start=1):
                for column, cell in enumerate(row):
                    table.rows[row_index].cells[column].text = cell_text(cell)
        elif content.kind == "declaration":
            paragraph = document.add_paragraph(content.text)
            paragraph.style = document.styles["Quote"]
        else:
            document.add_paragraph(render_markdown_ordered([block]).strip())
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()
