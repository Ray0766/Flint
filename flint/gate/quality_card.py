"""质量卡组装（M2-048，冻结件 QualityCard 全字段；v0.2 F4 + v0.3.1 §3.3）。

- 十二字段单点组装：证据统计三项由 docs 推导；对齐率/引用覆盖率由上游
  评测面传入（只统计 author=="system" 的口径归 M3 block 层，本层收数字）；
  降级记录来自 B7 阶梯（M2-043 文案原样进卡，对用户可见）；盲区声明来自
  GapHint 清单与维度停摆（M2-050）。
- blocking_reviews_open 联动位就绪：参数直通进卡（审11「未清零则导出被拒」
  的导出门禁归 M3 Renderer，本层保证数字在卡上）。
- reproducible：发生过删除（RedactionRecord，审9）→ False，质量卡如实标注。
"""
from __future__ import annotations

from datetime import date

from flint.domain.models import Doc, GapHint, QualityCard
from flint.gate.budget_ladder import BudgetLadderState, quality_card_entries


def evidence_age_median_days(docs: list[Doc], today: date) -> int:
    ages = sorted(
        (today - d.published_at).days for d in docs if d.published_at is not None
    )
    if not ages:
        return 0
    middle = len(ages) // 2
    if len(ages) % 2 == 1:
        return ages[middle]
    return (ages[middle - 1] + ages[middle]) // 2


def blind_spot_statements(
    gaps: list[GapHint], outage_statements: list[str]
) -> list[str]:
    return [g.missing_what for g in gaps] + list(outage_statements)


def build_quality_card(
    docs: list[Doc],
    today: date,
    citation_coverage: float,
    alignment_rate: float,
    ladder: BudgetLadderState,
    gaps: list[GapHint],
    outage_statements: list[str],
    disputed_facts: int,
    blocking_reviews_open: int,
    price_data_notes: list[str],
    has_redactions: bool,
) -> QualityCard:
    user_supplied = [d for d in docs if d.origin == "user_provided"]
    private = [d for d in docs if d.access == "private"]
    return QualityCard(
        evidence_count=len(docs),
        evidence_age_median_days=evidence_age_median_days(docs, today),
        citation_coverage=citation_coverage,
        alignment_rate=alignment_rate,
        degradations=quality_card_entries(ladder),
        user_supplied_evidence_count=len(user_supplied),
        private_evidence_ratio=(len(private) / len(docs)) if docs else 0.0,
        disputed_facts=disputed_facts,
        blocking_reviews_open=blocking_reviews_open,
        price_data_notes=list(price_data_notes),
        blind_spots=blind_spot_statements(gaps, outage_statements),
        reproducible=not has_redactions,
    )
