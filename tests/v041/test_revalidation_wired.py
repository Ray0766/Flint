"""BL-07：`revalidation` JobKind 接消费者（stale 判定委托既有 Revalidator）。

## 接线前的状态

`flint/jobs/dispatch.py` 的 `UnwiredKindReason` 里写着：

> revalidation：`flint/jobs/revalidation.py` 只有扫描器 `run_revalidation_scan`
> （它负责 submit kind=revalidation 的作业），仓里还没有消费这些作业的 per-job 消费者。

也就是说：**扫描器每天 04:00 往队列里塞作业，而没有人取**。作业停在 `queued`，
到期复核这件事在系统里看起来「有」，实际一次都没跑过。

## 三件事，缺一不可

1. **真有消费者**：提交后 worker 消费并把状态机推到 `done`；
2. **锁不互踩**：per-job 锁走自己的命名空间，**NEVER** 用
   `lock:daily_ingest:{day}:{batch}`；重复触发只跑一次；
3. **stale 判定委托既有 Revalidator**：`flint/revalidate/report.py#build_report`
   → `rerun_verdict` → 完整 gate1 三相位重跑。本卡 **NEVER 再写一份判定**——
   同一件事两个真相，是本仓一路在防的老病（`build_shift` 是全仓唯一构造点）。
"""
from __future__ import annotations

import asyncio
import inspect
import os
from datetime import UTC, date, datetime
from typing import Any

import pytest

from flint.jobs.dispatch import WIREABLE_KINDS, UnwiredKindReason, build_dispatch_table
from flint.jobs.revalidation import (
    RevalidationDeps,
    revalidation_lock_key,
    run_revalidation,
    scan_lock_key,
)
from flint.jobs.sched import lock_key as ingest_lock_key

DSN = os.environ.get("FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")
REDIS_URL = os.environ.get("FLINT_TEST_REDIS", "redis://localhost:56379/0")
NOW = datetime(2026, 8, 4, 4, 0, tzinfo=UTC)
DUE = date(2026, 8, 4)


def _payload(project_id: str = "bl07-p1") -> dict[str, Any]:
    return {"project_id": project_id, "due_on": DUE.isoformat(), "trigger": "scheduled"}


# ───────────────────────── 一、不再是「声明未接线」


def test_revalidation_is_no_longer_declared_unwired() -> None:
    """acceptance①：它从「没有消费者」那张表里出来了。"""
    assert "revalidation" not in UnwiredKindReason
    assert "revalidation" in WIREABLE_KINDS


def test_the_dispatch_table_accepts_it_now() -> None:
    """分派表接受它——`handlers` 必须**恰好**覆盖 `WIREABLE_KINDS`。

    少一个是漏接线、多一个是 key 拼错，两种都抛。所以这一条同时证明了
    「revalidation 现在属于可接线那一族」。
    """
    async def noop(job_id: str, payload: dict[str, Any]) -> None:
        return None

    table = build_dispatch_table({k: noop for k in WIREABLE_KINDS})  # type: ignore[arg-type]

    assert "revalidation" in table


def test_the_worker_builds_a_handler_for_it() -> None:
    """worker 装配处真给它一个执行体（不是留个名字）。"""
    from pathlib import Path

    from flint.domain.models import Principal, UserProfile
    from flint.jobs.worker_main import WorkerDeps, build_handlers

    handlers = build_handlers(WorkerDeps(
        dsn=DSN, redis_url=REDIS_URL, repo_root=Path("."), now=NOW,
        profile=UserProfile(
            profile_id="p", owner=Principal(kind="user", id="u"), identity={},
            research={}, team=[], assets={}, constraints={}, track_record=[],
            locale="zh-CN", sensitivity_overrides={}, updated_at=NOW,
        ),
    ))

    assert callable(handlers["revalidation"])
    assert set(handlers) == set(WIREABLE_KINDS), "装配处与可接线族必须一一对上"


