"""freeze_ledger：聚合 + 提升 + 派生（M3-020，冻结协议 ReportComposer.freeze_ledger）。

- 聚合 deliverable_ids 下全量 claim → ClaimPromoter（M3-006 白名单提升）→
  LedgerStore.derive 在当前版本之上派生新账本。
- reason 口径：无账本 → "initial"；已有账本的复冻 → "inject_evidence"
  （冻结 DerivationReason 四枚举无 freeze 专属值，取语义最近似者——新增
  claim 证据聚合入账；建议 v0.4 修订增 "freeze" 枚举，已记备忘）。
- promoted_fact_id 回填写回 claims 表（提升三字段闭环的存储面）；
  fact_id 确定性以 (claim_id, 所属 deliverable) 为键 → 复冻同输入产同
  fact_id（幂等内容）。
"""
from __future__ import annotations

import json
from typing import Any

import asyncpg

from flint.domain.models import DerivationReason, FactsLedger
from flint.ledger.entities import claim_from_row, fact_to_row
from flint.ledger.promoter import promote_claims
from flint.ledger.store import PgLedgerStore


async def _load_claims(dsn: str, deliverable_ids: list[str]) -> list[Any]:
    conn = await asyncpg.connect(dsn)
    try:
        rows = await conn.fetch(
            "SELECT * FROM claims WHERE deliverable_id = ANY($1::text[]) "
            "ORDER BY claim_id",
            deliverable_ids,
        )
    finally:
        await conn.close()
    result = []
    for r in rows:
        data = dict(r)
        data["citation_ids"] = json.loads(data["citation_ids"])
        result.append(claim_from_row(data))
    return result


async def _current_version(dsn: str, project_id: str) -> int:
    conn = await asyncpg.connect(dsn)
    try:
        version: int | None = await conn.fetchval(
            "SELECT MAX(version) FROM facts_ledgers WHERE project_id = $1",
            project_id,
        )
        return version or 0
    finally:
        await conn.close()


async def _backfill_promoted(dsn: str, promoted: dict[str, str]) -> None:
    if not promoted:
        return
    conn = await asyncpg.connect(dsn)
    try:
        await conn.executemany(
            "UPDATE claims SET promoted_fact_id = $2 WHERE claim_id = $1",
            list(promoted.items()),
        )
    finally:
        await conn.close()


async def freeze_ledger(
    dsn: str,
    store: PgLedgerStore,
    project_id: str,
    deliverable_ids: list[str],
    actor: str,
) -> FactsLedger:
    claims = await _load_claims(dsn, deliverable_ids)
    current = await _current_version(dsn, project_id)
    next_version = current + 1
    # 逐 deliverable 提升（fact_id 确定性以 (claim, 其所属 deliverable) 为键）
    facts_rows: list[dict[str, Any]] = []
    promoted: dict[str, str] = {}
    for claim in claims:
        result = promote_claims([claim], claim.deliverable_id, next_version)
        for fact in result.facts:
            facts_rows.append(fact_to_row(fact))
        for updated in result.claims:
            if updated.promoted_fact_id is not None:
                promoted[updated.claim_id] = updated.promoted_fact_id
    reason: DerivationReason = "initial" if current == 0 else "inject_evidence"
    ledger = await store.derive(
        project_id,
        expected_parent_version=current,
        reason=reason,
        changes={
            "add": facts_rows,
            "created_from": deliverable_ids,
            "actor": actor,
        },
    )
    await _backfill_promoted(dsn, promoted)
    return ledger
