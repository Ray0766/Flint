"""DagValidator 装配（M4-023，冻结协议 DagValidator）。

- validate(tasks) 一次聚合：图核心（环/孤儿/不可达）+ inputs 溯源 +
  双单位互斥 + vibe 质量门 → 冻结 DagReport（errors 聚合全量）。
- allow_reference_days（默认 False）：S5 明文「人日字段为参考值，NEVER
  用于排期」——本仓自用 tasks.json 的 ai 卡带参考人日属该口径，自校验时
  豁免 days-互斥项；**新生成的执行包不豁免**（vibe_tasks 生成器本就产
  days=None，豁免位不给生成路径）。
"""
from __future__ import annotations

from typing import Literal

from flint.dag.dual_unit import validate_dual_unit
from flint.dag.graph import analyze_graph
from flint.dag.inputs import validate_inputs
from flint.dag.quality_gate import vibe_quality_gate
from flint.domain.models import DagReport, TaskSpec


def validate(
    tasks: list[TaskSpec],
    audience: Literal["human_reader", "ai_executor"] = "ai_executor",
    external_inputs: set[str] | None = None,
    allow_reference_days: bool = False,
    exit_ids: set[str] | None = None,
) -> DagReport:
    graph = analyze_graph(tasks, exit_ids=exit_ids)
    errors = list(graph.errors)
    errors.extend(validate_inputs(tasks, external_inputs or set()))

    dual = validate_dual_unit(tasks, audience)
    if allow_reference_days:
        dual = [v for v in dual if "estimate_days must be absent" not in v]
    errors.extend(dual)

    if audience == "ai_executor":
        gate = vibe_quality_gate(tasks)
        errors.extend(gate.violations)

    return DagReport(
        acyclic=graph.acyclic,
        orphans=graph.orphans,
        unreachable=graph.unreachable,
        errors=errors,
    )
