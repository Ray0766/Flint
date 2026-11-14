"""M3-027 acceptance tests: expand (GapHint anti-padding).

Acceptance (tasks.json M3-027):
  - no new evidence -> GapHint list (D13) with missing_data/permission split
    (audit 8)
  - with new evidence -> new blocks that still honor ledger-only citations
"""
from __future__ import annotations

from datetime import UTC, datetime

import pytest

from flint.compose.draft import DraftViolation
from flint.compose.expand import expand_section
from flint.domain.models import (
    Block,
    Fact,
    FactsLedger,
    GapHint,
    HeadingContent,
    SectionSpec,
)

NOW = datetime(2026, 7, 29, tzinfo=UTC)
SPEC = SectionSpec(section_id="market", inputs=[], check_questions=["q"], charts=[])


def fact(fact_id: str) -> Fact:
    return Fact(
        fact_id=fact_id, statement="s", value=None, unit=None, citation_ids=[],
        status="frozen", origin="injected", created_in_version=1,
    )


def ledger(facts: list[Fact]) -> FactsLedger:
    return FactsLedger(
        ledger_id="led-1", project_id="p-1", version=1, parent_version=None,
        derivation_reason="initial", facts=facts, created_from=[],
        created_at=NOW, actor="u-1",
    )


def block(block_id: str, fact_ids: list[str]) -> Block:
    return Block(
        block_id=block_id, deliverable_id="d-1", section_id="market", order=0,
        type="heading", content=HeadingContent(kind="heading", level=2, text="t"),
        claim_ids=[], fact_ids=fact_ids, author="system", revision=1, locked=False,
    )


def test_no_new_evidence_returns_gap_hints_never_padding() -> None:
    led = ledger([fact("f-1")])
    outcome = expand_section(
        SPEC, led, cited_fact_ids={"f-1"},
        generator=lambda pool: [block("b-new", [p.fact_id for p in pool])],
        missing_scopes=["profile.finance"],
    )
    assert all(isinstance(g, GapHint) for g in outcome)
    causes = {g.cause for g in outcome}  # type: ignore[union-attr]
    assert causes == {"missing_data", "missing_permission"}, "audit-8 split"
    permission = [g for g in outcome if g.cause == "missing_permission"]  # type: ignore[union-attr]
    assert permission[0].required_scope == "profile.finance"
    assert permission[0].suggested_sources == []


def test_new_evidence_yields_blocks_with_ledger_only_citations() -> None:
    led = ledger([fact("f-1"), fact("f-2")])
    outcome = expand_section(
        SPEC, led, cited_fact_ids={"f-1"},  # f-2 是新证据
        generator=lambda pool: [block("b-new", [p.fact_id for p in pool])],
        missing_scopes=[],
    )
    assert all(isinstance(b, Block) for b in outcome)
    assert outcome[0].fact_ids == ["f-2"], "generator saw only the fresh pool"  # type: ignore[union-attr]


def test_generator_citing_outside_ledger_rejected() -> None:
    led = ledger([fact("f-1"), fact("f-2")])
    with pytest.raises(DraftViolation, match="outside the ledger"):
        expand_section(
            SPEC, led, cited_fact_ids={"f-1"},
            generator=lambda pool: [block("b-new", ["f-ghost"])],
            missing_scopes=[],
        )