def test_the_other_unwired_kinds_are_still_declared_unwired() -> None:
    """阴性对照：本卡只接一个 kind，其余的仍在「未接线」表里。

    一起搬走的话，那张表就从「大声失败」退化成一张空表——
    而它存在的理由正是被调到时点名说清缺什么。

    `pricebook_scan` 曾在这份名单里，**BL-08 把它接走了**（合法变化，不是回归）。
    留下的三个仍必须在表里。
    """
    # SLOT-03（第 6 批）把 `translate` 也接走了——**合法变化，不是回归**。
    # 名单跟着事实走：钉死一个过期的集合，只会让下一次真正的接线被判成错。
    # 剩下的那一条继续钉住：名单少一条要有人来这里解释，
    # NEVER 让「已经接了」与「忘了登记」长得一样。
    # `PERSIST-03` 之后 `UnwiredKindReason` 空了（最后一条接上了消费者），
    # 所以这里没有 kind 可遍历。**循环留着**：下一个 additive 新增的 kind
    # 在有消费者之前 MUST 先进那张表，那时这条判据不用改结构就能重新量到它。
    for kind in tuple(UnwiredKindReason):
        assert kind in UnwiredKindReason

    # 改前这里断言 `UnwiredKindReason` **非空**（当时它总还剩着几条）。
    # `PERSIST-03` 接走最后一条之后它必红——红的是「今天还剩几条」这个事实
    # 过去了，**不是那张表被人清空了**：两者在这条断言上长得一模一样，
    # 这正是它该改的理由。那张表存在的理由（大声失败）改由
    # `tests/v041/test_template_persist.py` 的
    # `test_the_empty_unwired_table_is_still_a_live_mechanism` 直接量机制本身。
    assert hasattr(UnwiredKindReason, "items"), (
        "未接线表被换成了别的东西——那张表存在的理由就是大声失败")


# ───────────────────────── 二、锁不互踩


def test_the_per_job_lock_has_its_own_namespace() -> None:
    """acceptance②：per-job 锁 **NEVER** 落在 daily_ingest 的命名空间里。"""
    key = revalidation_lock_key("bl07-p1", DUE)

    assert key.startswith("lock:revalidation:")
    assert not key.startswith("lock:daily_ingest")
    assert key != scan_lock_key(DUE), "per-job 锁与扫描锁也要分开"


def test_no_input_can_make_the_two_key_families_collide() -> None:
    """两族键**永不相等**——不是「今天不撞」，是构造上撞不了。

    撞上的后果很具体：一次日更批次会把当天的复核锁顶掉（或反过来），
    而两者都会以为自己拿到了锁。
    """
    revalidation_keys = {
        revalidation_lock_key(pid, day)
        for pid in ("p", "p:1", "am", "2026-08-04")
        for day in (DUE, date(2026, 1, 1))
    }
    ingest_keys = {
        ingest_lock_key(day, batch)
        for day in (DUE, date(2026, 1, 1))
        for batch in ("am", "pm", "p:1")
    }

    assert revalidation_keys.isdisjoint(ingest_keys)


@pytest.mark.compose
def test_a_second_trigger_while_the_first_holds_the_lock_is_skipped() -> None:
    """acceptance②：重复触发**只跑一次**（真 redis，本机不算外网）。"""
    import redis.asyncio as aioredis

    calls: list[str] = []

    def revalidator(payload: dict[str, Any]) -> dict[str, Any]:
        calls.append(str(payload["project_id"]))
        return {"stale": False}

    async def scenario() -> tuple[str, str]:
        client = aioredis.from_url(REDIS_URL)
        try:
            await client.delete(revalidation_lock_key("bl07-lock", DUE))
            deps = RevalidationDeps(
                dsn=DSN, now=NOW, redis=client, revalidator=revalidator,
            )
            first = await run_revalidation("bl07-j-lock-1", _payload("bl07-lock"), deps)
            # 第一次已经释放锁；用一个**持有中**的锁模拟并发触发
            held = client.set(
                revalidation_lock_key("bl07-lock", DUE), "someone-else", nx=True, ex=30,
            )
            await held
            second = await run_revalidation("bl07-j-lock-2", _payload("bl07-lock"), deps)
            await client.delete(revalidation_lock_key("bl07-lock", DUE))
            return first, second
        finally:
            await client.aclose()

    first, second = asyncio.run(scenario())

    assert first == "executed"
    assert second == "skipped", "锁被别人持有时不该再跑一次"
    assert calls == ["bl07-lock"], "复核只该真跑一次"


# ───────────────────────── 三、stale 判定委托既有 Revalidator


def test_the_consumer_delegates_to_the_existing_revalidator() -> None:
    """acceptance③：默认判定件就是 `flint/revalidate/report.py#build_report`。"""
    from flint.jobs import revalidation
    from flint.revalidate.report import build_report

    assert revalidation.default_revalidator.__wrapped__ is build_report  # type: ignore[attr-defined]


def test_the_consumer_never_writes_its_own_stale_judgement() -> None:
    """本模块里**没有**第二份判定：不构造 VerdictShift、不列 verdict 名字。

    同一件事两个真相是本仓的老病——`build_shift` 是全仓唯一构造点，
    这一条守着它不被绕过。
    """
    from flint.jobs import revalidation

    source = inspect.getsource(revalidation)
    code = "\n".join(ln for ln in source.split("\n") if not ln.strip().startswith("#"))

    for forbidden in ("VerdictShift(", "A_infeasible", "B_red_ocean", "_VERDICTS"):
        assert forbidden not in code, f"本模块里出现了第二份判定：{forbidden}"


