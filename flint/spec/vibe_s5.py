"""ai 路径 vibe_pack S5 章（M4-003，技术方案 E5「生成期即校验」）。

- 表格与机读 tasks_payload 由同一 TaskSpec 集一次构建（单真相，M4-008
  的包内 tasks.json 消费 tasks_payload）。
- 入章门：flint.compose.vibe_tasks.shape_check 违规即拒，NEVER 渲染
  带违规卡的章节；空集同拒（S5 章无任务 = 生成失败信号而非空表）。
"""
from __future__ import annotations

from dataclasses import dataclass

from flint.compose.vibe_tasks import shape_check
from flint.domain.models import JSON, TaskSpec


class S5ShapeError(Exception):
    pass


@dataclass(frozen=True)
class S5Chapter:
    markdown: str
    tasks_payload: JSON


def _payload_item(task: TaskSpec) -> JSON:
    return {
        "task_id": task.task_id,
        "title": task.title,
        "inputs": list(task.inputs),
        "outputs": list(task.outputs),
        "acceptance": list(task.acceptance),
        "depends_on": list(task.depends_on),
        "milestone": task.milestone,
        "estimate_cycles": task.estimate_cycles,
        "oneshot": task.oneshot,
        "verify_cmd": task.verify_cmd,
        "context_refs": list(task.context_refs or []),
        "review_gate": task.review_gate,
    }


def build_s5(tasks: list[TaskSpec]) -> S5Chapter:
    if not tasks:
        raise S5ShapeError("empty task set: S5 chapter requires >=1 card")
    violations = shape_check(tasks)
    if violations:
        raise S5ShapeError("; ".join(violations))
    lines = [
        "## S5 Task DAG",
        "",
        f"任务 {len(tasks)} 张；机读真相 = 包内 tasks.json（与本表同源生成）。",
        "",
        "| task_id | title | cycles | verify_cmd | review_gate | depends_on |",
        "|---|---|---|---|---|---|",
    ]
    for task in tasks:
        lines.append(
            f"| {task.task_id} | {task.title} | {task.estimate_cycles} "
            f"| {task.verify_cmd} | {task.review_gate} "
            f"| {', '.join(task.depends_on) or '-'} |"
        )
    return S5Chapter(
        markdown="\n".join(lines),
        tasks_payload={"tasks": [_payload_item(t) for t in tasks]},
    )
