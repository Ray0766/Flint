"""TS-010：POST /projects/combo 端到端 + analysis topic_keywords_for 接线。

combo 端点：真实读 evidence_cards 校验 + 合成 provider 编排 → 持久化 → 返 project/topics。
analysis 接线：resolver 从持久化 Topic 派生 keywords。真机 qwen3.6 NEVER 触（合成 provider）。
"""
from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import asyncpg
import httpx
import pytest

from flint.api.analysis import AnalysisApiDeps, create_analysis_app
from flint.api.combo import (
    ComboApiDeps,
    create_combo_app,
    make_topic_keywords_resolver,
)
from flint.domain.models import JSON, Principal
from flint.embed import DeterministicHashBackend, EmbeddingService
from flint.jobs.events import PgJobEventStream
from flint.jobs.runner import PgJobRunner
from flint.topic.store import PgProjectStore, PgTopicStore

pytestmark = pytest.mark.compose

DSN = os.environ.get("FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")
NOW = datetime(2026, 7, 26, 12, 0, 0, tzinfo=UTC)


def run(coro: Any) -> Any:
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def _clean() -> Any:
    async def wipe() -> None:
        conn = await asyncpg.connect(DSN)
        try:
            for stmt in (
                "DELETE FROM projects WHERE project_id LIKE 'proj-ts010%'",
                "DELETE FROM topics WHERE topic_id LIKE 'topic-ts010%'",
                "DELETE FROM generation_records WHERE record_id LIKE 'gr-ts010%'",
                "DELETE FROM topic_seeds WHERE seed_id LIKE 'seed-ts010%'",
                "DELETE FROM origins WHERE origin_id LIKE 'origin-ts010%'",
                "DELETE FROM jobs WHERE job_id LIKE 'ts010-%'",
                "DELETE FROM idempotency_keys",
            ):
                await conn.execute(stmt)
        finally:
            await conn.close()
    run(wipe())
    yield
    run(wipe())


async def _pick_cross_cluster(n: int) -> list[str]:
    conn = await asyncpg.connect(DSN)
    try:
        rows = await conn.fetch(
            "SELECT card_id, cluster_id FROM evidence_cards "
            "WHERE jsonb_array_length(keyword_ids) > 0 ORDER BY card_id")
    finally:
        await conn.close()
    picks: list[str] = []
    used: set[str] = set()
    for r in rows:
        cid = str(r["cluster_id"])
        if cid in used:
            continue
        used.add(cid)
        picks.append(str(r["card_id"]))
        if len(picks) == n:
            break
    if len(picks) < n:
        pytest.skip(f"local PG has <{n} distinct-cluster cards")
    return picks


def _payload(i: int) -> JSON:
    return {
        "one_liner": f"主题 {i}", "target_user_tag": f"u{i}", "form_factor_tag": f"f{i}",
        "why_now": {"claim": f"c{i}", "evidences": []},
        "keyword_mapping": {"扩散模型": [f"kw{i}", "diffusion"]},
    }


class SequenceProvider:
    def __init__(self) -> None:
        self._i = 0
        self.calls = 0

    def generate(self, prompt: str, tools: list[JSON] | None) -> object:
        raise NotImplementedError

    def generate_structured(self, prompt: str, schema: JSON, max_retries: int) -> JSON:
        payload = _payload(self._i)
        self._i += 1
        self.calls += 1
        return payload


def _combo_app(provider: Any) -> Any:
    counter = {"n": 0}

    def id_factory() -> str:
        counter["n"] += 1
        return f"ts010{counter['n']}"

    return create_combo_app(ComboApiDeps(
        dsn=DSN, provider=provider,
        embed_service=EmbeddingService(DeterministicHashBackend(dim=1024)),
        model="qwen3.6", id_factory=id_factory, now=lambda: NOW, target=6))


def test_combo_endpoint_creates_origin_topics_project() -> None:
    cards = run(_pick_cross_cluster(2))
    app = _combo_app(SequenceProvider())

    async def scenario() -> str:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
            resp = await c.post("/projects/combo",
                                json={"card_ids": cards, "hypothesis": "跨热点联想"},
                                headers={"X-User-Id": "u-1"})
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert 5 <= len(body["topic_ids"]) <= 8         # combo 5~8
            return str(body["project_id"])

    project_id = run(scenario())
    # 持久化验证：project + topics 落库
    project = run(PgProjectStore(dsn=DSN).load(project_id))
    assert project.topic_ids and project.chosen_topic_id is None
    topic = run(PgTopicStore(dsn=DSN).load(project.topic_ids[0]))
    assert topic.one_liner.startswith("主题")


def test_combo_endpoint_rejects_single_card() -> None:
    cards = run(_pick_cross_cluster(1))
    app = _combo_app(SequenceProvider())

    async def scenario() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
            resp = await c.post("/projects/combo",
                                json={"card_ids": cards, "hypothesis": "h"},
                                headers={"X-User-Id": "u-1"})
            assert resp.status_code == 400                  # 越下界拒
            assert resp.json()["code"] == "VALIDATION_FAILED"
    run(scenario())


def test_topic_keywords_resolver_wires_analysis() -> None:
    # 建 combo → 拿一个 topic_id → analysis 接 resolver → 派生 keywords 入 gate payload
    cards = run(_pick_cross_cluster(2))
    combo = _combo_app(SequenceProvider())

    async def make() -> tuple[str, list[str]]:
        transport = httpx.ASGITransport(app=combo)
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
            resp = await c.post("/projects/combo",
                                json={"card_ids": cards, "hypothesis": "h"},
                                headers={"X-User-Id": "u-1"})
            pid = resp.json()["project_id"]
        project = await PgProjectStore(dsn=DSN).load(pid)
        topic_id = project.topic_ids[0]
        topic = await PgTopicStore(dsn=DSN).load(topic_id)
        from flint.topic.gate_adapter import topic_to_keywords
        return topic_id, topic_to_keywords(topic)

    topic_id, expected_kw = run(make())

    enqueued: list[JSON] = []

    async def enqueue(job_id: str, kind: str, payload: JSON) -> None:
        enqueued.append(payload)

    analysis = create_analysis_app(AnalysisApiDeps(
        dsn=DSN,
        runner=PgJobRunner(dsn=DSN, role_resolver=lambda u, o: None,
                           id_factory=lambda: f"ts010-{uuid4().hex[:8]}",
                           enqueue=enqueue),
        events=PgJobEventStream(dsn=DSN),
        owner_scope_for_project=lambda pid: Principal(kind="user", id="u-1"),
        role_resolver=lambda u, o: None,
        topic_keywords_for=make_topic_keywords_resolver(DSN)))

    async def scenario() -> None:
        transport = httpx.ASGITransport(app=analysis)
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
            resp = await c.post("/projects/p/analysis",
                                json={"topic_id": topic_id, "budget_cny": 10.0},
                                headers={"X-User-Id": "u-1"})
            assert resp.status_code == 200, resp.text
    run(scenario())
    assert enqueued[0]["keywords"] == expected_kw          # resolver 派生真实 keywords
    assert expected_kw != []
