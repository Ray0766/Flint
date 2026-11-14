"""TS-001：主题子系统持久化 round-trip（本地 PG，迁移 0017）。

origins/topic_seeds/topics/projects 四表 + 4 repo（照冻结件）。save→load 保真；
topics.embedding vector(1024) 往返；WhyNow/Principal 判别嵌套往返。CI 离线（本地 PG）。
"""
from __future__ import annotations

import asyncio
import os
from datetime import UTC, date, datetime
from typing import Any

import asyncpg
import pytest

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


def run(coro: Any) -> Any:
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def _clean() -> Any:
    async def wipe() -> None:
        conn = await asyncpg.connect(DSN)
        try:
            await conn.execute("DELETE FROM projects WHERE project_id LIKE 'ts-%'")
            await conn.execute("DELETE FROM topics WHERE topic_id LIKE 'ts-%'")
            await conn.execute("DELETE FROM topic_seeds WHERE seed_id LIKE 'ts-%'")
            await conn.execute("DELETE FROM origins WHERE origin_id LIKE 'ts-%'")
        finally:
            await conn.close()
    run(wipe())
    yield
    run(wipe())


def test_origin_roundtrip() -> None:
    origin = Origin(
        origin_id="ts-o1", kind="combo",
        owner=Principal(kind="user", id="u-1"),
        payload={"card_ids": ["card-a", "card-b"], "hypothesis": "跨热点联想一句话"},
        created_at=NOW)
    run(PgOriginStore(dsn=DSN).save(origin))
    loaded = run(PgOriginStore(dsn=DSN).load("ts-o1"))
    assert loaded == origin


def test_topic_seed_roundtrip() -> None:
    run(PgOriginStore(dsn=DSN).save(Origin(
        origin_id="ts-o1", kind="combo", owner=Principal(kind="user", id="u"),
        payload={}, created_at=NOW)))
    seed = TopicSeed(seed_id="ts-s1", origin_id="ts-o1",
                     keywords=["kw1", "kw2"], hypothesis="关联假设",
                     context_text="上下文")
    run(PgTopicSeedStore(dsn=DSN).save(seed))
    assert run(PgTopicSeedStore(dsn=DSN).load("ts-s1")) == seed


def test_topic_roundtrip_with_vector_and_whynow() -> None:
    run(PgOriginStore(dsn=DSN).save(Origin(
        origin_id="ts-o1", kind="combo", owner=Principal(kind="user", id="u"),
        payload={}, created_at=NOW)))
    run(PgTopicSeedStore(dsn=DSN).save(TopicSeed(
        seed_id="ts-s1", origin_id="ts-o1", keywords=["k"], hypothesis=None,
        context_text="c")))
    topic = Topic(
        topic_id="ts-t1", seed_id="ts-s1", one_liner="一句话主题",
        target_user_tag="研究团队", form_factor_tag="SaaS",
        why_now=WhyNow(claim="现在正当时",
                       evidences=[WhyNowEvidence(event="事件", event_date=date(2026, 7, 1),
                                                 citation_id="cit-1")],
                       speculative=False),
        keyword_mapping={"k": ["kw1", "kw2"]},
        embedding=[0.1, 0.2, 0.3] + [0.0] * 1021)
    run(PgTopicStore(dsn=DSN).save(topic))
    loaded = run(PgTopicStore(dsn=DSN).load("ts-t1"))
    assert loaded.topic_id == "ts-t1"
    assert loaded.one_liner == "一句话主题"
    assert loaded.target_user_tag == "研究团队" and loaded.form_factor_tag == "SaaS"
    assert loaded.why_now.evidences[0].event_date == date(2026, 7, 1)
    assert loaded.why_now.speculative is False
    assert loaded.keyword_mapping == {"k": ["kw1", "kw2"]}
    assert loaded.embedding[:3] == [0.1, 0.2, 0.3] and len(loaded.embedding) == 1024
    # by_seed
    by_seed = run(PgTopicStore(dsn=DSN).by_seed("ts-s1"))
    assert [t.topic_id for t in by_seed] == ["ts-t1"]


def test_project_roundtrip() -> None:
    project = Project(
        project_id="ts-p1", owner=Principal(kind="org", id="org-1"),
        origin_id="ts-o1", topic_ids=["ts-t1", "ts-t2"], chosen_topic_id="ts-t1",
        deliverable_ids=[], change_log=[], status="active", created_at=NOW)
    run(PgProjectStore(dsn=DSN).save(project))
    assert run(PgProjectStore(dsn=DSN).load("ts-p1")) == project
