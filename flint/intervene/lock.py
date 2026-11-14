"""lock：block/section 两级锁（M3-041，冻结协议 InterventionService.lock）。

- 锁即置位 blocks.locked=true（保护谓词三条件之一，M3-009 单点）；
  重复锁幂等（flag 置位非改写，revision 不动）；未知目标 KeyError。
- 解锁归 owner 语义（S9 人审面），本卡不提供 unlock API——留位注明。
"""
from __future__ import annotations

from typing import Literal

import asyncpg


class PgLockService:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    async def lock(
        self, target_id: str, scope: Literal["block", "section"]
    ) -> None:
        column = "block_id" if scope == "block" else "section_id"
        conn = await asyncpg.connect(self._dsn)
        try:
            status = await conn.execute(
                f"UPDATE blocks SET locked = true WHERE {column} = $1",
                target_id,
            )
        finally:
            await conn.close()
        if status.endswith(" 0"):
            raise KeyError(f"unknown {scope}: {target_id}")
