"""TS-006：Project 建 + chosen_topic + Gate 集成（topic→keywords→run_gate1 内核不变）。

- build_project / choose_topic（chosen ∈ topic_ids 校验）+ PgProjectStore 往返。
- topic_to_keywords：Topic.keyword_mapping 键+值去重派生；空则回退 seed.keywords。
- /analysis 加可选 topic_id：带 → 走派生 keywords；不带 → body.keywords（旧测绿）。
  run_gate1 内核逐字不变（本卡不改 gate1.py）。
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
from flint.domain.models import Principal, Topic, TopicSeed, WhyNow
from flint.jobs.events import PgJobEventStream
from flint.jobs.runner import PgJobRunner
from flint.topic.gate_adapter import topic_to_keywords
from flint.topic.project import ProjectValidationError, build_project, choose_topic
from flint.topic.store import PgProjectStore

pytestmark = pytest.mark.compose

DSN = os.environ.get("FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")
NOW = datetime(2026, 7, 26, 12, 0, 0, tzinfo=UTC)
OWNER = Principal(kind="user", id="u-1")


def run(coro: Any) -> Any:
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def _clean() -> Any:
    async def wipe() -> None:
        conn = await asyncpg.connect(DSN)
        try:
            await conn.execute("DELETE FROM projects WHERE project_id LIKE 'ts-%'")
            await conn.execute("DELETE FROM jobs WHERE job_id LIKE 'ts006-%'")
            await conn.execute("DELETE FROM idempotency_keys")
        finally:
            await conn.close()
    run(wipe())
    yield
    run(wipe())


def _topic(tid: str, mapping: dict[str, list[str]]) -> Topic:
    return Topic(topic_id=tid, seed_id="ts-s1", one_liner="x",
                 target_user_tag="u", form_factor_tag="f",
                 why_now=WhyNow(claim="c", evidences=[], speculative=True),
                 keyword_mapping=mapping, embedding=[0.0] * 1024)


# ── topic_to_keywords ────────────────────────────────────────────
def test_topic_to_keywords_flattens_mapping_deduped() -> None:
    topic = _topic("ts-t1", {"扩散模型": ["diffusion", "生成式"], "药物": ["diffusion"]})
    assert topic_to_keywords(topic) == ["扩散模型", "diffusion", "生成式", "药物"]


def test_hypothesis_never_leaks_into_keywords() -> None:
    # owner #8：关联假设=人类判断，NEVER 喂 gate。seed.hypothesis 绝不入派生 keywords。
    topic = _topic("ts-th", {"扩散模型": ["diffusion"]})
    seed = TopicSeed(seed_id="ts-s1", origin_id="ts-o1", keywords=["kw"],
                     hypothesis="这条关联假设绝不该进 gate", context_text="c")
    derived = topic_to_keywords(topic, seed)
    assert "这条关联假设绝不该进 gate" not in derived
    assert derived == ["扩散模型", "diffusion"]      # 只有 mapping 派生


def test_topic_to_keywords_falls_back_to_seed() -> None:
    topic = _topic("ts-t2", {})
    seed = TopicSeed(seed_id="ts-s1", origin_id="ts-o1",
                     keywords=["固态电池", "钠离子"], hypothesis=None, context_text="c")
    assert topic_to_keywords(topic, seed) == ["固态电池", "钠离子"]
    assert topic_to_keywords(topic) == []          # 无 mapping 无 seed → 空


# ── build_project / choose_topic ─────────────────────────────────
def test_build_and_choose_topic_roundtrip() -> None:
    project = build_project(project_id="ts-p1", owner=OWNER, origin_id="ts-o1",
                            topic_ids=["ts-t1", "ts-t2"], created_at=NOW)
    assert project.chosen_topic_id is None
    assert project.deliverable_ids == [] and project.change_log == []
    chosen = choose_topic(project, "ts-t2")
    assert chosen.chosen_topic_id == "ts-t2"
    assert chosen.topic_ids == ["ts-t1", "ts-t2"]   # 其余不变
    run(PgProjectStore(dsn=DSN).save(chosen))
    assert run(PgProjectStore(dsn=DSN).load("ts-p1")) == chosen


def test_choose_topic_rejects_foreign_topic() -> None:
    project = build_project(project_id="ts-p2", owner=OWNER, origin_id="ts-o1",
                            topic_ids=["ts-t1"], created_at=NOW)
    with pytest.raises(ProjectValidationError):
        choose_topic(project, "ts-t-not-in-project")


# ── /analysis backward-compat + topic_id 派生 ────────────────────
def _make_app(enqueued: list[dict[str, Any]], resolver: Any = None) -> Any:
    async def enqueue(job_id: str, kind: str, payload: dict[str, Any]) -> None:
        enqueued.append(payload)   # 捕获喂给 gate 的 payload（含 keywords）

    deps = AnalysisApiDeps(
        dsn=DSN,
        runner=PgJobRunner(dsn=DSN, role_resolver=lambda u, o: None,
                           id_factory=lambda: f"ts006-{uuid4().hex[:10]}",
                           enqueue=enqueue),
        events=PgJobEventStream(dsn=DSN),
        owner_scope_for_project=lambda pid: Principal(kind="user", id="u-1"),
        role_resolver=lambda u, o: None,
        topic_keywords_for=resolver,
    )
    return create_analysis_app(deps)


def test_analysis_without_topic_id_uses_body_keywords() -> None:
    calls: list[str] = []
    enqueued: list[dict[str, Any]] = []

    async def resolver(topic_id: str) -> list[str]:
        calls.append(topic_id)
        return ["should-not-be-used"]

    app = _make_app(enqueued, resolver)

    async def scenario() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
            resp = await c.post("/projects/ts-p/analysis",
                                json={"keywords": ["固态电池"], "budget_cny": 10.0},
                                headers={"X-User-Id": "u-1"})
            assert resp.status_code == 200, resp.text
    run(scenario())
    assert enqueued[0]["keywords"] == ["固态电池"]     # 旧路径不变
    assert calls == []                                 # resolver 未被调用


def test_analysis_with_topic_id_derives_keywords() -> None:
    enqueued: list[dict[str, Any]] = []

    async def resolver(topic_id: str) -> list[str]:
        assert topic_id == "ts-t9"
        return ["扩散模型", "药物发现"]

    app = _make_app(enqueued, resolver)

    async def scenario() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
            resp = await c.post("/projects/ts-p/analysis",
                                json={"topic_id": "ts-t9", "budget_cny": 10.0},
                                headers={"X-User-Id": "u-1"})
            assert resp.status_code == 200, resp.text
    run(scenario())
    assert enqueued[0]["keywords"] == ["扩散模型", "药物发现"]  # 派生 keywords
