"""M4-030 acceptance tests: export-ban panorama eval.

Acceptance (tasks.json M4-030):
  - three ban paths (blocking / dag failure / registry unavailable) each
    exercised end-to-end
  - re-export succeeds after the violation clears (gate recoverability)
"""
from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import asyncpg
import pytest

from eval.export_gate import run_export_gate_eval
from flint.compose.deliverable import PgDeliverableStore
from flint.domain.models import Deliverable, TaskSpec
from flint.spec.contracts_copy import build_contracts_copy
from flint.spec.pack_zip import PackBundle
from flint.spec.tasks_json import export_tasks_json
from flint.spec.vibe_s5 import build_s5

pytestmark = pytest.mark.compose

DSN = os.environ.get("FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")
CONTRACTS = Path(__file__).resolve().parents[2] / "contracts"
NOW = datetime(2026, 7, 28, 12, 0, 0, tzinfo=UTC)


def run(coro: Any) -> Any:
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def clean_slate() -> None:
    async def wipe() -> None:
        conn = await asyncpg.connect(DSN)
        try:
            await conn.execute(
                "DELETE FROM deliverables WHERE deliverable_id LIKE 'm4030-%'"
            )
        finally:
            await conn.close()

    run(wipe())


def bundle() -> PackBundle:
    tasks = [TaskSpec(
        task_id="T-1", title="任务一", inputs=["repo-skeleton"],
        outputs=["mod.T-1"], acceptance=["验收一"], depends_on=[],
        milestone="M1", estimate_days=None, estimate_cycles=1.0,
        oneshot=True, verify_cmd="pytest tests/test_T-1.py -q",
        context_refs=["contracts/models.py#TaskSpec"], review_gate=False,
    )]
    chapter = build_s5(tasks)
    return PackBundle(
        claude_md="## S1 Charter\n\n目标一\n\n" + chapter.markdown,
        human_digest="监工视图。",
        tasks_json=export_tasks_json(chapter),
        contracts=build_contracts_copy(CONTRACTS),
    )


def test_three_ban_paths_and_recovery() -> None:
    run(PgDeliverableStore(dsn=DSN).save_deliverable(Deliverable(
        deliverable_id="m4030-d1", project_id="p-1", type="vibe_pack",
        version=1, supersedes=None, inputs=[], ledger_version=1,
        generation_record_id="gr-1", stale_reasons=[], created_at=NOW,
    )))
    report = run(run_export_gate_eval(DSN, "m4030-d1", bundle()))
    names = [r.name for r in report.rows]
    assert names == ["block-review", "block-dag", "block-registry", "recover"]
    assert report.all_ok, [r for r in report.rows if not r.ok]
