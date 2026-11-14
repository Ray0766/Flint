"""M2-042 acceptance tests: Analysis API + SSE endpoint.

Acceptance (tasks.json M2-042):
  - POST idempotency key: (principal, key) duplicate submit returns the
    original job_id
  - SSE Last-Event-ID resume replay works and the review-6 permission
    matrix is enforced
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

import asyncpg
import httpx
import pytest

from flint.api.analysis import AnalysisApiDeps, create_analysis_app
from flint.domain.models import Principal
from flint.jobs.events import PgJobEventStream
from flint.jobs.gate1 import build_offline_deps, run_gate1
from flint.jobs.runner import PgJobRunner

pytestmark = pytest.mark.compose

REPO_ROOT = Path(__file__).resolve().parents[2]
DSN = os.environ.get("FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")

ROLES = {("u-admin", "org-1"): "admin", ("u-member", "org-1"): "member"}

WIPE_SQL = [
    "DELETE FROM idempotency_keys",
    "DELETE FROM job_events WHERE job_id LIKE 'm2042-%'",
    "DELETE FROM job_steps WHERE job_id LIKE 'm2042-%'",
    "DELETE FROM jobs WHERE job_id LIKE 'm2042-%'",
    "DELETE FROM snapshots WHERE snapshot_id LIKE 'snap-m2042-%'",
]


def run(coro: Any) -> Any:
    return asyncio.run(coro)


async def _sql(statements: list[str]) -> None:
    conn = await asyncpg.connect(DSN)
    try:
        for stmt in statements:
            await conn.execute(stmt)
    finally:
        await conn.close()


@pytest.fixture(autouse=True)
def clean_slate() -> None:
    run(_sql(WIPE_SQL))


def make_app(project_scopes: dict[str, Principal] | None = None) -> Any:
    scopes = project_scopes or {}
    deps = AnalysisApiDeps(
        dsn=DSN,
        runner=PgJobRunner(
            dsn=DSN,
            role_resolver=lambda user, org: ROLES.get((user, org)),
            id_factory=lambda: f"m2042-{uuid4().hex[:10]}",
        ),
        events=PgJobEventStream(dsn=DSN),
        owner_scope_for_project=lambda pid: scopes.get(
            pid, Principal(kind="user", id="u-1")
        ),
        role_resolver=lambda user, org: ROLES.get((user, org)),
    )
    return create_analysis_app(deps)


async def _post(client: httpx.AsyncClient, user: str, key: str | None) -> str:
    headers = {"X-User-Id": user}
    if key is not None:
        headers["Idempotency-Key"] = key
    response = await client.post(
        "/projects/p-1/analysis",
        json={"keywords": ["固态电池"], "locale": "zh-CN", "budget_cny": 10.0},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return str(response.json()["job_id"])


def test_idempotency_key_returns_original_job() -> None:
    app = make_app()

    async def scenario() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://t"
        ) as client:
            first = await _post(client, "u-1", "key-a")
            repeat = await _post(client, "u-1", "key-a")
            assert repeat == first, "(principal, key) duplicate returns original"

            other_key = await _post(client, "u-1", "key-b")
            assert other_key != first

            other_user = await _post(client, "u-2", "key-a")
            assert other_user != first, "same key under another principal is a new job"

    run(scenario())


def test_job_snapshot_and_not_found_error_body() -> None:
    app = make_app()

    async def scenario() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://t"
        ) as client:
            job_id = await _post(client, "u-1", None)
            snap = await client.get(f"/jobs/{job_id}", headers={"X-User-Id": "u-1"})
            assert snap.status_code == 200
            body = snap.json()
            assert body["job_id"] == job_id
            assert body["state"] == "queued"
            assert "owner_scope" not in body

            missing = await client.get("/jobs/nope", headers={"X-User-Id": "u-1"})
            assert missing.status_code == 404
            assert missing.json()["code"] == "NOT_FOUND"

    run(scenario())


def test_review6_permission_matrix() -> None:
    app = make_app({"p-1": Principal(kind="org", id="org-1")})

    async def scenario() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://t"
        ) as client:
            job_id = await _post(client, "u-init", None)
            cases = [
                ("u-init", 200),    # initiated_by 本人
                ("u-admin", 200),   # org role admin
                ("u-member", 200),  # org role member 只读
                ("u-outsider", 403),
            ]
            for user, expected in cases:
                snap = await client.get(
                    f"/jobs/{job_id}", headers={"X-User-Id": user}
                )
                assert snap.status_code == expected, (user, snap.text)
                if expected == 403:
                    assert snap.json()["code"] == "PERMISSION_DENIED"

            blocked = await client.get(
                f"/jobs/{job_id}/events", headers={"X-User-Id": "u-outsider"}
            )
            assert blocked.status_code == 403
            assert blocked.json()["code"] == "PERMISSION_DENIED"

    run(scenario())


def test_sse_last_event_id_resume_replay() -> None:
    gate_deps = build_offline_deps(dsn=DSN, repo_root=REPO_ROOT)
    run(
        run_gate1(
            job_id="m2042-sse", keywords=["固态电池", "钠离子电池"],
            locale="zh-CN", deps=gate_deps,
        )
    )
    app = make_app()

    async def scenario() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://t"
        ) as client:
            response = await client.get(
                "/jobs/m2042-sse/events",
                headers={"X-User-Id": "u-owner", "Last-Event-ID": "5"},
            )
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/event-stream")
            ids = [
                int(line.split(":", 1)[1].strip())
                for line in response.text.splitlines()
                if line.startswith("id:")
            ]
            assert ids == list(range(6, 13)), "resume replays strictly after seq 5"
            payloads = [
                json.loads(line.split(":", 1)[1].strip())
                for line in response.text.splitlines()
                if line.startswith("data:")
            ]
            assert payloads[-1] == {"kind": "status", "state": "done"}

    run(scenario())
