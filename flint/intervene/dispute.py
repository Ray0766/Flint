"""dispute 流（M3-045，冻结件 Dispute docstring / 审10 / 审11）。

- accept：fact 标 disputed（derive reason="dispute"）→ 新生成排除
  （usable_fact_pool 天然生效）+ 既有引用 block 标 advisory（M3-007 复用）。
- resolve 两态：resolved_kept → 恢复 frozen；resolved_replaced → retired
  （替换事实由注证据/复核路径另行入账）；均派生新版本并清除相关 review
  （needs_review/reason/severity 归零）。
- open 状态不可 resolve（状态机防误用）；版本冲突原样上抛（用户确认重提
  归 M3-046，与 inject 自动重放刻意相反——审4 分派）。
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace

from flint.domain.models import Block, Dispute, FactsLedger
from flint.ledger.disputed import mark_advisory_for_disputed
from flint.ledger.store import PgLedgerStore


@dataclass
class DisputeOutcome:
    ledger: FactsLedger
    marked_blocks: list[Block] = field(default_factory=list)


async def accept_dispute(
    store: PgLedgerStore,
    project_id: str,
    dispute: Dispute,
    expected_version: int,
    blocks: list[Block],
) -> DisputeOutcome:
    ledger = await store.derive(
        project_id,
        expected_parent_version=expected_version,
        reason="dispute",
        changes={
            "set_status": {dispute.target_id: "disputed"},
            "actor": dispute.created_by,
        },
    )
    marked = mark_advisory_for_disputed(blocks, {dispute.target_id})
    return DisputeOutcome(ledger=ledger, marked_blocks=marked)


async def resolve_dispute(
    store: PgLedgerStore,
    project_id: str,
    dispute: Dispute,
    expected_version: int,
    blocks: list[Block],
) -> DisputeOutcome:
    if dispute.status == "open":
        raise ValueError("dispute still open: resolve requires a terminal status")
    new_status = "frozen" if dispute.status == "resolved_kept" else "retired"
    ledger = await store.derive(
        project_id,
        expected_parent_version=expected_version,
        reason="dispute",
        changes={
            "set_status": {dispute.target_id: new_status},
            "actor": dispute.created_by,
        },
    )
    cleared = [
        replace(
            b, needs_review=False, review_reason=None, review_severity=None
        )
        if dispute.target_id in b.fact_ids
        else replace(b)
        for b in blocks
    ]
    return DisputeOutcome(ledger=ledger, marked_blocks=cleared)
