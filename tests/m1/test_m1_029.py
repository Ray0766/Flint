"""M1-029 acceptance tests: LineageResult persistence + lineage audit view.

Acceptance (tasks.json M1-029):
  - any cluster's full lineage chain is queryable
  - the audit view can be exported by the labeling tool

Owner decision list (v0.4, Q-002) baked in: revived dedup (1), parent list
shape (4), append-only + lineage_id PK + day index (5), per-event cluster-ID
fan-out with index (6), 15-natural-day retention (route A).
"""
from __future__ import annotations

import asyncio
import os
from datetime import UTC, date, datetime, timedelta
from typing import Any

import asyncpg
import pytest
import yaml

from flint.cluster.daily import ClusterCandidate  # noqa: F401 — shape parity
from flint.domain.models import (
    CentroidDriftAudit,
    ContinuedEvent,
    LineageResult,
    MergedEvent,
    NewClusterEvent,
    RevivedEvent,
    SplitEvent,
)
from flint.lineage.s23 import LineageDecision
from flint.lineage.store import (
    build_lineage_result,
    deserialize_events,
    export_cluster_lineage_yaml,
    fetch_cluster_lineage,
    prune_expired,
    save_lineage_result,
    serialize_events,
)

DSN = os.environ.get("FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")
DAY = date(2026, 7, 23)
GENERATED = datetime(2026, 7, 23, 9, 0, 0, tzinfo=UTC)


def run(coro: Any) -> Any:
    return asyncio.run(coro)


def build_sample(lineage_id: str = "lin-1", day: date = DAY) -> LineageResult:
    return build_lineage_result(
        lineage_id=lineage_id,
        day=day,
        assignments={"c-live": ["kw-a"], "c-rev": ["kw-b", "kw-c"]},
        revived_cluster_ids=["c-rev"],
        decisions=[
            LineageDecision("split", "c-s1", ["kw-d"], [1.0], ["c-old"]),
            LineageDecision("split", "c-s2", ["kw-e"], [1.0], ["c-old"]),
            LineageDecision("merge", "c-m1", ["kw-f"], [1.0], ["c-a", "c-b"]),
            LineageDecision("new", "c-n1", ["kw-g"], [1.0], []),
        ],
        naming_degraded={"c-n1": True},
        dormant_cluster_ids=["c-sleepy"],
        drift_audits=[
            CentroidDriftAudit(
                cluster_id="c-live", attempted_shift=0.4, max_shift=0.2, action="rejected"
            )
        ],
        tau_match=0.8,
        tau_link=0.6,
        dormant_after_days=14,
        generated_at=GENERATED,
    )


# ── pure build semantics ──────────────────────────────────


def test_revived_cluster_not_duplicated_as_continued() -> None:
    """Decision (1): revived clusters emit exactly one RevivedEvent whose
    keyword_ids come from the day's assignments."""
    result = build_sample()
    continued = [e for e in result.events if isinstance(e, ContinuedEvent)]
    revived = [e for e in result.events if isinstance(e, RevivedEvent)]
    assert [e.cluster_id for e in continued] == ["c-live"]
    assert revived == [
        RevivedEvent(kind="revived", cluster_id="c-rev", keyword_ids=["kw-b", "kw-c"])
    ]


def test_split_events_carry_parent_list() -> None:
    """Decision (4): SplitEvent.parent_cluster_ids is a list, same shape as merge."""
    result = build_sample()
    splits = [e for e in result.events if isinstance(e, SplitEvent)]
    assert len(splits) == 2
    for split in splits:
        assert split.parent_cluster_ids == ["c-old"]


def test_merge_and_new_events_built() -> None:
    result = build_sample()
    merges = [e for e in result.events if isinstance(e, MergedEvent)]
    news = [e for e in result.events if isinstance(e, NewClusterEvent)]
    assert merges[0].merged_cluster_ids == ["c-a", "c-b"]
    assert news[0].naming_degraded is True
    assert result.dormant_cluster_ids == ["c-sleepy"]
    assert result.tau_match == 0.8


def test_events_serialization_roundtrip() -> None:
    result = build_sample()
    blob = serialize_events(result.events)
    restored = deserialize_events(blob)
    assert restored == result.events


# ── persistence + audit view (DB) ─────────────────────────


@pytest.fixture()
def clean_db() -> None:
    async def wipe() -> None:
        conn = await asyncpg.connect(DSN)
        try:
            # 路 A（uuid 批次）后前缀过滤失效：本文件断言含全表保留策略
            # （prune 计数），清场取全表——后续套件（037/040）各自全量重建，
            # 无跨文件状态依赖
            await conn.execute("DELETE FROM lineage_results")
        finally:
            await conn.close()

    run(wipe())


