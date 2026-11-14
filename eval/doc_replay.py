"""文书复现评测（M3-063，F2 / 审9 唯一例外）。

- replay_compose：同输入下以新 job 全新重跑 compose → render 快照与
  blocks 归一视图与原跑比对，diff 为空即复现成立。
- RedactionRecord 在场 → 复现豁免但必须留痕：质量卡「含已删除的个人数据，
  不可完整复现」+ Deliverable.reproducible=False（redaction_note /
  apply_redaction_flag）。
"""
from __future__ import annotations

from typing import Any

import asyncpg

from flint.domain.models import JSON, RedactionRecord
from flint.jobs.compose import ComposeDeps, run_compose

REDACTION_NOTE = "含已删除的个人数据，不可完整复现"


def redaction_note(records: list[RedactionRecord]) -> str | None:
    return REDACTION_NOTE if records else None


async def _artifact_view(dsn: str, job_id: str) -> dict[str, Any]:
    conn = await asyncpg.connect(dsn)
    try:
        blocks = await conn.fetch(
            "SELECT section_id, content::text, fact_ids::text FROM blocks "
            "WHERE deliverable_id = $1 ORDER BY section_id, block_order",
            f"del-{job_id}",
        )
        render = await conn.fetchval(
            "SELECT payload FROM snapshots WHERE snapshot_id = $1",
            f"snap-{job_id}-render",
        )
        return {
            "blocks": [tuple(r) for r in blocks],
            "render": bytes(render).decode("utf-8") if render else None,
        }
    finally:
        await conn.close()


async def replay_compose(
    dsn: str,
    original_job_id: str,
    replay_job_id: str,
    project_id: str,
    source_deliverable_ids: list[str],
    deps: ComposeDeps,
) -> JSON:
    await run_compose(
        job_id=replay_job_id, project_id=project_id,
        source_deliverable_ids=source_deliverable_ids, deps=deps,
    )
    original = await _artifact_view(dsn, original_job_id)
    replayed = await _artifact_view(dsn, replay_job_id)
    return {
        "blocks_match": original["blocks"] == replayed["blocks"],
        "render_match": original["render"] == replayed["render"],
        "diff_empty": original == replayed,
    }
