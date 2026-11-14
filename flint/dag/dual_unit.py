"""双单位互斥必填校验（M4-021，v0.3.3 / 冻结协议 DagValidator 注释）。

- human_reader：estimate_days 必填且 ≤0.5；estimate_cycles 必空；
- ai_executor：estimate_cycles 必填且 ≤2、verify_cmd 必填（无机检验收的
  任务不允许存在）；estimate_days 必空。
违规逐卡指认。
"""
from __future__ import annotations

from typing import Literal

from flint.domain.models import TaskSpec

MAX_HUMAN_DAYS = 0.5
MAX_AI_CYCLES = 2.0


def validate_dual_unit(
    tasks: list[TaskSpec],
    audience: Literal["human_reader", "ai_executor"],
) -> list[str]:
    violations: list[str] = []
    for task in tasks:
        if audience == "ai_executor":
            if task.estimate_cycles is None:
                violations.append(
                    f"{task.task_id}: estimate_cycles mandatory for ai_executor"
                )
            elif task.estimate_cycles > MAX_AI_CYCLES:
                violations.append(
                    f"{task.task_id}: estimate_cycles {task.estimate_cycles} "
                    f"exceeds {MAX_AI_CYCLES:.0f} (split first)"
                )
            if not task.verify_cmd:
                violations.append(
                    f"{task.task_id}: verify_cmd mandatory (machine-checkable "
                    "acceptance is non-negotiable)"
                )
            if task.estimate_days is not None:
                violations.append(
                    f"{task.task_id}: estimate_days must be absent on the ai path"
                )
        else:
            if task.estimate_days is None:
                violations.append(
                    f"{task.task_id}: estimate_days mandatory for human_reader"
                )
            elif task.estimate_days > MAX_HUMAN_DAYS:
                violations.append(
                    f"{task.task_id}: estimate_days {task.estimate_days} "
                    f"exceeds {MAX_HUMAN_DAYS}"
                )
            if task.estimate_cycles is not None:
                violations.append(
                    f"{task.task_id}: estimate_cycles must be absent on the "
                    "human path"
                )
    return violations
