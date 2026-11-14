"""E2E-01 · 在**装配后的 ASGI 应用 + 真队列**上跑完整主链路。

## 与 `ASM-05` 那 7 条的区别（卡面 acceptance④ 点名要写）

| | `ASM-05`（`tests/v041/test_asm_05_e2e.py`） | 本卡 |
|---|---|---|
| 客户端打的应用 | `create_compose_app(...)` / `create_deliverables_app(...)` —— **每族各造一个** | `harness/e2e_stack.py#build_e2e_app` —— **`create_app` 装配后的那一个** |
| 队列 | 真 arq（`build_enqueue_hook` + `build_worker`） | 同 |
| gate1 | **不在链上**（它从 seed 好的 claim 直接进组稿） | **在链上**：`POST /projects/{id}/analysis` → 队列 → `run_gate1` 四步 → 判定落盘 |
| 外部源 | 组稿 provider 回放 | 组稿 provider 回放 **+** gate1 的检索走 `fixtures/gate1_live/` 录制 |

**为什么这个区别要紧**：每族各造一个应用，测的是「这一族自己好不好」；
而线上跑的是**并进一个应用之后**的那份路由表。`WIRE-01` 那次漏掉 51 条路由，
正是因为没有任何判据在量装配后的样子——各族的测试当时全是绿的。

## 提交那两族在可部署应用里挂不上

`POST /projects/{id}/analysis` 与 `POST /projects/{id}/report` 属 `analysis` /
`compose` 两族，缺 `role_resolver` 与 runner 的装配面（`WIRE-01` 登记的
`UNWIRED_FAMILIES`，单子 `docs/blocked/WIRE-01-FOUR-FAMILIES-NEED-AUTH-AND-PROVIDER.md`）。
`harness/e2e_stack.py` 用夹具口径把这两族补上，并把「多出来的正好是这两族」
做成判据——**多一族要有人来确认它是不是也该进可部署应用**。
"""
from __future__ import annotations

import asyncio
import json
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import asyncpg
import httpx
import pytest
import respx
from arq import create_pool
from arq.connections import RedisSettings
from fastapi.testclient import TestClient

from flint.api.app import create_app, mounted_route_table
from flint.domain.models import Principal, UserProfile
from flint.evidence.search import GithubArxivSearcher
from flint.jobs.gate1 import (
    ANALYSIS_PRODUCT_PREFIX,
    analysis_product_id,
    build_live_deps,
)
from flint.jobs.worker_main import WorkerDeps, build_enqueue_hook, build_worker
from flint.llm.local import LocalProvider
from flint.testing.replay import HttpReplay
from harness.e2e_stack import E2EStackConfig, build_e2e_app, extra_families

pytestmark = pytest.mark.compose

REPO = Path(__file__).resolve().parents[2]
DSN = os.environ.get(
    "FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")
REDIS_URL = os.environ.get("FLINT_TEST_REDIS", "redis://localhost:56379/0")
FIXTURE = REPO / "fixtures" / "gate1_live" / "scripted" / "search.json"
TRACE = REPO / "docs" / "trace" / "E2E-01.md"
NOW = datetime(2026, 7, 26, 12, 0, 0, tzinfo=UTC)
PREFIX = "e2e01-"
PROSE = "本节由录制回放的组稿 provider 产出，用于端到端链路验证。"


def run(coro: Any) -> Any:
    return asyncio.run(coro)


def _profile() -> UserProfile:
    return UserProfile(
        profile_id=f"{PREFIX}profile", owner=Principal(kind="user", id="u-e2e"),
        identity={}, research={}, team=[], assets={}, constraints={},
        track_record=[], locale="zh-CN", sensitivity_overrides={}, updated_at=NOW)


def _compose_provider() -> LocalProvider:
    """组稿 provider：回放。`MockTransport` 不经默认传输，respx 护栏照样罩得住别处。"""
    def respond(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "choices": [{"message": {
                "content": json.dumps(
                    {"blocks": [{"type": "paragraph", "text": PROSE, "fact_ids": []}]},
                    ensure_ascii=False),
                "tool_calls": [],
            }}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
        })
    return LocalProvider(
        base_url="http://replay.invalid/v1", model="replay",
        http_client=httpx.Client(transport=httpx.MockTransport(respond)))


