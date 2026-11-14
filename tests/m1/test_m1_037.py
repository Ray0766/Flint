"""M1-037 acceptance tests: 30-day replay harness (make dev-replay).

Acceptance (tasks.json M1-037):
  - 30 offline days all green
  - per-day traces produced (inputs manifest + checkpoint log)
"""
from __future__ import annotations

import asyncio
import os
import shutil
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import asyncpg
import pytest

from harness.replay30 import ReplaySummary, run_replay

pytestmark = pytest.mark.compose

REPO_ROOT = Path(__file__).resolve().parents[2]
DSN = os.environ.get("FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")
END = date(2026, 7, 23)
DAYS = 30
TRACE_DIR = REPO_ROOT / "docs" / "trace" / "replay30"
DEGRADED_DAY = date(2026, 7, 5)   # weibo 429 fixture day
REVIVAL_DAY = date(2026, 7, 15)   # 复活测试词 returns after >14d absence

WIPE_SQL = [
    "DELETE FROM evidence_cards",
    "DELETE FROM heat_points",
    "DELETE FROM lineage_results",
    "DELETE FROM clusters",
    "DELETE FROM keywords",
    "DELETE FROM trend_items_raw",
    "DELETE FROM job_events WHERE job_id LIKE 'replay-%'",
    "DELETE FROM job_steps WHERE job_id LIKE 'replay-%'",
    "DELETE FROM jobs WHERE job_id LIKE 'replay-%'",
]


def run(coro: Any) -> Any:
    return asyncio.run(coro)


async def _fetch(query: str, *args: Any) -> list[asyncpg.Record]:
    conn = await asyncpg.connect(DSN)
    try:
        return await conn.fetch(query, *args)
    finally:
        await conn.close()


@pytest.fixture(scope="module")
def summary() -> ReplaySummary:
    async def wipe() -> None:
        conn = await asyncpg.connect(DSN)
        try:
            for stmt in WIPE_SQL:
                await conn.execute(stmt)
        finally:
            await conn.close()

    run(wipe())
    if TRACE_DIR.exists():
        shutil.rmtree(TRACE_DIR)
    return run_replay(
        days=DAYS, end=END, dsn=DSN,
        fixtures_root=REPO_ROOT / "fixtures", trace_dir=TRACE_DIR,
    )


def test_thirty_days_all_green(summary: ReplaySummary) -> None:
    assert len(summary.days) == DAYS
    assert summary.all_green is True
    rows = run(
        _fetch("SELECT job_id, state FROM jobs WHERE job_id LIKE 'replay-%' ORDER BY job_id")
    )
    assert len(rows) == DAYS
    assert {r["state"] for r in rows} == {"done"}


def test_per_day_traces_with_inputs_and_checkpoint_log(summary: ReplaySummary) -> None:
    files = sorted(TRACE_DIR.glob("*.md"))
    assert len(files) == DAYS
    for path in files:
        text = path.read_text(encoding="utf-8")
        assert "inputs 来源清单" in text, f"{path.name}: missing inputs manifest"
        assert "fixtures/" in text, f"{path.name}: manifest must list fixture files"
        assert "断点日志" in text, f"{path.name}: missing checkpoint log"
        assert "sources_done" in text, f"{path.name}: checkpoint content must be shown"
        assert "state=done" in text, f"{path.name}: job outcome missing"


def test_lineage_batches_one_per_day(summary: ReplaySummary) -> None:
    rows = run(_fetch("SELECT day FROM lineage_results ORDER BY day"))
    days = [r["day"] for r in rows]
    assert days == [END - timedelta(days=DAYS - 1 - i) for i in range(DAYS)]


def test_degraded_day_stays_green_and_is_annotated(summary: ReplaySummary) -> None:
    day_summary = next(d for d in summary.days if d.day == DEGRADED_DAY)
    assert day_summary.job_state == "done"
    assert ("weibo", "rate_limited") in day_summary.notes
    trace = (TRACE_DIR / f"{DEGRADED_DAY.isoformat()}.md").read_text(encoding="utf-8")
    assert "rate_limited" in trace
    # 其余三源当天照常落数据
    rows = run(
        _fetch(
            "SELECT DISTINCT source_id FROM trend_items_raw WHERE day = $1", DEGRADED_DAY
        )
    )
    assert {r["source_id"] for r in rows} == {"arxiv", "ghtrend", "gtrends"}


def test_replay_exercises_dormancy_and_revival(summary: ReplaySummary) -> None:
    """30 天窗口内构造的「复活测试词」：缺席 >14 天 -> dormant，回归日 -> revived。"""
    revived = run(
        _fetch(
            "SELECT day FROM lineage_audit WHERE event_kind = 'revived' ORDER BY day"
        )
    )
    assert any(r["day"] == REVIVAL_DAY for r in revived), "revival must fire on return day"
    dormant = run(
        _fetch("SELECT day FROM lineage_audit WHERE event_kind = 'dormant' ORDER BY day")
    )
    assert dormant and dormant[0]["day"] < REVIVAL_DAY, "dormancy precedes revival"


def test_heat_momentum_emerges_over_window(summary: ReplaySummary) -> None:
    """30 天热度窗口下至少出现一次 momentum 角标（分位随历史演化）。"""
    rows = run(_fetch("SELECT flags::text AS f FROM evidence_cards"))
    assert any("momentum" in r["f"] for r in rows)


def test_makefile_entry_matches_harness() -> None:
    makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")
    assert "dev-replay:" in makefile
    assert "python -m harness.replay30 --days $(DAYS)" in makefile
