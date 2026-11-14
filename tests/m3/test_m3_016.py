"""M3-016 acceptance tests: three-channel mutual-exclusion enforcer (iron rule 2).

Acceptance (tasks.json M3-016):
  - Fact/PriceCell/ProfileRef cross-channel misuse combinations all rejected
  - legal coexistence of all three channels in one document passes
"""
from __future__ import annotations

from datetime import UTC, datetime

from flint.compose.channels import validate_channels
from flint.domain.models import (
    Block,
    FactCell,
    ParagraphContent,
    PriceCell,
    PriceEntry,
    Principal,
    ProfileRef,
    TableContent,
    TextCell,
    TextSpan,
    UserProfile,
)

NOW = datetime(2026, 7, 29, tzinfo=UTC)


def profile() -> UserProfile:
    return UserProfile(
        profile_id="p-1", owner=Principal(kind="user", id="u-1"),
        identity={"org": "Flint Lab"}, research={}, team=[], assets={},
        constraints={}, track_record=[], locale="zh-CN",
        sensitivity_overrides={}, updated_at=NOW,
    )


def entry(entry_id: str) -> PriceEntry:
    return PriceEntry(
        entry_id=entry_id, item="服务器", unit="台", price_low=1.0,
        price_high=2.0, currency="CNY", region="CN", year=2026,
        source="https://p.example", updated_at=NOW,
    )


def block(block_id: str, content: object, fact_ids: list[str] | None = None) -> Block:
    return Block(
        block_id=block_id, deliverable_id="d-1", section_id="s-1", order=0,
        type="table" if isinstance(content, TableContent) else "paragraph",
        content=content, claim_ids=[], fact_ids=fact_ids or [],  # type: ignore[arg-type]
        author="system", revision=1, locked=False,
    )


KNOWN_FACTS = {"fact-1"}
ENTRIES = {"pe-1": entry("pe-1")}


def test_price_id_through_fact_channel_rejected() -> None:
    b = block("b-1", TableContent(
        kind="table", header=["项"],
        rows=[[FactCell(kind="fact", fact_id="pe-1")]],
    ))
    violations = validate_channels([b], KNOWN_FACTS, ENTRIES, profile())
    assert any("price entry" in v and "Fact channel" in v for v in violations)


def test_fact_id_through_price_channel_rejected() -> None:
    b = block("b-1", TableContent(
        kind="table", header=["项"],
        rows=[[PriceCell(kind="price", price_entry_id="fact-1", quantity=1.0)]],
    ))
    violations = validate_channels([b], KNOWN_FACTS, ENTRIES, profile())
    assert any("fact" in v and "price channel" in v for v in violations)


def test_unknown_fact_reference_rejected() -> None:
    b = block("b-1", TableContent(
        kind="table", header=["项"],
        rows=[[FactCell(kind="fact", fact_id="fact-ghost")]],
    ))
    violations = validate_channels([b], KNOWN_FACTS, ENTRIES, profile())
    assert any("unknown fact" in v for v in violations)


def test_naked_profile_value_rejected() -> None:
    b = block("b-1", ParagraphContent(
        kind="paragraph", spans=[TextSpan(kind="text", text="Flint Lab")],
    ))
    violations = validate_channels([b], KNOWN_FACTS, ENTRIES, profile())
    assert any("ProfileRef" in v for v in violations)


def test_naked_budget_number_rejected() -> None:
    b = block("b-1", TableContent(
        kind="table", header=["项"],
        rows=[[TextCell(kind="text", text="12万")]],
    ))
    violations = validate_channels([b], KNOWN_FACTS, ENTRIES, profile())
    assert any("naked number" in v for v in violations)


def test_legal_three_channel_coexistence_passes() -> None:
    table_block = block("b-1", TableContent(
        kind="table", header=["项", "值"],
        rows=[
            [TextCell(kind="text", text="服务器"),
             PriceCell(kind="price", price_entry_id="pe-1", quantity=2.0)],
            [TextCell(kind="text", text="市场规模"),
             FactCell(kind="fact", fact_id="fact-1")],
        ],
    ), fact_ids=["fact-1"])
    para_block = block("b-2", ParagraphContent(
        kind="paragraph",
        spans=[
            TextSpan(kind="text", text="团队隶属 "),
            ProfileRef(kind="profile", field_path="identity.org"),
        ],
    ))
    violations = validate_channels(
        [table_block, para_block], KNOWN_FACTS, ENTRIES, profile()
    )
    assert violations == [], "three channels coexist legally in one document"
