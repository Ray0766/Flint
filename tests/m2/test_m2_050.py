"""M2-050 acceptance tests: evidence-source degradation (E6 row 2).

Acceptance (tasks.json M2-050):
  - single evidence source down switches to backup (replay case)
  - dimension fully dead -> coverage not met -> falls to D per 2.2 with a
    blind-spot statement
"""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from flint.align.stage1 import LLMCitationAligner
from flint.domain.models import JSON, Doc, Query
from flint.evidence.degradation import (
    DimensionOutage,
    fetch_dimension_with_fallback,
    outage_coverage,
)
from flint.evidence.paper import CrossrefPaperSource
from flint.gate.engine import decide
from flint.gate.rule_a import RuleAResult
from flint.gate.rule_b import RuleBResult
from flint.gate.rule_c import evaluate_rule_c
from flint.gate.rule_d import derive_gaps
from flint.testing.replay import HttpReplay

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "fixtures" / "evidence6" / "paper"
NOW = datetime(2026, 7, 28, 12, 0, 0, tzinfo=UTC)
QUERY = Query(
    text="solid state battery", source_kinds=["paper"], intent="support", locale="en"
)
# failure / ratelimit fixtures 录制时的探针查询（对齐 M2-009 录制口径）
PROBE = Query(text="probe", source_kinds=["paper"], intent="support", locale="en")


def replay_fetcher(fixture: str, query: Query = QUERY) -> list[Doc]:
    with (
        HttpReplay(FIXTURES / f"{fixture}.json", mode="replay") as session,
        session.client() as client,
    ):
        return CrossrefPaperSource(client=client, now=lambda: NOW).search(
            query, since=None, limit=10
        )


def test_single_source_down_switches_to_backup_replay() -> None:
    result = fetch_dimension_with_fallback(
        "paper",
        [
            ("crossref-primary", lambda: replay_fetcher("failure", PROBE)),
            ("crossref-backup", lambda: replay_fetcher("solid-state-battery")),
        ],
    )
    assert result.outage is None
    assert result.used_source == "crossref-backup"
    assert result.failed_sources == ["crossref-primary"]
    assert len(result.docs) == 6, "backup delivers the dimension"


def test_dimension_fully_dead_yields_outage() -> None:
    result = fetch_dimension_with_fallback(
        "paper",
        [
            ("crossref-primary", lambda: replay_fetcher("failure", PROBE)),
            ("crossref-backup", lambda: replay_fetcher("ratelimit", PROBE)),
        ],
    )
    assert result.docs == [] and result.used_source is None
    outage = result.outage
    assert isinstance(outage, DimensionOutage)
    assert outage.attempted_sources == ["crossref-primary", "crossref-backup"]
    assert "paper" in outage.blind_spot and "覆盖不达标" in outage.blind_spot


class _NeverCalledProvider:
    def generate(self, prompt: str, tools: list[JSON] | None) -> object:
        raise AssertionError("no LLM call expected")

    def generate_structured(self, prompt: str, schema: JSON, max_retries: int) -> JSON:
        raise AssertionError("no LLM call expected")


def test_outage_falls_to_d_with_blind_spot() -> None:
    outage = DimensionOutage(
        dimension="paper",
        attempted_sources=["crossref-primary", "crossref-backup"],
        blind_spot="盲区：paper 维度证据源全部不可用（已尝试 crossref-primary、crossref-backup），该维度覆盖不达标",
    )
    coverage = outage_coverage(outage)
    assert coverage.covered is False
    assert coverage.pending_queries == [
        "paper:crossref-primary", "paper:crossref-backup",
    ]

    aligner = LLMCitationAligner(provider=_NeverCalledProvider())  # type: ignore[arg-type]
    rule_c = evaluate_rule_c(
        aligner, [], refute_executed=True, refute_hit_rate=0.8,
        coverage=coverage, competitors=[],
    )
    assert "coverage_not_met" in rule_c.failed_conditions

    # FIX-12：`derive_gaps` 回 `DerivedGap`；`decide` 吃的仍是冻结件那一份。
    derived = derive_gaps(rule_c, coverage, [], missing_scopes=[])
    gaps = [d.hint for d in derived]
    verdict = decide(
        RuleAResult(satisfied=False),
        RuleBResult(satisfied=False, by_count=False, by_strength=False,
                    reachable_count=0),
        rule_c, gaps=gaps, competitors=[],
    )
    assert verdict.verdict == "D_insufficient"
    coverage_gaps = [g for g in gaps if "覆盖" in g.missing_what]
    assert coverage_gaps and coverage_gaps[0].suggested_sources == [
        "paper:crossref-primary", "paper:crossref-backup",
    ], "blind-spot material flows into the D gap list"
