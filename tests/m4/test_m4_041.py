"""M4-041 acceptance tests: real ratio deviation instrument (carried cond 2).

Acceptance (tasks.json M4-041):
  - N>=12 real compositions: actual rendered word-count ratios vs declared
    shares, relative deviation <=±15% with trail
  - same instrument; honestly blocked when unavailable

Offline scope: instrument mechanics (measured counts, not construction
identity; shared line; N>=12 gate; empty rendering rejected).
"""
from __future__ import annotations

import pytest

from eval.doc_metrics import RATIO_DEVIATION_LINE, TEMPLATES
from eval.real_ratio import real_ratio_report, word_count
from eval.semantic_answers import Composition, InsufficientCompositions
from flint.compose.templates import load_template

pytestmark = pytest.mark.compose


def proportional_composition(cid: str, skew: float = 1.0) -> Composition:
    spec, _sections = load_template(TEMPLATES / "generic.yaml")
    sections: dict[str, str] = {}
    for i, (sid, ratio) in enumerate(spec.sections):
        chars = max(1, round(ratio.share * 997 * (skew if i == 0 else 1.0)))
        sections[sid] = "字" * chars
    return Composition(
        composition_id=cid, template_id="generic", sections=sections
    )


def test_measured_ratios_not_construction_identity() -> None:
    sample = [proportional_composition(f"c-{i:02d}") for i in range(12)]
    report = real_ratio_report(sample)
    assert report.n_compositions == 12
    assert report.meets_line is True
    assert report.worst_deviation <= RATIO_DEVIATION_LINE
    assert all(0 < r.actual_share < 1 for r in report.records)
    assert report.worst_deviation > 0.0, (
        "measured from text: rounding noise present, no identity zero"
    )


def test_skewed_rendering_breaks_the_line() -> None:
    sample = [proportional_composition(f"c-{i:02d}", skew=3.0) for i in range(12)]
    report = real_ratio_report(sample)
    assert report.meets_line is False
    worst = max(report.records, key=lambda r: r.relative_deviation)
    assert worst.relative_deviation == report.worst_deviation
    assert worst.relative_deviation > RATIO_DEVIATION_LINE


def test_n_below_12_blocked() -> None:
    with pytest.raises(InsufficientCompositions, match="5"):
        real_ratio_report(
            [proportional_composition(f"c-{i}") for i in range(5)]
        )


def test_empty_rendering_rejected() -> None:
    empty = Composition(
        composition_id="c-empty", template_id="generic", sections={}
    )
    sample = [proportional_composition(f"c-{i:02d}") for i in range(11)]
    with pytest.raises(InsufficientCompositions, match="empty"):
        real_ratio_report([*sample, empty])


def test_word_count_cjk_and_latin() -> None:
    assert word_count("市场规模一亿") == 6
    assert word_count("ARR grows 3x") == 3
    assert word_count("规模 1 亿，ARR 双位数") == 8


def test_bounds_checked_against_template_min_max() -> None:
    """Step-4 remediation: report must surface sections outside the
    template's own min_words/max_words (words-unit sections)."""
    sample = [proportional_composition(f"c-{i:02d}") for i in range(12)]
    report = real_ratio_report(sample)
    # 997-char scale => generic summary ~100 chars < min_words 300:
    # every words-unit section undersized must be itemized
    assert report.bound_violations, "under-min sections must be surfaced"
    assert any(
        "summary" in v and "min" in v for v in report.bound_violations
    ), report.bound_violations[:3]


def test_tokens_unit_sections_reported_as_conflict_not_checked() -> None:
    spec_comp = Composition(
        composition_id="c-vibe", template_id="vibe_pack",
        sections={"S1_charter": "字" * 100},
    )
    sample = [proportional_composition(f"c-{i:02d}") for i in range(11)]
    report = real_ratio_report([*sample, spec_comp])
    assert any(
        "S1_charter" in c and "tokens" in c for c in report.unit_conflicts
    ), "tokens-unit sections go to the conflict list, never char-checked"
    assert not any("S1_charter" in v for v in report.bound_violations)


def test_usable_for_gate_conjunction() -> None:
    """Ruling 1-3: gate closure may only trust usable_for_gate ==
    meets_line AND no bound violations AND no unit conflicts."""
    clean = [proportional_composition(f"c-{i:02d}") for i in range(12)]
    report = real_ratio_report(clean)
    # 997-scale sections are under min_words -> bound violations present
    assert report.bound_violations
    assert report.usable_for_gate is False, (
        "meets_line alone can never close the gate while bounds violated"
    )
    assert report.meets_line is True, "meets_line semantics unchanged"


def test_tokens_sections_fully_exit_judgment_surface() -> None:
    """Ruling 1-4: tokens-unit sections leave records/worst/meets_line
    entirely (empirical: vibe_pack S4_decision_log polluted v3 worst-5)."""
    vibe = Composition(
        composition_id="c-vibe", template_id="vibe_pack",
        sections={"S1_charter": "字" * 10},  # 极端占比：若进 records 必成 worst
    )
    sample = [proportional_composition(f"c-{i:02d}") for i in range(11)]
    report = real_ratio_report([*sample, vibe])
    assert not any(r.composition_id == "c-vibe" for r in report.records), (
        "tokens sections never enter records"
    )
    words_only = [r.relative_deviation for r in report.records]
    assert report.worst_deviation == max(words_only), (
        "worst_deviation computed over words-unit records only"
    )
    assert any("tokens" in c for c in report.unit_conflicts)
