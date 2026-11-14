"""human 路径 spec_export（M4-002，冻结件 SpecExporter / v0.3.3 受众分叉）。

- human_reader 独立产 spec 类 Deliverable；ai_executor 无独立 spec——
  该能力并入 vibe_pack S5~S7 章（protocols.py#SpecExporter 明文），
  在此入口即拒。
- 分叉不混排：human spec 内出现 ai 双单位卡（estimate_cycles 侧）即拒，
  反向由 vibe_tasks shape_check 把守。
- 每条目将 acceptance 逐项标注为测试断言候选（编号 + 原文，不改写）。
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass

from flint.domain.models import DeliverableType, TaskSpec
from flint.spec.store import PgSpecStore


class SpecExportForkError(Exception):
    pass


@dataclass(frozen=True)
class SpecEntry:
    task: TaskSpec
    assertions: list[str]


def plan_spec_deliverable(audience: str | None) -> DeliverableType:
    if audience == "human_reader":
        return "spec"
    if audience == "ai_executor":
        raise SpecExportForkError(
            "ai_executor has no standalone spec deliverable: "
            "the capability is merged into vibe_pack S5~S7"
        )
    raise SpecExportForkError(
        "audience is mandatory with no default: human_reader | ai_executor"
    )


def build_entries(tasks: list[TaskSpec]) -> list[SpecEntry]:
    mixed = [t.task_id for t in tasks if t.estimate_cycles is not None]
    if mixed:
        raise SpecExportForkError(
            f"ai_executor-unit cards in human spec export: {mixed}"
        )
    return [
        SpecEntry(
            task=task,
            assertions=[
                f"断言候选 {i}/{len(task.acceptance)}：{item}"
                for i, item in enumerate(task.acceptance, start=1)
            ],
        )
        for task in tasks
    ]


class PgHumanSpecExporter:
    """冻结件 SpecExporter 的 human 路径实现（spec_set_id := project_id）。"""

    def __init__(self, dsn: str) -> None:
        self._store = PgSpecStore(dsn)

    def export(self, project_id: str) -> list[TaskSpec]:
        return asyncio.run(self._store.load_set(project_id))
