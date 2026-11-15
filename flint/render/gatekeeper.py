"""导出门禁（M3-037，审11 / 冻结协议 Renderer 注释）。

- blocking（fact_removed 未处理）> 0 → 拒绝导出：ExportBlocked（异常文案
  携 EXPORT_BLOCKED 机器码 + 违规 block 清单，API 面直译错误体）。
- advisory 不拦：导出照常，质量卡列示「N 项待处理（advisory）」
  （pending_note，M2-048 blocking_reviews_open 位的姐妹口径）。
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from flint.domain.models import Block


class ExportBlocked(Exception):
    def __init__(self, blocking_block_ids: list[str]) -> None:
        super().__init__(
            f"EXPORT_BLOCKED: {len(blocking_block_ids)} blocking review(s) open "
            f"({', '.join(blocking_block_ids)})"
        )
        self.blocking_block_ids = blocking_block_ids


@dataclass(frozen=True)
class ExportCheck:
    exportable: bool
    blocking_open: int
    advisory_open: int
    blocking_block_ids: tuple[str, ...]


def check_export(blocks: list[Block]) -> ExportCheck:
    blocking = [
        b.block_id for b in blocks
        if b.needs_review and b.review_severity == "blocking"
    ]
    advisory = [
        b.block_id for b in blocks
        if b.needs_review and b.review_severity == "advisory"
    ]
    return ExportCheck(
        exportable=not blocking,
        blocking_open=len(blocking),
        advisory_open=len(advisory),
        blocking_block_ids=tuple(blocking),
    )


def guarded_render[RenderResult](
    blocks: list[Block], renderer: Callable[[list[Block]], RenderResult]
) -> RenderResult:
    check = check_export(blocks)
    if not check.exportable:
        raise ExportBlocked(list(check.blocking_block_ids))
    return renderer(blocks)


def pending_note(blocks: list[Block]) -> str | None:
    check = check_export(blocks)
    if check.advisory_open == 0:
        return None
    return f"{check.advisory_open} 项待处理（advisory）"
