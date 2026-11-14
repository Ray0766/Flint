"""M2-036 acceptance tests: rule C (four necessary conditions + negation).

Acceptance (tasks.json M2-036):
  - each condition (refute executed + hit rate, coverage, >=1 aligned support)
    has its own failure-demotion case
  - any strong or unknown competitor blocks C
"""
from __future__ import annotations

from datetime import UTC, date, datetime

from flint.align.stage1 import LLMCitationAligner
from flint.competitor.coverage import CoverageResult
from flint.domain.models import JSON, Competitor, Doc
from flint.gate.rule_c import RuleCResult, evaluate_rule_c

FETCHED = datetime(2026, 7, 28, 12, 0, 0, tzinfo=UTC).isoformat()

COVERED = CoverageResult(covered=True, reason="saturated")
NOT_COVERED = CoverageResult(covered=False, reason="not_saturated")


def make_doc(i: int, title: str) -> Doc:
    return Doc(
        doc_id=f"doc-{i}", source_id="crossref", kind="paper", title=title,
        url=f"https://a/{i}", published_at=date(2026, 1, 1),
        meta={"fetched_at": FETCHED}, origin="retrieved", access="public",
    )


def comp(name: str, strength: str) -> Competitor:
    return Competitor(
        name=name, url="https://x.example/p", strength=strength,  # type: ignore[arg-type]
        strength_signals=[], pricing=None,
    )


class AlignProvider:
    def __init__(self, failing_markers: list[str]) -> None:
        self.failing_markers = failing_markers

    def generate(self, prompt: str, tools: list[JSON] | None) -> object:
        raise NotImplementedError

    def generate_structured(self, prompt: str, schema: JSON, max_retries: int) -> JSON:
        segment = prompt.split("证据（doc_id=", 1)[1]
        if any(m in segment for m in self.failing_markers):
            return {"alignment": "unsupported"}
        return {"alignment": "supports"}


def aligner(failing: list[str] | None = None) -> LLMCitationAligner:
    return LLMCitationAligner(provider=AlignProvider(failing or []))  # type: ignore[arg-type]


SUPPORT = [("市场需求存在", make_doc(1, "adoption growth study"))]


def test_all_conditions_met_satisfies_c() -> None:
    result = evaluate_rule_c(
        aligner(), SUPPORT, refute_executed=True, refute_hit_rate=0.8,
        coverage=COVERED, competitors=[comp("A", "weak"), comp("B", "moderate")],
    )
    assert isinstance(result, RuleCResult)
    assert result.satisfied is True
    assert result.failed_conditions == []
    assert result.support_doc_ids == ["doc-1"]


def test_refute_not_executed_fails() -> None:
    result = evaluate_rule_c(
        aligner(), SUPPORT, refute_executed=False, refute_hit_rate=0.0,
        coverage=COVERED, competitors=[],
    )
    assert result.satisfied is False
    assert "refute_not_executed" in result.failed_conditions


def test_refute_hit_rate_below_theta_fails() -> None:
    result = evaluate_rule_c(
        aligner(), SUPPORT, refute_executed=True, refute_hit_rate=0.5,
        coverage=COVERED, competitors=[],
    )
    assert result.satisfied is False
    assert "refute_hit_rate_below_theta" in result.failed_conditions


def test_theta_configurable() -> None:
    result = evaluate_rule_c(
        aligner(), SUPPORT, refute_executed=True, refute_hit_rate=0.5,
        coverage=COVERED, competitors=[], theta=0.4,
    )
    assert "refute_hit_rate_below_theta" not in result.failed_conditions


def test_coverage_not_met_fails() -> None:
    result = evaluate_rule_c(
        aligner(), SUPPORT, refute_executed=True, refute_hit_rate=0.8,
        coverage=NOT_COVERED, competitors=[],
    )
    assert result.satisfied is False
    assert "coverage_not_met" in result.failed_conditions


def test_no_support_evidence_fails() -> None:
    result = evaluate_rule_c(
        aligner(), [], refute_executed=True, refute_hit_rate=0.8,
        coverage=COVERED, competitors=[],
    )
    assert result.satisfied is False
    assert "no_aligned_support" in result.failed_conditions
    assert result.demote_to_d is False, "absence is a gap, not a sick judgement"


def test_failed_support_alignment_demotes_to_d() -> None:
    pairs = [("市场需求存在", make_doc(9, "offtopic essay"))]
    result = evaluate_rule_c(
        aligner(["offtopic"]), pairs, refute_executed=True, refute_hit_rate=0.8,
        coverage=COVERED, competitors=[],
    )
    assert result.satisfied is False
    assert result.demote_to_d is True
    assert "no_aligned_support" in result.failed_conditions


def test_strong_competitor_blocks_c() -> None:
    result = evaluate_rule_c(
        aligner(), SUPPORT, refute_executed=True, refute_hit_rate=0.8,
        coverage=COVERED, competitors=[comp("Goliath", "strong")],
    )
    assert result.satisfied is False
    assert "strong_or_unknown_competitor" in result.failed_conditions
    assert result.blocking_competitors == ["Goliath"]


def test_unknown_competitor_blocks_c_conservatively() -> None:
    result = evaluate_rule_c(
        aligner(), SUPPORT, refute_executed=True, refute_hit_rate=0.8,
        coverage=COVERED, competitors=[comp("Mist", "unknown")],
    )
    assert result.satisfied is False
    assert result.blocking_competitors == ["Mist"], "unknown blocks C, never treated as weak"
