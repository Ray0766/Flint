"""M3-063 acceptance tests: doc replay eval (F2 + audit-9 exception).

Acceptance (tasks.json M3-063):
  - record -> snapshot -> re-compose -> re-render diff empty
  - RedactionRecord present -> quality card "cannot fully reproduce" note
    (the single iron-rule-3 exception, with trail)
"""
from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import asyncpg
import pytest

from eval.doc_replay import REDACTION_NOTE, redaction_note, replay_compose
from flint.domain.models import RedactionRecord
from flint.jobs.compose import build_offline_compose_deps, run_compose

pytestmark = pytest.mark.compose

REPO_ROOT = Path(__file__).resolve().parents[2]
DSN = os.environ.get("FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")
NOW = datetime(2026, 7, 29, tzinfo=UTC)


def run(coro: Any) -> Any:
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def clean_slate() -> None:
    async def wipe() -> None:
        conn = await asyncpg.connect(DSN)
        try:
            for sql in (
                "DELETE FROM job_events WHERE job_id LIKE 'm3063-%'",
                "DELETE FROM job_steps WHERE job_id LIKE 'm3063-%'",
                "DELETE FROM jobs WHERE job_id LIKE 'm3063-%'",
                "DELETE FROM snapshots WHERE snapshot_id LIKE 'snap-m3063-%'",
                "DELETE FROM blocks WHERE deliverable_id LIKE 'del-m3063-%'",
                "DELETE FROM generation_records WHERE record_id LIKE 'rec-m3063-%'",
                "DELETE FROM deliverables WHERE deliverable_id LIKE 'del-m3063-%'",
                (
                    "DELETE FROM facts WHERE ledger_id IN (SELECT ledger_id FROM "
                    "facts_ledgers WHERE project_id = 'm3063-p1')"
                ),
                "DELETE FROM facts_ledgers WHERE project_id = 'm3063-p1'",
                "DELETE FROM claims WHERE claim_id LIKE 'm3063-%'",
            ):
                await conn.execute(sql)
            await conn.execute(
                "INSERT INTO claims (claim_id, deliverable_id, block_id, "
                "text_span, confidence, citation_ids, alignment, "
                "promoted_fact_id) VALUES ('m3063-c1', 'src-a', 'b-1', '结论', "
                "'cited', '[\"cit-1\"]'::jsonb, 'supports', NULL)",
            )
        finally:
            await conn.close()

    run(wipe())


def test_replay_diff_empty() -> None:
    deps = build_offline_compose_deps(dsn=DSN, repo_root=REPO_ROOT)
    run(run_compose(
        job_id="m3063-orig", project_id="m3063-p1",
        source_deliverable_ids=["src-a"], deps=deps,
    ))
    report = run(replay_compose(
        DSN, original_job_id="m3063-orig", replay_job_id="m3063-replay",
        project_id="m3063-p1", source_deliverable_ids=["src-a"], deps=deps,
    ))
    assert report["blocks_match"] is True
    assert report["render_match"] is True
    assert report["diff_empty"] is True


def test_redaction_note_single_exception_with_trail() -> None:
    assert redaction_note([]) is None, "no redaction, no note"
    record = RedactionRecord(
        deliverable_id="d-1", redacted_at=NOW, scope="用户身份字段",
        actor="u-owner",
    )
    note = redaction_note([record])
    assert note == REDACTION_NOTE
    assert "不可完整复现" in note
