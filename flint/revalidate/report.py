"""复核报告：只检测不改状态（M3-052，D6 / 冻结件 RevalidationReport）。

- build_report 纯函数：完整重跑（M3-051）+ 新旧对比（新论文/新竞品按已知
  集过滤、热度逐键 old/new 摊平、verdict_shift 携重跑 id）→ 报告实体；
  accepted=None（应用归 accept，M3-053）——账本与交付物零触碰。
"""
from __future__ import annotations

from datetime import datetime
from typing import cast

from flint.domain.models import JSON, RevalidationReport, RevalidationTrigger
from flint.jobs.gate1 import Gate1Deps
from flint.revalidate.run import rerun_verdict


def build_report(
    deps: Gate1Deps,
    report_id: str,
    deliverable_id: str,
    keywords: list[str],
    locale: str,
    old_verdict: str,
    rerun_analysis_id: str,
    known_paper_ids: set[str],
    known_competitor_names: set[str],
    old_heat: JSON,
    new_heat: JSON,
    trigger: RevalidationTrigger,
    generated_at: datetime,
) -> RevalidationReport:
    outcome = rerun_verdict(
        deps, keywords, locale, old_verdict, rerun_analysis_id
    )
    payload = outcome.verdict_payload
    key_citation_ids = cast("list[str]", payload.get("key_citation_ids", []))
    competitors = cast(
        "list[dict[str, object]]", payload.get("competitors", [])
    )
    new_papers = [
        doc_id for doc_id in key_citation_ids if doc_id not in known_paper_ids
    ]
    new_competitors = [
        str(comp["name"])
        for comp in competitors
        if str(comp["name"]) not in known_competitor_names
    ]
    heat_shift: JSON = {
        key: {"old": old_heat.get(key), "new": new_heat.get(key)}
        for key in sorted({*old_heat, *new_heat})
    }
    return RevalidationReport(
        report_id=report_id,
        deliverable_id=deliverable_id,
        new_papers=new_papers,
        new_competitors=new_competitors,
        heat_shift=heat_shift,
        verdict_shift=outcome.shift,
        trigger=trigger,
        generated_at=generated_at,
        accepted=None,
    )