async def _sql(statements: list[str]) -> None:
    conn = await asyncpg.connect(DSN)
    try:
        for stmt in statements:
            await conn.execute(stmt)
    finally:
        await conn.close()


def _wipe() -> None:
    run(_sql([
        f"DELETE FROM job_events WHERE job_id LIKE '{PREFIX}%'",
        f"DELETE FROM job_steps WHERE job_id LIKE '{PREFIX}%'",
        f"DELETE FROM jobs WHERE job_id LIKE '{PREFIX}%'",
        f"DELETE FROM snapshots WHERE snapshot_id LIKE 'snap-{PREFIX}%'",
        f"DELETE FROM blocks WHERE deliverable_id LIKE 'del-{PREFIX}%'",
        f"DELETE FROM generation_records WHERE record_id LIKE 'rec-{PREFIX}%'",
        f"DELETE FROM deliverables WHERE deliverable_id LIKE 'del-{PREFIX}%'",
        f"DELETE FROM claims WHERE claim_id LIKE '{PREFIX}%'",
        "DELETE FROM claims WHERE deliverable_id LIKE "
        + f"'{ANALYSIS_PRODUCT_PREFIX}{PREFIX}%'",
        f"DELETE FROM projects WHERE project_id LIKE '{PREFIX}%'",
    ]))


def _seed_project(project_id: str) -> None:
    """`WIRE-07` 之后 `owner_scope_for_project` 是**真的**：它查 `projects.owner`。

    改前这一栈用的是常量归属，项目行不存在也照跑；现在项目不存在会抛
    `ProjectNotFound`（端点转 404）——那是对的行为，夹具得给它一行真项目。
    """
    owner = json.dumps({"kind": "user", "id": "u-e2e"})
    run(_sql([(
        f"INSERT INTO projects (project_id, owner, origin_id, topic_ids, "
        f"chosen_topic_id, deliverable_ids, change_log, status, created_at) "
        f"VALUES ('{project_id}', '{owner}'::jsonb, 'o', '[]'::jsonb, NULL, "
        f"'[]'::jsonb, '[]'::jsonb, 'active', now()) "
        f"ON CONFLICT (project_id) DO NOTHING"
    )]))


def _enqueue_for(queue: str) -> Any:
    async def enqueue(job_id: str, kind: Any, payload: Any) -> None:
        pool = await create_pool(RedisSettings.from_dsn(REDIS_URL))
        try:
            await build_enqueue_hook(pool, queue_name=queue)(job_id, kind, payload)
        finally:
            await pool.aclose()
    return enqueue


async def _queued(queue: str, job_id: str) -> bool:
    pool = await create_pool(RedisSettings.from_dsn(REDIS_URL))
    try:
        return await pool.zscore(queue, f"arq-{job_id}") is not None
    finally:
        await pool.aclose()


async def _consume(queue: str, gate1_deps: Any) -> tuple[int, int]:
    deps = WorkerDeps(
        dsn=DSN, redis_url=REDIS_URL, repo_root=REPO, profile=_profile(), now=NOW,
        compose_provider=_compose_provider(), gate1_deps=gate1_deps)
    worker = build_worker(deps, queue_name=queue, burst=True)
    try:
        await worker.async_run()
    finally:
        await worker.close()
    return worker.jobs_complete, worker.jobs_failed


async def _job(job_id: str) -> dict[str, Any] | None:
    conn = await asyncpg.connect(DSN)
    try:
        row = await conn.fetchrow(
            "SELECT state, error FROM jobs WHERE job_id=$1", job_id)
    finally:
        await conn.close()
    return dict(row) if row is not None else None


async def _snapshot(job_id: str, suffix: str) -> Any:
    conn = await asyncpg.connect(DSN)
    try:
        payload: bytes | None = await conn.fetchval(
            "SELECT payload FROM snapshots WHERE snapshot_id=$1",
            f"snap-{job_id}-{suffix}")
    finally:
        await conn.close()
    return None if payload is None else json.loads(payload.decode("utf-8"))


