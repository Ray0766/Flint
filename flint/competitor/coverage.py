"""竞品扫描覆盖判定（M2-033，PDD v0.3.1 §2.2）。

覆盖达标 = 计划 query 全部执行，且满足其一：
- 去重后结果饱和：最后一条已执行 query 的边际新竞品 <1（计数为整数，
  即最后一条 query 新增 0 个竞品）；
- 确认空集：总竞品数为 0 且该轮相关率 >= θ_rel——排除「没搜到是因为
  没搜对」（相关率不达标时空集不可信，交 M2-023 改写重检）。
unknown 竞品清单在此产出 GapHint 素材（missing_data → 人工确认规模与
定价），由 C 档阻断（M2-036）与 D 兜底（M2-037）消费。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from flint.domain.models import Competitor, GapHint
from flint.retrieval.relevance import THETA_REL

CoverageReason = Literal[
    "saturated",
    "confirmed_empty",
    "queries_pending",
    "not_saturated",
    "empty_unconfirmed",
]


@dataclass(frozen=True)
class QueryExecution:
    query_text: str
    executed: bool
    new_competitors: int  # 该 query 执行后去重新增的竞品数


@dataclass
class CoverageResult:
    covered: bool
    reason: CoverageReason
    pending_queries: list[str] = field(default_factory=list)


def assess_coverage(
    executions: list[QueryExecution],
    total_competitors: int,
    hit_rate: float,
    theta: float = THETA_REL,
) -> CoverageResult:
    pending = [e.query_text for e in executions if not e.executed]
    if pending:
        return CoverageResult(
            covered=False, reason="queries_pending", pending_queries=pending
        )
    if total_competitors == 0:
        if hit_rate >= theta:
            return CoverageResult(covered=True, reason="confirmed_empty")
        return CoverageResult(covered=False, reason="empty_unconfirmed")
    if executions and executions[-1].new_competitors < 1:
        return CoverageResult(covered=True, reason="saturated")
    return CoverageResult(covered=False, reason="not_saturated")


def unknown_competitor_gap(competitors: list[Competitor]) -> GapHint | None:
    """unknown 竞品 → 人工确认素材（PDD §2.2：GapHint 指向规模与定价确认）。"""
    unknown = [c for c in competitors if c.strength == "unknown"]
    if not unknown:
        return None
    names = "、".join(c.name for c in unknown)
    return GapHint(
        missing_what=f"竞品规模与定价确认：{names}",
        cause="missing_data",
        suggested_sources=[c.url for c in unknown],
        action="ask_user",
        target_count=len(unknown),
    )
