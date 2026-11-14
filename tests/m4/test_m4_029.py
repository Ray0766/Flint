"""M4-029 acceptance tests: spec_export job orchestration.

Acceptance (tasks.json M4-029):
  - SpecExportCheckpoint checkpoint resume (kill -9, diff empty)
  - event sequence complete (same spec as M2-040)
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from typing import Any

import asyncpg
import pytest

from flint.domain.models import PackageStatus, SpecExportCheckpoint, TaskSpec
from flint.jobs.checkpoints import deserialize_checkpoint
from flint.jobs.spec_export import (
    STEP_ORDER,
    build_offline_spec_export_deps,
    run_spec_export,
)
from flint.registry.batch import Ecosystem
from flint.spec.store import PgSpecStore

pytestmark = pytest.mark.compose

DSN = os.environ.get("FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

EXPECTED_SHAPES = [
    ("status", "validating"),
    ("step", "validate_registry", "start"), ("step", "validate_registry", "end"),
    ("step", "validate_dag", "start"), ("step", "validate_dag", "end"),
    ("status", "drafting"),
    ("step", "export", "start"), ("step", "export", "end"),
    ("status", "done"),
]


def run(coro: Any) -> Any:
    return asyncio.run(coro)


def wipe(prefix: str) -> None:
    async def _wipe() -> None:
        conn = await asyncpg.connect(DSN)
        try:
            await conn.execute(
                "DELETE FROM job_events WHERE job_id LIKE $1", f"{prefix}%"
            )
            await conn.execute(
                "DELETE FROM job_steps WHERE job_id LIKE $1", f"{prefix}%"
            )
            await conn.execute(
                "DELETE FROM snapshots WHERE snapshot_id LIKE $1", f"snap-{prefix}%"
            )
            await conn.execute(
                "DELETE FROM jobs WHERE job_id LIKE $1", f"{prefix}%"
            )
            await conn.execute(
                "DELETE FROM task_specs WHERE spec_set_id LIKE 'm4029-%'"
            )
        finally:
            await conn.close()

    run(_wipe())


@pytest.fixture(autouse=True)
def clean_slate() -> None:
    wipe("m4029-")


def human_card(task_id: str, deps: list[str]) -> TaskSpec:
    return TaskSpec(
        task_id=task_id, title=f"人类任务 {task_id}",
        inputs=["素材"], outputs=[f"产物.{task_id}"],
        acceptance=["主流程走通", "延迟达标"], depends_on=deps,
        milestone="M1", estimate_days=0.5,
        estimate_cycles=None, oneshot=None, verify_cmd=None,
        context_refs=None, review_gate=None,
    )


def seed_specs() -> None:
    run(PgSpecStore(DSN).save_set(
        "m4029-p1", [human_card("T-1", []), human_card("T-2", ["T-1"])]
    ))


async def _artifacts(job_id: str) -> dict[str, Any]:
    conn = await asyncpg.connect(DSN)
    try:
        steps = await conn.fetch(
            "SELECT name, snapshot_ref FROM job_steps WHERE job_id = $1 "
            "ORDER BY step_index", job_id,
        )
        state = await conn.fetchval(
            "SELECT state FROM jobs WHERE job_id = $1", job_id
        )
        snapshot = await conn.fetchval(
            "SELECT payload FROM snapshots WHERE snapshot_id = $1",
            f"snap-{job_id}-spec",
        )
        events = await conn.fetch(
            "SELECT seq, payload FROM job_events WHERE job_id = $1 ORDER BY seq",
            job_id,
        )
    finally:
        await conn.close()

    def shape(payload: dict[str, Any]) -> tuple[str, ...]:
        if payload["kind"] == "status":
            return ("status", payload["state"])
        return ("step", payload["step_name"], payload["phase"])

    return {
        "steps": [(r["name"], r["snapshot_ref"]) for r in steps],
        "state": state,
        "spec_text": bytes(snapshot).decode("utf-8") if snapshot else None,
        "seqs": [r["seq"] for r in events],
        "shapes": [shape(json.loads(r["payload"])) for r in events],
    }


def export(job_id: str) -> None:
    deps = build_offline_spec_export_deps(DSN)
    run(run_spec_export(job_id, "m4029-p1", deps))


def test_full_chain_checkpoints_and_events() -> None:
    seed_specs()
    export("m4029-solo")
    artifacts = run(_artifacts("m4029-solo"))
    assert artifacts["state"] == "done"
    assert [s[0] for s in artifacts["steps"]] == STEP_ORDER
    registry_ckpt = deserialize_checkpoint(artifacts["steps"][0][1])
    assert isinstance(registry_ckpt, SpecExportCheckpoint)
    assert registry_ckpt.validated_packages == ["fastapi", "httpx"]
    export_ckpt = deserialize_checkpoint(artifacts["steps"][2][1])
    assert isinstance(export_ckpt, SpecExportCheckpoint)
    assert export_ckpt.task_ids_done == ["T-1", "T-2"]
    assert export_ckpt.validated_packages == ["fastapi", "httpx"], (
        "cumulative across steps"
    )
    assert artifacts["spec_text"] is not None
    assert "断言候选 1/2：主流程走通" in artifacts["spec_text"]
    assert artifacts["seqs"] == list(range(1, len(EXPECTED_SHAPES) + 1))
    assert artifacts["shapes"] == EXPECTED_SHAPES


def test_kill9_resume_diff_empty_and_events_gapless() -> None:
    seed_specs()
    export("m4029-ref")
    reference = run(_artifacts("m4029-ref"))

    env = dict(os.environ, FLINT_TEST_DSN=DSN, PYTHONIOENCODING="utf-8")
    proc = subprocess.run(
        [
            sys.executable, "-m", "flint.jobs.spec_export",
            "--dsn", DSN, "--job-id", "m4029-crash",
            "--spec-set-id", "m4029-p1",
            "--crash-after", "validate_dag",
        ],
        cwd=REPO_ROOT, env=env, capture_output=True, text=True,
        timeout=600, check=False,
    )
    assert proc.returncode == 137, f"{proc.stdout}\n{proc.stderr}"

    partial = run(_artifacts("m4029-crash"))
    assert [s[0] for s in partial["steps"]] == ["validate_registry", "validate_dag"]

    export("m4029-crash")
    resumed = run(_artifacts("m4029-crash"))
    assert [s[0] for s in resumed["steps"]] == STEP_ORDER, "no step rerun"
    assert resumed["state"] == "done"
    assert resumed["spec_text"] == reference["spec_text"]
    assert resumed["steps"] == reference["steps"], (
        "checkpoints byte-identical (payloads carry no job id)"
    )
    assert resumed["seqs"] == list(range(1, len(EXPECTED_SHAPES) + 1)), (
        "gapless across crash"
    )
    assert resumed["shapes"] == EXPECTED_SHAPES


def test_registry_missing_fails_before_export() -> None:
    seed_specs()
    deps = build_offline_spec_export_deps(DSN)

    def missing_check(package: str, ecosystem: Ecosystem) -> PackageStatus:
        return PackageStatus(
            package=package, ecosystem=ecosystem, exists=False,
            latest_stable=None, replaced_with=None, reason="not found",
        )

    deps.check = missing_check
    report = run(run_spec_export("m4029-fail", "m4029-p1", deps))
    assert report.failed == "validate_registry"
    artifacts = run(_artifacts("m4029-fail"))
    assert artifacts["state"] == "failed"
    assert artifacts["spec_text"] is None, "never exports while failing"
    assert [s[0] for s in artifacts["steps"]] == []


def test_dag_violation_fails_before_export() -> None:
    run(PgSpecStore(DSN).save_set(
        "m4029-p1", [human_card("T-1", ["ghost"])]
    ))
    deps = build_offline_spec_export_deps(DSN)
    report = run(run_spec_export("m4029-dagfail", "m4029-p1", deps))
    assert report.failed == "validate_dag"
    artifacts = run(_artifacts("m4029-dagfail"))
    assert artifacts["state"] == "failed"
    assert artifacts["spec_text"] is None
