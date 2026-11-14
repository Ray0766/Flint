"""M3-011 acceptance tests: PriceBook table + 60 seed entries.

Acceptance (tasks.json M3-011):
  - field surface matches v0.3.1 section-3.2 (updated_at / stale_after_months /
    source mandatory)
  - 60 seed entries load and no source is empty
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

import asyncpg
import pytest

from fixtures._generate_pricebook import build
from flint.domain.models import PriceEntry
from flint.pricebook.seed import load_pricebook, seed_pricebook_on

REPO_ROOT = Path(__file__).resolve().parents[2]
ASSET = REPO_ROOT / "assets" / "pricebook.yaml"
DSN = os.environ.get("FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")


def run(coro: Any) -> Any:
    return asyncio.run(coro)


def test_sixty_entries_all_sourced() -> None:
    entries = load_pricebook(ASSET)
    assert len(entries) == 60
    assert all(isinstance(e, PriceEntry) for e in entries)
    assert all(e.source for e in entries), "no entry without provenance"
    assert all(e.price_high >= e.price_low >= 0 for e in entries)
    assert all(e.stale_after_months == 12 for e in entries)
    assert len({e.entry_id for e in entries}) == 60


def test_asset_matches_generator() -> None:
    on_disk = load_pricebook(ASSET)
    generated = build()["entries"]
    assert len(generated) == len(on_disk)
    assert [e.entry_id for e in on_disk] == [g["entry_id"] for g in generated]


@pytest.mark.compose
def test_seed_idempotent_and_source_check_enforced() -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(DSN)
        try:
            entries = load_pricebook(ASSET)
            await seed_pricebook_on(conn, entries)
            await seed_pricebook_on(conn, entries)  # idempotent upsert
            count: int = await conn.fetchval("SELECT COUNT(*) FROM pricebook")
            assert count == 60

            with pytest.raises(asyncpg.CheckViolationError):
                await conn.execute(
                    "INSERT INTO pricebook (entry_id, item, unit, price_low, "
                    "price_high, currency, region, year, source, updated_at) "
                    "VALUES ('pe-bad', 'x', 'u', 1, 2, 'CNY', 'CN', 2026, '', now())",
                )
        finally:
            await conn.close()

    run(scenario())
