"""revalidation run：完整 gate1 重跑（M3-051，v0.3.2 / 冻结协议 Revalidator）。

- verdict_shift 必须来自完整 gate1_analysis 重跑（plan→judge→validate 三
  相位纯函数全链）；VerdictShift.rerun_analysis_id 必填（build_shift 是
  全仓唯一构造点——不做启发式偏移，系统内只有一套判定逻辑，代码面由
  单构造点断言看守）。
- 档位未变 → shift=None（只检测不改状态归 M3-052 报告层）。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Final, cast

from flint.domain.models import Verdict, VerdictShift

_VERDICTS: Final[frozenset[str]] = frozenset(
    {"A_infeasible", "B_red_ocean", "C_opportunity", "D_insufficient"}
)
from flint.jobs.gate1 import (
    Gate1Deps,
    _fetch_docs_by_query,
    _flatten_docs,
    _judge_payload,
    _plan_queries,
    _validate_verdict,
)


def build_shift(old: str, new: str, rerun_analysis_id: str) -> VerdictShift:
    if not rerun_analysis_id:
        raise ValueError(
            "rerun_analysis_id is mandatory: no verdict_shift without a full "
            "gate1_analysis rerun"
        )
    if old not in _VERDICTS or new not in _VERDICTS:
        raise ValueError(f"unknown verdict in shift: {old!r} -> {new!r}")
    return VerdictShift(
        old=cast(Verdict, old), new=cast(Verdict, new),
        rerun_analysis_id=rerun_analysis_id,
    )


@dataclass
class RerunOutcome:
    new_verdict: str
    rerun_analysis_id: str
    shift: VerdictShift | None
    verdict_payload: dict[str, object]


def rerun_verdict(
    deps: Gate1Deps,
    keywords: list[str],
    locale: str,
    old_verdict: str,
    rerun_analysis_id: str,
) -> RerunOutcome:
    plan = _plan_queries(deps, keywords, locale)
    # `GATE1-DEDUP`：这里原先**自带一份 `_collect_docs` 的抄本**（同样的
    # 「逐 query 取、按 doc_id 去重」循环），而紧接着 `_judge_payload` 又取了一遍——
    # 复核这一路也在取两遍。
    #
    # 改成与 gate1 走**同一对函数**：抄本退役，取数只发生一次。
    # 两处各写一份循环的话，去重口径哪天改了只有一处会跟上。
    docs_by_query = _fetch_docs_by_query(deps, plan)
    docs = _flatten_docs(plan, docs_by_query)
    judge = _judge_payload(deps, keywords, plan, docs, docs_by_query)
    verdict_payload = _validate_verdict(deps, judge, docs)
    new_verdict = str(verdict_payload["verdict"])
    shift = (
        build_shift(old_verdict, new_verdict, rerun_analysis_id)
        if new_verdict != old_verdict
        else None
    )
    return RerunOutcome(
        new_verdict=new_verdict,
        rerun_analysis_id=rerun_analysis_id,
        shift=shift,
        verdict_payload=dict(verdict_payload),
    )