@pytest.mark.compose
def test_any_cluster_full_chain_queryable(clean_db: None) -> None:
    """c-old appears on day1 as a new cluster and on day2 as split parent of
    two children — its chain must surface all of it in day order."""
    day1 = build_lineage_result(
        lineage_id="lin-d1",
        day=DAY - timedelta(days=1),
        assignments={},
        revived_cluster_ids=[],
        decisions=[LineageDecision("new", "c-old", ["kw-z"], [1.0], [])],
        naming_degraded={},
        dormant_cluster_ids=[],
        drift_audits=[],
        tau_match=0.8,
        tau_link=0.6,
        dormant_after_days=14,
        generated_at=GENERATED,
    )
    day2 = build_sample(lineage_id="lin-d2", day=DAY)
    run(save_lineage_result(DSN, day1))
    run(save_lineage_result(DSN, day2))

    chain = run(fetch_cluster_lineage(DSN, "c-old"))
    kinds = [(row["day"], row["event_kind"], row["role"]) for row in chain]
    assert (DAY - timedelta(days=1), "new", "subject") in kinds
    assert (DAY, "split", "parent") in kinds
    assert len([k for k in kinds if k[1] == "split"]) == 2, "both children visible"
    assert kinds == sorted(kinds, key=lambda k: k[0]), "chain ordered by day"


@pytest.mark.compose
def test_dormant_and_revival_visible_in_chain(clean_db: None) -> None:
    run(save_lineage_result(DSN, build_sample(lineage_id="lin-x")))
    sleepy = run(fetch_cluster_lineage(DSN, "c-sleepy"))
    assert any(r["event_kind"] == "dormant" for r in sleepy)
    revived = run(fetch_cluster_lineage(DSN, "c-rev"))
    assert any(r["event_kind"] == "revived" for r in revived)


@pytest.mark.compose
def test_append_only_two_batches_same_day(clean_db: None) -> None:
    run(save_lineage_result(DSN, build_sample(lineage_id="lin-r1")))
    run(save_lineage_result(DSN, build_sample(lineage_id="lin-r2")))

    async def count() -> int:
        conn = await asyncpg.connect(DSN)
        try:
            value: int = await conn.fetchval(
                "SELECT count(*) FROM lineage_results WHERE day = $1", DAY
            )
            return value
        finally:
            await conn.close()

    assert run(count()) == 2, "same-day rebatch appends, never overwrites"


@pytest.mark.compose
def test_export_for_labeling_tool(clean_db: None) -> None:
    run(save_lineage_result(DSN, build_sample(lineage_id="lin-y")))
    dumped = run(export_cluster_lineage_yaml(DSN, "c-old"))
    payload = yaml.safe_load(dumped)
    assert payload["cluster_id"] == "c-old"
    assert isinstance(payload["timeline"], list) and payload["timeline"]
    kinds = {row["event_kind"] for row in payload["timeline"]}
    assert "split" in kinds, "labeling tool needs the four lineage kinds visible"


@pytest.mark.compose
def test_retention_keeps_last_15_natural_days(clean_db: None) -> None:
    old = build_sample(lineage_id="lin-old", day=DAY - timedelta(days=20))
    fresh = build_sample(lineage_id="lin-fresh", day=DAY - timedelta(days=3))
    run(save_lineage_result(DSN, old))
    run(save_lineage_result(DSN, fresh))
    removed = run(prune_expired(DSN, today=DAY, keep_days=15))
    assert removed == 1

    async def remaining() -> set[str]:
        conn = await asyncpg.connect(DSN)
        try:
            rows = await conn.fetch(
                "SELECT lineage_id FROM lineage_results WHERE lineage_id LIKE 'lin-%'"
            )
            return {r["lineage_id"] for r in rows}
        finally:
            await conn.close()

    assert run(remaining()) == {"lin-fresh"}


@pytest.mark.compose
def test_audit_table_indexed_on_cluster_id(clean_db: None) -> None:
    """Decision (6): the fan-out table carries a cluster_id index."""

    async def indexes() -> list[str]:
        conn = await asyncpg.connect(DSN)
        try:
            rows = await conn.fetch(
                "SELECT indexdef FROM pg_indexes WHERE tablename = 'lineage_audit'"
            )
            return [r["indexdef"] for r in rows]
        finally:
            await conn.close()

    assert any("cluster_id" in idx for idx in run(indexes()))
