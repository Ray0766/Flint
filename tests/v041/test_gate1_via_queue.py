"""QUEUE-01 · 经作业队列跑通 gate1（回放，非红线）。

## 这条链路缺的是注入，不是网络授权

`DEC-033②` 逐字：「**「经作业队列（`jobs` 表 → `worker_main` 消费）跑通 gate1」
缺的是 `gate1_deps` 注入而非网络授权** → 单开普通卡，走 respx 回放验证，
NEVER 继续挂红线。」

这份判据把那句话做成可执行的两半：

1. **注入了** → 提交 → `jobs` 表 → arq → `worker_main` 消费 → `run_gate1` 四步 →
   判定落盘。全程走 `fixtures/gate1_live/scripted/search.json` 的录制回放；
2. **没注入** → 作业以 `failed` 收场，错误里**点名要注入什么**。
   NEVER 停在 `queued`（那与「worker 没起来」长得一样），
   更 NEVER 报成功（那会让一份没有检索的判定看起来像跑过）。

第 2 半是第 1 半的**阴性对照**：只有第 1 半的话，「链路通了」可能是
「这条链路对任何 deps 都通」换来的。

## 回放护栏：`assert_all_mocked`

搜索客户端由 `flint/testing/replay.py#HttpReplay` 造（M1-008 机制，respx 路由器
`assert_all_mocked=True`）：**录制里没有的请求当场抛 `ReplayMiss`**，
NEVER 落到真网上。

卡面 acceptance③ 还有一条回退条款：**若回放下仍暴露出真实网络请求，
立即停下走 `docs/blocked/` 并把该链路退回红线卡**。本文件的
`test_nothing_reaches_the_real_network` 就是那条条款的探测器——
它一旦红，下一个人要做的不是改判据，是去开单。
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import asyncpg
import pytest

from flint.domain.models import Principal, UserProfile
from flint.evidence.search import GithubArxivSearcher
from flint.jobs.gate1 import build_live_deps
from flint.jobs.worker_main import (
    HandlerDepsMissing,
    WorkerDeps,
    build_dispatch_table_for,
    build_enqueue_hook,
    build_worker,
)
from flint.testing.replay import HttpReplay, ReplayMiss

pytestmark = pytest.mark.compose

REPO = Path(__file__).resolve().parents[2]
DSN = os.environ.get(
    "FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")
REDIS_URL = os.environ.get("FLINT_TEST_REDIS", "redis://localhost:56379/0")
FIXTURE = REPO / "fixtures" / "gate1_live" / "scripted" / "search.json"
LEDGER = REPO / "docs" / "progress-v041.jsonl"
NOW = datetime(2026, 7, 26, 12, 0, 0, tzinfo=UTC)
KEYWORD = "检索增强生成"
LOCALE = "en"
QUEUE = "arq:queue01"
JOB = "job-queue01-gate1"


def run(coro: Any) -> Any:
    return asyncio.run(coro)


def _profile() -> UserProfile:
    return UserProfile(
        profile_id="queue01-profile", owner=Principal(kind="user", id="u-owner"),
        identity={}, research={}, team=[], assets={}, constraints={},
        track_record=[], locale="zh-CN", sensitivity_overrides={}, updated_at=NOW)


def _compose_provider() -> Any:
    """`build_dispatch_table_for` 把 `compose_provider` 当硬前提——本卡不测组稿，
    给一个回放 provider 占位即可（沿用 `ASM-03` 的做法）。"""
    from tests.v041.test_asm_03 import _replay_provider

    return _replay_provider()


def _worker_deps(gate1_deps: Any) -> WorkerDeps:
    return WorkerDeps(
        dsn=DSN, redis_url=REDIS_URL, repo_root=REPO, profile=_profile(), now=NOW,
        compose_provider=_compose_provider(), gate1_deps=gate1_deps)


async def _forget_in_queue(job_id: str) -> None:
    """把队列侧关于这条作业的记录清掉。

    `build_enqueue_hook` 用 `_job_id=f"arq-{job_id}"` **按作业自身的 id 去重**
    （worker_main 原话：「同一作业重复提交在队列层就被去重，NEVER 跑两遍」）。
    那是生产上要的行为，但它意味着**同一个 job_id 第二次提交会静默地什么都不做**——
    实测就撞上了：第二次跑，队列空、worker 空转退出、`jobs` 表里一行都没有，
    而那个「什么都没发生」与「链路断了」长得一模一样。
    所以这里显式地忘掉它，NEVER 靠换一个随机 id 绕过去（绕过去就再也测不到去重）。
    """
    from arq import create_pool
    from arq.connections import RedisSettings

    pool = await create_pool(RedisSettings.from_dsn(REDIS_URL))
    try:
        await pool.delete(
            f"arq:job:arq-{job_id}", f"arq:result:arq-{job_id}",
            f"arq:in-progress:arq-{job_id}", f"arq:retry:arq-{job_id}")
        # 这条队列是本文件私有的（`arq:queue01`）。把上一轮遗留的成员也清掉，
        # 否则「提交后队列里有几条」会被别人的残留搅浑。
        await pool.zrem(QUEUE, f"arq-{job_id}")
    finally:
        await pool.aclose()


async def _wipe(job_id: str) -> None:
    await _forget_in_queue(job_id)
    conn = await asyncpg.connect(DSN)
    try:
        await conn.execute("DELETE FROM job_steps WHERE job_id=$1", job_id)
        await conn.execute("DELETE FROM job_events WHERE job_id=$1", job_id)
        await conn.execute(
            "DELETE FROM snapshots WHERE snapshot_id LIKE $1", f"snap-{job_id}-%")
        await conn.execute("DELETE FROM jobs WHERE job_id=$1", job_id)
    finally:
        await conn.close()


async def _job_row(job_id: str) -> dict[str, Any] | None:
    conn = await asyncpg.connect(DSN)
    try:
        row = await conn.fetchrow(
            "SELECT state, error, progress FROM jobs WHERE job_id=$1", job_id)
    finally:
        await conn.close()
    return dict(row) if row is not None else None


async def _steps(job_id: str) -> list[str]:
    conn = await asyncpg.connect(DSN)
    try:
        rows = await conn.fetch(
            "SELECT name, state FROM job_steps WHERE job_id=$1 ORDER BY step_index",
            job_id)
    finally:
        await conn.close()
    return [f"{r['name']}:{r['state']}" for r in rows]


async def _snapshot(job_id: str, suffix: str) -> Any:
    conn = await asyncpg.connect(DSN)
    try:
        payload: bytes | None = await conn.fetchval(
            "SELECT payload FROM snapshots WHERE snapshot_id=$1",
            f"snap-{job_id}-{suffix}")
    finally:
        await conn.close()
    return None if payload is None else json.loads(payload.decode("utf-8"))


async def _drain(
    deps: WorkerDeps, job_id: str, payload: dict[str, Any],
) -> dict[str, Any]:
    """走**生产的提交面**（`PgJobRunner.submit`）：写 `jobs` 行 → 推 arq →
    起一个 burst worker 把队列吃干净。返回**队列侧的证据**。

    **NEVER 直接调 handler**：直接调等于跳过队列，而这张卡要证的正是队列这一段。
    **也 NEVER 只调 enqueue hook**：那样跳过的是「提交」这一段——`jobs` 表里
    那一行是 `submit` 写的，跳过它，作业失败时连一行 `failed` 都写不出来
    （`mark_failed` 是 UPDATE，没有行可更新）。实测撞过一次，见 trace §4。
    """
    from arq import create_pool
    from arq.connections import RedisSettings

    from flint.jobs.runner import PgJobRunner

    pool = await create_pool(RedisSettings.from_dsn(REDIS_URL))
    try:
        runner = PgJobRunner(
            dsn=DSN, role_resolver=lambda _u, _o: "owner",
            id_factory=lambda: job_id, now=lambda: NOW,
            enqueue=build_enqueue_hook(pool, queue_name=QUEUE))
        await runner.submit(
            "gate1_analysis", payload, budget=1.0,
            owner_scope=Principal(kind="user", id="u-owner"),
            initiated_by="u-owner")
        # arq 0.28 的队列是**有序集合**（延时作业按 score 排），不是 list——
        # 用 llen 会撞 WRONGTYPE。实测撞过一次。
        queued = await pool.zcard(QUEUE)
        # 判**我们这条在不在**，而不只是「有几条」：数目会被残留搅浑，成员不会。
        mine = await pool.zscore(QUEUE, f"arq-{job_id}")
    finally:
        await pool.aclose()
    worker = build_worker(deps, queue_name=QUEUE, burst=True)
    try:
        await worker.main()
    finally:
        await worker.close()
    check = await create_pool(RedisSettings.from_dsn(REDIS_URL))
    try:
        result_key = await check.exists(f"arq:result:arq-{job_id}")
    finally:
        await check.aclose()
    return {
        "queued_before_run": queued,
        "mine_was_queued": mine is not None,
        "arq_consumed": worker.jobs_complete,
        "arq_failed": worker.jobs_failed,
        "arq_result_recorded": bool(result_key),
    }


def _gate1_deps(replay: HttpReplay) -> Any:
    from harness.gate1_live import ScriptedGateProvider

    searcher = GithubArxivSearcher(replay.client(), NOW, per_source=2, resilient=True)
    return build_live_deps(DSN, REPO, ScriptedGateProvider(), searcher, NOW)


# ───────────────────────── acceptance②：链路逐段跑通


@pytest.fixture(scope="module")
def ran() -> Any:
    """跑一次完整链路，结果给下面几条判据共用（一次真跑，多条断言）。

    **全程罩一层零路由的 respx**（acceptance③）：回放客户端走的是
    `httpx.MockTransport`，碰不到 respx；而任何**别处**新造的、走真实传输的
    httpx 客户端都会撞上这层网并当场抛。
    跑完断言 `router.calls` 为空——**一次都没有人试图出网**。
    """
    import respx

    with (
        respx.mock(assert_all_mocked=True) as router,
        HttpReplay(FIXTURE, "replay") as replay,
    ):
        run(_wipe(JOB))
        queue_evidence = run(_drain(
            _worker_deps(_gate1_deps(replay)), JOB,
            {"keywords": [KEYWORD], "locale": LOCALE}))
        attempted = [f"{c.request.method} {c.request.url}" for c in router.calls]

    assert attempted == [], f"这一趟有人试图出网：{attempted}"
    return {
        "queue": queue_evidence,
        "job": run(_job_row(JOB)),
        "steps": run(_steps(JOB)),
        "docs": run(_snapshot(JOB, "docs")),
        "verdict": run(_snapshot(JOB, "verdict")),
    }


def test_the_job_row_exists_and_finished(ran: dict[str, Any]) -> None:
    """`jobs` 表里那一行**跑完了**——NEVER 停在 `queued`。

    停在 `queued` 与「worker 根本没起来」在表上长得一模一样。
    """
    job = ran["job"]

    assert job is not None, "jobs 表里没有这条作业——提交那一段就没通"
    assert job["state"] == "done", f"作业没跑完：{job}"
    assert job["error"] is None, f"跑完了却带着错误：{job['error']}"


def test_the_work_actually_went_through_the_queue(ran: dict[str, Any]) -> None:
    """**队列侧的证据**：提交后队列里真有一条，worker 真消费了一条，arq 真记了结果。

    没有这一条，整份判据对「跳过 arq 直接调 handler」是**全绿**的——
    本卡实测的变异②正是这么干的，八条判据一条都没红。
    而这张卡要证的恰恰是队列那一段：`jobs` 表与判定落盘对**谁调的 handler** 一无所知。
    """
    queue = ran["queue"]

    assert queue["mine_was_queued"], (
        "提交之后队列里没有这条作业——提交那一段没通到 arq"
    )
    assert queue["queued_before_run"] >= 1
    assert queue["arq_consumed"] == 1, f"arq 没消费到这条作业：{queue}"
    assert queue["arq_failed"] == 0, f"arq 侧记了失败：{queue}"
    assert queue["arq_result_recorded"], "arq 没留下这条作业的结果记录"


def test_the_four_steps_all_ran(ran: dict[str, Any]) -> None:
    """`run_gate1` 四步逐段落盘：plan → retrieve → judge → validate。

    只判 `state == "done"` 是不够的：**一条什么都没做就置 done 的路径也是 done**。
    """
    assert ran["steps"] == [
        "plan:done", "retrieve:done", "judge:done", "validate:done",
    ], ran["steps"]


def test_the_verdict_landed_and_cites_retrieved_docs(ran: dict[str, Any]) -> None:
    """判定落盘，且它引的 doc 来自这次检索——**不是空判定**。"""
    docs, verdict = ran["docs"], ran["verdict"]

    assert docs, "这次跑没有检索到任何文档"
    assert verdict, "判定没落盘"
    assert all(".example" not in d["url"] for d in docs), "检索到的是占位 url"
    assert any("arxiv.org" in d["url"] for d in docs)


# ───────────────────────── acceptance①：缺的是注入，不是网络授权


def test_without_the_injection_the_job_fails_and_says_what_is_missing() -> None:
    """**阴性对照**：不注入 `gate1_deps`，同一条链路以 `failed` 收场并点名缺件。

    这一条是 `DEC-033②` 那句话的可执行形式——「缺的是注入」。
    它同时挡住两种更坏的收场：停在 `queued`（看起来像 worker 没起）、
    报成功（一份没有检索的判定看起来像跑过）。
    """
    job_id = f"{JOB}-noinject"
    run(_wipe(job_id))
    run(_drain(_worker_deps(None), job_id, {"keywords": [KEYWORD], "locale": LOCALE}))
    job = run(_job_row(job_id))

    assert job is not None and job["state"] == "failed", f"没有失败：{job}"
    assert "gate1_deps" in (job["error"] or ""), f"错误里没点名缺件：{job['error']}"
    assert run(_snapshot(job_id, "verdict")) is None, "没注入却落了判定"


def test_the_missing_injection_is_not_an_assembly_time_error() -> None:
    """缺 `gate1_deps` **不该**让整个 worker 起不来——它只让这一类作业失败。

    `compose_provider` 是装配期硬前提（起不来），`gate1_deps` 不是：
    demo 面本来就不接真实源，把它也变成硬前提，等于连报告都跑不了。
    这条判据把这条界线钉住。
    """
    table = build_dispatch_table_for(_worker_deps(None))

    assert "gate1_analysis" in table
    with pytest.raises(HandlerDepsMissing):
        build_dispatch_table_for(WorkerDeps(
            dsn=DSN, redis_url=REDIS_URL, repo_root=REPO, profile=_profile(),
            now=NOW, compose_provider=None))


# ───────────────────────── acceptance③：护栏不得绕过


def test_nothing_reaches_the_real_network() -> None:
    """回放里没有的请求**当场抛**，NEVER 落到真网上。

    `HttpReplay(..., "replay")` 用的是 respx 路由器 `assert_all_mocked=True`。
    这条判据真发一个录制里没有的请求，看它抛不抛。

    **卡面回退条款**：若这条红了（也就是回放下仍能出网），
    下一个人要做的不是改判据，是**停下走 `docs/blocked/` 并把该链路退回红线卡**。
    """
    with HttpReplay(FIXTURE, "replay") as replay:
        client = replay.client()
        with pytest.raises(ReplayMiss):
            client.get("https://example.invalid/not-recorded")


def test_the_repo_guard_still_passes_on_this_file() -> None:
    """`tools/check_no_live_network.py`（NET-01 的守门器）对本文件也要绿。

    本文件造 http 客户端**只经 `HttpReplay`**；哪天有人在这里写一行裸
    `httpx.Client()`，那把尺子会点名这一行。
    """
    done = subprocess.run(
        [sys.executable, str(REPO / "tools" / "check_no_live_network.py"),
         "--root", str(Path(__file__).parent)],
        cwd=REPO, capture_output=True, text=True, encoding="utf-8", check=False)

    assert done.returncode == 0, done.stdout + done.stderr


# ───────────────────────── acceptance④：NET-03 的台账行


def test_net03_is_recorded_as_skipped_by_owner() -> None:
    """`NET-03` 的台账行**在**，且理由逐字记着（`DEC-033①`）。

    卡面 acceptance④ 要的是这一条。它与本卡的链路无关，但同属 `DEC-033` 的两半——
    少了它，那半的处置就只活在裁决文里，台账上看不出来。
    """
    rows = [
        json.loads(line) for line in LEDGER.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]
    net03 = [r for r in rows if r["task_id"] == "NET-03"]

    assert net03, "台账里没有 NET-03"
    assert net03[-1]["event"] == "skipped_by_owner", f"末态不是跳过：{net03[-1]['event']}"
    note = net03[-1]["note"]
    assert "DEC-033" in note and "payoff" in note, note
    assert "已登记未执行" in note, "没记下「NEVER 按已登记未执行写判据」那句"
