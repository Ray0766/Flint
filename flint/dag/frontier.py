"""关键路径与并行前沿（M4-025，S5：多 agent 并行的瓶颈是关键路径）。"""
from __future__ import annotations

from flint.domain.models import TaskSpec


def critical_path_cycles(tasks: list[TaskSpec]) -> int:
    by_id = {t.task_id: t for t in tasks}
    memo: dict[str, float] = {}

    def longest(task_id: str) -> float:
        if task_id in memo:
            return memo[task_id]
        task = by_id[task_id]
        best = max(
            (longest(d) for d in task.depends_on if d in by_id), default=0.0
        )
        memo[task_id] = best + float(task.estimate_cycles or 0)
        return memo[task_id]

    return int(max(longest(t.task_id) for t in tasks)) if tasks else 0


def ready_frontier(tasks: list[TaskSpec], done: set[str]) -> list[str]:
    return sorted(
        t.task_id
        for t in tasks
        if t.task_id not in done
        and all(dep in done for dep in t.depends_on)
    )
