"""PERSIST-01：外链的 SQL 实现（`share_links` 表，迁移 0023）。

`flint/api/share.py:61` 自述「内存实现；SQL 实现随 E2 接入」——**这就是那个接入**。
三个方法（`put` / `get` / `for_owner`）的名字与语义逐字照抄内存件，
所以 `create_share_app` 的门禁与状态码分法一行都不用改。

## 撤销**不是**删除

`revoke` 端点做的是 `store.put(replace(row, revoked=True))`——一次覆盖写。
所以这里 `put` 必须是 upsert：写成纯 `INSERT` 的话撤销会撞主键，
而最省事的「修法」是改成 `DELETE`——那正是冻结件判死的动作：

- 删掉：持链人拿到 404「没这条」，他会以为自己拿错了链接；
- 留着：回 410「你没走错，它到期了」，他据此去找人续期。

## 口令只以 hash 形态存在

明文 NEVER 落库（`hash_password` 在 `flint/share/links.py`，本模块只搬运）。
表上那一列叫 `password_hash`，**没有 password 列**——冻结件原话
「连放明文的地方都不留：只要有 `password: str` 字段，就一定有人在某个构造点
把明文塞进去，然后它随对象一起进日志、进快照、进导出」。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import asyncpg

from flint.api.share import ShareLink
from flint.db.sync_bridge import run_sync
from flint.domain.models import Principal

_COLUMNS: Final[str] = (
    "token, target_kind, target_id, created_by_kind, created_by_id, "
    "expires_at, revoked, created_at, password_hash"
)


def _row_to_link(row: asyncpg.Record) -> ShareLink:
    return ShareLink(
        token=row["token"],
        target_kind=row["target_kind"],
        target_id=row["target_id"],
        created_by=Principal(kind=row["created_by_kind"], id=row["created_by_id"]),
        expires_at=row["expires_at"],
        revoked=row["revoked"],
        created_at=row["created_at"],
        password_hash=row["password_hash"],
    )


@dataclass
class PgShareLinkStore:
    """`ShareLinkStore` 的 SQL 实现。"""

    dsn: str

    async def _connect(self) -> asyncpg.Connection:
        return await asyncpg.connect(self.dsn)

    def put(self, link: ShareLink) -> None:
        """建或整行覆盖。**撤销走的就是这条路**（见模块 docstring）。"""
        async def _go() -> None:
            conn = await self._connect()
            try:
                await conn.execute(
                    f"INSERT INTO share_links ({_COLUMNS}) "
                    "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) "
                    "ON CONFLICT (token) DO UPDATE SET "
                    "target_kind = EXCLUDED.target_kind, "
                    "target_id = EXCLUDED.target_id, "
                    "created_by_kind = EXCLUDED.created_by_kind, "
                    "created_by_id = EXCLUDED.created_by_id, "
                    "expires_at = EXCLUDED.expires_at, "
                    "revoked = EXCLUDED.revoked, "
                    "created_at = EXCLUDED.created_at, "
                    "password_hash = EXCLUDED.password_hash",
                    link.token,
                    link.target_kind,
                    link.target_id,
                    link.created_by.kind,
                    link.created_by.id,
                    link.expires_at,
                    link.revoked,
                    link.created_at,
                    link.password_hash,
                )
            finally:
                await conn.close()

        run_sync(_go())

    def get(self, token: str) -> ShareLink | None:
        """一条，或 `None`。**撤销过的照样返回**——410 那条路要的正是它。"""
        async def _go() -> ShareLink | None:
            conn = await self._connect()
            try:
                row = await conn.fetchrow(
                    "SELECT * FROM share_links WHERE token = $1", token)
            finally:
                await conn.close()
            return None if row is None else _row_to_link(row)

        return run_sync(_go())

    def for_owner(self, owner: Principal) -> list[ShareLink]:
        """我建的那些。别人的 NEVER 出现在这个列表里。"""
        async def _go() -> list[ShareLink]:
            conn = await self._connect()
            try:
                rows = await conn.fetch(
                    "SELECT * FROM share_links WHERE created_by_kind = $1 "
                    "AND created_by_id = $2 ORDER BY created_at",
                    owner.kind, owner.id)
            finally:
                await conn.close()
            return [_row_to_link(row) for row in rows]

        return run_sync(_go())
