"""M4-024 acceptance tests: split signal.

Acceptance (tasks.json M4-024):
  - cycles > 2 -> split signal (GapHint identifying the card, never
    auto-splitting)
  - split suggestion carries dependency-rewiring hints
"""
from __future__ import annotations

from flint.dag.split_signal import split_signals
from flint.domain.models import GapHint, TaskSpec


def task(task_id: str, cycles: float, depends_on: list[str] | None = None,
         dependents_hint: list[str] | None = None) -> TaskSpec:
    return TaskSpec(
        task_id=task_id, title=task_id, inputs=[], outputs=[task_id],
        acceptance=["a"], depends_on=depends_on or [], milestone="M1",
        estimate_cycles=cycles, oneshot=cycles <= 1, verify_cmd="pytest x",
        context_refs=["S3"], review_gate=False,
    )


def test_over_limit_yields_gap_hint_never_auto_split() -> None:
    tasks = [task("T-1", 1), task("T-big", 3, ["T-1"]), task("T-3", 1, ["T-big"])]
    hints = split_signals(tasks)
    assert len(hints) == 1
    hint = hints[0]
    assert isinstance(hint, GapHint)
    assert "T-big" in hint.missing_what
    assert hint.cause == "missing_data"
    assert hint.action == "ask_user", "splitting is a planning act, never automatic"


def test_rewiring_hints_carry_neighbors() -> None:
    tasks = [task("T-up", 1), task("T-big", 4, ["T-up"]), task("T-down", 1, ["T-big"])]
    hint = split_signals(tasks)[0]
    joined = " ".join(hint.suggested_sources)
    assert "T-up" in joined and "T-down" in joined, (
        "upstream and downstream named for dependency rewiring"
    )


def test_within_limit_silent() -> None:
    assert split_signals([task("T-1", 2), task("T-2", 1, ["T-1"])]) == []
