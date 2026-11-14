"""PERSIST-03：模板注册表的 SQL 实现（`templates` 表，迁移 0025）。

`flint/design/templates/registry.py:39` 自述「内存实现；SQL 实现随 E2 的
`template_registry` 表接入」——**这就是那个接入**（表名以 `DEC-048` 为准叫
`templates`，理由在迁移 0025 的模块 docstring 里）。

两个方法（`all` / `append`）与一个属性（`available`）逐字对齐内存件，
所以 `register_template` / `list_templates` / `may_explore` / `solidify_mock`
**一行都不用改**：去重、版本递增、checksum 绑定全在那边，本模块只搬运。

## `available` 从构造参数变成一件可以被问出来的事实

内存件的 `available: bool = True` 是调用方给的（`flint/api/app.py` 改前注的是
`TemplateRegistry(available=False)`——因为表根本不存在）。

换成 SQL 之后它有了真实的含义：**这张表在不在、连不连得上**。
`E6` 那条降级线因此第一次有了依据——不可用时阻断固化与生产渲染、
**不阻断探索**，而报错文本里写清什么还能做。

## `append` NEVER upsert

注册表是 append-only 的版本序列：固化过的东西可能已经被别人拿去渲染了，
覆盖它等于让那些产物失去出处。同内容不产出新版本这件事由
`register_template` 在写之前判掉（它先按 checksum 在 `mine` 里找），
所以到了这里的每一条**都该是新的一行**。

写成 `ON CONFLICT (template_id) DO UPDATE` 的话，第二个版本会把第一个版本
**就地改掉**，而 `list_templates` 仍然回一条——版本序列从此只剩最后一版，
且**没有任何迹象表明它曾经有过别的版本**。

## `all()` 回全量，按 owner 过滤归 `register_template` / `list_templates`

与 `PgFavoriteStore` 同一条理由：把过滤下推到 SQL 里，
去重那一步（`register_template` 在 `mine` 里比 checksum）就要多传一个 owner 进来，
而那是在**为了省一次全表读**改一个已经 verified 的域函数的签名。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final

import asyncpg

from flint.db.sync_bridge import run_sync
from flint.domain.models import Principal

_COLUMNS: Final[str] = (
    "template_id, version, owner_kind, owner_id, name, slots, "
    "source_deliverable_id, html, checksum, solidified_at, enabled"
)


def _record_model() -> Any:
    """`TemplateRecord` 住在 additive 那一层，与 `_graph_node_model` 同一条取法。"""
    from contracts_v04.models_v04 import TemplateRecord

    return TemplateRecord


def _row_to_record(row: asyncpg.Record) -> Any:
    return _record_model()(
        template_id=row["template_id"],
        owner=Principal(kind=row["owner_kind"], id=row["owner_id"]),
        name=row["name"],
        version=row["version"],
        # 冻结件要**元组**：插槽集合固化后不该被就地追加（那会绕过 checksum 绑定）。
        slots=tuple(row["slots"]),
        source_deliverable_id=row["source_deliverable_id"],
        html=row["html"],
        checksum=row["checksum"],
        solidified_at=row["solidified_at"],
        enabled=row["enabled"],
    )


@dataclass
class PgTemplateRegistry:
    """`TemplateRegistry` 的 SQL 实现。"""

    dsn: str

    async def _connect(self) -> asyncpg.Connection:
        return await asyncpg.connect(self.dsn)

    @property
    def available(self) -> bool:
        """这张表在不在、连不连得上——`E6` 那条降级线的依据。

        **NEVER 让它抛**：`available` 的调用点正是「注册表不可用时该怎么办」
        那段代码的入口，它自己抛异常的话，那段代码一次都执行不到，
        用户拿到的是 500 而不是「固化不可用、探索仍可继续」。
        """
        async def _go() -> bool:
            try:
                conn = await self._connect()
            except (OSError, asyncpg.PostgresError):
                return False
            try:
                return bool(await conn.fetchval(
                    "SELECT to_regclass('public.templates') IS NOT NULL"))
            except asyncpg.PostgresError:
                return False
            finally:
                await conn.close()

        return run_sync(_go())

    def all(self) -> list[Any]:
        """全量版本序列，按 owner 与版本排序（过滤归调用方，见模块 docstring）。"""
        async def _go() -> list[Any]:
            conn = await self._connect()
            try:
                rows = await conn.fetch(
                    "SELECT * FROM templates ORDER BY owner_id, version")
            finally:
                await conn.close()
            return [_row_to_record(row) for row in rows]

        return run_sync(_go())

    def append(self, record: Any) -> None:
        """新增一行。**NEVER upsert**（见模块 docstring）。"""
        async def _go() -> None:
            conn = await self._connect()
            try:
                await conn.execute(
                    f"INSERT INTO templates ({_COLUMNS}) "
                    "VALUES ($1, $2, $3, $4, $5, $6::text[], $7, $8, $9, $10, $11)",
                    record.template_id,
                    record.version,
                    record.owner.kind,
                    record.owner.id,
                    record.name,
                    list(record.slots),
                    record.source_deliverable_id,
                    record.html,
                    record.checksum,
                    _as_datetime(record.solidified_at),
                    record.enabled,
                )
            finally:
                await conn.close()

        run_sync(_go())


def _as_datetime(value: Any) -> datetime:
    """`solidified_at` 恒是 datetime；这一层只是把类型收窄给 asyncpg 看。"""
    assert isinstance(value, datetime)
    return value
