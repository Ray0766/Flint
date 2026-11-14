"""M4-008 acceptance tests: pack tasks.json machine export.

Acceptance (tasks.json M4-008):
  - pack tasks.json and the S5 chapter share one source of truth
    (mutual validation)
  - dag_report attached (acyclic + critical path data)
"""
from __future__ import annotations

import json

import pytest

from flint.domain.models import TaskSpec
from flint.spec.tasks_json import TasksJsonExportError, export_tasks_json
from flint.spec.vibe_s5 import S5Chapter, build_s5

pytestmark = pytest.mark.compose


def ai_card(task_id: str, cycles: float, depends_on: list[str]) -> TaskSpec:
    return TaskSpec(
        task_id=task_id, title=f"任务 {task_id}", inputs=["repo-skeleton"],
        outputs=[f"mod.{task_id}"], acceptance=["验收一"],
        depends_on=depends_on, milestone="M1", estimate_days=None,
        estimate_cycles=cycles, oneshot=True,
        verify_cmd=f"pytest tests/test_{task_id}.py -q",
        context_refs=["contracts/models.py#TaskSpec"], review_gate=False,
    )


def test_export_carries_dag_report_and_tasks() -> None:
    chapter = build_s5(
        [ai_card("T-1", 1, []), ai_card("T-2", 2, ["T-1"]), ai_card("T-3", 1, ["T-2"])]
    )
    data = json.loads(export_tasks_json(chapter))
    assert [t["task_id"] for t in data["tasks"]] == ["T-1", "T-2", "T-3"]
    report = data["dag_report"]
    assert report == {
        "tasks": 3, "acyclic": True,
        "critical_path_cycles": 4, "total_cycles": 4.0,
    }


def test_table_payload_divergence_rejected() -> None:
    chapter = build_s5([ai_card("T-1", 1, []), ai_card("T-2", 1, ["T-1"])])
    lines = [
        line for line in chapter.markdown.splitlines()
        if not line.startswith("| T-2 ")
    ]
    tampered = S5Chapter(
        markdown="\n".join(lines), tasks_payload=chapter.tasks_payload
    )
    with pytest.raises(TasksJsonExportError, match="diverged"):
        export_tasks_json(tampered)


def test_count_line_divergence_rejected() -> None:
    chapter = build_s5([ai_card("T-1", 1, [])])
    tampered = S5Chapter(
        markdown=chapter.markdown.replace("任务 1 张", "任务 2 张"),
        tasks_payload=chapter.tasks_payload,
    )
    with pytest.raises(TasksJsonExportError, match="count"):
        export_tasks_json(tampered)