@pytest.fixture(scope="module")
def chain() -> Any:
    """跑一整条链，结果给下面几条判据共用。**全程罩零路由 respx**（acceptance②）。"""
    _wipe()
    tag = uuid.uuid4().hex[:8]
    queue = f"arq:e2e01-{tag}"
    project = f"{PREFIX}p-{tag}"

    ids = iter([f"{PREFIX}unused-{tag}"])   # 两个 id 都由服务端给，这里不再用
    cfg = E2EStackConfig(
        dsn=DSN, user_id="u-e2e", now=lambda: NOW, enqueue=_enqueue_for(queue),
        job_ids=lambda: next(ids), topic_keywords_for=lambda *_a, **_k: ["检索增强生成"],
        redis_url=REDIS_URL, queue_name=queue)
    out: dict[str, Any] = {"queue": queue}

    _seed_project(project)

    with (
        respx.mock(assert_all_mocked=True) as router,
        HttpReplay(FIXTURE, "replay") as replay,
    ):
        searcher = GithubArxivSearcher(
            replay.client(), NOW, per_source=2, resilient=True)
        gate1_deps = build_live_deps(DSN, REPO, _scripted_provider(), searcher, NOW)
        app = build_e2e_app(cfg)
        with TestClient(app) as client:
            out["submit_analysis"] = _post(
                client, f"/projects/{project}/analysis",
                {"keywords": ["检索增强生成"], "locale": "en", "budget_cny": 1.0})
            # **作业 id 由服务端给**：`create_app` 自己的 runner 有自己的
            # id_factory（`WIRE-07` 之后 analysis 归它管），夹具那个 id 生成器
            # 只管 compose 那一半。假设 id 会撞上「队列里没有它」——实测撞过。
            analysis_job = out["submit_analysis"].json()["job_id"]
            out["analysis_job_id"] = analysis_job
            out["analysis_queued"] = run(_queued(queue, analysis_job))
            out["consumed_1"] = run(_consume(queue, gate1_deps))
            out["analysis_job"] = run(_job(analysis_job))
            out["verdict"] = run(_snapshot(analysis_job, "verdict"))

            # **CHAIN-02：这里原来种一条 claim**。`CHAIN-01` 之后 gate1
            # 自己把 support_claims 落成 claims 行，来源 id 就是那次判定的
            # **分析产物 id**——组稿那侧一个字不用改，它把 payload 里的
            # `analysis_id` 原样当来源 id 用。
            source = analysis_product_id(analysis_job)
            out["source"] = source
            out["claims_from_gate1"] = run(_claims_for(source))
            out["submit_report"] = _post(
                client, f"/projects/{project}/report",
                {"analysis_id": source, "template_id": "generic"})
            # 同 analysis：`WIRE-08` 之后 compose 也归 `create_app`，
            # **两个作业 id 都由服务端给**。
            report_job = out["submit_report"].json()["job_id"]
            out["report_job_id"] = report_job
            out["report_queued"] = run(_queued(queue, report_job))
            out["consumed_2"] = run(_consume(queue, None))
            out["report_job"] = run(_job(report_job))

            out["claim_shapes"] = run(_claim_shapes(source))
            out["facts_from_source"] = run(_facts_from(source))
            deliverable = f"del-{report_job}"
            out["deliverable_id"] = deliverable
            out["blocks"] = client.get(f"/deliverables/{deliverable}/blocks")
            out["render_ok"] = client.get(
                f"/deliverables/{deliverable}/render", params={"fmt": "markdown"})
            _set_blocking(deliverable)
            out["render_blocked"] = client.get(
                f"/deliverables/{deliverable}/render", params={"fmt": "markdown"})
        out["went_out"] = [f"{c.request.method} {c.request.url}" for c in router.calls]
    return out


def _scripted_provider() -> Any:
    from harness.gate1_live import ScriptedGateProvider

    return ScriptedGateProvider()


def _post(client: TestClient, path: str, body: dict[str, Any]) -> Any:
    return client.post(path, json=body, headers={"X-User-Id": "u-e2e"})


def _set_blocking(deliverable_id: str) -> None:
    run(_sql([(
        "UPDATE blocks SET needs_review = true, review_reason = 'fact_removed', "
        f"review_severity = 'blocking' WHERE deliverable_id = '{deliverable_id}'"
    )]))


