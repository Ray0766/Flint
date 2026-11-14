"""M3-013 acceptance tests: PriceCell channel enforcer.

Acceptance (tasks.json M3-013):
  - budget-table numbers only via PriceCell (naked numbers rejected by
    type + validator double gate)
  - entries with empty source are NEVER citable (violation raises)
"""
from __future__ import annotations

from datetime import UTC, datetime

import pytest

from flint.domain.models import (
    FactCell,
    PriceCell,
    PriceEntry,
    TableContent,
    TextCell,
)
from flint.pricebook.cell import (
    PriceChannelViolation,
    make_price_cell,
    validate_budget_table,
)


def entry(entry_id: str, source: str = "https://p.example/x") -> PriceEntry:
    return PriceEntry(
        entry_id=entry_id, item="服务器", unit="台", price_low=40000.0,
        price_high=120000.0, currency="CNY", region="CN", year=2026,
        source=source, updated_at=datetime(2026, 7, 1, tzinfo=UTC),
    )


def table(*rows: list) -> TableContent:
    return TableContent(kind="table", header=["项目", "数量/金额"], rows=list(rows))


def test_make_price_cell_happy_path() -> None:
    cell = make_price_cell(entry("pe-1"), quantity=2.0)
    assert isinstance(cell, PriceCell)
    assert cell.price_entry_id == "pe-1" and cell.quantity == 2.0


def test_empty_source_never_citable() -> None:
    with pytest.raises(PriceChannelViolation, match="source"):
        make_price_cell(entry("pe-2", source=""), quantity=1.0)


def test_naked_number_text_cell_rejected() -> None:
    budget = table(
        [TextCell(kind="text", text="服务器"), TextCell(kind="text", text="120000")],
    )
    violations = validate_budget_table(budget, {"pe-1": entry("pe-1")})
    assert len(violations) == 1
    assert "naked number" in violations[0]


def test_formatted_numbers_also_rejected() -> None:
    for naked in ("¥120,000", "120000.50", " 3.5 ",
                  "120000元", "12万", "1.2亿元", "35%"):
        budget = table([TextCell(kind="text", text=naked)])
        assert validate_budget_table(budget, {}), naked
    plain = table([TextCell(kind="text", text="预算充足")])
    assert validate_budget_table(plain, {}) == [], "prose never misfires"


def test_price_cell_referencing_unknown_or_unsourced_entry_rejected() -> None:
    budget = table(
        [PriceCell(kind="price", price_entry_id="pe-ghost", quantity=1.0)],
    )
    violations = validate_budget_table(budget, {"pe-1": entry("pe-1")})
    assert any("unknown" in v for v in violations)

    unsourced = entry("pe-3", source="")
    budget2 = table(
        [PriceCell(kind="price", price_entry_id="pe-3", quantity=1.0)],
    )
    violations2 = validate_budget_table(budget2, {"pe-3": unsourced})
    assert any("source" in v for v in violations2)


def test_clean_budget_table_passes() -> None:
    budget = table(
        [TextCell(kind="text", text="服务器"),
         PriceCell(kind="price", price_entry_id="pe-1", quantity=2.0)],
        [TextCell(kind="text", text="市场规模（引用）"),
         FactCell(kind="fact", fact_id="f-1")],
    )
    assert validate_budget_table(budget, {"pe-1": entry("pe-1")}) == []
