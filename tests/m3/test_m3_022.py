"""M3-022 acceptance tests: draft_section ledger-only citations.

Acceptance (tasks.json M3-022):
  - sections may cite only fact_ids inside the ledger (B6; external ids
    rejected)
  - disputed facts excluded from the usable pool (audit 10)
"""
from __future__ import annotations

from datetime import UTC, datetime

import pytest

from flint.compose.draft import DraftViolation, draft_section
from flint.domain.models import (
    Block,
    Fact,
    FactsLedger,
    HeadingContent,
    SectionSpec,
)

NOW = datetime(2026, 7, 29, tzinfo=UTC)


def fact(fact_id: str, status: str = "frozen") -> Fact:
    return Fact(
        fact_id=fact_id, statement=f"s-{fact_id}", value=None, unit=None,
        citation_ids=[], status=status,  # type: ignore[arg-type]
        origin="injected", created_in_version=1,
    )


def ledger(facts: list[Fact]) -> FactsLedger:
    return FactsLedger(
        ledger_id="led-1", project_id="p-1", version=1, parent_version=None,
        derivation_reason="initial", facts=facts, created_from=["d-0"],
        created_at=NOW, actor="u-1",
    )


SPEC = SectionSpec(
    section_id="market", inputs=[], check_questions=["数字全挂出处？"], charts=[],
)


def block_citing(fact_ids: list[str]) -> Block:
    return Block(
        block_id=f"b-{'-'.join(fact_ids) or 'none'}", deliverable_id="d-1",
        section_id="market", order=0, type="heading",
        content=HeadingContent(kind="heading", level=2, text="市场"),
        claim_ids=[], fact_ids=fact_ids, author="system", revision=1,
        locked=False,
    )


def test_generator_receives_usable_pool_only() -> None:
    seen_pools: list[list[str]] = []

    def generator(pool: list[Fact]) -> list[Block]:
        seen_pools.append([f.fact_id for f in pool])
        return [block_citing([pool[0].fact_id])]

    led = ledger([fact("f-1"), fact("f-2", "disputed"), fact("f-3", "retired")])
    blocks = draft_section(SPEC, led, generator)
    assert seen_pools == [["f-1"]], "disputed and retired never reach the generator"
    assert blocks[0].fact_ids == ["f-1"]


def test_external_fact_id_rejected() -> None:
    led = ledger([fact("f-1")])
    with pytest.raises(DraftViolation, match="outside the ledger"):
        draft_section(SPEC, led, lambda pool: [block_citing(["f-ghost"])])


def test_disputed_reference_rejected_even_if_generator_cheats() -> None:
    led = ledger([fact("f-1"), fact("f-2", "disputed")])
    with pytest.raises(DraftViolation, match="disputed"):
        draft_section(SPEC, led, lambda pool: [block_citing(["f-2"])])


def test_clean_draft_passes_and_keeps_section_binding() -> None:
    led = ledger([fact("f-1")])
    blocks = draft_section(SPEC, led, lambda pool: [block_citing(["f-1"])])
    assert len(blocks) == 1
    assert blocks[0].section_id == "market"
