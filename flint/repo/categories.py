"""大类目录：种子装载与只读查询（M1-022）。

目录为人工固定资产（assets/categories.yaml，12 类）；seed 幂等
（ON CONFLICT 更新 name），端点侧只读。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import asyncpg
import yaml


class CategoryCatalogError(Exception):
    pass


def load_categories(path: Path) -> list[tuple[str, str]]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    entries = payload.get("categories") if isinstance(payload, dict) else None
    if not isinstance(entries, list):
        raise CategoryCatalogError("categories.yaml must contain a 'categories' list")
    result: list[tuple[str, str]] = []
    seen: set[str] = set()
    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise CategoryCatalogError(f"categories[{i}]: entry must be a mapping")
        cid, name = entry.get("id"), entry.get("name")
        if not isinstance(cid, str) or not cid or not isinstance(name, str) or not name:
            raise CategoryCatalogError(f"categories[{i}]: id/name missing or empty")
        if cid in seen:
            raise CategoryCatalogError(f"categories[{i}]: duplicate id {cid!r}")
        seen.add(cid)
        result.append((cid, name))
    return result


async def seed_categories(dsn: str, categories: list[tuple[str, str]]) -> None:
    conn = await asyncpg.connect(dsn)
    try:
        await conn.executemany(
            "INSERT INTO categories (category_id, name) VALUES ($1, $2) "
            "ON CONFLICT (category_id) DO UPDATE SET name = EXCLUDED.name",
            categories,
        )
    finally:
        await conn.close()


async def fetch_categories(dsn: str) -> list[dict[str, Any]]:
    conn = await asyncpg.connect(dsn)
    try:
        rows = await conn.fetch(
            "SELECT category_id, name FROM categories ORDER BY category_id"
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()
