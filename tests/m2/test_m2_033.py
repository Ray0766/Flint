"""M2-033 acceptance tests: competitor scan coverage decision.

Acceptance (tasks.json M2-033):
  - all planned queries executed + marginal new competitors <1 => saturated
  - confirmed-empty needs hit rate >= theta_rel
  - unknown competitor list yields GapHint material
"""
from __future__ import annotations

from flint.competitor.coverage import (
    CoverageResult,
    QueryExecution,
    assess_coverage,
    unknown_competitor_gap,
)
from flint.domain.models import Competitor, GapHint


def executed(text: str, new: int) -> QueryExecution:
    return QueryExecution(query_text=text, executed=True, new_competitors=new)


def comp(name: str, strength: str, url: str = "https://x.example/p") -> Competitor:
    return Competitor(
        name=name, url=url, strength=strength,  # type: ignore[arg-type]
        strength_signals=[], pricing=None,
    )


def test_saturated_when_all_executed_and_marginal_below_one() -> None:
    result = assess_coverage(
        [executed("q1", 4), executed("q2", 2), executed("q3", 0)],
        total_competitors=6, hit_rate=0.9,
    )
    assert isinstance(result, CoverageResult)
    assert result.covered is True
    assert result.reason == "saturated"


def test_pending_query_blocks_coverage() -> None:
    result = assess_coverage(
        [executed("q1", 3), QueryExecution("q2", executed=False, new_competitors=0)],
        total_competitors=3, hit_rate=0.9,
    )
    assert result.covered is False
    assert result.reason == "queries_pending"
    assert result.pending_queries == ["q2"]


def test_not_saturated_when_last_query_still_adds() -> None:
    result = assess_coverage(
        [executed("q1", 4), executed("q2", 2)], total_competitors=6, hit_rate=0.9
    )
    assert result.covered is False
    assert result.reason == "not_saturated"


def test_confirmed_empty_requires_hit_rate_at_theta() -> None:
    ok = assess_coverage([executed("q1", 0)], total_competitors=0, hit_rate=0.7)
    assert ok.covered is True and ok.reason == "confirmed_empty"

    low = assess_coverage([executed("q1", 0)], total_competitors=0, hit_rate=0.3)
    assert low.covered is False and low.reason == "empty_unconfirmed"


def test_theta_configurable_for_empty_confirmation() -> None:
    result = assess_coverage(
        [executed("q1", 0)], total_competitors=0, hit_rate=0.35, theta=0.3
    )
    assert result.covered is True


def test_unknown_competitors_yield_gap_hint() -> None:
    competitors = [
        comp("Alpha", "unknown", "https://alpha.example"),
        comp("Beta", "moderate"),
        comp("Gamma", "unknown", "https://gamma.example"),
    ]
    hint = unknown_competitor_gap(competitors)
    assert isinstance(hint, GapHint)
    assert hint.cause == "missing_data"
    assert hint.action == "ask_user"
    assert hint.target_count == 2
    assert "Alpha" in hint.missing_what and "Gamma" in hint.missing_what
    assert hint.suggested_sources == ["https://alpha.example", "https://gamma.example"]


def test_no_unknowns_no_gap() -> None:
    assert unknown_competitor_gap([comp("Beta", "weak")]) is None
