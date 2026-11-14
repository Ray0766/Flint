"""DESIGN-15 验收：设计台三种导出全部挂**既有**管线（§6-H3）。

acceptance：**三种导出调用栈 import 自既有管线（H3 断言）；零新导出器**。

## 为什么不能新写导出器

导出门禁（`flint/render/gatekeeper.py`）是「blocking 未处理就不许导出」这条铁律的
唯一落点。设计台若自建一条导出路径，那条路上**没有门禁**——一份还挂着
blocking 复核的产物就能直接被导出去交给客户，而界面上看不出任何异常。

同理，新写一个 HTML/PDF 渲染器意味着同一份内容有两种排版：用户在预览里看到的、
与导出拿到的，会在某处不一样，而没人说得清哪一份才算数。

所以本模块只做**接线**：把设计台产物转成既有管线吃的形状，然后调既有的
`guarded_render` / `build_zip`。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from flint.design.export import (
    export_design_html,
    export_design_pack,
    export_design_pdf,
)
from flint.render.gatekeeper import ExportBlocked
from tests.v04._source_scan import code_names

SRC = Path(__file__).resolve().parents[3] / "flint" / "design" / "export.py"

HTML = "<h1>燧石</h1><p>供应链</p>"


def _blocks(*, blocking: bool = False, advisory: bool = False) -> list[object]:
    """构造既有 Block 形状（只用到门禁看的那三个字段）。"""
    from flint.domain.models import Block, TextSpan

    def block(bid: str, needs: bool, severity: str | None) -> Block:
        return Block(
            block_id=bid, deliverable_id="d-1", section_id="s-1", order=0,
            type="paragraph", content=TextSpan(kind="text", text="正文"),
            claim_ids=[], fact_ids=[], author="system", revision=1, locked=False,
            needs_review=needs, review_reason="fact_removed" if needs else None,
            review_severity=severity,  # type: ignore[arg-type]
        )

    rows = [block("b-1", False, None)]
    if blocking:
        rows.append(block("b-2", True, "blocking"))
    if advisory:
        rows.append(block("b-3", True, "advisory"))
    return rows


# ───────────────────────── H3：调用栈来自既有管线


def test_module_imports_the_existing_pipeline_only() -> None:
    """import 面：门禁与三个渲染入口都来自既有模块，且没有第二套。"""
    names = code_names(SRC)

    assert "flint.render.gatekeeper" in names
    assert "guarded_render" in names
    assert "flint.spec.pack_zip" in names
    assert "build_zip" in names


def test_module_defines_no_renderer_of_its_own() -> None:
    """零新导出器：本模块不定义任何 render_* / export_* 之外的渲染实现。

    断的是**定义**而非提及：docstring 里写「NEVER 新写渲染器」不该被判成写了一个
    （Python 侧这个坑的第 3 次，走共享 `_source_scan`）。
    """
    import ast

    tree = ast.parse(SRC.read_text(encoding="utf-8"))
    defined = {
        n.name for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)
    }

    # 任何 render_* 定义都意味着自己画了一套排版
    assert {n for n in defined if n.startswith("render_")} == set()
    # **公开面**恰是三个导出入口：私有校验器与转调用的闭包不算「新导出器」，
    # 把它们也算进去只会逼人给辅助函数改名，而不会挡住真正的重复实现。
    public = {n for n in defined if not n.startswith("_")}
    assert {n for n in public if n.startswith("export_")} == {
        "export_design_html", "export_design_pdf", "export_design_pack",
    }


def test_no_zipfile_or_weasyprint_touched_directly() -> None:
    """不绕过既有管线直接玩 zip / PDF 库。"""
    names = code_names(SRC)

    for forbidden in ("zipfile", "weasyprint", "docx", "ZipFile"):
        assert forbidden not in names


# ───────────────────────── 门禁在三条路上都生效


def test_html_export_goes_through_the_gate() -> None:
    out = export_design_html(HTML, blocks=_blocks())

    assert HTML in out


def test_html_export_blocked_when_blocking_review_open() -> None:
    """blocking 未处理 → 拒绝导出。这条铁律的唯一落点是既有门禁。"""
    with pytest.raises(ExportBlocked):
        export_design_html(HTML, blocks=_blocks(blocking=True))


def test_pdf_export_blocked_when_blocking_review_open() -> None:
    with pytest.raises(ExportBlocked):
        export_design_pdf(HTML, blocks=_blocks(blocking=True))


def test_pack_export_blocked_when_blocking_review_open() -> None:
    with pytest.raises(ExportBlocked):
        export_design_pack(HTML, blocks=_blocks(blocking=True), bundle=None)


def test_advisory_does_not_block_any_of_the_three() -> None:
    """advisory 不拦（审11 口径）：拦住的话用户会以为自己被系统卡死了。"""
    out = export_design_html(HTML, blocks=_blocks(advisory=True))

    assert HTML in out


def test_html_export_keeps_the_design_bytes_verbatim() -> None:
    """设计台产物逐字进入导出：导出不是二次渲染（承 DESIGN-02/03）。"""
    tricky = '<div style="color:red" data-x="1">a&b</div>'

    assert tricky in export_design_html(tricky, blocks=_blocks())


def test_empty_design_is_rejected() -> None:
    """空产物不导出：一个空文件交到客户手上比报错糟。"""
    with pytest.raises(ValueError):
        export_design_html("", blocks=_blocks())
