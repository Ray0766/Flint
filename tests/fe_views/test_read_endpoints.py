"""FE-VIEWS 三读端点验收（本地 PG 种子，离线零联网零付费 S2-7）。

① 广场 GET /plaza/hot?day= → 当日热点簇（clusters × heat_points，按 norm_score 排，
   带四源分值 + category）。② 工作台 GET /clusters/{id}/evidence-cards → 证据卡
   （top_links + flags + keyword_ids）。③ Gate GET /jobs/{id}/verdict → 四分类全字段
   （取自 snap-{job}-verdict）。全为**既有模型上的只读端点**，NEVER 改冻结件、NEVER 造数据。
"""
from __future__ import annotations

import asyncio
import json
import os
from datetime import UTC, date, datetime, timedelta
from typing import Any

import asyncpg
import httpx
import pytest

from flint.api.views import ViewsApiDeps, create_views_app

pytestmark = pytest.mark.compose

DSN = os.environ.get("FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")
NOW = datetime(2026, 7, 26, 12, 0, 0, tzinfo=UTC)
DAY = date(2026, 7, 20)
VEC = "[" + ",".join(["0"] * 1024) + "]"

VERDICT = {
    "verdict": "C_opportunity", "all_satisfied": ["A", "B"],
    "key_citation_ids": ["cit-1", "cit-2"], "rationale_fact_ids": ["fact-1"],
    "competitors": [{"name": "Acme", "url": "http://a", "strength": "weak",
                     "strength_signals": [], "pricing": None}],
    "constraints_checked": True,
    "gaps": [{"missing_what": "价格", "cause": "missing_data",
              "suggested_sources": [], "action": "search",
              "target_count": None, "required_scope": None}],
}


def run(coro: Any) -> Any:
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def _clean() -> Any:
    async def wipe() -> None:
        conn = await asyncpg.connect(DSN)
        try:
            await conn.execute("DELETE FROM evidence_cards WHERE card_id LIKE 'fv-%'")
            await conn.execute("DELETE FROM heat_points WHERE cluster_id LIKE 'fv-%'")
            await conn.execute(
                "DELETE FROM cluster_centroid_daily WHERE cluster_id LIKE 'fv-%'")
            await conn.execute("DELETE FROM clusters WHERE cluster_id LIKE 'fv-%'")
            await conn.execute("DELETE FROM snapshots WHERE snapshot_id LIKE 'snap-fv-%'")
        finally:
            await conn.close()
    run(wipe())
    yield
    run(wipe())


async def _seed() -> None:
    conn = await asyncpg.connect(DSN)
    try:
        for cid, name in [("fv-c1", "热点甲"), ("fv-c2", "热点乙")]:
            await conn.execute(
                "INSERT INTO clusters (cluster_id, canonical_name, category_id, centroid, "
                "status, first_seen, last_active, parent_cluster_ids, merged_into, aliases) "
                "VALUES ($1, $2, 'cat-ai', $3, 'active', $4, $4, '[]'::jsonb, NULL, '[]'::jsonb)",
                cid, name, VEC, DAY)
        for cid, src, norm in [("fv-c1", "arxiv", 0.9), ("fv-c1", "weibo", 0.5),
                               ("fv-c2", "gtrends", 0.3)]:
            await conn.execute(
                "INSERT INTO heat_points (cluster_id, source_id, day, raw_value, norm_score) "
                "VALUES ($1, $2, $3, $4, $4)", cid, src, DAY, norm)
        await conn.execute(
            "INSERT INTO evidence_cards (card_id, cluster_id, keyword_ids, flags, top_links) "
            "VALUES ('fv-card1', 'fv-c1', '[\"kw1\"]'::jsonb, '[\"novelty\"]'::jsonb, "
            "'[\"http://x\"]'::jsonb)")
        await conn.execute(
            "INSERT INTO snapshots (snapshot_id, payload, created_at) VALUES ($1, $2, $3)",
            "snap-fv-job1-verdict",
            json.dumps(VERDICT, ensure_ascii=False).encode("utf-8"), NOW)
    finally:
        await conn.close()


def _app() -> Any:
    return create_views_app(ViewsApiDeps(dsn=DSN))


async def _client(app: Any) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t")


def test_plaza_hot_clusters_sorted_with_per_source() -> None:
    run(_seed())

    async def scenario() -> None:
        async with await _client(_app()) as client:
            r = await client.get("/plaza/hot", params={"day": "2026-07-20"})
            assert r.status_code == 200
            body = r.json()
            assert body["day"] == "2026-07-20"
            cl = body["clusters"]
            # fv-c1 total 1.4 > fv-c2 total 0.3 → 排序
            assert [c["cluster_id"] for c in cl] == ["fv-c1", "fv-c2"]
            c1 = cl[0]
            assert c1["canonical_name"] == "热点甲" and c1["category_id"] == "cat-ai"
            assert c1["by_source"] == {"arxiv": 0.9, "weibo": 0.5}
            assert c1["total_heat"] == pytest.approx(1.4)
    run(scenario())


async def _seed_cross_source() -> None:
    # 同 agg（130）、同龄（DAY 首现）：fv-hx1 跨源印证（65+65）vs fv-hx2 单源猎奇（130）。
    conn = await asyncpg.connect(DSN)
    try:
        for cid in ("fv-hx1", "fv-hx2"):
            await conn.execute(
                "INSERT INTO clusters (cluster_id, canonical_name, category_id, centroid, "
                "status, first_seen, last_active, parent_cluster_ids, merged_into, aliases) "
                "VALUES ($1, $1, 'cat-ai', $2, 'active', $3, $3, '[]'::jsonb, NULL, '[]'::jsonb)",
                cid, VEC, DAY)
        for cid, src, norm in [("fv-hx1", "weibo", 65.0), ("fv-hx1", "arxiv", 65.0),
                               ("fv-hx2", "weibo", 130.0)]:
            await conn.execute(
                "INSERT INTO heat_points (cluster_id, source_id, day, raw_value, norm_score) "
                "VALUES ($1, $2, $3, $4, $4)", cid, src, DAY, norm)
    finally:
        await conn.close()


