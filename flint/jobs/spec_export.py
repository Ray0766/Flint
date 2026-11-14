"""spec_export job 编排（M4-029，技术方案 E4 / 冻结件 SpecExportCheckpoint）。

- 三步：validate_registry（批校验，M4-015）→ validate_dag（human 受众
  DagValidator）→ export（human spec 条目 + 快照出件）；步事务 +
  job_steps 断点，重入跳过已完成步（M2-040/M3-060 同规格）。
- SpecExportCheckpoint 逐步累积：validated_packages 在 validate_registry
  落账，resume 时从该步 checkpoint 恢复（不重打 registry）；
  task_ids_done 在 export 落账。
- 失败姿态：registry 不可用/缺包、dag errors → job failed + 事件留痕，
  NEVER 带病出件。
"""
from __future__ import annotations

import argparse
import asyncio
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Final

import asyncpg

from flint.dag.validator import validate
from flint.domain.models import (
    JobState,
    PackageStatus,
    SpecExportCheckpoint,
    StepEvent,
)
from flint.jobs.checkpoints import deserialize_checkpoint, serialize_checkpoint
from flint.jobs.events import PgJobEventStream
from flint.jobs.state import enter_state
from flint.registry.batch import CheckFn, Ecosystem, validate_batch
from flint.spec.export_human import build_entries
from flint.spec.store import PgSpecStore

STEP_ORDER: Final[list[str]] = ["validate_registry", "validate_dag", "export"]

_STEP_STATE: Final[dict[str, JobState]] = {
    "validate_registry": "validating",
    "validate_dag": "validating",
    "export": "drafting",
}


@dataclass
class SpecExportDeps:
    dsn: str
    now: datetime
    packages: list[tuple[str, Ecosystem]]
    check: CheckFn
    external_inputs: set[str]


@dataclass
class SpecExportReport:
    job_id: str
    steps_run: list[str] = field(default_factory=list)
    failed: str | None = None


def _offline_check(package: str, ecosystem: Ecosystem) -> PackageStatus:
    return PackageStatus(
        package=package, ecosystem=ecosystem, exists=True,
        latest_stable="1.0.0", replaced_with=None, reason=None,
    )


def build_offline_spec_export_deps(dsn: str) -> SpecExportDeps:
    return SpecExportDeps(
        dsn=dsn,
        now=datetime(2026, 7, 28, 12, 0, 0, tzinfo=UTC),
        packages=[("fastapi", "pypi"), ("httpx", "pypi")],
        check=_offline_check,
        external_inputs={"素材", "repo-skeleton"},
    )


async def _ensure_job(conn: asyncpg.Connection, job_id: str, now: datetime) -> str:
    await conn.execute(
        "INSERT INTO jobs (job_id, kind, owner_scope, state, progress, budget, "
        "cost_accum, cancel_requested, initiated_by, created_at, updated_at) "
        "VALUES ($1, 'spec_export', '{\"kind\":\"user\",\"id\":\"u-owner\"}', "
        "'queued', 0, 0, 0, false, 'u-owner', $2, $2) "
        "ON CONFLICT (job_id) DO NOTHING",
        job_id, now,
    )
    state: str = await conn.fetchval(
        "SELECT state FROM jobs WHERE job_id = $1", job_id
    )
    return state


#: `DESIGN-STATE`：**推进状态只有一处真相**（`flint/jobs/state.py`）。
#: 改前这个函数在 compose / gate1 / spec_export 三处各有一份、逐字相同，
#: 而 `design_generate` 一份都没有——于是它只写事件流，`jobs.state` 停在 queued。
#: 这里保留同名别名，既有调用点一个都不用改。
_enter_state = enter_state


async def _completed_steps(
    conn: asyncpg.Connection, job_id: str
) -> dict[str, str]:
    rows = await conn.fetch(
        "SELECT name, snapshot_ref FROM job_steps WHERE job_id = $1 "
        "ORDER BY step_index",
        job_id,
    )
    return {r["name"]: r["snapshot_ref"] for r in rows}


async def _fail(
    conn: asyncpg.Connection, events: PgJobEventStream, job_id: str,
    reason: str, now: datetime,
) -> None:
    await _enter_state(conn, events, job_id, "failed", now)
    await conn.execute(
        "UPDATE jobs SET partial_output_ref = NULL, updated_at = $2 "
        "WHERE job_id = $1",
        job_id, now,
    )


