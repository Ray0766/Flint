"""ASM-04：定时批 cron 装配（×2/日：清晨全量 + 午后增量）。

`flint/jobs/sched.py` 自述「cron 骨架：×2/日 批次定义（arq cron 于 worker 进程装配；
本模块提供 batch 定义与入口，实调度随部署任务接线）」——那个「随部署任务接线」一直没
接。本卡把它接上：注册面从 `sched.CRON_BATCHES` 与 `revalidation.SCAN_HOUR` **取**，
NEVER 另写一份时刻表（另写一份就有两个真相，改一处另一处不跟）。

幂等复用既有 `run_scheduled_ingest` + `lock:daily_ingest:{day}:{batch}`，不新造锁。
"""
from __future__ import annotations

import ast
import asyncio
import inspect
import os
import re
from datetime import UTC, date
from pathlib import Path
from typing import Any

import pytest
import redis.asyncio as aioredis

from flint.jobs import cron as cron_mod
from flint.jobs import revalidation as reval_mod
from flint.jobs import sched as sched_mod
from flint.jobs.cron import (
    CronRegistration,
    build_cron_jobs,
    build_cron_registrations,
    parse_daily_cron_expr,
)

REPO = Path(__file__).resolve().parents[2]
REDIS_URL = os.environ.get("FLINT_TEST_REDIS", "redis://localhost:56379/0")
DSN = os.environ.get(
    "FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test"
)
DAY = date(2026, 8, 3)


def run(coro: Any) -> Any:
    return asyncio.run(coro)


# ── acceptance ①：时刻取自既有定义，NEVER 另写一份 ──────────────────────

def test_registrations_match_the_existing_batch_definitions() -> None:
    regs = {r.name: r for r in build_cron_registrations()}
    for batch, expr in sched_mod.CRON_BATCHES.items():
        minute, hour = parse_daily_cron_expr(expr)
        reg = regs[f"daily_ingest_{batch}"]
        assert (reg.minute, reg.hour) == (minute, hour), (
            f"{batch} 批的时刻与 sched.CRON_BATCHES 不一致：{reg}"
        )


def test_registrations_follow_sched_when_it_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """把 sched 的时刻表改掉，注册面必须跟着变——证明它是**取**的不是**抄**的。"""
    monkeypatch.setattr(
        sched_mod, "CRON_BATCHES", {"am": "7 1 * * *", "pm": "9 21 * * *"}
    )
    regs = {r.name: r for r in build_cron_registrations()}
    assert (regs["daily_ingest_am"].minute, regs["daily_ingest_am"].hour) == (7, 1)
    assert (regs["daily_ingest_pm"].minute, regs["daily_ingest_pm"].hour) == (9, 21)