def test_plaza_cross_source_corroboration_ranks_ahead() -> None:
    # 主榜核心（owner 定案）：跨源印证排前、单源猎奇靠后；hotness 字段与分量暴露。
    run(_seed_cross_source())

    async def scenario() -> None:
        async with await _client(_app()) as client:
            r = await client.get("/plaza/hot", params={"day": "2026-07-20"})
            assert r.status_code == 200
            cl = r.json()["clusters"]
            assert [c["cluster_id"] for c in cl] == ["fv-hx1", "fv-hx2"]  # 跨源排前
            top = cl[0]
            assert top["hotness"] > cl[1]["hotness"]
            assert top["hotness_components"]["cross_count"] == 2
            assert top["hotness_components"]["multi_boost"] > 1.0
    run(scenario())


async def _seed_weak_signal() -> None:
    # 弱信号轨（H-4）：fv-ws1 小而在加速（5→25）+ 语义稳定质心 → 弱信号；fv-ws2 大 agg（90）→ 主榜料非弱信号。
    vec1 = "[" + ",".join(["1.0", *(["0.0"] * 1023)]) + "]"
    conn = await asyncpg.connect(DSN)
    try:
        for cid, fs in [("fv-ws1", DAY - timedelta(days=2)), ("fv-ws2", DAY)]:
            await conn.execute(
                "INSERT INTO clusters (cluster_id, canonical_name, category_id, centroid, "
                "status, first_seen, last_active, parent_cluster_ids, merged_into, aliases) "
                "VALUES ($1, $1, 'cat-ai', $2, 'active', $3, $4, '[]'::jsonb, NULL, '[]'::jsonb)",
                cid, VEC, fs, DAY)
        for cid, hday, norm in [("fv-ws1", DAY - timedelta(days=1), 5.0),
                                ("fv-ws1", DAY, 25.0), ("fv-ws2", DAY, 90.0)]:
            await conn.execute(
                "INSERT INTO heat_points (cluster_id, source_id, day, raw_value, norm_score) "
                "VALUES ($1, 'weibo', $2, $3, $3)", cid, hday, norm)
        for cid, cday in [("fv-ws1", DAY - timedelta(days=1)), ("fv-ws1", DAY),
                          ("fv-ws2", DAY)]:
            await conn.execute(
                "INSERT INTO cluster_centroid_daily (day, cluster_id, centroid) "
                "VALUES ($1, $2, $3::vector)", cday, cid, vec1)
    finally:
        await conn.close()


def test_plaza_weak_signal_lane_separate_from_main_board() -> None:
    # 弱信号单列一轨，NEVER 混主榜：小而在加速的进弱信号轨、大 agg 的只在主榜。
    run(_seed_weak_signal())

    async def scenario() -> None:
        async with await _client(_app()) as client:
            r = await client.get("/plaza/hot", params={"day": "2026-07-20"})
            assert r.status_code == 200
            body = r.json()
            main = [c["cluster_id"] for c in body["clusters"]]
            weak = [w["cluster_id"] for w in body["weak_signals"]]
            assert "fv-ws1" in main and "fv-ws2" in main       # 主榜含两者
            assert "fv-ws1" in weak and "fv-ws2" not in weak   # 弱信号轨只收小而在加速
            w1 = next(w for w in body["weak_signals"] if w["cluster_id"] == "fv-ws1")
            assert w1["velocity"] == 20.0 and w1["weak_score"] > 0.0
    run(scenario())


def test_workbench_evidence_cards_by_cluster() -> None:
    run(_seed())

    async def scenario() -> None:
        async with await _client(_app()) as client:
            r = await client.get("/clusters/fv-c1/evidence-cards")
            assert r.status_code == 200
            cards = r.json()["evidence_cards"]
            assert len(cards) == 1
            card = cards[0]
            assert card["card_id"] == "fv-card1"
            assert card["keyword_ids"] == ["kw1"]
            assert card["flags"] == ["novelty"]
            assert card["top_links"] == ["http://x"]
            # 未知 cluster → 空列表（非 404）
            r2 = await client.get("/clusters/fv-nope/evidence-cards")
            assert r2.status_code == 200 and r2.json()["evidence_cards"] == []
    run(scenario())


def test_gate_verdict_full_fields() -> None:
    run(_seed())

    async def scenario() -> None:
        async with await _client(_app()) as client:
            r = await client.get("/jobs/fv-job1/verdict")
            assert r.status_code == 200
            body = r.json()
            assert body["job_id"] == "fv-job1"
            v = body["verdict"]
            assert v["verdict"] == "C_opportunity"
            assert v["key_citation_ids"] == ["cit-1", "cit-2"]
            assert v["rationale_fact_ids"] == ["fact-1"]
            assert v["competitors"][0]["name"] == "Acme"
            assert v["gaps"][0]["missing_what"] == "价格"
            # 无 verdict 快照 → 404
            r2 = await client.get("/jobs/fv-nojob/verdict")
            assert r2.status_code == 404 and r2.json()["code"] == "NOT_FOUND"
    run(scenario())


def test_plaza_bad_day_400() -> None:
    async def scenario() -> None:
        async with await _client(_app()) as client:
            r = await client.get("/plaza/hot", params={"day": "not-a-date"})
            assert r.status_code == 400 and r.json()["code"] == "VALIDATION_FAILED"
    run(scenario())
