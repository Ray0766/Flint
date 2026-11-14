"""M2-001 acceptance tests: evidence-layer migration 0006.

Acceptance (tasks.json M2-001):
  - upgrade -> downgrade -> upgrade round-trips cleanly
  - docs.origin/access discriminator fields and the snapshots 180-day
    retention field are all present
"""
from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import asyncpg
import pytest

pytestmark = pytest.mark.compose

REPO_ROOT = Path(__file__).resolve().parents[2]
DSN = os.environ.get("FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")


def run(coro: Any) -> Any:
    return asyncio.run(coro)


def _alembic_env() -> dict[str, str]:
    """alembic 子进程 MUST 迁移 DSN 指的那个库（见 tests/m3/test_m3_001.py 同名函数）。

    migrations/env.py 的 DEFAULT_URL 指向 demo 库；不传 DATABASE_URL 就会打在 demo 上。
    """
    url = DSN.replace("postgresql://", "postgresql+asyncpg://", 1)
    return {**os.environ, "DATABASE_URL": url}


def alembic(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=300, check=False,
        encoding="utf-8", errors="replace", env=_alembic_env(),
    )


async def _fetch(query: str, *args: Any) -> list[asyncpg.Record]:
    conn = await asyncpg.connect(DSN)
    try:
        return await conn.fetch(query, *args)
    finally:
        await conn.close()


async def _execute(query: str, *args: Any) -> None:
    conn = await asyncpg.connect(DSN)
    try:
        await conn.execute(query, *args)
    finally:
        await conn.close()


@pytest.fixture(scope="module")
def migrated() -> None:
    up = alembic("upgrade", "head")
    assert up.returncode == 0, up.stderr
    down = alembic("downgrade", "0005")
    assert down.returncode == 0, down.stderr
    up2 = alembic("upgrade", "head")
    assert up2.returncode == 0, up2.stderr


def test_four_evidence_tables_exist(migrated: None) -> None:
    rows = run(_fetch("SELECT tablename FROM pg_tables WHERE schemaname = 'public'"))
    tables = {r["tablename"] for r in rows}
    assert {"docs", "citations", "pricing_records", "snapshots"} <= tables


def test_docs_origin_and_access_discriminators_enforced(migrated: None) -> None:
    run(_execute("DELETE FROM docs WHERE doc_id LIKE 'm2001-%'"))
    run(
        _execute(
            "INSERT INTO docs (doc_id, source_id, kind, title, url, published_at, "
            "meta, origin, access) VALUES ('m2001-ok', 'crossref', 'paper', 't', "
            "'https://x', NULL, '{}', 'retrieved', 'public')"
        )
    )
    with pytest.raises(asyncpg.CheckViolationError):
        run(
            _execute(
                "INSERT INTO docs (doc_id, source_id, kind, title, url, published_at, "
                "meta, origin, access) VALUES ('m2001-bad', 'crossref', 'paper', 't', "
                "'https://x', NULL, '{}', 'guessed', 'public')"
            )
        )
    with pytest.raises(asyncpg.CheckViolationError):
        run(
            _execute(
                "INSERT INTO docs (doc_id, source_id, kind, title, url, published_at, "
                "meta, origin, access) VALUES ('m2001-bad2', 'crossref', 'blog', 't', "
                "'https://x', NULL, '{}', 'retrieved', 'public')"
            )
        )


def test_citations_reference_docs(migrated: None) -> None:
    with pytest.raises(asyncpg.ForeignKeyViolationError):
        run(
            _execute(
                "INSERT INTO citations (citation_id, doc_id, locator, quote_span) "
                "VALUES ('m2001-c1', 'm2001-ghost-doc', NULL, NULL)"
            )
        )


def test_snapshots_have_retention_field(migrated: None) -> None:
    rows = run(
        _fetch(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'snapshots'"
        )
    )
    columns = {r["column_name"] for r in rows}
    assert {"snapshot_id", "payload", "created_at"} <= columns, (
        "created_at drives the 180-day retention sweep"
    )


def test_pricing_records_confidence_bounded(migrated: None) -> None:
    with pytest.raises(asyncpg.CheckViolationError):
        run(
            _execute(
                "INSERT INTO pricing_records (record_id, plan, price, currency, "
                "region, confidence, captured_at, url) VALUES ('m2001-p1', 'pro', "
                "99.0, 'USD', 'us', 1.5, now(), 'https://x/pricing')"
            )
        )
