"""M1-022 acceptance tests: category catalog seed (12 categories).

Acceptance (tasks.json M1-022):
  - 12 top-level categories land in the DB
  - a read-only endpoint returns the full table
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

import httpx
import pytest

from flint.repo.categories import fetch_categories, load_categories, seed_categories

pytestmark = pytest.mark.compose

REPO_ROOT = Path(__file__).resolve().parents[2]
CATALOG = REPO_ROOT / "assets" / "categories.yaml"
DSN = os.environ.get("FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")


def run(coro: Any) -> Any:
    return asyncio.run(coro)


@pytest.fixture(scope="module")
def seeded() -> list[tuple[str, str]]:
    categories = load_categories(CATALOG)
    run(seed_categories(DSN, categories))
    run(seed_categories(DSN, categories))  # idempotent re-seed
    return categories


def test_catalog_has_exactly_12(seeded: list[tuple[str, str]]) -> None:
    assert len(seeded) == 12


def test_seeded_into_db(seeded: list[tuple[str, str]]) -> None:
    rows = run(fetch_categories(DSN))
    ids = {r["category_id"] for r in rows}
    assert ids >= {cid for cid, _ in seeded}
    assert len([r for r in rows if r["category_id"] in ids]) >= 12


def test_readonly_endpoint_returns_full_table(seeded: list[tuple[str, str]]) -> None:
    from flint.api.app import create_app

    app = create_app(DSN)

    async def call() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            return await client.get("/categories")

    response = run(call())
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) >= 12
    sample = payload[0]
    assert set(sample) == {"category_id", "name"}
    returned_ids = {c["category_id"] for c in payload}
    assert returned_ids >= {cid for cid, _ in seeded}


def test_endpoint_is_readonly(seeded: list[tuple[str, str]]) -> None:
    from flint.api.app import create_app

    app = create_app(DSN)

    async def call() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            return await client.post("/categories", json={"category_id": "x", "name": "y"})

    response = run(call())
    assert response.status_code == 405
