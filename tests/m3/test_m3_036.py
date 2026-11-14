"""M3-036 acceptance tests: docx renderer.

Acceptance (tasks.json M3-036):
  - block-level structure maps completely (heading/paragraph/table)
  - re-render of the same tree is structurally stable
"""
from __future__ import annotations

import io

from docx import Document

from flint.domain.models import (
    Block,
    DeclarationContent,
    FactCell,
    HeadingContent,
    ParagraphContent,
    TableContent,
    TextCell,
    TextSpan,
)
from flint.render.docx import render_docx


def block(block_id: str, order: int, btype: str, content: object) -> Block:
    return Block(
        block_id=block_id, deliverable_id="d-1", section_id="s-1", order=order,
        type=btype, content=content,  # type: ignore[arg-type]
        claim_ids=[], fact_ids=[], author="system", revision=1, locked=False,
    )


TREE = [
    block("b-1", 0, "heading", HeadingContent(kind="heading", level=2, text="市场")),
    block("b-2", 1, "paragraph", ParagraphContent(
        kind="paragraph", spans=[TextSpan(kind="text", text="需求增速 30%")],
    )),
    block("b-3", 2, "table", TableContent(kind="table", header=["项", "值"], rows=[
        [TextCell(kind="text", text="规模"), FactCell(kind="fact", fact_id="f-1")],
    ])),
    block("b-4", 3, "declaration",
          DeclarationContent(kind="declaration", text="边界声明")),
]


def _structure(payload: bytes) -> list[tuple[str, str]]:
    document = Document(io.BytesIO(payload))
    items: list[tuple[str, str]] = [
        (p.style.name or "", p.text) for p in document.paragraphs if p.text
    ]
    for table in document.tables:
        cells = tuple(c.text for row in table.rows for c in row.cells)
        items.append(("Table", "|".join(cells)))
    return items


def test_block_structure_maps_completely() -> None:
    payload = render_docx(TREE)
    assert payload[:2] == b"PK", "a real docx (zip container)"
    structure = _structure(payload)
    styles = [s for s, _t in structure]
    texts = [t for _s, t in structure]
    assert any("Heading 2" in s for s in styles)
    assert "需求增速 30%" in texts
    assert any("边界声明" in t for t in texts)
    table_rows = [t for s, t in structure if s == "Table"]
    assert table_rows == ["项|值|规模|{{fact:f-1}}"]


def test_structurally_stable_re_render() -> None:
    assert _structure(render_docx(TREE)) == _structure(render_docx(TREE))
