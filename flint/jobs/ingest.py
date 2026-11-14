"""daily_ingest 编排 + 断点续跑（M1-035，技术方案 E4）。

- 8 步线性：fetch:{arxiv,ghtrend,gtrends,weibo}（各自独立，失败降级不阻塞，E4
  部分成功）→ normalize → cluster_lineage → heat_signals → cards。
- 断点续跑：每步数据自身幂等提交（范围 delete+insert / upsert / 确定性 ID），
  完成后写 job_steps 行（snapshot_ref 内联序列化 IngestCheckpoint）；重跑读
  job_steps 跳过已完成步，从断点之后继续（kill -9 语义）。
- 确定性：注入固定时钟 + DeterministicHashBackend + 确定性 keyword/cluster/
  lineage/card ID 规则 → 续跑产物与一次跑完 diff 为空（验收硬条款）。
- 命名走 s5：离线回放无 LLM，_NoLLMProvider 恒抛 → 全部降级 top 关键词
  （E6 章节类降级，不阻塞）。
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time
from pathlib import Path
from time import monotonic as time_monotonic
from typing import Any, Final, cast
from uuid import uuid4

import asyncpg
import structlog

from flint.cards import LinkCandidate, build_card
from flint.cluster.centroid import update_centroid
from flint.cluster.daily import cluster_keywords
from flint.domain.models import (
    JSON,
    CentroidDriftAudit,
    Cluster,
    ClusterStatus,
    HeatPoint,
    IngestCheckpoint,
    Keyword,
    SignalFlag,
    StepEvent,
    TrendItem,
)
from flint.domain.protocols import TrendSource
from flint.embed import DeterministicHashBackend, EmbeddingService
from flint.heat import RawHeatObservation, build_heat_points, write_heat_points_on
from flint.jobs.checkpoints import serialize_checkpoint
from flint.jobs.events import PgJobEventStream
from flint.lineage.s1 import ClusterRef, match_continuation
from flint.lineage.s4 import apply_dormancy, detect_revivals
from flint.lineage.s5 import register_new_cluster
from flint.lineage.s23 import detect_split_merge
from flint.lineage.store import build_lineage_result, save_lineage_result_on
from flint.norm.canonical import canonicalize
from flint.norm.terms import TermMap, load_term_map
from flint.obs.metrics import inc, observe
from flint.region.backfill import CrossRegionClusterError, region_of_members
from flint.repo.categories import load_categories, seed_categories
from flint.repo.centroid_daily import PgCentroidDailyStore
from flint.repo.keyword import upsert_keywords_on
from flint.signals import SignalConfig, detect_signals
from flint.sources.arxiv import ArxivSource
from flint.sources.degradation import (
    DegradationNote,
    fetch_notes_on,
    persist_note_on,
)
from flint.sources.errors import ParseDrift, RateLimitedError, SourceFetchError
from flint.sources.ghtrend import GitHubTrendingSource
from flint.sources.gtrends import GoogleTrendsSource
from flint.sources.weibo import WeiboHotSource
from flint.testing.replay import HttpReplay

SOURCE_IDS: Final[list[str]] = ["arxiv", "ghtrend", "gtrends", "weibo"]
STEP_ORDER: Final[list[str]] = [
    *(f"fetch:{sid}" for sid in SOURCE_IDS),
    "normalize",
    "cluster_lineage",
    "heat_signals",
    "cards",
]


class _NoLLMProvider:
    """离线回放禁 LLM：恒抛，s5 命名走 top 关键词降级路径。"""

    def generate(self, prompt: str, tools: list[JSON] | None) -> Any:
        raise RuntimeError("offline replay: LLM disabled")

    def generate_structured(self, prompt: str, schema: JSON, max_retries: int) -> JSON:
        raise RuntimeError("offline replay: LLM disabled")


@dataclass
class IngestDeps:
    dsn: str
    open_source: Callable[[str], Any]  # context manager yielding TrendSource
    embedder: EmbeddingService
    terms: TermMap
    now: datetime
    categories_path: Path
    tau_cluster: float = 0.75
    tau_match: float = 0.8
    tau_link: float = 0.6
    dormant_after_days: int = 14
    ema_alpha: float = 0.3
    max_centroid_shift: float = 0.5
    fallback_category_id: str = "cat-ai"
    top_links_n: int = 5


@dataclass
class IngestReport:
    job_id: str
    steps_run: list[str] = field(default_factory=list)
    degradation_notes: list[DegradationNote] = field(default_factory=list)


def keyword_id_for(canonical: str, lang: str) -> str:
    digest = hashlib.sha256(f"{canonical}|{lang}".encode()).hexdigest()
    return f"kw-{digest[:12]}"


def build_replay_deps(dsn: str, fixtures_root: Path, day: date) -> IngestDeps:
    fixed_now = datetime.combine(day, time(12, 0), tzinfo=UTC)
    adapters: dict[str, Callable[[Any], TrendSource]] = {
        "gtrends": lambda c: GoogleTrendsSource(client=c, now=lambda: fixed_now),
        "weibo": lambda c: WeiboHotSource(client=c, now=lambda: fixed_now),
        "ghtrend": lambda c: GitHubTrendingSource(client=c, now=lambda: fixed_now),
        "arxiv": lambda c: ArxivSource(client=c, now=lambda: fixed_now),
    }

    @contextmanager
    def open_source(source_id: str) -> Iterator[TrendSource]:
        fixture = fixtures_root / source_id / f"{day.isoformat()}.json"
        with HttpReplay(fixture, mode="replay") as session, session.client() as client:
            yield adapters[source_id](client)

    repo_root = fixtures_root.parent
    return IngestDeps(
        dsn=dsn,
        open_source=open_source,
        embedder=EmbeddingService(backend=DeterministicHashBackend(dim=1024)),
        terms=load_term_map(repo_root / "assets" / "term-map.yaml"),
        now=fixed_now,
        categories_path=repo_root / "assets" / "categories.yaml",
    )


# ── SQL helpers ───────────────────────────────────────────


def _vec(embedding: list[float]) -> str:
    return "[" + ",".join(repr(v) for v in embedding) + "]"


async def _ensure_job(conn: asyncpg.Connection, job_id: str, now: datetime) -> str:
    await conn.execute(
        "INSERT INTO jobs (job_id, kind, owner_scope, state, progress, budget, "
        "cost_accum, cancel_requested, initiated_by, created_at, updated_at) "
        "VALUES ($1, 'daily_ingest', '{\"kind\":\"org\",\"id\":\"system\"}', "
        "'queued', 0, 0, 0, false, 'u-system', $2, $2) "
        "ON CONFLICT (job_id) DO NOTHING",
        job_id,
        now,
    )
    state: str = await conn.fetchval("SELECT state FROM jobs WHERE job_id = $1", job_id)
    return state


async def _set_state(conn: asyncpg.Connection, job_id: str, state: str, now: datetime) -> None:
    await conn.execute(
        "UPDATE jobs SET state = $2, updated_at = $3 WHERE job_id = $1",
        job_id, state, now,
    )


async def _completed_steps(conn: asyncpg.Connection, job_id: str) -> list[str]:
    rows = await conn.fetch(
        "SELECT name FROM job_steps WHERE job_id = $1 ORDER BY step_index", job_id
    )
    return [r["name"] for r in rows]


async def _record_step(
    conn: asyncpg.Connection,
    job_id: str,
    index: int,
    name: str,
    state: str,
    checkpoint: IngestCheckpoint,
    now: datetime,
) -> None:
    await conn.execute(
        "INSERT INTO job_steps (job_id, step_index, name, state, started_at, "
        "ended_at, cost, snapshot_ref) VALUES ($1, $2, $3, $4, $5, $5, 0, $6)",
        job_id, index, name, state, now, serialize_checkpoint(checkpoint),
    )


# ── steps ─────────────────────────────────────────────────


async def _step_fetch(
    conn: asyncpg.Connection, deps: IngestDeps, day: date, source_id: str
) -> DegradationNote | None:
    note: DegradationNote | None = None
    items: list[TrendItem] = []
    try:
        with deps.open_source(source_id) as source:
            items = source.fetch_daily(day)
    except RateLimitedError as err:
        note = DegradationNote(day=day, source_id=source_id, reason="rate_limited", detail=str(err))
    except ParseDrift as err:
        note = DegradationNote(day=day, source_id=source_id, reason="parse_drift", detail=str(err))
    except (SourceFetchError, FileNotFoundError) as err:
        note = DegradationNote(day=day, source_id=source_id, reason="fetch_failed", detail=str(err))
    if note is None and not items:
        # **「跑成了」与「拿到了」是两件事**（`CN-07`）。
        # 往返成功而一条都没拿到时照旧留痕——不留的话，
        # 回执写着 `ok`、当日 `degradation_notes` 0 行，
        # 而广场上少了这一源**没有任何人会知道**。
        note = DegradationNote(
            day=day, source_id=source_id, reason="empty_result",
            detail="往返成功，而上游这一天一条都没给")
    if note is not None:
        await persist_note_on(conn, note)  # E6 行 1：落库（M1-040 硬条件）
        inc("degraded_sources_total", {"source": source_id})
        return note
    inc("ingest_success_total", {"source": source_id})
    async with conn.transaction():
        await conn.execute(
            "DELETE FROM trend_items_raw WHERE day = $1 AND source_id = $2",
            day, source_id,
        )
        await conn.executemany(
            "INSERT INTO trend_items_raw (day, source_id, item_index, keyword, "
            "score, region, url, captured_at) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)",
            [
                (day, source_id, i, it.keyword, it.score, it.region, it.url, it.captured_at)
                for i, it in enumerate(items)
            ],
        )
    return None


async def _load_day_canonicals(
    conn: asyncpg.Connection, deps: IngestDeps, day: date
) -> dict[str, str]:
    """day 原始词 -> {canonical: lang}，排序确定。"""
    rows = await conn.fetch(
        "SELECT keyword FROM trend_items_raw WHERE day = $1 ORDER BY source_id, item_index",
        day,
    )
    result: dict[str, str] = {}
    for r in rows:
        ck = canonicalize(r["keyword"], deps.terms)
        if ck.canonical:
            result.setdefault(ck.canonical, ck.lang)
    return result


async def _step_normalize(conn: asyncpg.Connection, deps: IngestDeps, day: date) -> None:
    canonicals = await _load_day_canonicals(conn, deps, day)
    ordered = sorted(canonicals)
    vectors = deps.embedder.embed(ordered)
    batch = [
        Keyword(
            keyword_id=keyword_id_for(c, canonicals[c]),
            canonical=c,
            lang=canonicals[c],
            aliases=[],
            embedding=vec,
            first_seen=day,
        )
        for c, vec in zip(ordered, vectors)
    ]
    if batch:
        await upsert_keywords_on(conn, batch)


async def _load_clusters(conn: asyncpg.Connection) -> dict[str, dict[str, Any]]:
    rows = await conn.fetch("SELECT * FROM clusters ORDER BY cluster_id")
    result: dict[str, dict[str, Any]] = {}
    for r in rows:
        result[r["cluster_id"]] = {
            "cluster_id": r["cluster_id"],
            "canonical_name": r["canonical_name"],
            "category_id": r["category_id"],
            "centroid": json.loads(r["centroid"]),
            "status": r["status"],
            "first_seen": r["first_seen"],
            "last_active": r["last_active"],
            "parent_cluster_ids": json.loads(r["parent_cluster_ids"]),
            "merged_into": r["merged_into"],
            "aliases": json.loads(r["aliases"]),
        }
    return result


# REGION-08 的跨区告警走这条既有通道（E7 结构化日志）。
_log = structlog.get_logger(__name__)


async def _upsert_cluster(
    conn: asyncpg.Connection, c: Cluster, region: str | None = None
) -> None:
    """建档/更新一个簇。

    **REGION-08 加的 region**：判不出来时传 `None`（列可空），NEVER 兜一个默认区
    ——「这个簇属于全球」与「我们没判出它属于哪」在广场上必须看得出区别。

    只回填不写日更的话，今天之后新建的每一个簇都没有区，
    而广场那个筛选器会把它们全部漏掉，看起来像「这个区今天没热点」。
    """
    await conn.execute(
        "INSERT INTO clusters (cluster_id, canonical_name, category_id, centroid, "
        "status, first_seen, last_active, parent_cluster_ids, merged_into, aliases, "
        "region) "
        "VALUES ($1, $2, $3, $4::vector, $5, $6, $7, $8::jsonb, $9, $10::jsonb, $11) "
        "ON CONFLICT (cluster_id) DO UPDATE SET canonical_name = EXCLUDED.canonical_name, "
        "centroid = EXCLUDED.centroid, status = EXCLUDED.status, "
        "last_active = EXCLUDED.last_active, "
        "parent_cluster_ids = EXCLUDED.parent_cluster_ids, "
        "merged_into = EXCLUDED.merged_into, aliases = EXCLUDED.aliases, "
        # 已判出区的簇 NEVER 被一个 NULL 覆盖回去：`COALESCE` 取新值优先、旧值兜底。
        "region = COALESCE(EXCLUDED.region, clusters.region)",
        c.cluster_id, c.canonical_name, c.category_id, _vec(c.centroid), c.status,
        c.first_seen, c.last_active,
        json.dumps(c.parent_cluster_ids, ensure_ascii=False), c.merged_into,
        json.dumps(c.aliases, ensure_ascii=False), region,
    )


async def _day_regions_by_canonical(
    conn: asyncpg.Connection, deps: IngestDeps, day: date
) -> dict[str, set[str]]:
    """当日原始条目的 region，按规范词归拢（REGION-08 的第三跳，日更侧）。"""
    rows = await conn.fetch(
        "SELECT keyword, region FROM trend_items_raw "
        "WHERE day = $1 AND region IS NOT NULL", day)
    out: dict[str, set[str]] = {}
    for row in rows:
        ck = canonicalize(str(row["keyword"]), deps.terms)
        if ck.canonical:
            out.setdefault(ck.canonical, set()).add(str(row["region"]))
    return out


async def _step_cluster_lineage(
    conn: asyncpg.Connection, deps: IngestDeps, day: date
) -> None:
    canonicals = await _load_day_canonicals(conn, deps, day)
    ordered = sorted(canonicals)
    kw_ids = [keyword_id_for(c, canonicals[c]) for c in ordered]
    vectors = deps.embedder.embed(ordered)
    id_to_canonical = dict(zip(kw_ids, ordered))

    day_regions = await _day_regions_by_canonical(conn, deps, day)
    existing = await _load_clusters(conn)
    refs = [
        ClusterRef(
            cluster_id=cid,
            centroid=row["centroid"],
            status=cast(ClusterStatus, row["status"]),
        )
        for cid, row in existing.items()
    ]
    cont = match_continuation(kw_ids, vectors, refs, tau_match=deps.tau_match)

    statuses = {cid: row["status"] for cid, row in existing.items()}
    revivals = detect_revivals(cont.matched_cluster_ids, statuses)
    revived_ids = [e.cluster_id for e in revivals]

    # 剩余关键词 → 候选新簇 → 分裂/合并/新生
    leftover_ids = cont.leftover_keyword_ids
    leftover_vecs = [vectors[kw_ids.index(k)] for k in leftover_ids]
    candidates = cluster_keywords(leftover_ids, leftover_vecs, deps.tau_cluster)
    stamp = day.strftime("%Y%m%d")
    sm = detect_split_merge(
        candidates, refs, tau_link=deps.tau_link,
        new_id_factory=lambda i: f"c-{stamp}-{i:03d}",
    )

    provider = _NoLLMProvider()
    allowed = [cid for cid, _ in load_categories(deps.categories_path)]
    naming_degraded: dict[str, bool] = {}
    # 当日判不出区的簇（成员跨区）。**与 naming_degraded 分开一本**：
    # 「名字降级了」与「区判不出来」是两件事，合成一本就分不清今天到底缺了什么。
    region_conflicts: dict[str, tuple[str, ...]] = {}
    drift_audits: list[CentroidDriftAudit] = []

    async with conn.transaction():
        # 延续簇：EMA 簇心 + last_active + 复活转 active
        vec_by_id = dict(zip(kw_ids, vectors))
        for cid in cont.matched_cluster_ids:
            row = existing[cid]
            members = cont.assignments[cid]
            mean = [
                sum(vec_by_id[m][d] for m in members) / len(members)
                for d in range(len(vec_by_id[members[0]]))
            ]
            update = update_centroid(
                cid, row["centroid"], mean, deps.ema_alpha, deps.max_centroid_shift
            )
            if update.audit is not None:
                drift_audits.append(update.audit)
            await conn.execute(
                "UPDATE clusters SET centroid = $2::vector, last_active = $3, "
                "status = 'active' WHERE cluster_id = $1",
                cid, _vec(update.centroid), day,
            )

        # 新生/分裂/合并建档
        for decision in sm.decisions:
            members = [id_to_canonical[k] for k in decision.keyword_ids]
            cluster, degraded = register_new_cluster(
                decision=decision,
                keyword_canonicals=sorted(members),
                allowed_category_ids=allowed,
                provider=provider,
                day=day,
                fallback_category_id=deps.fallback_category_id,
            )
            naming_degraded[cluster.cluster_id] = degraded
            # REGION-08：region 随成员走。规则**转调** flint/region/backfill.py 的
            # 那一个函数，NEVER 在这里再写一遍——两套规则会把同一个簇归到两个区。
            member_regions = [
                r for canonical in members
                for r in sorted(day_regions.get(canonical, ()))
            ]
            try:
                region = region_of_members(cluster.cluster_id, member_regions)
            except CrossRegionClusterError as err:
                # **跨区不掐日更。** 回填是一次性动作，停下来给人看是对的；
                # 日更是每天跑的批，一条簇跨区就终止整天，等于让一条数据问题
                # 把当天**其余全部热点**一起丢掉——那比漏一个区标记坏得多。
                # 所以这里留 NULL（「还不知道」）并**大声记一笔**，NEVER 取众数。
                region = None
                region_conflicts[cluster.cluster_id] = tuple(sorted(set(member_regions)))
                _log.warning(
                    "cluster_region_conflict", cluster_id=cluster.cluster_id,
                    day=day.isoformat(), regions=sorted(set(member_regions)),
                    detail=str(err))
            await _upsert_cluster(conn, cluster, region)
        for old_id, new_id in sm.merged_into.items():
            await conn.execute(
                "UPDATE clusters SET status = 'merged', merged_into = $2 "
                "WHERE cluster_id = $1",
                old_id, new_id,
            )

        # 休眠（含当日未命中者）
        fresh = await _load_clusters(conn)
        states = {
            cid: (row["status"], row["last_active"]) for cid, row in fresh.items()
        }
        dormant_ids = apply_dormancy(states, today=day, dormant_after_days=deps.dormant_after_days)
        for cid in dormant_ids:
            await conn.execute(
                "UPDATE clusters SET status = 'dormant' WHERE cluster_id = $1", cid
            )

    result = build_lineage_result(
        lineage_id=uuid4().hex,  # 决策⑤：uuid 主键；可复现性走产物内容比对（路 A）
        day=day,
        assignments=cont.assignments,
        revived_cluster_ids=revived_ids,
        decisions=sm.decisions,
        naming_degraded=naming_degraded,
        dormant_cluster_ids=dormant_ids,
        drift_audits=drift_audits,
        tau_match=deps.tau_match,
        tau_link=deps.tau_link,
        dormant_after_days=deps.dormant_after_days,
        generated_at=deps.now,
    )
    if region_conflicts:
        # 汇总一条：逐条的告警上面已经发过，这一条是给「今天到底有几个」用的。
        _log.warning(
            "cluster_region_conflicts_today", day=day.isoformat(),
            count=len(region_conflicts), cluster_ids=sorted(region_conflicts))
    # append-only（决策⑤）直插：kill-9 不留半条由步级同事务提交（M1-040）
    # 保证——步未记账则整批回滚，重跑整批重插，无需先删
    await save_lineage_result_on(conn, result)


async def _day_membership(
    conn: asyncpg.Connection, day: date
) -> dict[str, list[str]]:
    """当日 lineage events -> cluster_id -> keyword_ids（确定序）。
    读取口径（路 A）：按 day 取最新一批（append-only 下同日可多批）。"""
    row = await conn.fetchrow(
        "SELECT events FROM lineage_results WHERE day = $1 "
        "ORDER BY generated_at DESC, lineage_id DESC LIMIT 1",
        day,
    )
    membership: dict[str, list[str]] = {}
    if row is None:
        return membership
    for event in json.loads(row["events"]):
        kind = event["kind"]
        cid = event["cluster_id"] if kind in ("continued", "revived", "new") else event["new_cluster_id"]
        membership.setdefault(cid, []).extend(event["keyword_ids"])
    return {cid: sorted(set(kws)) for cid, kws in sorted(membership.items())}


async def _step_heat_signals(
    conn: asyncpg.Connection, deps: IngestDeps, day: date
) -> None:
    membership = await _day_membership(conn, day)
    if not membership:
        return
    kw_rows = await conn.fetch("SELECT keyword_id, canonical FROM keywords")
    canonical_by_id = {r["keyword_id"]: r["canonical"] for r in kw_rows}
    cluster_by_canonical = {
        canonical_by_id[k]: cid
        for cid, kws in membership.items()
        for k in kws
        if k in canonical_by_id
    }
    raw_rows = await conn.fetch(
        "SELECT source_id, keyword, score FROM trend_items_raw WHERE day = $1 "
        "ORDER BY source_id, item_index",
        day,
    )
    sums: dict[tuple[str, str], float] = {}
    for r in raw_rows:
        canonical = canonicalize(r["keyword"], deps.terms).canonical
        cid = cluster_by_canonical.get(canonical)
        if cid is not None:
            key = (cid, r["source_id"])
            sums[key] = sums.get(key, 0.0) + float(r["score"])

    observations = [
        RawHeatObservation(source_id=sid, cluster_id=cid, day=day, raw_value=v)
        for (cid, sid), v in sorted(sums.items())
    ]
    hist_rows = await conn.fetch(
        "SELECT cluster_id, source_id, day, raw_value FROM heat_points WHERE day < $1",
        day,
    )
    history = [
        RawHeatObservation(
            source_id=r["source_id"], cluster_id=r["cluster_id"],
            day=r["day"], raw_value=r["raw_value"],
        )
        for r in hist_rows
    ]
    points = build_heat_points(observations, history)
    await conn.execute(
        "DELETE FROM heat_points WHERE day = $1", day
    )
    if points:
        await write_heat_points_on(conn, points)
        # H-4：把当日热点簇质心从 clusters 快照进 cluster_centroid_daily（弱信号轨质心历史，
        # 迁移 0018；NEVER 改冻结 Cluster）。事务内、幂 upsert。
        await PgCentroidDailyStore(deps.dsn).snapshot_from_clusters_on(
            conn, day, [p.cluster_id for p in points])


async def _step_cards(conn: asyncpg.Connection, deps: IngestDeps, day: date) -> None:
    membership = await _day_membership(conn, day)
    if not membership:
        return
    day_notes = await fetch_notes_on(conn, day)
    clusters = await _load_clusters(conn)
    kw_rows = await conn.fetch("SELECT keyword_id, canonical FROM keywords")
    canonical_by_id = {r["keyword_id"]: r["canonical"] for r in kw_rows}
    raw_rows = await conn.fetch(
        "SELECT source_id, keyword, score, url FROM trend_items_raw WHERE day = $1 "
        "ORDER BY source_id, item_index",
        day,
    )
    links_by_canonical: dict[str, list[LinkCandidate]] = {}
    for r in raw_rows:
        canonical = canonicalize(r["keyword"], deps.terms).canonical
        links_by_canonical.setdefault(canonical, []).append(
            LinkCandidate(url=r["url"], source_id=r["source_id"], score=float(r["score"]))
        )
    heat_rows = await conn.fetch(
        "SELECT cluster_id, source_id, day, raw_value, norm_score FROM heat_points "
        "ORDER BY cluster_id, source_id, day"
    )
    revived_row = await conn.fetchrow(
        "SELECT events FROM lineage_results WHERE day = $1 "
        "ORDER BY generated_at DESC, lineage_id DESC LIMIT 1",
        day,
    )
    revived_today = {
        e["cluster_id"]
        for e in (json.loads(revived_row["events"]) if revived_row else [])
        if e["kind"] == "revived"
    }

    stamp = day.strftime("%Y%m%d")
    async with conn.transaction():
        for cid, kws in membership.items():
            row = clusters[cid]
            cluster = Cluster(
                cluster_id=cid,
                canonical_name=row["canonical_name"],
                category_id=row["category_id"],
                centroid=row["centroid"],
                status=cast(ClusterStatus, row["status"]),
                first_seen=row["first_seen"],
                last_active=row["last_active"],
                parent_cluster_ids=row["parent_cluster_ids"],
                merged_into=row["merged_into"],
                aliases=row["aliases"],
            )
            cluster_points = [
                HeatPoint(
                    cluster_id=r["cluster_id"], source_id=r["source_id"],
                    day=r["day"], raw_value=r["raw_value"], norm_score=r["norm_score"],
                )
                for r in heat_rows
                if r["cluster_id"] == cid
            ]
            series = sorted(
                ((p.day, p.norm_score) for p in cluster_points), key=lambda t: t[0]
            )
            flags: list[SignalFlag] = detect_signals(
                first_seen=cluster.first_seen,
                revived_today=cid in revived_today,
                norm_series=series,
                today=day,
                config=SignalConfig(),
            )
            candidates = [
                cand
                for k in kws
                for cand in links_by_canonical.get(canonical_by_id.get(k, ""), [])
            ]
            view = build_card(
                card_id=f"card-{stamp}-{cid}",
                cluster=cluster,
                keyword_ids=kws,
                flags=flags,
                link_candidates=candidates,
                heat_points=cluster_points,
                degradation_notes=day_notes,
                top_n=deps.top_links_n,
            )
            await conn.execute(
                "INSERT INTO evidence_cards (card_id, cluster_id, keyword_ids, flags, "
                "top_links) VALUES ($1, $2, $3::jsonb, $4::jsonb, $5::jsonb) "
                "ON CONFLICT (card_id) DO UPDATE SET keyword_ids = EXCLUDED.keyword_ids, "
                "flags = EXCLUDED.flags, top_links = EXCLUDED.top_links",
                view.card.card_id, cid,
                json.dumps(view.card.keyword_ids, ensure_ascii=False),
                json.dumps(view.card.flags, ensure_ascii=False),
                json.dumps(view.card.top_links, ensure_ascii=False),
            )


# ── orchestrator ──────────────────────────────────────────


async def run_daily_ingest(
    job_id: str,
    day: date,
    deps: IngestDeps,
    crash_after: str | None = None,
) -> IngestReport:
    report = IngestReport(job_id=job_id)
    await seed_categories(deps.dsn, load_categories(deps.categories_path))
    events = PgJobEventStream(dsn=deps.dsn)
    conn = await asyncpg.connect(deps.dsn)
    try:
        state = await _ensure_job(conn, job_id, deps.now)
        if state in ("done", "failed", "cancelled"):
            return report
        if state == "queued":
            await _set_state(conn, job_id, "retrieving", deps.now)
        completed = await _completed_steps(conn, job_id)

        started_monotonic = time_monotonic()
        for index, name in enumerate(STEP_ORDER):
            if name in completed:
                continue
            await events.append(
                job_id, StepEvent(kind="step", step_name=name, phase="start", cost=None),
                ts=deps.now,
            )
            # 步数据与 job_steps 记录同事务提交（M1-035 审核跟进：消除
            # 「数据已提交、步记录未提交」的重放窗口）
            async with conn.transaction():
                step_state = "done"
                if name.startswith("fetch:"):
                    source_id = name.split(":", 1)[1]
                    note = await _step_fetch(conn, deps, day, source_id)
                    if note is not None:
                        report.degradation_notes.append(note)
                        step_state = "failed"
                elif name == "normalize":
                    await _step_normalize(conn, deps, day)
                elif name == "cluster_lineage":
                    await _step_cluster_lineage(conn, deps, day)
                elif name == "heat_signals":
                    await _step_heat_signals(conn, deps, day)
                else:
                    await _step_cards(conn, deps, day)

                sources_done = sorted(
                    {
                        n.split(":", 1)[1]
                        for n in [*completed, name]
                        if n.startswith("fetch:")
                    }
                )
                checkpoint = IngestCheckpoint(
                    kind="daily_ingest", day=day, sources_done=sources_done
                )
                await _record_step(
                    conn, job_id, index, name, step_state, checkpoint, deps.now
                )
            completed.append(name)
            report.steps_run.append(name)
            await events.append(
                job_id, StepEvent(kind="step", step_name=name, phase="end", cost=0.0),
                ts=deps.now,
            )
            if crash_after == name:
                os._exit(137)  # kill -9 semantics: no cleanup, no commit beyond this point

        await _set_state(conn, job_id, "validating", deps.now)
        await _set_state(conn, job_id, "done", deps.now)
        observe(
            "job_duration_seconds",
            {"kind": "daily_ingest"},
            time_monotonic() - started_monotonic,
        )
        inc("llm_cost_cny_total", {"kind": "daily_ingest"}, 0.0)  # 离线回放零 LLM 成本
    finally:
        await conn.close()
    return report


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="flint daily_ingest driver")
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--day", required=True)
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--fixtures-root", required=True)
    parser.add_argument("--crash-after", default=None)
    args = parser.parse_args(argv)
    day = date.fromisoformat(args.day)
    deps = build_replay_deps(dsn=args.dsn, fixtures_root=Path(args.fixtures_root), day=day)
    asyncio.run(
        run_daily_ingest(
            job_id=args.job_id, day=day, deps=deps, crash_after=args.crash_after
        )
    )


if __name__ == "__main__":
    main()
