"""accept：报告应用（M3-053，D6 / D8 统一 stale）。

- accept 才改状态：LedgerStore.derive(reason="revalidation") 应用报告变更；
- 下游经统一 diff/stale 机制：compute_diff(旧, 新) → apply_review_marks
  （M3-005 复用，零新机制）+ Staleness(ledger_changed) 挂 deliverable
  （携 revalidation_report_id 可溯源）。
- 版本冲突原样上抛（整 job 失效重跑归 M3-054）。
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime

from flint.domain.models import (
    JSON,
    Block,
    FactsLedger,
    RevalidationReport,
    Staleness,
)
from flint.ledger.diff import apply_review_marks, compute_diff
from flint.ledger.read import get_ledger
from flint.ledger.store import PgLedgerStore


@dataclass
class AcceptOutcome:
    ledger: FactsLedger
    report: RevalidationReport
    marked_blocks: list[Block] = field(default_factory=list)
    staleness: Staleness | None = None


async def accept_report(
    store: PgLedgerStore,
    project_id: str,
    report: RevalidationReport,
    expected_version: int,
    changes: JSON,
    blocks: list[Block],
    now: datetime,
) -> AcceptOutcome:
    old = await get_ledger(store.dsn, project_id, expected_version)
    ledger = await store.derive(
        project_id,
        expected_parent_version=expected_version,
        reason="revalidation",
        changes=changes,
    )
    diff = compute_diff(old.facts, ledger.facts)
    marked = apply_review_marks(blocks, diff)
    staleness = Staleness(
        reason="ledger_changed",
        detail=f"revalidation accepted: v{expected_version} -> v{ledger.version}",
        detected_at=now,
        revalidation_report_id=report.report_id,
    )
    return AcceptOutcome(
        ledger=ledger,
        report=replace(report, accepted=True),
        marked_blocks=marked,
        staleness=staleness,
    )
