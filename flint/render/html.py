"""html 渲染（M3-034，markdown-it 管线；D3 渲染目标不回写）。

- 复用 M3-033 markdown 渲染 + pin_order（M3-040：declaration 恒钉质量卡
  上方、两者前置）→ markdown-it 出 html；同树重渲染字节稳定。
"""
from __future__ import annotations

from markdown_it import MarkdownIt

from flint.compose.disclaimer import pin_order
from flint.domain.models import Block
from flint.render.markdown import render_markdown_ordered

_MD = MarkdownIt("commonmark", {"typographer": False}).enable("table")


def render_html(blocks: list[Block]) -> str:
    return str(_MD.render(render_markdown_ordered(pin_order(blocks))))
