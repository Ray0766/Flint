"""PgLedgerStore：账本派生乐观锁（M3-003，审4 / 冻结协议 LedgerStore）。

- derive：expected_parent_version 与当前最高版本不匹配 → 抛
  LedgerVersionConflict（携带 current_version + current_facts）；冲突处置
  按来源分派（inject 自动重放 / dispute 用户确认 / revalidation 整 job
  重跑）归 M3-044/046/054，本层只负责冲突如实上抛。
- 并发防线两道：先读后比（快路径）+ (project_id, version) 唯一索引兜底
  （竞态窗口内双写，唯一违例翻译为重读后的 Conflict——败者看到胜者状态）。
- changes 口径：add（fact 行列表，created_in_version 由本层盖章）、
  set_status（fact_id → 新 status）、created_from（deliverable_ids）。
- 账本不可变：新版本全量快照 facts（父版本行拷贝 + 变更应用），旧版永存。
"""
from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import asyncpg

from flint.domain.models import (
    JSON,
    DerivationReason,
    Fact,
    FactsLedger,
    LedgerVersionConflict,
)
from flint.ledger.entities import fact_from_row, fact_to_row


class StoredLedgerVersionConflict(LedgerVersionConflict):
    """冻结异常的实现子类：冻结件 __init__ 为存根体（...），属性不落——
    与 Protocol 由 Pg* 实现同判例，本子类补属性存储；类型身份保持
    （捕获方仍 catch 冻结 LedgerVersionConflict）。存根体补全建议已记
    v0.4 备忘。"""

    def __init__(self, current_version: int, current_facts: list[Fact]) -> None:
        Exception.__init__(
            self,
            f"ledger version conflict: current version is {current_version}",
        )
        self.current_version = current_version
        self.current_facts = current_facts


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _default_id() -> str:
    return f"led-{uuid4().hex}"


def _row_to_dict(row: asyncpg.Record) -> dict[str, Any]:
    data = dict(row)
    data["value"] = json.loads(data["value"]) if data["value"] is not None else None
    data["citation_ids"] = json.loads(data["citation_ids"])
    return data


class PgLedgerStore:
    """冻结协议 LedgerStore 的 PostgreSQL 实现（async 面，先例 M1-033）。"""

    def __init__(
        self,
        dsn: str,
        id_factory: Callable[[], str] = _default_id,
        now: Callable[[], datetime] = _utcnow,
    ) -> None:
        self._dsn = dsn
        self._id_factory = id_factory
        self._now = now

    @property
    def dsn(self) -> str:
        return self._dsn

    async def _current(
        self, conn: asyncpg.Connection, project_id: str
    ) -> tuple[int, str | None]:
        row = await conn.fetchrow(
            "SELECT version, ledger_id FROM facts_ledgers WHERE project_id = $1 "
            "ORDER BY version DESC LIMIT 1",
            project_id,
        )
        if row is None:
            return 0, None
        return int(row["version"]), str(row["ledger_id"])

    async def _facts_of(
        self, conn: asyncpg.Connection, ledger_id: str | None
    ) -> list[Fact]:
        if ledger_id is None:
            return []
        rows = await conn.fetch(
            "SELECT fact_id, statement, value, unit, citation_ids, status, origin, "
            "created_in_version, source_claim_id, promoted_from FROM facts "
            "WHERE ledger_id = $1 ORDER BY fact_id",
            ledger_id,
        )
        return [fact_from_row(_row_to_dict(r)) for r in rows]

    async def _conflict(
        self, conn: asyncpg.Connection, project_id: str
    ) -> StoredLedgerVersionConflict:
        version, ledger_id = await self._current(conn, project_id)
        return StoredLedgerVersionConflict(
            version, await self._facts_of(conn, ledger_id)
        )

    def _apply_changes(
        self, parent_facts: list[Fact], changes: JSON, new_version: int
    ) -> list[Fact]:
        merged: dict[str, Fact] = {f.fact_id: f for f in parent_facts}
        for raw in changes.get("add", []):
            row = dict(raw)
            row["created_in_version"] = new_version
            fact = fact_from_row(row)
            merged[fact.fact_id] = fact
        for fact_id, status in changes.get("set_status", {}).items():
            if fact_id not in merged:
                raise KeyError(f"set_status on unknown fact: {fact_id}")
            row = fact_to_row(merged[fact_id])
            row["status"] = status
            merged[fact_id] = fact_from_row(row)
        return [merged[k] for k in sorted(merged)]

    async def derive(
        self,
        project_id: str,
        expected_parent_version: int,
        reason: DerivationReason,
        changes: JSON,
    ) -> FactsLedger:
        conn = await asyncpg.connect(self._dsn)
        try:
            current_version, current_ledger_id = await self._current(conn, project_id)
            if current_version != expected_parent_version:
                raise await self._conflict(conn, project_id)

            parent_facts = await self._facts_of(conn, current_ledger_id)
            new_version = current_version + 1
            facts = self._apply_changes(parent_facts, changes, new_version)
            ledger_id = self._id_factory()
            created_from = [str(d) for d in changes.get("created_from", [])]
            stamp = self._now()
            try:
                async with conn.transaction():
                    await conn.execute(
                        "INSERT INTO facts_ledgers (ledger_id, project_id, version, "
                        "parent_version, derivation_reason, created_from, created_at, "
                        "actor) VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, $8)",
                        ledger_id, project_id, new_version,
                        current_version if current_version > 0 else None,
                        reason, json.dumps(created_from, ensure_ascii=False),
                        stamp, str(changes.get("actor", "u-system")),
                    )
                    await conn.executemany(
                        "INSERT INTO facts (ledger_id, fact_id, statement, value, "
                        "unit, citation_ids, status, origin, created_in_version, "
                        "source_claim_id, promoted_from) VALUES ($1, $2, $3, "
                        "$4::jsonb, $5, $6::jsonb, $7, $8, $9, $10, $11)",
                        [
                            (
                                ledger_id, f.fact_id, f.statement,
                                json.dumps(f.value, ensure_ascii=False)
                                if f.value is not None else None,
                                f.unit,
                                json.dumps(f.citation_ids, ensure_ascii=False),
                                f.status, f.origin, f.created_in_version,
                                f.source_claim_id, f.promoted_from,
                            )
                            for f in facts
                        ],
                    )
            except asyncpg.UniqueViolationError as err:
                # 竞态窗口内双写：唯一索引兜底，败者重读胜者状态（审4）
                raise await self._conflict(conn, project_id) from err
            return FactsLedger(
                ledger_id=ledger_id,
                project_id=project_id,
                version=new_version,
                parent_version=current_version if current_version > 0 else None,
                derivation_reason=reason,
                facts=facts,
                created_from=created_from,
                created_at=stamp,
                actor=str(changes.get("actor", "u-system")),
            )
        finally:
            await conn.close()
