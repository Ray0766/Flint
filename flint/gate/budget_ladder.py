"""B7 预算降级阶梯（M2-043，PDD v0.2 §4.7；阶梯写死、对用户可见）。

- 顺序 NEVER 参数化：L1 每 query 取回篇数 −50% → L2 扩展 query 数减半 →
  L3 非核心章节降模型档 → L4 附录类章节截断并标注。每次超限降一级，
  L4 之后仍超 → LadderExhausted（调用方置 job failed，错误码
  BUDGET_EXCEEDED——不存在 L5，也不回头重降已降级别）。
- 每级降级 MUST 写质量卡对用户可见：quality_card_entries 产出
  QualityCard.degradations 的既定文案（B7 采纳条款「阶梯写死、对用户可见」）。
- 记账来源：Job.cost_accum（M2-005 add_job_cost 通道）；本层只做
  超限判定与降级动作，不碰 DB。
- 减半下限 1：检索面绝不降到零（L1/L2 的 max(1, n // 2)）。
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Final, Literal

DegradationLevel = Literal["L1", "L2", "L3", "L4"]

LADDER: Final[tuple[DegradationLevel, ...]] = ("L1", "L2", "L3", "L4")

_DESCRIPTIONS: Final[dict[DegradationLevel, str]] = {
    "L1": "每 query 取回篇数 −50%（预算超限自动降级）",
    "L2": "扩展 query 数减半（预算超限自动降级）",
    "L3": "非核心章节降模型档（预算超限自动降级）",
    "L4": "附录类章节截断并标注（预算超限自动降级）",
}


class LadderExhausted(Exception):
    """L4 之后仍超限：降无可降，调用方置 job failed（BUDGET_EXCEEDED）。"""

    def __init__(self, budget_cny: float, cost_accum: float) -> None:
        super().__init__(
            f"budget ladder exhausted after L4: cost {cost_accum} still over "
            f"budget {budget_cny}"
        )


@dataclass(frozen=True)
class LadderAction:
    level: DegradationLevel
    description: str


@dataclass(frozen=True)
class AnalysisBudgetKnobs:
    docs_per_query: int
    expansion_queries: int
    noncore_model_tier: Literal["large", "small"]
    appendix_truncated: bool


@dataclass
class BudgetLadderState:
    budget_cny: float
    applied: list[LadderAction] = field(default_factory=list)


def next_action_if_over(
    state: BudgetLadderState, cost_accum: float
) -> LadderAction | None:
    """超限则降下一级并记入 state；未超返回 None。一次超限只降一级
    （调用点在阶段边界重查记账，与 D4 阶段边界语义一致）。"""
    if cost_accum <= state.budget_cny:
        return None
    if len(state.applied) >= len(LADDER):
        raise LadderExhausted(state.budget_cny, cost_accum)
    level = LADDER[len(state.applied)]
    action = LadderAction(level=level, description=_DESCRIPTIONS[level])
    state.applied.append(action)
    return action


def apply_action(
    action: LadderAction, knobs: AnalysisBudgetKnobs
) -> AnalysisBudgetKnobs:
    if action.level == "L1":
        return replace(knobs, docs_per_query=max(1, knobs.docs_per_query // 2))
    if action.level == "L2":
        return replace(knobs, expansion_queries=max(1, knobs.expansion_queries // 2))
    if action.level == "L3":
        return replace(knobs, noncore_model_tier="small")
    return replace(knobs, appendix_truncated=True)


def quality_card_entries(state: BudgetLadderState) -> list[str]:
    """QualityCard.degradations 进账文案（每级降级对用户可见，B7 硬条款）。"""
    return [f"{a.level}：{a.description}" for a in state.applied]
