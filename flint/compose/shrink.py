"""shrink：保护条件下压缩（M3-026，冻结协议 ReportComposer.shrink / S2-5）。

- 压缩器只拿到未受保护块；受保护块（is_protected 单点判定）原样保留并
  按原相对序合回——逐字节不动，NEVER 改写。
- 产出 order 重排为连续序（树序稳定）；引用完整性由压缩器契约 +
  验收断言双守（压缩不许丢引用块）。
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from flint.compose.blocks import is_protected
from flint.domain.models import Block

Compressor = Callable[[list[Block]], list[Block]]


def shrink_section(blocks: list[Block], compressor: Compressor) -> list[Block]:
    ordered = sorted(blocks, key=lambda b: b.order)
    unprotected = [b for b in ordered if not is_protected(b)]
    kept_ids = {b.block_id for b in compressor(list(unprotected))}

    merged: list[Block] = []
    for block in ordered:
        if is_protected(block) or block.block_id in kept_ids:
            merged.append(block)
    return [replace(b, order=i) for i, b in enumerate(merged)]
