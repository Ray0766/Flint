"""dag 图核心（M4-019，冻结协议 DagValidator / 冻结件 DagReport）。

- 环检出携路径指认（errors 内 A -> B -> A 形态）；
- 孤儿 = 无人依赖且非出口终端；出口由调用方显式声明（exit_ids）——
  未声明时回退深度启发式（最深终端 = 出口，并列全算）；
- 不可达 = 依赖了未知任务的卡（依赖悬空即无法调度）。
"""
from __future__ import annotations

from flint.domain.models import DagReport, TaskSpec


def analyze_graph(
    tasks: list[TaskSpec], exit_ids: set[str] | None = None
) -> DagReport:
    by_id = {t.task_id: t for t in tasks}
    errors: list[str] = []

    unreachable: list[str] = []
    for task in tasks:
        for dep in task.depends_on:
            if dep not in by_id:
                unreachable.append(task.task_id)
                errors.append(
                    f"{task.task_id}: unknown dependency {dep} (unschedulable)"
                )
                break

    state: dict[str, int] = {}
    stack: list[str] = []
    acyclic = True

    def visit(task_id: str) -> None:
        nonlocal acyclic
        if state.get(task_id) == 2:
            return
        if state.get(task_id) == 1:
            cycle_start = stack.index(task_id)
            path = " -> ".join([*stack[cycle_start:], task_id])
            errors.append(f"cycle: {path}")
            acyclic = False
            return
        state[task_id] = 1
        stack.append(task_id)
        for dep in by_id[task_id].depends_on:
            if dep in by_id:
                visit(dep)
        stack.pop()
        state[task_id] = 2

    for task in tasks:
        visit(task.task_id)

    depended = {dep for t in tasks for dep in t.depends_on}
    terminals = sorted(t.task_id for t in tasks if t.task_id not in depended)

    depth_memo: dict[str, int] = {}

    def depth(task_id: str) -> int:
        if task_id in depth_memo:
            return depth_memo[task_id]
        deps = [d for d in by_id[task_id].depends_on if d in by_id]
        depth_memo[task_id] = 1 + max((depth(d) for d in deps), default=0)
        return depth_memo[task_id]

    orphans: list[str] = []
    if len(terminals) > 1 and acyclic:
        if exit_ids is not None:
            orphans = [t for t in terminals if t not in exit_ids]
        else:
            deepest = max(depth(t) for t in terminals)
            orphans = [t for t in terminals if depth(t) < deepest]

    return DagReport(
        acyclic=acyclic,
        orphans=orphans,
        unreachable=sorted(set(unreachable)),
        errors=errors,
    )
