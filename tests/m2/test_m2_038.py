"""M2-038 acceptance tests: verdict order engine (A>B>C>D + all_satisfied).

Acceptance (tasks.json M2-038):
  - order is hardwired; all_satisfied records every tier hit
  - A+B simultaneously satisfied shows A with B expandable
    (four-tier symmetric matrix)
"""
from __future__ import annotations

import pytest

from flint.domain.models import Competitor, GapHint, VerdictResult
from flint.gate.engine import VERDICT_ORDER, decide
from flint.gate.rule_a import RuleAResult
from flint.gate.rule_b import RuleBResult
from flint.gate.rule_c import RuleCResult


def rule_a(satisfied: bool, demote: bool = False) -> RuleAResult:
    return RuleAResult(
        satisfied=satisfied, demote_to_d=demote,
        refute_doc_ids=["doc-a1"] if satisfied else [],
    )


def rule_b(satisfied: bool) -> RuleBResult:
    return RuleBResult(
        satisfied=satisfied, by_count=satisfied, by_strength=False,
        reachable_count=3 if satisfied else 0,
    )


def rule_c(satisfied: bool, demote: bool = False) -> RuleCResult:
    return RuleCResult(
        satisfied=satisfied, demote_to_d=demote,
        support_doc_ids=["doc-c1"] if satisfied else [],
    )


GAP = GapHint(
    missing_what="证伪检索未执行", cause="missing_data",
    suggested_sources=["refute 模板族检索"], action="search",
)

COMPETITORS = [
    Competitor(name="A", url="https://a.example", strength="moderate",
               strength_signals=["active_last_12m"], pricing=None),
]


def test_order_is_hardwired() -> None:
    assert VERDICT_ORDER == (
        "A_infeasible", "B_red_ocean", "C_opportunity", "D_insufficient"
    )


@pytest.mark.parametrize(
    ("a", "b", "c", "expected_verdict", "expected_all"),
    [
        (True, True, False, "A_infeasible", ["A_infeasible", "B_red_ocean"]),
        (True, False, False, "A_infeasible", ["A_infeasible"]),
        (False, True, False, "B_red_ocean", ["B_red_ocean"]),
        (False, False, True, "C_opportunity", ["C_opportunity"]),
        (False, False, False, "D_insufficient", ["D_insufficient"]),
        (True, True, True, "A_infeasible",
         ["A_infeasible", "B_red_ocean", "C_opportunity"]),
    ],
)
def test_four_tier_symmetric_matrix(
    a: bool, b: bool, c: bool, expected_verdict: str, expected_all: list[str]
) -> None:
    result = decide(
        rule_a(a), rule_b(b), rule_c(c), gaps=[GAP], competitors=COMPETITORS
    )
    assert isinstance(result, VerdictResult)
    assert result.verdict == expected_verdict
    assert result.all_satisfied == expected_all


def test_a_plus_b_shows_a_with_b_expandable() -> None:
    result = decide(
        rule_a(True), rule_b(True), rule_c(False), gaps=[], competitors=COMPETITORS
    )
    assert result.verdict == "A_infeasible"
    assert "B_red_ocean" in result.all_satisfied, "B stays expandable in the record"
    assert result.key_citation_ids == ["doc-a1"]


def test_c_verdict_cites_support_evidence() -> None:
    result = decide(
        rule_a(False), rule_b(False), rule_c(True), gaps=[], competitors=[]
    )
    assert result.verdict == "C_opportunity"
    assert result.key_citation_ids == ["doc-c1"]


def test_alignment_demotion_forces_d_over_satisfied_b() -> None:
    result = decide(
        rule_a(False, demote=True), rule_b(True), rule_c(False),
        gaps=[GAP], competitors=COMPETITORS,
    )
    assert result.verdict == "D_insufficient"
    assert result.all_satisfied == ["D_insufficient"]
    assert result.constraints_checked["demoted_by_alignment"] is True


def test_d_without_gaps_raises() -> None:
    with pytest.raises(ValueError, match="gap"):
        decide(rule_a(False), rule_b(False), rule_c(False), gaps=[], competitors=[])


def test_constraints_checked_records_every_rule() -> None:
    result = decide(
        rule_a(True), rule_b(True), rule_c(False), gaps=[], competitors=COMPETITORS
    )
    checked = result.constraints_checked
    assert checked["order"] == list(VERDICT_ORDER)
    assert checked["rule_a"]["satisfied"] is True
    assert checked["rule_b"]["by_count"] is True
    assert checked["rule_c"]["satisfied"] is False
    assert result.competitors == COMPETITORS
