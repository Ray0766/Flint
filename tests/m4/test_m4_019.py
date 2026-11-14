"""M4-019 acceptance tests: dag graph core.

Acceptance (tasks.json M4-019):
  - cycle detection (path identified); orphans (undepended non-exit) and
    unreachable nodes detected
  - frozen DagReport four-field construction
"""
from __future__ import annotations

from flint.dag.graph import analyze_graph
from flint.domain.models import DagReport, TaskSpec


def task(task_id: str, depends_on: list[str],
         outputs: list[str] | None = None) -> TaskSpec:
    return TaskSpec(
        task_id=task_id, title=task_id, inputs=[], outputs=outputs or [task_id],
        acceptance=["a"], depends_on=depends_on, milestone="M1",
        estimate_cycles=1, oneshot=True, verify_cmd="pytest x",
        context_refs=["S3"], review_gate=False,
    )


def test_clean_chain_acyclic() -> None:
    report = analyze_graph([
        task("T-1", []), task("T-2", ["T-1"]), task("T-3", ["T-2"]),
    ])
    assert isinstance(report, DagReport)
    assert report.acyclic is True
    assert report.orphans == [] and report.unreachable == []
    assert report.errors == []


def test_cycle_detected_with_path() -> None:
    report = analyze_graph([
        task("T-1", ["T-3"]), task("T-2", ["T-1"]), task("T-3", ["T-2"]),
    ])
    assert report.acyclic is False
    assert any("T-1" in e and "T-3" in e for e in report.errors), (
        "cycle path identified in errors"
    )


def test_orphan_is_undepended_non_exit() -> None:
    report = analyze_graph([
        task("T-1", []), task("T-2", ["T-1"]), task("T-island", ["T-1"]),
        task("T-exit", ["T-2"]),
    ])
    assert report.orphans == ["T-island"], (
        "undepended and not the single exit -> orphan"
    )
    assert "T-exit" not in report.orphans, "the exit terminal is legitimate"


def test_unreachable_unknown_dependency() -> None:
    report = analyze_graph([
        task("T-1", []), task("T-2", ["T-ghost"]),
    ])
    assert report.unreachable == ["T-2"]
    assert any("T-ghost" in e for e in report.errors)
