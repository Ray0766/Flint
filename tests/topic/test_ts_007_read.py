"""TS-007：主题只读端点 GET /projects/{id}/topics、GET /topics/{id}（FV-001 模式）。

只读既有 topics/projects（TS-001 落库）；未知 project→空、未知 topic→404。零写。
"""
from __future__ import annotations

import asyncio
import os
from datetime import UTC, date, datetime
from typing import Any

import asyncpg
import httpx
import pytest

from flint.api.views import ViewsApiDeps, create_views_app
from flint.domain.models import (
    Origin,
    Principal,
    Project,
    Topic,
    TopicSeed,
    WhyNow,
    WhyNowEvidence,
)
from flint.topic.store import (
    PgOriginStore,
    PgProjectStore,
    PgTopicSeedStore,
    PgTopicStore,
)

pytestmark = pytest.mark.compose

DSN = os.environ.get("FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")
NOW = datetime(2026, 7, 26, 12, 0, 0, tzinfo=UTC)
OWNER = Principal(kind="user", id="u-1")


def run(coro: Any) -> Any:
    return asyncio.run(coro)


def _topic(tid: str) -> Topic:
    return Topic(
        topic_id=tid, seed_id="ts-s1", one_liner=f"主题-{tid}",
        target_user_tag="研究团队", form_factor_tag="SaaS",
        why_now=WhyNow(claim="现在正当时",
                       evidences=[WhyNowEvidence("事件", date(2026, 7, 1), "cit-1")],
                       speculative=False),
        keyword_mapping={"k": ["kw1"]}, embedding=[0.1, 0.2] + [0.0] * 1022)


async def _wipe() -> None:
    conn = await asyncpg.connect(DSN)
    try:
        for stmt in (
            "DELETE FROM projects WHERE project_id LIKE 'ts-%'",
            "DELETE FROM topics WHERE topic_id LIKE 'ts-%'",
            "DELETE FROM topic_seeds WHERE seed_id LIKE 'ts-%'",
            "DELETE FROM origins WHERE origin_id LIKE 'ts-%'",
        ):
            await conn.execute(stmt)
    finally:
        await conn.close()


async def _setup() -> None:
    await _wipe()
    await PgOriginStore(dsn=DSN).save(Origin(
        origin_id="ts-o1", kind="combo", owner=OWNER, payload={}, created_at=NOW))
    await PgTopicSeedStore(dsn=DSN).save(TopicSeed(
        seed_id="ts-s1", origin_id="ts-o1", keywords=["k"], hypothesis=None,
        context_text="c"))
    await PgTopicStore(dsn=DSN).save(_topic("ts-t1"))
    await PgTopicStore(dsn=DSN).save(_topic("ts-t2"))
    await PgProjectStore(dsn=DSN).save(Project(
        project_id="ts-p1", owner=OWNER, origin_id="ts-o1",
        topic_ids=["ts-t1", "ts-t2"], chosen_topic_id="ts-t1",
        deliverable_ids=[], change_log=[], status="active", created_at=NOW))


@pytest.fixture(autouse=True)
def _seed() -> Any:
    run(_setup())
    yield
    run(_wipe())


def _app() -> Any:
    return create_views_app(ViewsApiDeps(dsn=DSN))


def test_get_single_topic_full_fields() -> None:
    async def scenario() -> None:
        transport = httpx.ASGITransport(app=_app())
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
            resp = await c.get("/topics/ts-t1")
            assert resp.status_code == 200, resp.text
            body = resp.json()["topic"]
            assert body["topic_id"] == "ts-t1"
            assert body["one_liner"] == "主题-ts-t1"
            assert body["target_user_tag"] == "研究团队"
            assert body["form_factor_tag"] == "SaaS"
            assert body["why_now"]["speculative"] is False
            assert body["why_now"]["evidences"][0]["citation_id"] == "cit-1"
            assert body["why_now"]["evidences"][0]["event_date"] == "2026-07-01"
            assert body["keyword_mapping"] == {"k": ["kw1"]}
    run(scenario())


def test_get_unknown_topic_404() -> None:
    async def scenario() -> None:
        transport = httpx.ASGITransport(app=_app())
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
            resp = await c.get("/topics/ts-nope")
            assert resp.status_code == 404
            assert resp.json()["code"] == "NOT_FOUND"
    run(scenario())


def test_get_project_topics() -> None:
    async def scenario() -> None:
        transport = httpx.ASGITransport(app=_app())
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
            resp = await c.get("/projects/ts-p1/topics")
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert body["project_id"] == "ts-p1"
            assert body["chosen_topic_id"] == "ts-t1"
            ids = [t["topic_id"] for t in body["topics"]]
            assert ids == ["ts-t1", "ts-t2"]           # project.topic_ids 序
    run(scenario())


def test_get_unknown_project_empty() -> None:
    async def scenario() -> None:
        transport = httpx.ASGITransport(app=_app())
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
            resp = await c.get("/projects/ts-nope/topics")
            assert resp.status_code == 200            # 未知 project → 空（非 404）
            body = resp.json()
            assert body["topics"] == [] and body["chosen_topic_id"] is None
    run(scenario())