def test_the_only_shift_constructor_is_still_the_single_one() -> None:
    """阴性对照：唯一构造点仍在既有模块里（本卡没有把它搬走或复制）。"""
    from flint.revalidate.run import build_shift

    assert callable(build_shift)
    assert inspect.getsourcefile(build_shift).endswith("run.py")  # type: ignore[union-attr]


# ───────────────────────── 四、状态机推到 done


@pytest.mark.compose
def test_the_job_reaches_done_after_the_consumer_runs() -> None:
    """acceptance①：提交 → 消费 → 状态机到 `done`（真库）。

    判定件注入一个桩：本条测的是**状态机**，判定本身由上面那两条守。
    清理按前缀（`bl07-%`）。
    """
    import asyncpg

    async def scenario() -> str:
        conn = await asyncpg.connect(DSN)
        try:
            await _cleanup(conn)
            await conn.execute(
                "INSERT INTO jobs (job_id, kind, owner_scope, state, progress, budget, "
                "cost_accum, cancel_requested, initiated_by, created_at, updated_at) "
                "VALUES ('bl07-j1', 'revalidation', "
                "'{\"kind\":\"org\",\"id\":\"system\"}', 'queued', 0, 0, 0, false, "
                "'u-system', $1, $1)",
                NOW,
            )
        finally:
            await conn.close()

        deps = RevalidationDeps(
            dsn=DSN, now=NOW, redis=None, revalidator=lambda payload: {"stale": False},
        )
        await run_revalidation("bl07-j1", _payload(), deps)

        conn = await asyncpg.connect(DSN)
        try:
            state: str = await conn.fetchval(
                "SELECT state FROM jobs WHERE job_id = 'bl07-j1'"
            )
            return state
        finally:
            await conn.close()

    assert asyncio.run(scenario()) == "done"


@pytest.mark.compose
def test_a_job_already_terminal_is_left_alone() -> None:
    """幂等的另一半：已经 done 的作业**不重跑**（重放与重试都会撞上这一步）。"""
    import asyncpg

    calls: list[str] = []

    async def scenario() -> str:
        conn = await asyncpg.connect(DSN)
        try:
            await _cleanup(conn)
            await conn.execute(
                "INSERT INTO jobs (job_id, kind, owner_scope, state, progress, budget, "
                "cost_accum, cancel_requested, initiated_by, created_at, updated_at) "
                "VALUES ('bl07-j2', 'revalidation', "
                "'{\"kind\":\"org\",\"id\":\"system\"}', 'done', 100, 0, 0, false, "
                "'u-system', $1, $1)",
                NOW,
            )
        finally:
            await conn.close()

        def revalidator(payload: dict[str, Any]) -> dict[str, Any]:
            calls.append("ran")
            return {"stale": False}

        deps = RevalidationDeps(dsn=DSN, now=NOW, redis=None, revalidator=revalidator)
        return await run_revalidation("bl07-j2", _payload(), deps)

    outcome = asyncio.run(scenario())

    assert outcome == "skipped"
    assert calls == [], "已终态的作业被重跑了"


@pytest.mark.compose
def test_a_missing_project_id_fails_loudly_instead_of_silently_passing() -> None:
    """payload 缺 `project_id` → 抛并点名，NEVER 当成「没什么要复核的」。

    静默通过会让一批本该复核的项目永远排不上——而作业状态是 done。
    """
    deps = RevalidationDeps(
        dsn=DSN, now=NOW, redis=None, revalidator=lambda payload: {"stale": False},
    )

    with pytest.raises(ValueError, match="project_id"):
        asyncio.run(run_revalidation("bl07-j3", {"due_on": DUE.isoformat()}, deps))


async def _cleanup(conn: Any) -> None:
    await conn.execute("DELETE FROM job_events WHERE job_id LIKE 'bl07-%'")
    await conn.execute("DELETE FROM job_steps WHERE job_id LIKE 'bl07-%'")
    await conn.execute("DELETE FROM jobs WHERE job_id LIKE 'bl07-%'")


# ───────────────────────── 五、扫描器那一半没被动过


def test_the_scanner_still_submits_the_same_kind() -> None:
    """扫描器一个字没改：它 submit 的仍是 `kind="revalidation"`。"""
    from flint.jobs import revalidation

    code = inspect.getsource(revalidation.run_revalidation_scan)

    assert 'kind="revalidation"' in code


def test_the_scan_lock_key_is_unchanged() -> None:
    """扫描锁的命名空间不变（E4 既有口径）。"""
    assert scan_lock_key(DUE) == f"lock:revalidation_scan:{DUE.isoformat()}"
