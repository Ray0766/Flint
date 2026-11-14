"""PriceBook 资产装载与落库（M3-011）。"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import asyncpg
import yaml

from flint.domain.models import PriceEntry


def load_pricebook(path: Path) -> list[PriceEntry]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    entries: list[PriceEntry] = []
    for row in payload["entries"]:
        source = str(row["source"])
        if not source:
            raise ValueError(f"{row['entry_id']}: empty source is not citable")
        entries.append(
            PriceEntry(
                entry_id=str(row["entry_id"]),
                item=str(row["item"]),
                unit=str(row["unit"]),
                price_low=float(row["price_low"]),
                price_high=float(row["price_high"]),
                currency=str(row["currency"]),
                region=str(row["region"]),
                year=int(row["year"]),
                source=source,
                updated_at=datetime.fromisoformat(str(row["updated_at"])),
                stale_after_months=int(row["stale_after_months"]),
            )
        )
    return entries


async def seed_pricebook_on(
    conn: asyncpg.Connection, entries: list[PriceEntry]
) -> None:
    await conn.executemany(
        "INSERT INTO pricebook (entry_id, item, unit, price_low, price_high, "
        "currency, region, year, source, updated_at, stale_after_months) "
        "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11) "
        "ON CONFLICT (entry_id) DO UPDATE SET item = EXCLUDED.item, "
        "unit = EXCLUDED.unit, price_low = EXCLUDED.price_low, "
        "price_high = EXCLUDED.price_high, source = EXCLUDED.source, "
        "updated_at = EXCLUDED.updated_at, "
        "stale_after_months = EXCLUDED.stale_after_months",
        [
            (
                e.entry_id, e.item, e.unit, e.price_low, e.price_high, e.currency,
                e.region, e.year, e.source, e.updated_at, e.stale_after_months,
            )
            for e in entries
        ],
    )
