"""M1-021 acceptance tests: Keyword repository (idempotent upsert).

Acceptance (tasks.json M1-021):
  - canonical+lang is idempotent
  - first_seen is never overwritten
"""
from __future__ import annotations

import asyncio
import os
from datetime import date
from typing import Any

import asyncpg
import pytest

from flint.domain.models import Keyword
from flint.repo.keyword import upsert_keywords

pytestmark = pytest.mark.compose

DSN = os.environ.get("FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")
DIM = 1024


def run(coro: Any) -> Any:
    return asyncio.run(coro)


def vec(seed: float) -> list[float]:
    return [seed] * DIM


def kw(
    kid: str,
    canonical: str,
    lang: str = "en",
    aliases: list[str] | None = None,
    embedding: list[float] | None = None,
    first_seen: date = date(2026, 7, 23),
) -> Keyword:
    return Keyword(
        keyword_id=kid,
        canonical=canonical,
        lang=lang,
        aliases=aliases if aliases is not None else [],
        embedding=embedding if embedding is not None else vec(0.1),
        first_seen=first_seen,
    )


async def fetch_row(canonical: str, lang: str) -> asyncpg.Record | None:
    conn = await asyncpg.connect(DSN)
    try:
        return await conn.fetchrow(
            "SELECT keyword_id, canonical, lang, aliases, first_seen "
            "FROM keywords WHERE canonical = $1 AND lang = $2",
            canonical,
            lang,
        )
    finally:
        await conn.close()


@pytest.fixture(autouse=True)
def clean_slate() -> None:
    async def wipe() -> None:
        conn = await asyncpg.connect(DSN)
        try:
            await conn.execute("DELETE FROM keywords WHERE canonical LIKE 'm1021-%'")
        finally:
            await conn.close()

    run(wipe())


def test_insert_then_reupsert_same_id_and_first_seen() -> None:
    first = kw("m1021-id-a", "m1021-solid-state battery")
    ids1 = run(upsert_keywords(DSN, [first]))

    again = kw(
        "m1021-id-b",  # new surrogate id must NOT replace the existing row's id
        "m1021-solid-state battery",
        aliases=["m1021-ssb"],
        embedding=vec(0.9),
        first_seen=date(2026, 7, 26),  # later sighting
    )
    ids2 = run(upsert_keywords(DSN, [again]))

    assert ids1["m1021-solid-state battery", "en"] == ids2["m1021-solid-state battery", "en"]
    row = run(fetch_row("m1021-solid-state battery", "en"))
    assert row is not None
    assert row["keyword_id"] == "m1021-id-a", "existing keyword_id must survive upsert"
    assert row["first_seen"] == date(2026, 7, 23), "first_seen must never be overwritten"


def test_upsert_refreshes_aliases() -> None:
    run(upsert_keywords(DSN, [kw("m1021-id-c", "m1021-agent memory")]))
    run(
        upsert_keywords(
            DSN,
            [kw("m1021-id-d", "m1021-agent memory", aliases=["m1021-mem"])],
        )
    )
    row = run(fetch_row("m1021-agent memory", "en"))
    assert row is not None
    assert "m1021-mem" in row["aliases"]


def test_same_canonical_different_lang_are_distinct() -> None:
    run(
        upsert_keywords(
            DSN,
            [
                kw("m1021-id-e", "m1021-数字孪生", lang="zh"),
                kw("m1021-id-f", "m1021-数字孪生", lang="en"),
            ],
        )
    )
    assert run(fetch_row("m1021-数字孪生", "zh")) is not None
    assert run(fetch_row("m1021-数字孪生", "en")) is not None


def test_batch_upsert_idempotent_row_count() -> None:
    batch = [kw(f"m1021-id-{i}", f"m1021-kw-{i}") for i in range(10)]
    run(upsert_keywords(DSN, batch))
    run(upsert_keywords(DSN, batch))

    async def count() -> int:
        conn = await asyncpg.connect(DSN)
        try:
            value: int = await conn.fetchval(
                "SELECT count(*) FROM keywords WHERE canonical LIKE 'm1021-kw-%'"
            )
            return value
        finally:
            await conn.close()

    assert run(count()) == 10
