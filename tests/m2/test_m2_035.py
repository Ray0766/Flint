"""M2-035 acceptance tests: rule B (count OR strength dual path).

Acceptance (tasks.json M2-035):
  - >=3 competitors each with reachable source triggers B
  - >=1 strong competitor alone triggers B (separate cases per path)
"""
from __future__ import annotations

from flint.domain.models import Competitor
from flint.gate.rule_b import COUNT_THRESHOLD, RuleBResult, evaluate_rule_b


def comp(name: str, strength: str, url: str = "https://x.example/p") -> Competitor:
    return Competitor(
        name=name, url=url, strength=strength,  # type: ignore[arg-type]
        strength_signals=[], pricing=None,
    )


def test_count_path_three_reachable() -> None:
    result = evaluate_rule_b(
        [comp("A", "weak"), comp("B", "moderate"), comp("C", "weak")]
    )
    assert isinstance(result, RuleBResult)
    assert result.satisfied is True
    assert result.by_count is True and result.by_strength is False
    assert result.reachable_count == 3


def test_strength_path_single_strong() -> None:
    result = evaluate_rule_b([comp("Goliath", "strong")])
    assert result.satisfied is True
    assert result.by_strength is True and result.by_count is False
    assert result.strong_names == ["Goliath"]


def test_two_weak_not_satisfied() -> None:
    result = evaluate_rule_b([comp("A", "weak"), comp("B", "weak")])
    assert result.satisfied is False
    assert result.by_count is False and result.by_strength is False


def test_unreachable_source_excluded_from_count() -> None:
    result = evaluate_rule_b(
        [comp("A", "weak"), comp("B", "weak"), comp("C", "weak", url="ftp://mirror")]
    )
    assert result.reachable_count == 2
    assert result.satisfied is False, "count path needs reachable web sources"


def test_both_paths_can_fire_together() -> None:
    result = evaluate_rule_b(
        [comp("A", "strong"), comp("B", "moderate"), comp("C", "weak")]
    )
    assert result.by_count is True and result.by_strength is True
    assert result.satisfied is True


def test_count_threshold_locked_at_three() -> None:
    assert COUNT_THRESHOLD == 3
