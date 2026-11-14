"""M3-060 acceptance tests: compose job orchestration (DraftCheckpoint).

Acceptance (tasks.json M3-060):
  - outline -> freeze -> draft -> align -> render resumes via DraftCheckpoint
  - kill -9 rerun artifacts diff empty and event sequence complete
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import asyncpg
import pytest

from flint.domain.models import DraftCheckpoint
from flint.jobs.checkpoints import deserialize_checkpoint
from flint.jobs.compose import STEP_ORDER, build_offline_compose_deps, run_compose

pytestmark = pytest.mark.compose

REPO_ROOT = Path(__file__).resolve().parents[2]
DSN = os.environ.get("FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")

EXPECTED_SHAPES = [
    ("status", "drafting"),
    ("step", "outline", "start"), ("step", "outline", "end"),
    ("step", "freeze", "start"), ("step", "freeze", "end"),
    ("step", "draft", "start"),
    *(("partial",) for _ in range(7)),
    ("step", "draft", "end"),
    ("status", "validating"),
    ("step", "align", "start"), ("step", "align", "end"),
    ("step", "render", "start"), ("step", "render", "end"),
    ("status", "done"),
]


def run(coro: Any) -> Any:
    return asyncio.run(coro)


async def _sql(statements: list[str]) -> None:
    conn = await asyncpg.connect(DSN)
    try:
        for stmt in statements:
            await conn.execute(stmt)
    finally:
        await conn.close()


def wipe(job_prefix: str) -> None:
    run(_sql([
        f"DELETE FROM job_events WHERE job_id LIKE '{job_prefix}%'",
        f"DELETE FROM job_steps WHERE job_id LIKE '{job_prefix}%'",
        f"DELETE FROM jobs WHERE job_id LIKE '{job_prefix}%'",
        f"DELETE FROM snapshots WHERE snapshot_id LIKE 'snap-{job_prefix}%'",
        f"DELETE FROM blocks WHERE deliverable_id LIKE 'del-{job_prefix}%'",
        (
            "DELETE FROM generation_records WHERE record_id LIKE "
            f"'rec-{job_prefix}%'"
        ),
        f"DELETE FROM deliverables WHERE deliverable_id LIKE 'del-{job_prefix}%'",
        (
            "DELETE FROM facts WHERE ledger_id IN (SELECT ledger_id FROM "
            "facts_ledgers WHERE project_id LIKE 'm3060-%')"
        ),
        "DELETE FROM facts_ledgers WHERE project_id LIKE 'm3060-%'",
        "DELETE FROM claims WHERE claim_id LIKE 'm3060-%'",
    ]))


def seed_claim() -> None:
    run(_sql([
        ("INSERT INTO claims (claim_id, deliverable_id, block_id, text_span, "
        "confidence, citation_ids, alignment, promoted_fact_id) VALUES "
        "('m3060-c1', 'src-analysis', 'b-src', '市场规模 12 亿', 'cited', "
        "'[\"cit-1\"]'::jsonb, 'supports', NULL) ON CONFLICT (claim_id) DO "
        "UPDATE SET promoted_fact_id = NULL"),
    ]))


@pytest.fixture(autouse=True)
def clean_slate() -> None:
    wipe("m3060-")
    seed_claim()


def compose(job_id: str, project_id: str = "m3060-p1") -> Any:
    deps = build_offline_compose_deps(dsn=DSN, repo_root=REPO_ROOT)
    return run(run_compose(
        job_id=job_id, project_id=project_id,
        source_deliverable_ids=["src-analysis"], deps=deps,
    ))


async def _artifacts(job_id: str) -> dict[str, Any]:
    conn = await asyncpg.connect(DSN)
    try:
        blocks = await conn.fetch(
            "SELECT block_id, section_id, content::text, fact_ids::text FROM blocks "
            "WHERE deliverable_id = $1 ORDER BY section_id, block_order",
            f"del-{job_id}",
        )
        render = await conn.fetchval(
            "SELECT payload FROM snapshots WHERE snapshot_id = $1",
            f"snap-{job_id}-render",
        )
        rate = await conn.fetchval(
            "SELECT alignment_rate FROM generation_records WHERE record_id = $1",
            f"rec-{job_id}",
        )
        ledger = await conn.fetch(
            "SELECT version, derivation_reason, created_from::text FROM "
            "facts_ledgers WHERE project_id = 'm3060-p1' ORDER BY version"
        )
        steps = await conn.fetch(
            "SELECT name, snapshot_ref FROM job_steps WHERE job_id = $1 "
            "ORDER BY step_index",
            job_id,
        )
        state = await conn.fetchval(
            "SELECT state FROM jobs WHERE job_id = $1", job_id
        )
        return {
            "blocks": [
                (r["block_id"].replace(job_id, "JOB"), r["section_id"],
                 r["content"], r["fact_ids"])
                for r in blocks
            ],
            "render": bytes(render).decode("utf-8") if render else None,
            "alignment_rate": rate,
            "ledger": [tuple(r) for r in ledger],
            "steps": [(r["name"], r["snapshot_ref"]) for r in steps],
            "state": state,
        }
    finally:
        await conn.close()


def _shape(payload: dict[str, Any]) -> tuple[str, ...]:
    if payload["kind"] == "status":
        return ("status", payload["state"])
    if payload["kind"] == "partial_block":
        return ("partial",)
    return ("step", payload["step_name"], payload["phase"])


async def _event_shapes(job_id: str) -> tuple[list[int], list[tuple[str, ...]]]:
    conn = await asyncpg.connect(DSN)
    try:
        rows = await conn.fetch(
            "SELECT seq, payload FROM job_events WHERE job_id = $1 ORDER BY seq",
            job_id,
        )
    finally:
        await conn.close()
    return (
        [r["seq"] for r in rows],
        [_shape(json.loads(r["payload"])) for r in rows],
    )


def test_uninterrupted_run_full_chain() -> None:
    compose("m3060-solo")
    artifacts = run(_artifacts("m3060-solo"))
    assert artifacts["state"] == "done"
    assert [s[0] for s in artifacts["steps"]] == STEP_ORDER
    for name, ref in artifacts["steps"]:
        checkpoint = deserialize_checkpoint(ref)
        assert isinstance(checkpoint, DraftCheckpoint)
        if name in ("draft", "align", "render"):
            assert len(checkpoint.completed_section_ids) == 7
            assert checkpoint.ledger_version == 1
    assert artifacts["alignment_rate"] == 1.0
    assert artifacts["render"] and "## summary" in artifacts["render"]
    assert len(artifacts["blocks"]) == 7
    assert artifacts["ledger"] == [(1, "initial", '["src-analysis"]')]

    seqs, shapes = run(_event_shapes("m3060-solo"))
    assert seqs == list(range(1, len(EXPECTED_SHAPES) + 1))
    assert shapes == EXPECTED_SHAPES


def test_kill9_resume_diff_empty_and_events_complete() -> None:
    compose("m3060-ref")
    reference = run(_artifacts("m3060-ref"))
    reference_blocks = reference["blocks"]

    wipe("m3060-crash")  # 连带清 m3060- 账本与种子（helper 内正则），重播种子
    seed_claim()
    env = dict(os.environ, FLINT_TEST_DSN=DSN, PYTHONIOENCODING="utf-8")
    proc = subprocess.run(
        [
            sys.executable, "-m", "flint.jobs.compose",
            "--dsn", DSN, "--job-id", "m3060-crash",
            "--project-id", "m3060-p1", "--sources", "src-analysis",
            "--crash-after", "draft",
        ],
        cwd=REPO_ROOT, env=env, capture_output=True, text=True,
        timeout=600, check=False,
    )
    assert proc.returncode == 137, f"{proc.stdout}\n{proc.stderr}"

    steps = run(_artifacts("m3060-crash"))["steps"]
    assert [s[0] for s in steps] == ["outline", "freeze", "draft"]

    compose("m3060-crash", project_id="m3060-p1")
    resumed = run(_artifacts("m3060-crash"))
    assert [s[0] for s in resumed["steps"]] == STEP_ORDER, "no step rerun"
    assert resumed["blocks"] == reference_blocks
    assert resumed["render"] == reference["render"]
    assert resumed["alignment_rate"] == reference["alignment_rate"]
    assert resumed["state"] == "done"

    seqs, shapes = run(_event_shapes("m3060-crash"))
    assert seqs == list(range(1, len(EXPECTED_SHAPES) + 1)), "gapless across crash"
    assert shapes == EXPECTED_SHAPES
