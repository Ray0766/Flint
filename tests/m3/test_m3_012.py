"""M3-012 acceptance tests: PriceBook staleness semantics.

Acceptance (tasks.json M3-012):
  - staleness decision (updated_at + stale_after_months) + yellow-flag slot
  - quality-card year note produced (price_data_notes intake)
"""
from __future__ import annotations

from datetime import UTC, date, datetime

from flint.domain.models import PriceEntry
from flint.pricebook.stale import StaleCheck, check_stale, price_data_notes


def entry(entry_id: str, updated: datetime, months: int = 12) -> PriceEntry:
    return PriceEntry(
        entry_id=entry_id, item=f"item-{entry_id}", unit="个",
        price_low=1.0, price_high=2.0, currency="CNY", region="CN",
        year=updated.year, source="seed:x", updated_at=updated,
        stale_after_months=months,
    )


TODAY = date(2026, 7, 29)


def test_fresh_entry_not_stale() -> None:
    check = check_stale(entry("a", datetime(2026, 1, 1, tzinfo=UTC)), TODAY)
    assert isinstance(check, StaleCheck)
    assert check.stale is False
    assert check.yellow_flag is False


def test_stale_after_configured_months() -> None:
    check = check_stale(entry("b", datetime(2025, 6, 1, tzinfo=UTC)), TODAY)
    assert check.stale is True, "13 months old > 12"
    assert check.yellow_flag is True, "stale entries stay usable but flagged"


def test_per_category_months_honored() -> None:
    old_but_long_ttl = entry("c", datetime(2025, 6, 1, tzinfo=UTC), months=24)
    assert check_stale(old_but_long_ttl, TODAY).stale is False
    short_ttl = entry("d", datetime(2026, 3, 1, tzinfo=UTC), months=3)
    assert check_stale(short_ttl, TODAY).stale is True


def test_quality_card_year_notes_deduplicated() -> None:
    entries = [
        entry("a", datetime(2025, 6, 1, tzinfo=UTC)),      # stale, 2025
        entry("b", datetime(2025, 3, 1, tzinfo=UTC)),      # stale, 2025
        entry("c", datetime(2026, 1, 1, tzinfo=UTC)),      # fresh
        entry("d", datetime(2024, 12, 1, tzinfo=UTC)),     # stale, 2024
    ]
    notes = price_data_notes(entries, TODAY)
    assert notes == ["单价数据为 2024 年", "单价数据为 2025 年"], (
        "one note per stale year, sorted, fresh entries excluded"
    )
