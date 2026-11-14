"""M3-001 acceptance tests: ledger table family migration 0008.

Acceptance (tasks.json M3-001):
  - three tables with version-chain FK + reason/status/origin discriminator
    CHECKs land
  - alembic upgrade/downgrade round trip is clean
"""
from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import asyncpg
import pytest

pytestmark = pytest.mark.compose

REPO_ROOT = Path(__file__).resolve().parents[2]
DSN = os.environ.get("FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")
NOW = datetime(2026, 7, 29, 12, 0, 0, tzinfo=UTC)


def run(coro: Any) -> Any:
    return asyncio.run(coro)


def _alembic_env() -> dict[str, str]:
    """alembic 子进程 MUST 迁移 DSN 指的那个库。

    migrations/env.py 的 DEFAULT_URL 指向 **demo 库**：不显式传 DATABASE_URL，
    下面的 downgrade/upgrade 就打在 demo 库上——demo 的 deliverables / blocks /
    projects / topics 历史上正是被这条路径 **DROP TABLE** 掉的（比各用例的
    DELETE 清得更狠）。而断言读的是测试库，两边分裂还会让断言假红。
    """
    url = DSN.replace("postgresql://", "postgresql+asyncpg://", 1)
    return {**os.environ, "DATABASE_URL": url}


def alembic(*args: str) -> None:
    subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=REPO_ROOT, check=True, capture_output=True, env=_alembic_env(),
    )


@pytest.fixture(autouse=True)
def at_head() -> None:
    alembic("upgrade", "head")
    run(_sql([
        "DELETE FROM facts WHERE ledger_id LIKE 'm3001-%'",
        "DELETE FROM claims WHERE claim_id LIKE 'm3001-%'",
        "DELETE FROM facts_ledgers WHERE ledger_id LIKE 'm3001-%'",
    ]))


async def _sql(statements: list[str]) -> None:
    conn = await asyncpg.connect(DSN)
    try:
        for stmt in statements:
            await conn.execute(stmt)
    finally:
        await conn.close()


async def _tables() -> set[str]:
    conn = await asyncpg.connect(DSN)
    try:
        rows = await conn.fetch(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public'"
        )
        return {r["table_name"] for r in rows}
    finally:
        await conn.close()


async def _insert_ledger(ledger_id: str, version: int = 1) -> None:
    conn = await asyncpg.connect(DSN)
    try:
        await conn.execute(
            "INSERT INTO facts_ledgers (ledger_id, project_id, version, "
            "parent_version, derivation_reason, created_from, created_at, actor) "
            "VALUES ($1, 'p-m3001', $2, NULL, 'initial', '[]'::jsonb, $3, 'u-1')",
            ledger_id, version, NOW,
        )
    finally:
        await conn.close()


def test_tables_exist_after_upgrade() -> None:
    tables = run(_tables())
    for name in ("facts_ledgers", "facts", "claims"):
        assert name in tables


def test_reason_status_origin_checks_enforced() -> None:
    run(_insert_ledger("m3001-l1"))

    async def bad_reason() -> None:
        conn = await asyncpg.connect(DSN)
        try:
            await conn.execute(
                "INSERT INTO facts_ledgers (ledger_id, project_id, version, "
                "parent_version, derivation_reason, created_from, created_at, actor) "
                "VALUES ('m3001-bad', 'p-m3001', 2, 1, 'freestyle', '[]'::jsonb, "
                "$1, 'u-1')",
                NOW,
            )
        finally:
            await conn.close()

    with pytest.raises(asyncpg.CheckViolationError):
        run(bad_reason())

    async def bad_status() -> None:
        conn = await asyncpg.connect(DSN)
        try:
            await conn.execute(
                "INSERT INTO facts (ledger_id, fact_id, statement, value, unit, "
                "citation_ids, status, origin, created_in_version, source_claim_id, "
                "promoted_from) VALUES ('m3001-l1', 'm3001-f1', 's', NULL, NULL, "
                "'[]'::jsonb, 'melted', 'injected', 1, NULL, NULL)",
            )
        finally:
            await conn.close()

    with pytest.raises(asyncpg.CheckViolationError):
        run(bad_status())


def test_promoted_claim_requires_source_claim_id() -> None:
    run(_insert_ledger("m3001-l2"))

    async def promoted_without_source() -> None:
        conn = await asyncpg.connect(DSN)
        try:
            await conn.execute(
                "INSERT INTO facts (ledger_id, fact_id, statement, value, unit, "
                "citation_ids, status, origin, created_in_version, source_claim_id, "
                "promoted_from) VALUES ('m3001-l2', 'm3001-f2', 's', NULL, NULL, "
                "'[]'::jsonb, 'frozen', 'promoted_claim', 1, NULL, NULL)",
            )
        finally:
            await conn.close()

    with pytest.raises(asyncpg.CheckViolationError):
        run(promoted_without_source())


def test_project_version_unique() -> None:
    run(_insert_ledger("m3001-l3", version=7))
    with pytest.raises(asyncpg.UniqueViolationError):
        run(_insert_ledger("m3001-l3b", version=7))


def test_claim_discriminator_checks() -> None:
    async def bad_confidence() -> None:
        conn = await asyncpg.connect(DSN)
        try:
            await conn.execute(
                "INSERT INTO claims (claim_id, deliverable_id, block_id, text_span, "
                "confidence, citation_ids, alignment, promoted_fact_id) VALUES "
                "('m3001-c1', 'd-1', 'b-1', 't', 'certain', '[]'::jsonb, "
                "'pending', NULL)",
            )
        finally:
            await conn.close()

    with pytest.raises(asyncpg.CheckViolationError):
        run(bad_confidence())


def test_downgrade_upgrade_round_trip() -> None:
    alembic("downgrade", "0007")
    tables = run(_tables())
    assert {"facts_ledgers", "facts", "claims"}.isdisjoint(tables)
    alembic("upgrade", "head")
    assert {"facts_ledgers", "facts", "claims"} <= run(_tables())
