"""pdf 渲染（M3-035——**blocked，Q-003**：Windows 缺 GTK3 运行库）。

骨架先行：weasyprint 懒加载（模块导入无原生依赖；render_pdf 调用时才
require）。GTK 就绪后本模块按原规格补验收（页结构含质量卡、中文字形）；
端点层（M3-058）以 _pdf_available 探测降级 503。
"""
from __future__ import annotations

import importlib

from flint.domain.models import Block
from flint.render.html import render_html


def render_pdf(blocks: list[Block]) -> bytes:
    weasyprint = importlib.import_module("weasyprint")  # Q-003：GTK 就绪后可用
    html = render_html(blocks)
    payload: bytes = weasyprint.HTML(string=html).write_pdf()
    return payload
