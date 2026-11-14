"""账本版本读取（M3-004，冻结协议 LedgerStore.get 面）。"""
from __future__ import annotations

import json
from typing import Any, cast

import asyncpg

from flint.domain.models import DerivationReason, FactsLedger
from flint.ledger.entities import fact_from_row


async def get_ledger(dsn: str, project_id: str, version: int) -> FactsLedger:
    conn = await asyncpg.connect(dsn)
    try:
        row = await conn.fetchrow(
            "SELECT * FROM facts_ledgers WHERE project_id = $1 AND version = $2",
            project_id, version,
        )
        if row is None:
            raise KeyError(f"unknown ledger: {project_id} v{version}")
        fact_rows = await conn.fetch(
            "SELECT fact_id, statement, value, unit, citation_ids, status, origin, "
            "created_in_version, source_claim_id, promoted_from FROM facts "
            "WHERE ledger_id = $1 ORDER BY fact_id",
            row["ledger_id"],
        )
    finally:
        await conn.close()

    def to_dict(record: asyncpg.Record) -> dict[str, Any]:
        data = dict(record)
        data["value"] = (
            json.loads(data["value"]) if data["value"] is not None else None
        )
        data["citation_ids"] = json.loads(data["citation_ids"])
        return data

    reason = str(row["derivation_reason"])
    return FactsLedger(
        ledger_id=str(row["ledger_id"]),
        project_id=str(row["project_id"]),
        version=int(row["version"]),
        parent_version=(
            int(row["parent_version"]) if row["parent_version"] is not None else None
        ),
        derivation_reason=cast(DerivationReason, reason),
        facts=[fact_from_row(to_dict(r)) for r in fact_rows],
        created_from=[str(d) for d in json.loads(row["created_from"])],
        created_at=row["created_at"],
        actor=str(row["actor"]),
    )
