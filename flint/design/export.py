"""DESIGN-15：设计台三种导出的**接线**（§6-H3，零新导出器）。

## 为什么一行渲染逻辑都不写

导出门禁（`flint/render/gatekeeper.py#guarded_render`）是「blocking 未处理就不许导出」
这条铁律的唯一落点。设计台若自建一条导出路径，那条路上**没有门禁**——
一份还挂着 blocking 复核的产物就能直接导出去交给客户，而界面上看不出任何异常。

同理，新写一个 HTML/PDF 渲染器意味着同一份内容有两种排版：用户在预览里看到的、
与导出拿到的会在某处不一样，而没人说得清哪一份才算数。

所以本模块只做三件事：**校验产物非空 → 过既有门禁 → 交既有管线**。
它自己不 import zipfile、不 import weasyprint、不定义任何 `render_*`。

## 设计台产物逐字进入导出

导出不是二次渲染（承 DESIGN-02 零构建、DESIGN-03 的三接口不改字节）：
`html` 参数原样交出去，中间不清洗、不格式化。
"""
from __future__ import annotations

from typing import Any

from flint.render.gatekeeper import guarded_render
from flint.spec.pack_zip import build_zip


def _require_design(html: str) -> None:
    if html.strip() == "":
        # 一个空文件交到客户手上，比报一次错糟得多
        raise ValueError("design html NEVER 为空：空产物不导出")


def export_design_html(html: str, *, blocks: list[Any]) -> str:
    """单文件 HTML 导出：过既有门禁，产物字节逐字不动。"""
    _require_design(html)
    return guarded_render(blocks, lambda _blocks: html)


def export_design_pdf(html: str, *, blocks: list[Any]) -> bytes:
    """PDF 导出：同一道门禁；渲染仍走既有 `flint.render.pdf`（本模块不碰 PDF 库）。"""
    _require_design(html)

    def render(_blocks: list[Any]) -> bytes:
        from flint.render.pdf import render_pdf  # 既有渲染器，NEVER 另写一个

        return render_pdf(_blocks)

    return guarded_render(blocks, render)


def export_design_pack(html: str, *, blocks: list[Any], bundle: Any) -> bytes:
    """vibe_pack zip 导出：先过 Block 门禁，再交既有 `build_zip`（它自带包内门）。"""
    _require_design(html)
    return guarded_render(blocks, lambda _blocks: build_zip(bundle))
