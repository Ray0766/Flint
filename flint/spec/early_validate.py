"""生成期校验前移（M4-017，技术方案 E5「生成时即校验」）。

- proposal job 内 S3/S5 产物生成时即校验：S5 走 shape_check（M3-031
  形校验）、S3 走 registry 门（M4-016）——错误比导出门禁早暴露一个阶段。
- 不通过 → 对应章 GapHint（章级缺口，job 不带病继续该章）；两章独立
  判定互不遮蔽。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from flint.compose.vibe_tasks import shape_check
from flint.domain.models import GapHint, TaskSpec
from flint.registry.batch import BatchReport
from flint.registry.gate import registry_pack_gate


@dataclass(frozen=True)
class EarlyValidation:
    ok: bool
    s3_gap: GapHint | None
    s5_gap: GapHint | None
    violations: list[str]


def validate_s5_at_build(tasks: list[TaskSpec]) -> tuple[GapHint | None, list[str]]:
    violations = shape_check(tasks)
    if not violations:
        return None, []
    return (
        GapHint(
            missing_what=(
                f"S5 任务卡形校验未过（{len(violations)} 项违规），"
                "章暂缺待修"
            ),
            cause="missing_data",
            suggested_sources=["重生成本章任务卡", "人工修正违规卡"],
            action="search",
        ),
        [f"S5: {v}" for v in violations],
    )


def validate_s3_at_build(
    report: BatchReport,
    audience: Literal["human_reader", "ai_executor"] = "ai_executor",
) -> tuple[GapHint | None, list[str]]:
    result = registry_pack_gate(report, audience)
    if not result.violations:
        return None, []
    gap = result.gap or GapHint(
        missing_what="S3 锁版清单存在不存在包，替换未决",
        cause="missing_data",
        suggested_sources=["提供替换包名（经 registry 校验）"],
        action="ask_user",
    )
    return gap, [f"S3: {v}" for v in result.violations]


def early_validate(
    tasks: list[TaskSpec], report: BatchReport
) -> EarlyValidation:
    s5_gap, s5_violations = validate_s5_at_build(tasks)
    s3_gap, s3_violations = validate_s3_at_build(report)
    violations = s3_violations + s5_violations
    return EarlyValidation(
        ok=not violations, s3_gap=s3_gap, s5_gap=s5_gap,
        violations=violations,
    )
