"""M3-056 acceptance tests: API hardening (M2 exit leftover 2).

Acceptance (tasks.json M3-056):
  - idempotency race: INSERT..ON CONFLICT then read back the winner job_id
    (concurrent same-key submits expose exactly one job)
  - malformed Last-Event-ID -> 400 VALIDATION_FAILED (never 500)
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

import asyncpg
import httpx
import pytest

from flint.api.analysis import AnalysisApiDeps, create_analysis_app
from flint.api.hardening import claim_idempotency
from flint.domain.models import Principal
from flint.jobs.events import PgJobEventStream
from flint.jobs.gate1 import build_offline_deps, run_gate1
from flint.jobs.runner import PgJobRunner

pytestmark = pytest.mark.compose

REPO_ROOT = Path(__file__).resolve().parents[2]
DSN = os.environ.get("FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")


def run(coro: Any) -> Any:
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def clean_slate() -> None:
    async def wipe() -> None:
        conn = await asyncpg.connect(DSN)
        try:
            await conn.execute("DELETE FROM idempotency_keys")
            await conn.execute("DELETE FROM job_events WHERE job_id LIKE 'm3056-%'")
            await conn.execute("DELETE FROM job_steps WHERE job_id LIKE 'm3056-%'")
            await conn.execute("DELETE FROM jobs WHERE job_id LIKE 'm3056-%'")
            await conn.execute(
                "DELETE FROM snapshots WHERE snapshot_id LIKE 'snap-m3056-%'"
            )
        finally:
            await conn.close()

    run(wipe())


def runner() -> PgJobRunner:
    return PgJobRunner(
        dsn=DSN, role_resolver=lambda user, org: None,
        id_factory=lambda: f"m3056-{uuid4().hex[:10]}",
    )


def test_race_single_winner_readback() -> None:
    """两个并发同键提交各自建 job 后 claim：恰一胜者可见，败者 job 取消。"""
    r = runner()
    principal = Principal(kind="user", id="u-1")

    async def scenario() -> None:
        job_a = await r.submit("gate1_analysis", {}, 0.0, principal, "u-1")
        job_b = await r.submit("gate1_analysis", {}, 0.0, principal, "u-1")
        winner_a = await claim_idempotency(DSN, principal, "key-race", job_a)
        winner_b = await claim_idempotency(DSN, principal, "key-race", job_b)
        assert winner_a == job_a, "first claim wins"
        assert winner_b == job_a, "loser reads back the winner, not itself"

        conn = await asyncpg.connect(DSN)
        try:
            states = {
                row["job_id"]: row["state"]
                for row in await conn.fetch(
                    "SELECT job_id, state FROM jobs WHERE job_id = ANY($1::text[])",
                    [job_a, job_b],
                )
            }
        finally:
            await conn.close()
        assert states[job_a] == "queued"
        assert states[job_b] == "cancelled", "orphan loser job is cancelled"

    run(scenario())


def make_app() -> Any:
    return create_analysis_app(AnalysisApiDeps(
        dsn=DSN, runner=runner(), events=PgJobEventStream(dsn=DSN),
        owner_scope_for_project=lambda pid: Principal(kind="user", id="u-owner"),
        role_resolver=lambda user, org: None,
    ))


def test_malformed_last_event_id_400_not_500() -> None:
    deps = build_offline_deps(dsn=DSN, repo_root=REPO_ROOT)
    run(run_gate1(job_id="m3056-sse", keywords=["固态电池"],
                  locale="zh-CN", deps=deps))
    app = make_app()

    async def scenario() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://t"
        ) as client:
            response = await client.get(
                "/jobs/m3056-sse/events",
                headers={"X-User-Id": "u-owner", "Last-Event-ID": "not-a-number"},
            )
            assert response.status_code == 400
            assert response.json()["code"] == "VALIDATION_FAILED"

            fine = await client.get(
                "/jobs/m3056-sse/events",
                headers={"X-User-Id": "u-owner", "Last-Event-ID": "5"},
            )
            assert fine.status_code == 200

    run(scenario())


def test_endpoint_uses_winner_readback() -> None:
    app = make_app()

    async def scenario() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://t"
        ) as client:
            first = await client.post(
                "/projects/p-1/analysis",
                json={"keywords": ["x"], "locale": "zh-CN", "budget_cny": 1.0},
                headers={"X-User-Id": "u-1", "Idempotency-Key": "k-1"},
            )
            second = await client.post(
                "/projects/p-1/analysis",
                json={"keywords": ["x"], "locale": "zh-CN", "budget_cny": 1.0},
                headers={"X-User-Id": "u-1", "Idempotency-Key": "k-1"},
            )
            assert first.json()["job_id"] == second.json()["job_id"]

    run(scenario())