# ───────────────────────── acceptance①：装配后的应用上跑完整主链


def test_the_stack_adds_no_family_to_the_deployable_app_anymore() -> None:
    """夹具栈 = 可部署应用，**一族都不多**。

    **`WIRE-07` 之后这条判据变过一次**：那时 `analysis` 也在这份名单里，
    它进了可部署应用之后这条当场变红——**红得对**，它就是来提醒这件事的。
    多一族要有人来确认它是不是也该进可部署应用；少一族说明又进去了一族、这里该收。
    """
    cfg = E2EStackConfig(
        dsn="postgresql://x@127.0.0.1:1/y", user_id="u", now=lambda: NOW,
        enqueue=lambda *_a: None, job_ids=lambda: "j",
        topic_keywords_for=lambda *_a, **_k: [])
    base = {(m, r.path) for r in mounted_route_table(
        create_app("postgresql://x@127.0.0.1:1/y")) for m in r.methods}
    full = {(m, r.path) for r in mounted_route_table(build_e2e_app(cfg))
            for m in r.methods}

    assert base - full == set(), f"可部署应用有的，夹具栈却没有：{sorted(base - full)}"
    assert full - base == set(), f"夹具栈还多着这些：{sorted(full - base)}"
    assert extra_families() == ()


def test_both_submissions_went_through_the_queue(chain: dict[str, Any]) -> None:
    """两次提交都**经过队列**：入队看得见，worker 各消费一条。

    直接调 handler 也能让后面的断言全绿——这条判据把队列那一段单独钉住。
    """
    assert chain["submit_analysis"].status_code == 200, chain["submit_analysis"].text
    assert chain["analysis_queued"], "gate1 作业没进队列"
    assert chain["consumed_1"] == (1, 0), f"gate1 那轮 worker 计数不对：{chain['consumed_1']}"

    assert chain["submit_report"].status_code == 200, chain["submit_report"].text
    assert chain["report_queued"], "report 作业没进队列"
    assert chain["consumed_2"] == (1, 0), f"组稿那轮 worker 计数不对：{chain['consumed_2']}"


def test_gate1_ran_and_left_a_verdict(chain: dict[str, Any]) -> None:
    """gate1 那半：作业 done，判定落盘。"""
    job = chain["analysis_job"]

    assert job is not None and job["state"] == "done", f"gate1 作业没跑完：{job}"
    assert chain["verdict"], "判定没落盘"


def test_compose_and_render_produced_real_content(chain: dict[str, Any]) -> None:
    """组稿 → 渲染：块树非空且有正文段，markdown 非空。

    只判 200 不够——**占位生成器只产 heading**，那时 `/blocks` 也是 200。
    """
    blocks = chain["blocks"]
    assert blocks.status_code == 200, blocks.text
    kinds = [b["type"] for b in blocks.json()["blocks"]]
    assert kinds, "块树是空的"
    assert "paragraph" in kinds, f"没有正文段（块型={kinds}）——生产生成器没接上"

    render = chain["render_ok"]
    assert render.status_code == 200, render.text
    assert render.text.strip(), "渲染出了空 markdown"


# ───────────────────────── acceptance③：导出门禁两种用例


def test_the_export_gate_blocks_when_a_blocking_review_is_open(
    chain: dict[str, Any],
) -> None:
    """同一份交付物：干净时 200，挂上 blocking 复核后 **409**。

    两种用例都要有——只测 409 的话，「门禁对谁都拒」也是 409。
    """
    assert chain["render_ok"].status_code == 200
    assert chain["render_blocked"].status_code == 409, chain["render_blocked"].text
    body = chain["render_blocked"].json()
    assert "EXPORT_BLOCKED" in json.dumps(body, ensure_ascii=False), body


# ───────────────────────── acceptance②：零真实出网


def test_nothing_reached_the_real_network(chain: dict[str, Any]) -> None:
    """整条链**一次都没有人试图出网**。

    回放客户端与 ASGI 传输都不经默认 http 传输；这层零路由的 respx
    罩的是**别处**任何新造的真实客户端。
    """
    assert chain["went_out"] == [], f"这一趟有人试图出网：{chain['went_out']}"


