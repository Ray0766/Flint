"""M1-003 acceptance tests: baseline migration (index-layer 5 tables + vector index).

Acceptance (tasks.json M1-003):
  - upgrade -> downgrade -> upgrade round-trips cleanly (exercised by verify_cmd)
  - keywords.embedding = vector(1024) + HNSW(m=16)
"""
from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from pathlib import Path

import asyncpg
import pytest

pytestmark = pytest.mark.compose

REPO_ROOT = Path(__file__).resolve().parents[2]
DSN = os.environ.get(
    "FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test"
)
INDEX_TABLES = {"categories", "keywords", "clusters", "heat_points", "evidence_cards"}


def _alembic_env() -> dict[str, str]:
    """alembic 子进程 MUST 迁移 DSN 指的那个库（见 tests/m3/test_m3_001.py 同名函数）。

    migrations/env.py 的 DEFAULT_URL 指向 demo 库；不传 DATABASE_URL 就会打在 demo 上。
    """
    url = DSN.replace("postgresql://", "postgresql+asyncpg://", 1)
    return {**os.environ, "DATABASE_URL": url}


def alembic(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
        env=_alembic_env(),
        # 迁移消息是中文、alembic 按 UTF-8 输出；Windows 下 text=True 默认按 GBK 解码，
        # 整套跑时（迁移真有输出那次）会在读取线程里抛 UnicodeDecodeError。
        # 与 tests/m2/test_m2_001.py 的 alembic 助手取同一写法。
        encoding="utf-8",
        errors="replace",
    )


def fetch(query: str) -> list[asyncpg.Record]:
    async def run() -> list[asyncpg.Record]:
        conn = await asyncpg.connect(DSN)
        try:
            return await conn.fetch(query)
        finally:
            await conn.close()

    return asyncio.run(run())


@pytest.fixture(scope="module")
def migrated() -> None:
    result = alembic("upgrade", "head")
    assert result.returncode == 0, f"alembic upgrade failed:\n{result.stderr}"


def test_five_index_tables_exist(migrated: None) -> None:
    rows = fetch(
        "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
    )
    tables = {r["tablename"] for r in rows}
    missing = INDEX_TABLES - tables
    assert not missing, f"missing index-layer tables: {missing}"


def test_keywords_embedding_is_vector_1024(migrated: None) -> None:
    rows = fetch(
        "SELECT format_type(atttypid, atttypmod) AS t FROM pg_attribute "
        "WHERE attrelid = 'keywords'::regclass AND attname = 'embedding'"
    )
    assert rows and rows[0]["t"] == "vector(1024)"


def test_keywords_hnsw_index_m16(migrated: None) -> None:
    rows = fetch(
        "SELECT indexdef FROM pg_indexes WHERE tablename = 'keywords' "
        "AND indexdef ILIKE '%hnsw%'"
    )
    assert rows, "keywords has no HNSW index"
    indexdef = rows[0]["indexdef"]
    assert "m='16'" in indexdef
    assert "ef_construction='64'" in indexdef
    assert "vector_cosine_ops" in indexdef


def test_clusters_centroid_vector_and_hnsw(migrated: None) -> None:
    rows = fetch(
        "SELECT format_type(atttypid, atttypmod) AS t FROM pg_attribute "
        "WHERE attrelid = 'clusters'::regclass AND attname = 'centroid'"
    )
    assert rows and rows[0]["t"] == "vector(1024)"
    idx = fetch(
        "SELECT indexdef FROM pg_indexes WHERE tablename = 'clusters' "
        "AND indexdef ILIKE '%hnsw%'"
    )
    assert idx, "clusters has no HNSW index"


def test_keywords_upsert_key_unique(migrated: None) -> None:
    """M1-021 depends on canonical+lang idempotent upsert — the key must be
    unique at the schema level."""
    rows = fetch(
        "SELECT indexdef FROM pg_indexes WHERE tablename = 'keywords' "
        "AND indexdef ILIKE '%UNIQUE%' AND indexdef ILIKE '%canonical%'"
    )
    assert rows, "no unique index on keywords(canonical, lang)"
    assert "lang" in rows[0]["indexdef"]


def test_heat_points_partitioned_by_day_range(migrated: None) -> None:
    rows = fetch(
        "SELECT partstrat::text AS strat FROM pg_partitioned_table "
        "WHERE partrelid = 'heat_points'::regclass"
    )
    assert rows and rows[0]["strat"] == "r", "heat_points must be RANGE partitioned"


def test_cluster_status_constrained(migrated: None) -> None:
    rows = fetch(
        "SELECT conname FROM pg_constraint "
        "WHERE conrelid = 'clusters'::regclass AND contype = 'c'"
    )
    assert rows, "clusters.status needs a CHECK constraint (active/dormant/merged)"


def test_alembic_version_at_head(migrated: None) -> None:
    heads = sorted(
        p.name.split("_")[0] for p in (REPO_ROOT / "migrations" / "versions").glob("*.py")
    )
    rows = fetch("SELECT version_num FROM alembic_version")
    assert rows and rows[0]["version_num"] == heads[-1]
