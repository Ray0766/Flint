"""M1-035 acceptance tests: daily_ingest orchestration + checkpoint resume.

Acceptance (tasks.json M1-035):
  - after kill -9 the rerun resumes from the checkpoint
  - resumed artifacts diff empty against a single uninterrupted run
"""
from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any

import asyncpg
import pytest

from flint.domain.models import IngestCheckpoint
from flint.jobs.checkpoints import deserialize_checkpoint
from flint.jobs.ingest import build_replay_deps, run_daily_ingest

pytestmark = pytest.mark.compose

REPO_ROOT = Path(__file__).resolve().parents[2]
DSN = os.environ.get("FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")
DAY = date(2026, 7, 23)
FAIL_DAY = date(2026, 7, 27)

ARTIFACT_QUERIES = {
    "raw": "SELECT day, source_id, item_index, keyword, score, region, url, "
    "captured_at FROM trend_items_raw ORDER BY day, source_id, item_index",
    "keywords": "SELECT keyword_id, canonical, lang, aliases::text, embedding::text, "
    "first_seen FROM keywords ORDER BY keyword_id",
    "clusters": "SELECT cluster_id, canonical_name, category_id, centroid::text, "
    "status, first_seen, last_active, parent_cluster_ids::text, merged_into, "
    "aliases::text FROM clusters ORDER BY cluster_id",
    # 路 A（uuid 主键）：快照按内容比对，不含随机 lineage_id
    "lineage": "SELECT day, events::text, dormant_cluster_ids::text, "
    "drift_audits::text, tau_match, tau_link, dormant_after_days, generated_at "
    "FROM lineage_results ORDER BY day",
    "heat": "SELECT cluster_id, source_id, day, raw_value, norm_score "
    "FROM heat_points ORDER BY cluster_id, source_id, day",
    "cards": "SELECT card_id, cluster_id, keyword_ids::text, flags::text, "
    "top_links::text FROM evidence_cards ORDER BY card_id",
}

WIPE_SQL = [
    "DELETE FROM evidence_cards",
    "DELETE FROM heat_points",
    "DELETE FROM lineage_results",
    "DELETE FROM clusters",
    "DELETE FROM keywords",
    "DELETE FROM trend_items_raw",
    "DELETE FROM job_events WHERE job_id LIKE 'm1035-%'",
    "DELETE FROM job_steps WHERE job_id LIKE 'm1035-%'",
    "DELETE FROM jobs WHERE job_id LIKE 'm1035-%'",
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


async def _snapshot() -> dict[str, list[tuple[Any, ...]]]:
    conn = await asyncpg.connect(DSN)
    try:
        result: dict[str, list[tuple[Any, ...]]] = {}
        for name, query in ARTIFACT_QUERIES.items():
            rows = await conn.fetch(query)
            result[name] = [tuple(r) for r in rows]
        return result
    finally:
        await conn.close()


async def _fetch(query: str, *args: Any) -> list[asyncpg.Record]:
    conn = await asyncpg.connect(DSN)
    try:
        return await conn.fetch(query, *args)
    finally:
        await conn.close()


@pytest.fixture(autouse=True)
def clean_slate() -> None:
    run(_sql(WIPE_SQL))


def ingest(job_id: str, day: date = DAY) -> Any:
    deps = build_replay_deps(dsn=DSN, fixtures_root=REPO_ROOT / "fixtures", day=day)
    return run(run_daily_ingest(job_id=job_id, day=day, deps=deps))


def test_uninterrupted_run_produces_full_artifact_chain() -> None:
    report = ingest("m1035-solo")
    snap = run(_snapshot())
    assert len(snap["raw"]) > 80, "four sources land raw items"
    assert len(snap["keywords"]) > 80
    assert len(snap["clusters"]) > 0
    assert len(snap["lineage"]) == 1
    assert len(snap["heat"]) > 0
    assert len(snap["cards"]) == len(snap["clusters"])
    assert report.degradation_notes == []
    job_row = run(_fetch("SELECT state FROM jobs WHERE job_id = 'm1035-solo'"))
    assert job_row[0]["state"] == "done"
    steps = run(
        _fetch(
            "SELECT name FROM job_steps WHERE job_id = 'm1035-solo' ORDER BY step_index"
        )
    )
    assert [s["name"] for s in steps] == [
        "fetch:arxiv", "fetch:ghtrend", "fetch:gtrends", "fetch:weibo",
        "normalize", "cluster_lineage", "heat_signals", "cards",
    ]


def test_kill9_resume_matches_uninterrupted_run() -> None:
    # reference: one uninterrupted run
    ingest("m1035-ref")
    reference = run(_snapshot())

    # crashed run: real subprocess killed via os._exit(137) after fetch:weibo
    run(_sql(WIPE_SQL))
    env = dict(os.environ, FLINT_TEST_DSN=DSN, PYTHONIOENCODING="utf-8")
    proc = subprocess.run(
        [
            sys.executable, "-m", "flint.jobs.ingest",
            "--dsn", DSN,
            "--day", DAY.isoformat(),
            "--job-id", "m1035-crash",
            "--fixtures-root", str(REPO_ROOT / "fixtures"),
            "--crash-after", "fetch:weibo",
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    assert proc.returncode == 137, f"driver must die hard: {proc.stdout}\n{proc.stderr}"

    # the checkpoint of the last completed step survived the kill
    steps = run(
        _fetch(
            "SELECT name, snapshot_ref FROM job_steps WHERE job_id = 'm1035-crash' "
            "ORDER BY step_index"
        )
    )
    done_names = [s["name"] for s in steps]
    assert done_names == ["fetch:arxiv", "fetch:ghtrend", "fetch:gtrends", "fetch:weibo"]
    checkpoint = deserialize_checkpoint(steps[-1]["snapshot_ref"])
    assert isinstance(checkpoint, IngestCheckpoint)
    assert checkpoint.day == DAY
    assert set(checkpoint.sources_done) == {"arxiv", "ghtrend", "gtrends", "weibo"}

    # resume the SAME job: must continue after the checkpoint...
    ingest("m1035-crash")
    resumed_steps = run(
        _fetch("SELECT name FROM job_steps WHERE job_id = 'm1035-crash' ORDER BY step_index")
    )
    names = [s["name"] for s in resumed_steps]
    assert len(names) == 8
    assert len([n for n in names if n == "fetch:weibo"]) == 1, "completed steps never rerun"

    # ...and the artifacts diff-empty against the uninterrupted reference
    resumed = run(_snapshot())
    assert resumed == reference


def test_all_sources_down_day_completes_with_degradation() -> None:
    report = ingest("m1035-dark", day=FAIL_DAY)
    assert len(report.degradation_notes) == 4
    assert {n.source_id for n in report.degradation_notes} == {
        "arxiv", "ghtrend", "gtrends", "weibo"
    }
    job_row = run(_fetch("SELECT state FROM jobs WHERE job_id = 'm1035-dark'"))
    assert job_row[0]["state"] == "done", "single-source (even all-source) loss never blocks"
    snap = run(_snapshot())
    assert snap["raw"] == []
    assert snap["cards"] == []


def test_rerun_after_done_is_noop_idempotent() -> None:
    ingest("m1035-idem")
    first = run(_snapshot())
    ingest("m1035-idem")  # job already done -> no step reruns, artifacts unchanged
    assert run(_snapshot()) == first