# ───────────────────────── acceptance④：与 ASM-05 的区别写下来


def test_the_difference_from_asm05_is_written_down() -> None:
    """卡面 acceptance④ 点名：区别要写进 trace。"""
    text = TRACE.read_text(encoding="utf-8")

    assert "ASM-05" in text
    assert "harness 直调" in text or "每族各造一个" in text
    assert "装配后" in text


def test_the_chain_now_runs_from_gate1_all_the_way_to_compose(
    chain: dict[str, Any],
) -> None:
    """**改前这条是守门断言**：它断言那个来源 id 下一条 claim 都没有，
    并写着「哪天接上了，这条会红——那时来这里把链路改成一条」。

    `CHAIN-01` 把那一跳接上了，`CHAIN-02` 兑现这句话：
    判据翻成**正向**——组稿读到的 claim 就是 gate1 落下来的那批，
    中间**没有任何人手种的行**。

    量的是三件事：来源 id 由判定推导（NEVER 是测试编的）、
    那批行真的在库里、且它们的 `claim_id` 不带测试前缀（不是种出来的）。
    """
    assert chain["source"] == analysis_product_id(chain["analysis_job_id"])
    assert chain["claims_from_gate1"] > 0, (
        "gate1 那半没产 claim——这一跳又断了")
    assert run(_seeded_claims_for(chain["source"])) == 0, (
        "还有人手种的行混在里面")


def test_the_chain_carries_conclusions_but_not_yet_citations(
    chain: dict[str, Any],
) -> None:
    """**据实记账**：那批 claim 是 `speculative`，账本里因此一条 Fact 都没有。

    原因不在本卡：钉引用那一步（`pin_verdict_citations`，把 quote_span
    钉进 `citations` 表）**只在 `gate1.main()` 的生产路径跑**，
    队列 worker 的 gate1 handler 不跑它。于是队列跑出来的判定
    有结论、没引用，`promote_claims` 一条都提不动（要 cited ∧ supports）。

    **NEVER 把这条写成「本来就该是 0」**：它是一处真实缺口，
    登记在 `docs/trace/CHAIN-01.md` §6 等 owner 裁。
    哪天钉引用那步进了队列路径，本条会红——那正是提醒来这里改判据的机制：
    到时候 `speculative` 变 `cited`，facts 从 0 变正。
    """
    assert chain["claim_shapes"] == [("speculative", "supports")], (
        f"claim 的形状变了：{chain['claim_shapes']}——"
        f"若是引用钉上了（cited），把本条与 facts 那行一起改成正数")
    assert chain["facts_from_source"] == 0, (
        f"账本里出现了 {chain['facts_from_source']} 条 Fact："
        f"引用钉上了？那是好事，来这里把判据改成它该有的数")


async def _seeded_claims_for(source: str) -> int:
    """带测试前缀的行 = 人手种的。本卡之后必须是 0。"""
    conn = await asyncpg.connect(DSN)
    try:
        count: int = await conn.fetchval(
            "SELECT count(*) FROM claims WHERE deliverable_id = $1 "
            "AND claim_id LIKE $2", source, f"{PREFIX}%")
    finally:
        await conn.close()
    return count


async def _claim_shapes(source: str) -> list[tuple[str, str]]:
    """那批 claim 的 (confidence, alignment) 各是什么——**据实取回**。"""
    conn = await asyncpg.connect(DSN)
    try:
        rows = await conn.fetch(
            "SELECT confidence, alignment FROM claims WHERE deliverable_id = $1 "
            "ORDER BY claim_id", source)
    finally:
        await conn.close()
    return [(str(r["confidence"]), str(r["alignment"])) for r in rows]


async def _facts_from(source: str) -> int:
    conn = await asyncpg.connect(DSN)
    try:
        count: int = await conn.fetchval(
            "SELECT count(*) FROM facts WHERE promoted_from = $1", source)
    finally:
        await conn.close()
    return count


async def _claims_for(source: str) -> int:
    conn = await asyncpg.connect(DSN)
    try:
        count: int = await conn.fetchval(
            "SELECT count(*) FROM claims WHERE deliverable_id = $1", source)
    finally:
        await conn.close()
    return count