async def run_spec_export(
    job_id: str,
    spec_set_id: str,
    deps: SpecExportDeps,
    crash_after: str | None = None,
) -> SpecExportReport:
    report = SpecExportReport(job_id=job_id)
    events = PgJobEventStream(dsn=deps.dsn)
    store = PgSpecStore(deps.dsn)

    conn = await asyncpg.connect(deps.dsn)
    try:
        state = await _ensure_job(conn, job_id, deps.now)
        if state in ("done", "failed", "cancelled"):
            return report
        completed = await _completed_steps(conn, job_id)

        validated: list[str] = []
        if "validate_registry" in completed:
            prior = deserialize_checkpoint(completed["validate_registry"])
            assert isinstance(prior, SpecExportCheckpoint)
            validated = list(prior.validated_packages)

        for index, name in enumerate(STEP_ORDER):
            await _enter_state(conn, events, job_id, _STEP_STATE[name], deps.now)
            if name in completed:
                continue
            await events.append(
                job_id,
                StepEvent(kind="step", step_name=name, phase="start", cost=None),
                ts=deps.now,
            )
            async with conn.transaction():
                task_ids_done: list[str] = []
                if name == "validate_registry":
                    batch = validate_batch(deps.check, deps.packages)
                    if not batch.available or batch.missing:
                        await _fail(
                            conn, events, job_id,
                            f"registry gate: available={batch.available} "
                            f"missing={batch.missing}",
                            deps.now,
                        )
                        report.failed = "validate_registry"
                        return report
                    validated = [p for p, _e in deps.packages]
                elif name == "validate_dag":
                    tasks = await store.load_set(spec_set_id)
                    dag = validate(
                        tasks, audience="human_reader",
                        external_inputs=deps.external_inputs,
                        exit_ids={tasks[-1].task_id} if tasks else None,
                    )
                    findings = [
                        *dag.errors, *dag.orphans, *dag.unreachable,
                    ]
                    if not tasks or findings:
                        await _fail(
                            conn, events, job_id,
                            f"dag gate: {findings or 'empty set'}", deps.now,
                        )
                        report.failed = "validate_dag"
                        return report
                else:  # export
                    tasks = await store.load_set(spec_set_id)
                    entries = build_entries(tasks)
                    task_ids_done = [e.task.task_id for e in entries]
                    lines = [
                        f"## {e.task.task_id} {e.task.title}\n"
                        + "\n".join(f"- {a}" for a in e.assertions)
                        for e in entries
                    ]
                    await conn.execute(
                        "INSERT INTO snapshots (snapshot_id, payload, created_at) "
                        "VALUES ($1, $2, $3) ON CONFLICT (snapshot_id) DO NOTHING",
                        f"snap-{job_id}-spec",
                        "\n\n".join(lines).encode("utf-8"), deps.now,
                    )
                    await conn.execute(
                        "UPDATE jobs SET partial_output_ref = $2, updated_at = $3 "
                        "WHERE job_id = $1",
                        job_id, f"snap-{job_id}-spec", deps.now,
                    )
                checkpoint = SpecExportCheckpoint(
                    kind="spec_export",
                    validated_packages=validated,
                    task_ids_done=task_ids_done,
                )
                await conn.execute(
                    "INSERT INTO job_steps (job_id, step_index, name, state, "
                    "started_at, ended_at, cost, snapshot_ref) VALUES "
                    "($1, $2, $3, 'done', $4, $4, 0, $5)",
                    job_id, index, name, deps.now,
                    serialize_checkpoint(checkpoint),
                )
            report.steps_run.append(name)
            await events.append(
                job_id,
                StepEvent(kind="step", step_name=name, phase="end", cost=0.0),
                ts=deps.now,
            )
            if crash_after == name:
                os._exit(137)

        await _enter_state(conn, events, job_id, "done", deps.now)
    finally:
        await conn.close()
    return report


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="flint spec_export driver")
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--spec-set-id", required=True)
    parser.add_argument("--crash-after", default=None)
    args = parser.parse_args(argv)
    deps = build_offline_spec_export_deps(dsn=args.dsn)
    asyncio.run(
        run_spec_export(
            job_id=args.job_id, spec_set_id=args.spec_set_id,
            deps=deps, crash_after=args.crash_after,
        )
    )


if __name__ == "__main__":
    main()
