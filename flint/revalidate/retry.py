"""revalidation 冲突：整 job 失效重跑（M3-054，审4 第三路径）。

- accept 撞 LedgerVersionConflict → 旧报告标废弃（superseded），基于
  冲突后的最新状态**完整重跑**产新报告（detect-only，accepted=None——
  用户在新状态上重新决定是否接受，绝不静默应用）。
- 无冲突 → 直接应用（M3-053 accept_report）。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from flint.domain.models import JSON, Block, LedgerVersionConflict, RevalidationReport
from flint.jobs.gate1 import Gate1Deps
from flint.ledger.store import PgLedgerStore
from flint.revalidate.accept import AcceptOutcome, accept_report
from flint.revalidate.report import build_report


@dataclass
class WholeJobOutcome:
    reran: bool
    applied: AcceptOutcome | None
    fresh_report: RevalidationReport
    superseded_report_id: str | None


async def accept_with_whole_job_rerun(
    store: PgLedgerStore,
    deps: Gate1Deps,
    project_id: str,
    stale_report: RevalidationReport,
    stale_expected_version: int,
    keywords: list[str],
    locale: str,
    old_verdict: str,
    rerun_report_id: str,
    rerun_analysis_id: str,
    changes: JSON,
    blocks: list[Block],
    now: datetime,
) -> WholeJobOutcome:
    try:
        applied = await accept_report(
            store=store, project_id=project_id, report=stale_report,
            expected_version=stale_expected_version, changes=changes,
            blocks=blocks, now=now,
        )
    except LedgerVersionConflict:
        fresh = build_report(
            deps=deps, report_id=rerun_report_id,
            deliverable_id=stale_report.deliverable_id,
            keywords=keywords, locale=locale, old_verdict=old_verdict,
            rerun_analysis_id=rerun_analysis_id,
            known_paper_ids=set(stale_report.new_papers),
            known_competitor_names=set(stale_report.new_competitors),
            old_heat={}, new_heat={}, trigger=stale_report.trigger,
            generated_at=now,
        )
        return WholeJobOutcome(
            reran=True, applied=None, fresh_report=fresh,
            superseded_report_id=stale_report.report_id,
        )
    return WholeJobOutcome(
        reran=False, applied=applied, fresh_report=applied.report,
        superseded_report_id=None,
    )
