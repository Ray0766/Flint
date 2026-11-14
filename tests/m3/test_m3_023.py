"""M3-023 acceptance tests: draft channel constraints wiring.

Acceptance (tasks.json M3-023):
  - self-referential content only via ProfileRef, budget numbers only via
    PriceCell (violating drafts rejected)
  - channel material traceable inside blocks (fact_ids / refs discriminated)
"""
from __future__ import annotations

from datetime import UTC, datetime

import pytest

from flint.compose.draft import DraftViolation
from flint.compose.draft_channels import channel_manifest, draft_section_with_channels
from flint.domain.models import (
    Block,
    Fact,
    FactCell,
    FactsLedger,
    ParagraphContent,
    PriceCell,
    PriceEntry,
    Principal,
    ProfileRef,
    SectionSpec,
    TableContent,
    TextCell,
    TextSpan,
    UserProfile,
)

NOW = datetime(2026, 7, 29, tzinfo=UTC)

SPEC = SectionSpec(section_id="budget", inputs=[], check_questions=["q"], charts=[])


def profile() -> UserProfile:
    return UserProfile(
        profile_id="p-1", owner=Principal(kind="user", id="u-1"),
        identity={"org": "Flint Lab"}, research={}, team=[], assets={},
        constraints={}, track_record=[], locale="zh-CN",
        sensitivity_overrides={}, updated_at=NOW,
    )


def entry() -> PriceEntry:
    return PriceEntry(
        entry_id="pe-1", item="服务器", unit="台", price_low=1.0, price_high=2.0,
        currency="CNY", region="CN", year=2026, source="https://p.example",
        updated_at=NOW,
    )


def ledger() -> FactsLedger:
    return FactsLedger(
        ledger_id="led-1", project_id="p-1", version=1, parent_version=None,
        derivation_reason="initial",
        facts=[Fact(
            fact_id="fact-1", statement="s", value=None, unit=None,
            citation_ids=[], status="frozen", origin="injected",
            created_in_version=1,
        )],
        created_from=[], created_at=NOW, actor="u-1",
    )


def block(content: object, fact_ids: list[str] | None = None) -> Block:
    return Block(
        block_id="b-1", deliverable_id="d-1", section_id="budget", order=0,
        type="table" if isinstance(content, TableContent) else "paragraph",
        content=content, claim_ids=[], fact_ids=fact_ids or [],  # type: ignore[arg-type]
        author="system", revision=1, locked=False,
    )


def test_naked_budget_number_draft_rejected() -> None:
    bad = block(TableContent(
        kind="table", header=["项"],
        rows=[[TextCell(kind="text", text="12万")]],
    ))
    with pytest.raises(DraftViolation, match="naked number"):
        draft_section_with_channels(
            SPEC, ledger(), lambda pool: [bad], {"pe-1": entry()}, profile()
        )


def test_naked_profile_value_draft_rejected() -> None:
    bad = block(ParagraphContent(
        kind="paragraph", spans=[TextSpan(kind="text", text="Flint Lab")],
    ))
    with pytest.raises(DraftViolation, match="ProfileRef"):
        draft_section_with_channels(
            SPEC, ledger(), lambda pool: [bad], {"pe-1": entry()}, profile()
        )


def test_clean_draft_passes_all_gates() -> None:
    good = block(
        TableContent(
            kind="table", header=["项", "值"],
            rows=[
                [TextCell(kind="text", text="服务器"),
                 PriceCell(kind="price", price_entry_id="pe-1", quantity=2.0)],
                [TextCell(kind="text", text="规模"),
                 FactCell(kind="fact", fact_id="fact-1")],
            ],
        ),
        fact_ids=["fact-1"],
    )
    blocks = draft_section_with_channels(
        SPEC, ledger(), lambda pool: [good], {"pe-1": entry()}, profile()
    )
    assert len(blocks) == 1


def test_channel_manifest_traceable() -> None:
    table = block(
        TableContent(
            kind="table", header=["项"],
            rows=[[PriceCell(kind="price", price_entry_id="pe-1", quantity=2.0)],
                  [FactCell(kind="fact", fact_id="fact-1")]],
        ),
        fact_ids=["fact-1"],
    )
    para = block(ParagraphContent(
        kind="paragraph",
        spans=[ProfileRef(kind="profile", field_path="identity.org")],
    ))
    manifest = channel_manifest([table, para])
    assert manifest == {
        "facts": ["fact-1"],
        "price_entries": ["pe-1"],
        "profile_paths": ["identity.org"],
    }, "every channel reference is discoverable and discriminated"
