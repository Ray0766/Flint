"""每日簇质心快照 repo（H-4，迁移 0018）——弱信号轨质心历史落库（ingest 写机制）。"""
from __future__ import annotations

import asyncio
import json
import os
from datetime import date
from typing import Any

import asyncpg
import pytest

from flint.repo.centroid_daily import PgCentroidDailyStore

pytestmark = pytest.mark.compose

DSN = os.environ.get("FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")
DAY = date(2026, 7, 20)
VEC = "[" + ",".join(["0.5", *(["0.0"] * 1023)]) + "]"


def run(coro: Any) -> Any:
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def _wipe() -> Any:
    async def wipe() -> None:
        conn = await asyncpg.connect(DSN)
        try:
            await conn.execute(
                "DELETE FROM cluster_centroid_daily WHERE cluster_id LIKE 'ccd-%'")
            await conn.execute("DELETE FROM clusters WHERE cluster_id LIKE 'ccd-%'")
        finally:
            await conn.close()
    run(wipe())
    yield
    run(wipe())


def test_snapshot_from_clusters_copies_current_centroid() -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(DSN)
        try:
            for cid in ("ccd-1", "ccd-2", "ccd-untouched"):
                await conn.execute(
                    "INSERT INTO clusters (cluster_id, canonical_name, category_id, "
                    "centroid, status, first_seen, last_active, parent_cluster_ids, "
                    "merged_into, aliases) VALUES ($1, $1, 'cat-ai', $2, 'active', $3, "
                    "$3, '[]'::jsonb, NULL, '[]'::jsonb)", cid, VEC, DAY)
            store = PgCentroidDailyStore(DSN)
            await store.snapshot_from_clusters_on(conn, DAY, ["ccd-1", "ccd-2"])
            rows = await conn.fetch(
                "SELECT cluster_id, centroid FROM cluster_centroid_daily "
                "WHERE cluster_id LIKE 'ccd-%' AND day = $1 ORDER BY cluster_id", DAY)
            assert [str(r["cluster_id"]) for r in rows] == ["ccd-1", "ccd-2"]
            assert json.loads(rows[0]["centroid"])[0] == 0.5   # 质心从 clusters 直拷
            # 幂等：重拷不炸、不增行
            await store.snapshot_from_clusters_on(conn, DAY, ["ccd-1", "ccd-2"])
            n = await conn.fetchval(
                "SELECT count(*) FROM cluster_centroid_daily WHERE cluster_id LIKE 'ccd-%'")
            assert n == 2
        finally:
            await conn.close()
    run(scenario())


def test_empty_cluster_ids_noop() -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(DSN)
        try:
            await PgCentroidDailyStore(DSN).snapshot_from_clusters_on(conn, DAY, [])
            n = await conn.fetchval(
                "SELECT count(*) FROM cluster_centroid_daily WHERE cluster_id LIKE 'ccd-%'")
            assert n == 0
        finally:
            await conn.close()
    run(scenario())
