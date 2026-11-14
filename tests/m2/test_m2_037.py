"""M2-037 acceptance tests: rule D fallback + gap list.

Acceptance (tasks.json M2-037):
  - landing on D always outputs a gap list + GapHint
  - missing_data vs missing_permission are split (audit 8)
"""
from __future__ import annotations

import pytest

from flint.competitor.coverage import CoverageResult
from flint.domain.models import Competitor, GapHint
from flint.gate.rule_c import RuleCResult
from flint.gate.rule_d import derive_gaps

COVERED = CoverageResult(covered=True, reason="saturated")


def comp(name: str, strength: str, url: str = "https://x.example/p") -> Competitor:
    return Competitor(
        name=name, url=url, strength=strength,  # type: ignore[arg-type]
        strength_signals=[], pricing=None,
    )


# FIX-12（v0.4.1 第 6 批）：`derive_gaps` 现在回 `DerivedGap`——
# 冻结件那一份原样装在 `.hint` 里，机器那一半（`reason_code` / `params`）并排放。
# 本文件因此把 `g.xxx` 改成 `g.hint.xxx`：**判据的意图与期望值一个都没改**，
# 变的只是取那一份的路径。唯一的例外记在
# `test_coverage_gap_carries_pending_queries` 上（那条的期望值本身过期了）。


def failed_c(*conditions: str) -> RuleCResult:
    return RuleCResult(satisfied=False, failed_conditions=list(conditions))  # type: ignore[arg-type]


def test_rule_c_failures_map_to_missing_data_gaps() -> None:
    gaps = derive_gaps(
        rule_c=failed_c("refute_not_executed", "no_aligned_support"),
        coverage=COVERED, competitors=[], missing_scopes=[],
    )
    assert len(gaps) == 2
    assert all(isinstance(g.hint, GapHint) for g in gaps)
    assert all(g.hint.cause == "missing_data" for g in gaps)
    assert all(g.hint.suggested_sources for g in gaps), "missing_data offers concrete sources"
    assert all(g.hint.required_scope is None for g in gaps)


def test_coverage_gap_carries_pending_queries() -> None:
    coverage = CoverageResult(
        covered=False, reason="queries_pending", pending_queries=["q7", "q8"]
    )
    gaps = derive_gaps(
        rule_c=failed_c("coverage_not_met"), coverage=coverage,
        competitors=[], missing_scopes=[],
    )
    assert len(gaps) == 1
    assert gaps[0].hint.suggested_sources == ["q7", "q8"]
    assert gaps[0].hint.action == "search"


def test_missing_permission_never_disguised_as_missing_data() -> None:
    gaps = derive_gaps(
        rule_c=failed_c(), coverage=COVERED, competitors=[],
        missing_scopes=["profile.finance"],
    )
    assert len(gaps) == 1
    hint = gaps[0].hint
    assert hint.cause == "missing_permission"
    assert hint.action == "request_permission"
    assert hint.required_scope == "profile.finance"
    assert hint.suggested_sources == [], "no data sources offered for a permission gap"


def test_unknown_competitors_produce_ask_user_gap() -> None:
    gaps = derive_gaps(
        rule_c=failed_c(), coverage=COVERED,
        competitors=[comp("Mist", "unknown", "https://mist.example")],
        missing_scopes=[],
    )
    assert len(gaps) == 1
    assert gaps[0].hint.action == "ask_user"
    assert gaps[0].hint.target_count == 1
    assert "Mist" in gaps[0].hint.missing_what


def test_alignment_demotion_yields_gap() -> None:
    gaps = derive_gaps(
        rule_c=failed_c(), coverage=COVERED, competitors=[],
        missing_scopes=[], alignment_demoted=True,
    )
    assert len(gaps) == 1
    assert gaps[0].hint.cause == "missing_data"
    assert gaps[0].hint.action == "upload"


def test_empty_derivation_raises() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        derive_gaps(
            rule_c=failed_c(), coverage=COVERED, competitors=[], missing_scopes=[],
        )
