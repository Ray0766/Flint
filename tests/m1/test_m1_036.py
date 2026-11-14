"""M1-036 acceptance tests: scheduling + overlap protection (cron x2/day + lock).

Acceptance (tasks.json M1-036):
  - concurrent triggers of the same batch execute only once
  - the lock auto-releases on timeout
"""
from __future__ import annotations

import asyncio
import os
from datetime import date
from typing import Any

import pytest
import redis.asyncio as aioredis

from flint.jobs.sched import (
    CRON_BATCHES,
    BatchLock,
    ScheduledRunReport,
    lock_key,
    run_scheduled_ingest,
)

pytestmark = pytest.mark.compose

REDIS_URL = os.environ.get("FLINT_TEST_REDIS", "redis://localhost:56379/0")
DAY = date(2026, 7, 23)


def run(coro: Any) -> Any:
    return asyncio.run(coro)


async def _flush_locks() -> None:
    client = aioredis.from_url(REDIS_URL)
    try:
        keys = await client.keys("lock:daily_ingest:*")
        if keys:
            await client.delete(*keys)
    finally:
        await client.aclose()


@pytest.fixture(autouse=True)
def clean_locks() -> None:
    run(_flush_locks())


def test_lock_key_matches_e4_naming() -> None:
    assert lock_key(DAY, "am") == "lock:daily_ingest:2026-07-23:am"


def test_cron_two_batches_per_day() -> None:
    assert len(CRON_BATCHES) == 2


def test_concurrent_triggers_execute_only_once() -> None:
    executions: list[str] = []

    async def fake_ingest() -> None:
        executions.append("run")
        await asyncio.sleep(0.3)  # hold the lock while "working"

    async def scenario() -> list[ScheduledRunReport]:
        client = aioredis.from_url(REDIS_URL)
        try:
            return list(
                await asyncio.gather(
                    run_scheduled_ingest(client, DAY, "am", fake_ingest, ttl_seconds=60),
                    run_scheduled_ingest(client, DAY, "am", fake_ingest, ttl_seconds=60),
                    run_scheduled_ingest(client, DAY, "am", fake_ingest, ttl_seconds=60),
                )
            )
        finally:
            await client.aclose()

    reports = run(scenario())
    assert executions == ["run"], "same batch triggered concurrently runs exactly once"
    assert sorted(r.outcome for r in reports) == ["executed", "skipped", "skipped"]


def test_different_batches_do_not_block_each_other() -> None:
    executions: list[str] = []

    async def fake_ingest() -> None:
        executions.append("run")
        await asyncio.sleep(0.1)

    async def scenario() -> None:
        client = aioredis.from_url(REDIS_URL)
        try:
            await asyncio.gather(
                run_scheduled_ingest(client, DAY, "am", fake_ingest, ttl_seconds=60),
                run_scheduled_ingest(client, DAY, "pm", fake_ingest, ttl_seconds=60),
            )
        finally:
            await client.aclose()

    run(scenario())
    assert executions == ["run", "run"]


def test_lock_timeout_auto_releases() -> None:
    async def scenario() -> tuple[bool, bool, bool]:
        client = aioredis.from_url(REDIS_URL)
        try:
            lock = BatchLock(client, DAY, "am", ttl_seconds=1)
            first = await lock.acquire()
            # a competitor cannot enter while the holder is alive...
            second = await BatchLock(client, DAY, "am", ttl_seconds=1).acquire()
            await asyncio.sleep(1.3)  # holder died without releasing -> TTL expiry
            third = await BatchLock(client, DAY, "am", ttl_seconds=1).acquire()
            return first, second, third
        finally:
            await client.aclose()

    first, second, third = run(scenario())
    assert first is True
    assert second is False
    assert third is True, "TTL must free the lock without manual release"


def test_completed_run_releases_lock_immediately() -> None:
    async def noop() -> None:
        return None

    async def scenario() -> tuple[str, str]:
        client = aioredis.from_url(REDIS_URL)
        try:
            r1 = await run_scheduled_ingest(client, DAY, "am", noop, ttl_seconds=60)
            r2 = await run_scheduled_ingest(client, DAY, "am", noop, ttl_seconds=60)
            return r1.outcome, r2.outcome
        finally:
            await client.aclose()

    outcome1, outcome2 = run(scenario())
    assert outcome1 == "executed"
    assert outcome2 == "executed", "released lock lets the retriggered batch run"


def test_release_with_wrong_token_keeps_lock() -> None:
    async def scenario() -> tuple[bool, bool]:
        client = aioredis.from_url(REDIS_URL)
        try:
            holder = BatchLock(client, DAY, "pm", ttl_seconds=60)
            await holder.acquire()
            intruder = BatchLock(client, DAY, "pm", ttl_seconds=60)
            released = await intruder.release()  # wrong token: must be a no-op
            steal = await intruder.acquire()
            return released, steal
        finally:
            await client.aclose()

    released, steal = run(scenario())
    assert released is False
    assert steal is False, "holder keeps the lock after a foreign release attempt"
