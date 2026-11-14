"""inputs 溯源校验（M4-020，冻结件 TaskSpec.inputs 注释）。

- 合法 inputs = 传递闭包内前置任务的 outputs ∪ 外部既有物白名单；
  其余为悬空（逐卡指认）。旁支任务产物不经依赖边不可直取（溯源纪律：
  S6 的 inputs 装载清单以此为界）。
"""
from __future__ import annotations

from flint.domain.models import TaskSpec


def _transitive_outputs(
    task: TaskSpec, by_id: dict[str, TaskSpec]
) -> set[str]:
    seen: set[str] = set()
    outputs: set[str] = set()
    stack = [d for d in task.depends_on if d in by_id]
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        predecessor = by_id[current]
        outputs.update(predecessor.outputs)
        stack.extend(d for d in predecessor.depends_on if d in by_id)
    return outputs


def validate_inputs(
    tasks: list[TaskSpec], external: set[str]
) -> list[str]:
    by_id = {t.task_id: t for t in tasks}
    violations: list[str] = []
    for task in tasks:
        allowed = _transitive_outputs(task, by_id) | external
        for item in task.inputs:
            if item not in allowed:
                violations.append(
                    f"{task.task_id}: input {item!r} is neither a predecessor "
                    "output nor whitelisted external"
                )
    return violations
