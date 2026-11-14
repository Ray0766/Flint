"""vibe 质量门（M4-022，冻结协议 DagValidator 注释 / S6 预算）。

- verify 覆盖率 = 有 verify_cmd 的 ai 卡占比，硬门 100%（零容忍）；
- context 预算：refs 估算 ≤40k tokens——估算口径写死：恒装 6k + 每锚点
  按引用粒度计（全文件引用 8k / 带锚点章节 2k），超算即报（宁紧勿松）；
- context_refs 为空同报（S6：执行时装载单元缺失）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final

from flint.domain.models import TaskSpec

CONTEXT_BUDGET_TOKENS: Final[int] = 40_000
_BASE_TOKENS: Final[int] = 6_000
_WHOLE_FILE_TOKENS: Final[int] = 8_000
_ANCHORED_TOKENS: Final[int] = 2_000


def estimate_context_tokens(context_refs: list[str]) -> int:
    total = _BASE_TOKENS
    for ref in context_refs:
        total += _ANCHORED_TOKENS if "#" in ref else _WHOLE_FILE_TOKENS
    return total


@dataclass
class QualityGateReport:
    verify_coverage: float
    over_budget_tasks: list[str] = field(default_factory=list)
    violations: list[str] = field(default_factory=list)
    passed: bool = False


def vibe_quality_gate(tasks: list[TaskSpec]) -> QualityGateReport:
    with_verify = [t for t in tasks if t.verify_cmd]
    coverage = len(with_verify) / len(tasks) if tasks else 0.0
    report = QualityGateReport(verify_coverage=coverage)
    for task in tasks:
        if not task.verify_cmd:
            report.violations.append(
                f"{task.task_id}: no verify_cmd (coverage gate is 100%, "
                "zero tolerance)"
            )
        refs = task.context_refs or []
        if not refs:
            report.violations.append(
                f"{task.task_id}: empty context_refs (S6 loading unit missing)"
            )
        elif estimate_context_tokens(refs) > CONTEXT_BUDGET_TOKENS:
            report.over_budget_tasks.append(task.task_id)
            report.violations.append(
                f"{task.task_id}: context estimate exceeds "
                f"{CONTEXT_BUDGET_TOKENS} tokens"
            )
    report.passed = coverage == 1.0 and not report.violations
    return report
