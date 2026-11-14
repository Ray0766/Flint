"""PERSIST-01：收藏的 SQL 实现（`favorites` 表，迁移 0023）。

`flint/fav/store.py:35` 自述「内存实现；SQL 实现随 E2 的 `favorites` 表接入」——
**这就是那个接入**。四个方法的名字与语义逐字照抄内存件，
所以 `add_favorite` / `remove_favorite` / `list_favorites` / `evaluate_snapshot_stale`
/ `refresh_snapshot` **一行都不用改**。

## 三条从内存件抄过来的语义（换实现时最容易掉的正是这种）

1. **`get` 返回副本**：内存件靠 `copy.deepcopy`；这里每次从 JSONB 重建对象，
   天生是副本。掉了的话，调用方改一下返回值就改了库里的快照。
2. **`drop` 幂等**：删不存在的返回 `False`，NEVER 抛错。
3. **`all()` 全量**，按 owner 过滤那一步归 `list_favorites`——
   **NEVER 挪到 SQL 里顺手做掉**：`_mine`（`flint/api/favorites.py`）判归属靠的是
   「先按 id 取到、再比 owner」，把过滤下推之后别人占着我的 id 时会取到 `None`，
   于是端点走进「这个 id 没人用」的分支，把别人那条收藏原样返回给我。

## `snapshot_stale` 照原样存

只能由 Revalidator 置（§6-H1）。存储层 NEVER 在读写路径上算一个出来。

## 为什么每次开一条连接

与 `PgProfileStore` / `PgLedgerStore` 同一房规：连接**不在建对象时**发生，
留到真的读写时才连。应用装配阶段（`flint/api/app.py`）一次连接都不发，
库不可达时应用照样建得出来——冒烟脚本才起得来。
"""
from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import asyncpg

from flint.db.sync_bridge import run_sync
from flint.domain.models import Principal

_CONTRACT_PATH: Final[Path] = (
    Path(__file__).resolve().parents[2] / "contracts_v04" / "models_v04.py"
)
_COLUMNS: Final[str] = (
    "favorite_id, owner_kind, owner_id, target_kind, target_id, "
    "evidence_snapshot, created_at, snapshot_stale"
)


def _contract() -> Any:
    """与 `flint/api/favorites.py` 同一种加载法（唯一真相是冻结件）。"""
    cached = sys.modules.get("models_v04_favorites")
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location(
        "models_v04_favorites", _CONTRACT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["models_v04_favorites"] = module
    spec.loader.exec_module(module)
    return module


def _row_to_favorite(row: asyncpg.Record) -> Any:
    return _contract().Favorite(
        favorite_id=row["favorite_id"],
        owner=Principal(kind=row["owner_kind"], id=row["owner_id"]),
        target_kind=row["target_kind"],
        target_id=row["target_id"],
        evidence_snapshot=json.loads(row["evidence_snapshot"]),
        created_at=row["created_at"],
        snapshot_stale=row["snapshot_stale"],
    )


@dataclass
class PgFavoriteStore:
    """`FavoriteStore` 的 SQL 实现。方法名与语义逐字对齐内存件。"""

    dsn: str

    async def _connect(self) -> asyncpg.Connection:
        return await asyncpg.connect(self.dsn)

    def put(self, favorite: Any) -> None:
        """建或整行覆盖。

        upsert 而不是 `INSERT`：`evaluate_snapshot_stale` 与 `refresh_snapshot`
        都是「读出来、`replace` 一份、`put` 回去」，纯 `INSERT` 会在那里撞主键。
        """
        async def _go() -> None:
            conn = await self._connect()
            try:
                await conn.execute(
                    f"INSERT INTO favorites ({_COLUMNS}) "
                    "VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, $8) "
                    "ON CONFLICT (favorite_id) DO UPDATE SET "
                    "owner_kind = EXCLUDED.owner_kind, owner_id = EXCLUDED.owner_id, "
                    "target_kind = EXCLUDED.target_kind, "
                    "target_id = EXCLUDED.target_id, "
                    "evidence_snapshot = EXCLUDED.evidence_snapshot, "
                    "created_at = EXCLUDED.created_at, "
                    "snapshot_stale = EXCLUDED.snapshot_stale",
                    favorite.favorite_id,
                    favorite.owner.kind,
                    favorite.owner.id,
                    favorite.target_kind,
                    favorite.target_id,
                    json.dumps(favorite.evidence_snapshot, ensure_ascii=False),
                    favorite.created_at,
                    favorite.snapshot_stale,
                )
            finally:
                await conn.close()

        run_sync(_go())

    def get(self, favorite_id: str) -> Any:
        """一条，或 `None`。返回的**是副本**（每次从 JSONB 重建）。"""
        async def _go() -> Any:
            conn = await self._connect()
            try:
                row = await conn.fetchrow(
                    "SELECT * FROM favorites WHERE favorite_id = $1", favorite_id)
            finally:
                await conn.close()
            return None if row is None else _row_to_favorite(row)

        return run_sync(_go())

    def drop(self, favorite_id: str) -> bool:
        """幂等：不存在时返回 `False`，NEVER 抛错。"""
        async def _go() -> bool:
            conn = await self._connect()
            try:
                tag = await conn.execute(
                    "DELETE FROM favorites WHERE favorite_id = $1", favorite_id)
            finally:
                await conn.close()
            # asyncpg 的 `execute` 回的是命令标签，形如 "DELETE 1"。
            return tag.rsplit(" ", 1)[-1] != "0"

        return run_sync(_go())

    def all(self) -> list[Any]:
        """全量。**按 owner 过滤那一步归 `list_favorites`**（见模块 docstring 第 3 条）。"""
        async def _go() -> list[Any]:
            conn = await self._connect()
            try:
                rows = await conn.fetch("SELECT * FROM favorites ORDER BY created_at")
            finally:
                await conn.close()
            return [_row_to_favorite(row) for row in rows]

        return run_sync(_go())
