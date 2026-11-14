"""估算超限拆分信号（M4-024，S5：超 2 cycles 先拆再动手）。

- cycles>2 → GapHint 指认（NEVER 自动拆——拆分是规划行为，回 tasks.json
  改卡）；suggested_sources 携上下游卡名（依赖重连提示面）。
"""
from __future__ import annotations

from flint.dag.dual_unit import MAX_AI_CYCLES
from flint.domain.models import GapHint, TaskSpec


def split_signals(tasks: list[TaskSpec]) -> list[GapHint]:
    dependents: dict[str, list[str]] = {}
    for task in tasks:
        for dep in task.depends_on:
            dependents.setdefault(dep, []).append(task.task_id)

    hints: list[GapHint] = []
    for task in tasks:
        if task.estimate_cycles is None or task.estimate_cycles <= MAX_AI_CYCLES:
            continue
        upstream = "、".join(task.depends_on) or "（无）"
        downstream = "、".join(dependents.get(task.task_id, [])) or "（无）"
        hints.append(
            GapHint(
                missing_what=(
                    f"任务 {task.task_id} 预估 {task.estimate_cycles} cycles "
                    f"超上限 {MAX_AI_CYCLES:.0f}：先拆再动手（S5）"
                ),
                cause="missing_data",
                suggested_sources=[
                    f"上游依赖重连：{upstream}",
                    f"下游依赖重连：{downstream}",
                ],
                action="ask_user",
            )
        )
    return hints
