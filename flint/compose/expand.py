"""expand：拒绝注水的扩写（M3-027，冻结协议 ReportComposer.expand / D13 / 审8）。

- 新证据池 = 账本可用池 − 本节已引用 fact——池空即「无新证据」，返回
  GapHint 列表（missing_data 补录引导 + missing_permission 按 scope 分流，
  绝不注水扩写）。
- 有新证据 → 只把**新池**交给生成器产 block，产出仍过 ledger-only 门
  （M3-022 复用）；保护条件由调用路径（M3-028/042）守。
"""
from __future__ import annotations

from flint.compose.draft import BlockGenerator, draft_section
from flint.domain.models import Block, FactsLedger, GapHint, SectionSpec
from flint.ledger.disputed import usable_fact_pool


def expand_section(
    spec: SectionSpec,
    ledger: FactsLedger,
    cited_fact_ids: set[str],
    generator: BlockGenerator,
    missing_scopes: list[str],
) -> list[Block] | list[GapHint]:
    fresh = [
        f for f in usable_fact_pool(ledger.facts)
        if f.fact_id not in cited_fact_ids
    ]
    if not fresh:
        gaps: list[GapHint] = [
            GapHint(
                missing_what=f"章节「{spec.section_id}」无新证据可扩写",
                cause="missing_data",
                suggested_sources=["补充检索", "注入用户证据"],
                action="search",
            )
        ]
        for scope in missing_scopes:
            gaps.append(
                GapHint(
                    missing_what=f"扩写所需字段组不可访问：{scope}",
                    cause="missing_permission",
                    suggested_sources=[],
                    action="request_permission",
                    required_scope=scope,
                )
            )
        return gaps

    fresh_ledger = FactsLedger(
        ledger_id=ledger.ledger_id, project_id=ledger.project_id,
        version=ledger.version, parent_version=ledger.parent_version,
        derivation_reason=ledger.derivation_reason, facts=fresh,
        created_from=ledger.created_from, created_at=ledger.created_at,
        actor=ledger.actor,
    )
    return draft_section(spec, fresh_ledger, generator)
