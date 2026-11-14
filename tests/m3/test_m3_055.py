"""M3-055 acceptance tests: revalidation scheduler job.

Acceptance (tasks.json M3-055):
  - daily 04:00 scan submits one revalidation job per due project (recorded
    fake-clock run)
  - lock semantics do not interfere with daily_ingest
"""
from __future__ import annotations

import asyncio
import os
from datetime import UTC, date, datetime
from typing import Any
from uuid import uuid4

import asyncpg
import pytest

from flint.jobs.revalidation import SCAN_HOUR, run_revalidation_scan
from flint.jobs.runner import PgJobRunner

pytestmark = pytest.mark.compose

DSN = os.environ.get("FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")
TODAY = date(2026, 7, 29)
NOW = datetime(2026, 7, 29, 4, 0, 0, tzinfo=UTC)


def run(coro: Any) -> Any:
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def clean_slate() -> None:
    async def wipe() -> None:
        conn = await asyncpg.connect(DSN)
        try:
            await conn.execute("DELETE FROM jobs WHERE job_id LIKE 'm3055-%'")
        finally:
            await conn.close()

    run(wipe())


def runner() -> PgJobRunner:
    return PgJobRunner(
        dsn=DSN, role_resolver=lambda user, org: None,
        id_factory=lambda: f"m3055-{uuid4().hex[:10]}",
    )


PROJECTS = [
    ("p-new", date(2026, 7, 20), None),
    ("p-due-mid", date(2026, 6, 1), None),
    ("p-due-old", date(2026, 1, 1), date(2026, 5, 1)),
]


def test_scan_hour_is_0400() -> None:
    assert SCAN_HOUR == 4


def test_scan_submits_one_job_per_due_project() -> None:
    submitted = run(run_revalidation_scan(
        runner(), projects=PROJECTS, today=TODAY,
    ))
    assert len(submitted) == 2, "two due, one too new"

    async def kinds() -> list[tuple[str, str]]:
        conn = await asyncpg.connect(DSN)
        try:
            rows = await conn.fetch(
                "SELECT job_id, kind, project_id FROM jobs "
                "WHERE job_id LIKE 'm3055-%' ORDER BY project_id"
            )
            return [(r["kind"], r["project_id"]) for r in rows]
        finally:
            await conn.close()

    assert run(kinds()) == [
        ("revalidation", "p-due-mid"), ("revalidation", "p-due-old"),
    ]


def test_no_interference_with_daily_ingest_lock_namespace() -> None:
    from flint.jobs.revalidation import scan_lock_key

    key = scan_lock_key(TODAY)
    assert key.startswith("lock:revalidation_scan:"), key
    assert "daily_ingest" not in key, "separate lock namespace (E4)"
