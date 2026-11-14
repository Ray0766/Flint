"""M4-025 acceptance tests: critical path + ready frontier.

Acceptance (tasks.json M4-025):
  - critical path cycles + ready-frontier list (parallel scheduling basis)
  - numbers reconcile with this repo's dag_report
"""
from __future__ import annotations

import json
from pathlib import Path

from flint.dag.frontier import critical_path_cycles, ready_frontier
from flint.domain.models import TaskSpec

REPO_ROOT = Path(__file__).resolve().parents[2]


def task(task_id: str, cycles: float, depends_on: list[str]) -> TaskSpec:
    return TaskSpec(
        task_id=task_id, title=task_id, inputs=[], outputs=[task_id],
        acceptance=["a"], depends_on=depends_on, milestone="M1",
        estimate_cycles=cycles, oneshot=True, verify_cmd="pytest x",
        context_refs=["S3"], review_gate=False,
    )


def test_critical_path_and_frontier() -> None:
    tasks = [
        task("T-1", 1, []), task("T-2", 2, ["T-1"]), task("T-3", 1, ["T-1"]),
        task("T-4", 1, ["T-2", "T-3"]),
    ]
    assert critical_path_cycles(tasks) == 4, "1 + 2 + 1 longest chain"
    assert ready_frontier(tasks, done=set()) == ["T-1"]
    assert ready_frontier(tasks, done={"T-1"}) == ["T-2", "T-3"], (
        "parallel frontier after the root"
    )
    assert ready_frontier(tasks, done={"T-1", "T-2", "T-3"}) == ["T-4"]
    assert ready_frontier(tasks, done={"T-1", "T-2", "T-3", "T-4"}) == []


def test_reconciles_with_own_dag_report() -> None:
    from tests.m4.test_m4_023 import own_tasks

    data = json.loads(
        (REPO_ROOT / "tasks.json").read_text(encoding="utf-8-sig")
    )
    tasks = own_tasks()
    assert critical_path_cycles(tasks) == data["dag_report"]["critical_path_cycles"]
    total = sum(t.estimate_cycles or 0 for t in tasks)
    assert total == data["dag_report"]["total_cycles"]
