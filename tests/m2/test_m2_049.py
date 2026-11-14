"""M2-049 acceptance tests: retrieval snapshot replay reproduction (F2).

Acceptance (tasks.json M2-049):
  - any Analysis reproduces fully from its retrieval snapshot
  - reproduction artifacts diff empty against the original run
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

import asyncpg
import pytest

from flint.gate.replay import ReplayReport, replay_analysis
from flint.jobs.gate1 import build_offline_deps, run_gate1

pytestmark = pytest.mark.compose

REPO_ROOT = Path(__file__).resolve().parents[2]
DSN = os.environ.get("FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")
KEYWORDS = ["固态电池", "钠离子电池"]

WIPE_SQL = [
    "DELETE FROM job_events WHERE job_id LIKE 'm2049-%'",
    "DELETE FROM job_steps WHERE job_id LIKE 'm2049-%'",
    "DELETE FROM jobs WHERE job_id LIKE 'm2049-%'",
    "DELETE FROM snapshots WHERE snapshot_id LIKE 'snap-m2049-%'",
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


def test_analysis_reproduces_from_snapshot_diff_empty() -> None:
    deps = build_offline_deps(dsn=DSN, repo_root=REPO_ROOT)
    run(run_gate1(job_id="m2049-rep", keywords=KEYWORDS, locale="zh-CN", deps=deps))

    report = run(
        replay_analysis(
            job_id="m2049-rep", keywords=KEYWORDS, locale="zh-CN", deps=deps
        )
    )
    assert isinstance(report, ReplayReport)
    assert report.judge_matches is True, "judge phase reproduces byte-identically"
    assert report.verdict_matches is True, "verdict reproduces byte-identically"
    assert report.diff_empty is True
    assert report.verdict["verdict"] == "B_red_ocean"


def test_tampered_snapshot_detected() -> None:
    """复现器必须真的在比对——篡改原判定快照后 diff 不再为空。"""
    deps = build_offline_deps(dsn=DSN, repo_root=REPO_ROOT)
    run(run_gate1(job_id="m2049-tam", keywords=KEYWORDS, locale="zh-CN", deps=deps))

    async def tamper() -> None:
        conn = await asyncpg.connect(DSN)
        try:
            await conn.execute(
                "UPDATE snapshots SET payload = $2 WHERE snapshot_id = $1",
                "snap-m2049-tam-verdict", b'{"verdict": "C_opportunity"}',
            )
        finally:
            await conn.close()

    run(tamper())
    report = run(
        replay_analysis(
            job_id="m2049-tam", keywords=KEYWORDS, locale="zh-CN", deps=deps
        )
    )
    assert report.judge_matches is True
    assert report.verdict_matches is False, "tamper must be caught by the byte diff"
    assert report.diff_empty is False