def test_revalidation_hour_follows_the_revalidation_module(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(reval_mod, "SCAN_HOUR", 9)
    regs = {r.name: r for r in build_cron_registrations()}
    assert regs["revalidation_scan"].hour == 9


def test_module_holds_no_second_copy_of_a_cron_expression() -> None:
    """AST 面：cron.py 里没有任何形如 `M H * * *` 的字面量时刻表。"""
    source = inspect.getsource(cron_mod)
    literals = [
        node.value for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]
    offenders = [s for s in literals if re.fullmatch(r"[\d*/,]+( [\d*/,]+){4}", s)]
    assert offenders == [], f"cron.py 里另写了一份时刻表：{offenders}"
    # 反例：同款检查在 sched.py 上必须认得出那里确有时刻表（证明不空转）。
    sched_literals = [
        node.value for node in ast.walk(ast.parse(inspect.getsource(sched_mod)))
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]
    assert [s for s in sched_literals if re.fullmatch(r"[\d*/,]+( [\d*/,]+){4}", s)]


def test_parse_rejects_a_non_daily_expression() -> None:
    with pytest.raises(ValueError, match="每日"):
        parse_daily_cron_expr("*/5 * * * *")


# ── acceptance ③：注册面可在不启动真实调度的前提下被断言 ────────────────

def test_registry_is_inspectable_without_starting_a_scheduler() -> None:
    regs = build_cron_registrations()
    assert [r.name for r in regs] == [
        "daily_ingest_am", "daily_ingest_pm", "revalidation_scan",
    ]
    assert all(isinstance(r, CronRegistration) for r in regs)
    assert all(0 <= r.hour <= 23 and 0 <= r.minute <= 59 for r in regs)


def test_cron_jobs_carry_the_registered_times_into_arq() -> None:
    async def _noop() -> None:
        return None

    jobs = build_cron_jobs(
        redis_url=REDIS_URL, day_of=lambda: DAY, ingest=_noop, scan=_noop,
    )
    by_name = {j.name: j for j in jobs}
    assert set(by_name) == {"daily_ingest_am", "daily_ingest_pm", "revalidation_scan"}
    for reg in build_cron_registrations():
        assert by_name[reg.name].hour == reg.hour
        assert by_name[reg.name].minute == reg.minute
    assert all(j.max_tries == 1 for j in jobs), "定时批 NEVER 靠盲重试补跑"


def test_worker_accepts_the_cron_jobs() -> None:
    """注册面能真的挂进 ASM-03 的 worker（不启动调度，只看挂载结果）。"""
    from datetime import datetime as _dt

    from flint.domain.models import Principal, UserProfile
    from flint.jobs.worker_main import WorkerDeps, build_worker
    from tests.v041.test_asm_03 import _replay_provider

    async def _noop() -> None:
        return None

    async def scenario() -> list[str]:
        deps = WorkerDeps(
            dsn=DSN,
            redis_url=REDIS_URL, repo_root=REPO,
            profile=UserProfile(
                profile_id="p", owner=Principal(kind="user", id="u"),
                identity={}, research={}, team=[], assets={}, constraints={},
                track_record=[], locale="zh-CN", sensitivity_overrides={},
                updated_at=_dt(2026, 7, 26, 12, 0, 0, tzinfo=UTC)),
            now=_dt(2026, 7, 26, 12, 0, 0, tzinfo=UTC),
            compose_provider=_replay_provider(),
        )
        worker = build_worker(
            deps, queue_name="arq:asm04-inspect", burst=True,
            cron_jobs=build_cron_jobs(
                redis_url=REDIS_URL, day_of=lambda: DAY, ingest=_noop, scan=_noop,
            ),
        )
        return [j.name for j in worker.cron_jobs]

    assert run(scenario()) == [
        "daily_ingest_am", "daily_ingest_pm", "revalidation_scan",
    ]


# ── acceptance ②：幂等，复用既有 lock:daily_ingest:{day}:{batch} ────────

@pytest.mark.compose
def test_same_day_same_batch_runs_once() -> None:
    unique_day = date(2026, 8, 3)
    calls: list[str] = []

    async def _ingest() -> None:
        calls.append("ran")

    async def scenario() -> tuple[str, str]:
        client = aioredis.from_url(REDIS_URL)
        try:
            await client.delete(sched_mod.lock_key(unique_day, "am"))
            first = await cron_mod.run_batch(
                client, unique_day, "am", _ingest, release=False,
            )
            second = await cron_mod.run_batch(
                client, unique_day, "am", _ingest, release=False,
            )
            await client.delete(sched_mod.lock_key(unique_day, "am"))
            return first.outcome, second.outcome
        finally:
            await client.aclose()

    first, second = run(scenario())
    assert (first, second) == ("executed", "skipped")
    assert calls == ["ran"], f"同一天同一批次跑了 {len(calls)} 次"


@pytest.mark.compose
def test_two_batches_on_the_same_day_both_run() -> None:
    calls: list[str] = []

    async def _ingest() -> None:
        calls.append("ran")

    async def scenario() -> list[str]:
        client = aioredis.from_url(REDIS_URL)
        try:
            outcomes: list[str] = []
            for batch in ("am", "pm"):
                await client.delete(sched_mod.lock_key(DAY, batch))
                report = await cron_mod.run_batch(
                    client, DAY, batch, _ingest, release=False,
                )
                outcomes.append(report.outcome)
            for batch in ("am", "pm"):
                await client.delete(sched_mod.lock_key(DAY, batch))
            return outcomes
        finally:
            await client.aclose()

    assert run(scenario()) == ["executed", "executed"]
    assert calls == ["ran", "ran"]


@pytest.mark.compose
def test_the_lock_key_is_the_existing_one_not_a_new_namespace() -> None:
    """断言持锁期间 redis 里真的是 `lock:daily_ingest:{day}:{batch}` 这个键。"""
    seen: list[Any] = []

    async def scenario() -> None:
        client = aioredis.from_url(REDIS_URL)
        try:
            key = sched_mod.lock_key(DAY, "am")
            await client.delete(key)

            async def _probe() -> None:
                seen.append(await client.get(key))

            await cron_mod.run_batch(client, DAY, "am", _probe, release=True)
            seen.append(await client.get(key))
        finally:
            await client.aclose()

    run(scenario())
    assert seen[0] is not None, "执行期间既有锁键上没有持有者令牌"
    assert seen[1] is None, "release=True 时锁没被释放"
