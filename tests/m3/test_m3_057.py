"""M3-057 acceptance tests: report/proposal submit endpoints.

Acceptance (tasks.json M3-057):
  - POST /projects/{id}/proposal: audience mandatory (missing -> 422);
    ai_executor locked to vibe_pack
  - report endpoint submits a compose job; idempotency surface reused
"""
from __future__ import annotations

import asyncio
import os
from typing import Any
from uuid import uuid4

import asyncpg
import httpx
import pytest

from flint.api.compose import ComposeApiDeps, create_compose_app
from flint.domain.models import Principal
from flint.jobs.runner import PgJobRunner

pytestmark = pytest.mark.compose

DSN = os.environ.get("FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")


def run(coro: Any) -> Any:
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def clean_slate() -> None:
    async def wipe() -> None:
        conn = await asyncpg.connect(DSN)
        try:
            await conn.execute("DELETE FROM idempotency_keys")
            await conn.execute("DELETE FROM jobs WHERE job_id LIKE 'm3057-%'")
        finally:
            await conn.close()

    run(wipe())


def make_app() -> Any:
    deps = ComposeApiDeps(
        dsn=DSN,
        runner=PgJobRunner(
            dsn=DSN, role_resolver=lambda user, org: None,
            id_factory=lambda: f"m3057-{uuid4().hex[:10]}",
        ),
        owner_scope_for_project=lambda pid: Principal(kind="user", id="u-1"),
        # WIRE-08 之后 compose 有权限门。本用例的归属是**个人**
        # （`kind == "user"`），那条路比的是 id 本身、不问角色——
        # 所以这里给一个恒答 None 的解析器就够，且它 NEVER 放行任何人。
        role_resolver=lambda _user, _org: None,
    )
    return create_compose_app(deps)


async def _client(app: Any) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://t"
    )


def test_proposal_audience_mandatory_422() -> None:
    app = make_app()

    async def scenario() -> None:
        async with await _client(app) as client:
            response = await client.post(
                "/projects/p-1/proposal",
                json={"report_id": "d-report", "template_id": "generic"},
                headers={"X-User-Id": "u-1"},
            )
            assert response.status_code == 422, "audience missing -> 422"

    run(scenario())


def test_proposal_ai_locked_and_mix_rejected() -> None:
    app = make_app()

    async def scenario() -> None:
        async with await _client(app) as client:
            mixed = await client.post(
                "/projects/p-1/proposal",
                json={"audience": "ai_executor", "report_id": "d-r",
                      "template_id": "startup"},
                headers={"X-User-Id": "u-1"},
            )
            assert mixed.status_code == 422
            assert mixed.json()["code"] == "VALIDATION_FAILED"

            ok = await client.post(
                "/projects/p-1/proposal",
                json={"audience": "ai_executor", "report_id": "d-r"},
                headers={"X-User-Id": "u-1"},
            )
            assert ok.status_code == 200, ok.text
            body = ok.json()
            assert body["template_id"] == "vibe_pack"
            job_kind = await _job_kind(body["job_id"])
            assert job_kind == "proposal"

    run(scenario())


async def _job_kind(job_id: str) -> str:
    conn = await asyncpg.connect(DSN)
    try:
        kind: str = await conn.fetchval(
            "SELECT kind FROM jobs WHERE job_id = $1", job_id
        )
        return kind
    finally:
        await conn.close()


def test_report_submits_job_with_idempotency_reuse() -> None:
    app = make_app()

    async def scenario() -> None:
        async with await _client(app) as client:
            first = await client.post(
                "/projects/p-1/report",
                json={"analysis_id": "d-analysis", "template_id": "generic"},
                headers={"X-User-Id": "u-1", "Idempotency-Key": "rk-1"},
            )
            assert first.status_code == 200, first.text
            second = await client.post(
                "/projects/p-1/report",
                json={"analysis_id": "d-analysis", "template_id": "generic"},
                headers={"X-User-Id": "u-1", "Idempotency-Key": "rk-1"},
            )
            assert second.json()["job_id"] == first.json()["job_id"], (
                "idempotency surface reused"
            )
            assert await _job_kind(first.json()["job_id"]) == "report"

    run(scenario())
