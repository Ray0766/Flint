"""M4-003 acceptance tests: ai-path vibe_pack S5 chapter.

Acceptance (tasks.json M4-003):
  - S5 chapter rendered from the TaskSpec set (table + machine tasks.json
    payload kept in sync from the same source)
  - shape_check-violating cards NEVER enter the chapter (build-time gate, E5)
"""
from __future__ import annotations

import pytest

from flint.domain.models import TaskSpec
from flint.spec.vibe_s5 import S5ShapeError, build_s5

pytestmark = pytest.mark.compose


def ai_card(task_id: str, cycles: float, depends_on: list[str]) -> TaskSpec:
    return TaskSpec(
        task_id=task_id, title=f"任务 {task_id}",
        inputs=["repo-skeleton"], outputs=[f"mod.{task_id}"],
        acceptance=["验收一"], depends_on=depends_on,
        milestone="M1", estimate_days=None, estimate_cycles=cycles,
        oneshot=True, verify_cmd=f"pytest tests/test_{task_id}.py -q",
        context_refs=["contracts/models.py#TaskSpec"], review_gate=False,
    )


def test_chapter_and_payload_from_same_source() -> None:
    tasks = [ai_card("T-1", 1, []), ai_card("T-2", 2, ["T-1"])]
    chapter = build_s5(tasks)
    assert chapter.markdown.startswith("## S5 Task DAG")
    for task in tasks:
        row = next(
            line for line in chapter.markdown.splitlines()
            if line.startswith(f"| {task.task_id} ")
        )
        assert task.verify_cmd in row
    payload_ids = [
        str(item["task_id"])
        for item in chapter.tasks_payload["tasks"]  # type: ignore[union-attr, index]
    ]
    assert payload_ids == ["T-1", "T-2"], "table and payload share one source"
    assert "tasks.json" in chapter.markdown, "machine-truth pointer stated"


def test_violating_cards_never_enter_chapter() -> None:
    bad = [ai_card("T-1", 3.0, []), ai_card("T-2", 1, ["ghost"])]
    with pytest.raises(S5ShapeError) as err:
        build_s5(bad)
    joined = str(err.value)
    assert "estimate_cycles" in joined and "ghost" in joined


def test_empty_set_rejected() -> None:
    with pytest.raises(S5ShapeError, match="empty"):
        build_s5([])
