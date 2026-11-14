"""前半程三界面读端点（FE-VIEWS）：广场 / 工作台 / Gate 视图。

**既有模型上的只读端点**——查现有持久化表（clusters/heat_points/evidence_cards/
snapshots），NEVER 改冻结件、NEVER 造数据。缺口界面（主题 Q-009 / 关联假设 Q-010）
本轮不建（未持久化，登记待 owner）。
- GET /plaza/hot?day= → 当日热点簇（clusters × heat_points，按 compute_hotness 综合分排
  （速度+加速+衰减+新颖+跨源印证）；另单列 weak_signals 早期弱信号轨）。
- GET /clusters/{id}/evidence-cards → 该簇证据卡（keyword_ids/flags/top_links）。
- GET /jobs/{id}/verdict → Gate① 四分类全字段（取自 snapshots['snap-{job}-verdict']）。
- GET /topics/{id} → 单 Topic 全字段（TS-007）；未知 → 404。
- GET /projects/{id}/topics → 该 project 的 Topic 列表 + chosen_topic_id（TS-007）；
  未知 project → 空。
"""
from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, get_args

import asyncpg
from fastapi import FastAPI
from fastapi.responses import JSONResponse, Response

from flint.api.schemas import ErrorBody, ErrorCode
from flint.burst import BurstConfig, cluster_burst
from flint.domain.models import Topic
from flint.hotness import ClusterSeries, HotnessConfig, compute_hotness
from flint.norm.canonical import canonicalize
from flint.norm.terms import load_term_map
from flint.region.source_constants import SOURCE_CONSTANT_REGIONS as _SOURCE_CONST
from flint.region.source_text import (
    RawItem,
    as_payload,
    cluster_of_canonical,
    wordings_by_cluster,
)
from flint.region.version_scope import CURRENT_SCOPE, in_scope
from flint.repo.cluster_verdict import latest_verdict_job
from flint.topic.store import PgProjectStore, PgTopicSeedStore, PgTopicStore
from flint.weaksignal import WeakSignalConfig, rank_weak_signals, weak_signal_score


@dataclass
class ViewsApiDeps:
    dsn: str


def _topic_json(topic: Topic) -> dict[str, object]:
    return {
        "topic_id": topic.topic_id,
        "seed_id": topic.seed_id,
        "one_liner": topic.one_liner,
        "target_user_tag": topic.target_user_tag,
        "form_factor_tag": topic.form_factor_tag,
        "why_now": {
            "claim": topic.why_now.claim,
            "evidences": [
                {"event": e.event, "event_date": e.event_date.isoformat(),
                 "citation_id": e.citation_id}
                for e in topic.why_now.evidences
            ],
            "speculative": topic.why_now.speculative,
        },
        "keyword_mapping": topic.keyword_mapping,
    }


def _error(status: int, code: ErrorCode, message: str) -> JSONResponse:
    body = ErrorBody(code=code, message=message, detail=None)
    return JSONResponse(status_code=status, content=body.model_dump(exclude_none=True))


# REGION-11 / DEC-040：未归区。**它不是第十个地区**，是筛选面上的第十个**选项**。
#
# 库里 `clusters.region` 的分布（steward 实查）：`global = 103` · `CN = 89` · `NULL = 1`。
# `global` 是 `ghtrend` 写死的常量，不是地理事实。把它当第九区，用户会在地理列表里
# 选到一个不存在的地方；让它从筛选面消失，那 104 条**一旦开始筛就蒸发**。
#
# 记号取一个**不可能与地区码撞车**的词：`Region` 那九个全是两位大写字母。
UNASSIGNED_REGION = "unassigned"

# term map 的进程内缓存（REGION-12）。它是只读资产，每请求重读一次纯属浪费。
_TERMS: Any = None

# 落在 `region` 列里、但**不是地理事实**的那些值。它们与 `NULL` 一起归入未归区。
# 与 `NULL` 的区别恒保留在库里：`NULL` = 从来没归过区，`global` = 源说了「全球」。
# **NEVER 把 NULL 回填成 global** —— 回填过的行与本来就是 global 的行长得一模一样。
#
# `DEC-058` 之后**清单本身搬去了 `flint/region/source_constants.py`**：
# 定区那一侧（`backfill.region_of_members`）与筛选面这一侧要用同一份，
# 各写一份的话，加第二个源常量那天只有一处会跟上。
# 这里保留同名再导出——既有读者与判据都按这个名字找它。
SOURCE_CONSTANT_REGIONS = _SOURCE_CONST


def _term_map() -> Any:
    """term map 只加载一次。

    它是 `assets/term-map.yaml`，与日更作业读的**是同一个文件**——
    另存一份的话，某天改了词表而广场没跟上，屏上的词面会归到别的簇去。
    """
    global _TERMS
    if _TERMS is None:
        _TERMS = load_term_map(
            Path(__file__).resolve().parents[2] / "assets" / "term-map.yaml")
    return _TERMS


async def _day_source_wordings(
    conn: asyncpg.Connection, day: date,
) -> dict[str, dict[str, str]]:
    """REGION-12：当日每条簇上、每个源说的那句**原话**。

    三跳与 `flint/region/backfill.py` 同一个方向：
    `lineage_results` 当日成员 → `keywords.canonical` →
    canonicalize 后相同的 `trend_items_raw.keyword`。

    当日没有血缘批次（`lineage_results` 无行）时回空 dict——
    那是「这一天还没算过成员」，**NEVER 退化成按名字猜**：
    猜错一次，屏上会写着「微博对这个热点说过某句话」，而它说的是别的事。
    """
    row = await conn.fetchrow(
        "SELECT events FROM lineage_results WHERE day = $1 "
        "ORDER BY generated_at DESC, lineage_id DESC LIMIT 1", day)
    if row is None:
        return {}
    membership: dict[str, list[str]] = {}
    for event in json.loads(row["events"]):
        kind = event["kind"]
        cid = (event["cluster_id"] if kind in ("continued", "continuation", "revived",
                                               "new") else event["new_cluster_id"])
        membership.setdefault(cid, []).extend(event["keyword_ids"])

    kw_rows = await conn.fetch("SELECT keyword_id, canonical FROM keywords")
    by_canonical = cluster_of_canonical(
        membership, {str(r["keyword_id"]): str(r["canonical"]) for r in kw_rows})

    raw_rows = await conn.fetch(
        "SELECT source_id, keyword FROM trend_items_raw WHERE day = $1 "
        "ORDER BY source_id, item_index", day)
    terms = _term_map()
    wordings = wordings_by_cluster(
        [RawItem(source_id=str(r["source_id"]), keyword=str(r["keyword"]))
         for r in raw_rows],
        by_canonical,
        lambda raw: canonicalize(raw, terms).canonical,
    )
    return {cid: as_payload(per_source) for cid, per_source in wordings.items()}


def _selectable_regions() -> frozenset[str]:
    """筛选器**接受**的全部取值：九个地区 + 未归区。

    与 `_known_regions()` 分开：那一个是**地理词表**（冻结件 `Region`，
    也是 `GET /settings/locale` 的 `options.region`），未归区不属于它——
    塞进去等于允许 `PUT /settings/locale` 把「未归区」存成一个人的常住地。
    """
    return _known_regions() | {UNASSIGNED_REGION}


def _known_regions() -> frozenset[str]:
    """合法地区**取自冻结件 `contracts_v04.Region`**，与 `GET /settings/locale` 同源。

    ## 改前拿的是「表里现在有什么」

    `SELECT DISTINCT region FROM clusters`。那把两件完全不同的事混成了一件：

    - **`AU` 不是一个区**  ← 假的。它在产品词表里，只是今天没数据；
    - **`AU` 今天没数据**  ← 真的，而它该回 200 + 空，
      落到规格 #2.14 已建的「该区当日无数据」态。

    混起来的后果是：`/settings/locale` 给屏上九个区，其中八个一点就报 400——
    用户看到的是「这个区不存在」，而真相是「这个区今天没热点」。

    反过来，库里的 `global` **不在**这份词表里（`ghtrend` 写死的常量，不是一个区），
    所以选 `global` 仍然是 400。**那是对的、也是要的**——`global` 不是一个地方。

    `REGION-11` 之后那 104 条不再筛不到：它们经**未归区**（`UNASSIGNED_REGION`）
    这个显式选项出来，而不是靠把 `global` 硬认成第九区。词表本身一字未动。
    """
    cached = sys.modules.get("models_v04_views")
    if cached is None:
        spec = importlib.util.spec_from_file_location(
            "models_v04_views",
            Path(__file__).resolve().parents[2] / "contracts_v04" / "models_v04.py")
        assert spec is not None and spec.loader is not None
        cached = importlib.util.module_from_spec(spec)
        sys.modules["models_v04_views"] = cached
        spec.loader.exec_module(cached)
    return frozenset(str(r) for r in get_args(cached.Region))



def create_views_app(deps: ViewsApiDeps) -> FastAPI:
    app = FastAPI(title="flint-views-api")

    @app.get("/plaza/hot")
    async def plaza(day: str, region: str | None = None) -> Response:
        """当日热点簇。`region` 非空时**真的筛**（REGION-09）。

        改前这个参数不在签名里——FastAPI 对未声明的 query **静默忽略**，
        于是带 `region=CN` 回的是全量，与不带逐字相同。`DEC-035` 的原话：
        **一个静静地什么都不筛的筛选器比没有筛选器更坏**。

        不传（或传空串）时行为与基线**逐字相同**：规格 #2.14 的增量口径。
        """
        try:
            parsed = date.fromisoformat(day)
        except ValueError:
            return _error(400, "VALIDATION_FAILED", f"bad day (want YYYY-MM-DD): {day!r}")
        # H-1/H-3/H-5 主榜综合分（读时算、零契约）：取回看窗口 day 时序 → 速度/加速度/
        # HN 衰减/新颖度/**跨源印证**（主榜核心）。参数临时初值（标定通道见 v0.4-问题单）。
        cfg = HotnessConfig()
        window_start = parsed - timedelta(days=cfg.window_days)
        wanted = (region or "").strip()
        if wanted and wanted not in _selectable_regions():
                # 静默回全量是最坏的：用户拼错一个区名，拿到的是全世界的热点，
                # 而屏上写着他选的那个区。
                # 清单里**含未归区**（REGION-11）：漏了它的话，调用方照着报错信息
                # 把请求改一遍，还是选不到那 104 条。
                return _error(
                    400, "VALIDATION_FAILED",
                    f"unknown region {wanted!r}; "
                f"known: {', '.join(sorted(_selectable_regions()))}")
        # REGION-11：未归区一次捞两种——`NULL`（从来没归过区）与源常量（`global`）。
        # **只是查询把它们放到同一个选项里，库里两者恒可分辨**（DEC-040）。
        unassigned = wanted == UNASSIGNED_REGION
        conn = await asyncpg.connect(deps.dsn)
        try:
            rows = await conn.fetch(
                "SELECT c.cluster_id, c.canonical_name, c.category_id, c.status, "
                "c.first_seen, c.region, h.source_id, h.norm_score, h.day "
                "FROM heat_points h "
                "JOIN clusters c ON c.cluster_id = h.cluster_id "
                "WHERE h.day BETWEEN $1 AND $2 "
                # 三条互斥的分支，逐条对应筛选面上的三种状态：
                #   ① 不筛           → $3 为 NULL 且 $4 假；
                #   ② 未归区         → $4 真：`region IS NULL` 或落在源常量里；
                #   ③ 某个地理区     → $3 非空，逐字相等。
                # region IS NULL 的簇**哪个地理区都不属于**（REGION-08 留 NULL 的用意）：
                # 塞进任何一个区，用户看到的都是一条我们并不知道产地的热点。
                # 它现在有了自己的去处——未归区，而不是继续在筛选面上消失。
                "AND ( ($3::text IS NULL AND NOT $4::bool) "
                "   OR ($4::bool AND (c.region IS NULL OR c.region = ANY($5::text[]))) "
                "   OR ($3::text IS NOT NULL AND c.region = $3) )",
                window_start, parsed,
                None if unassigned else (wanted or None),
                unassigned, list(SOURCE_CONSTANT_REGIONS),
            )
            # H-4 弱信号轨：取窗口内每日质心（cluster_centroid_daily，迁移 0018）算漂移。
            crows = await conn.fetch(
                "SELECT cluster_id, centroid FROM cluster_centroid_daily "
                "WHERE day BETWEEN $1 AND $2 ORDER BY day ASC",
                window_start, parsed,
            )
            # REGION-12：每个源对每条簇说的那句**原话**（`PLAZA-02` 缺口二）。
            # 在同一个连接里取，NEVER 为它再开一次连接。
            wordings = await _day_source_wordings(conn, parsed)
        finally:
            await conn.close()
        centroid_history: dict[str, list[list[float]]] = {}
        for cr in crows:
            centroid_history.setdefault(str(cr["cluster_id"]), []).append(
                [float(x) for x in json.loads(cr["centroid"])])
        agg_by_day: dict[str, dict[date, float]] = {}
        by_source_today: dict[str, dict[str, float]] = {}
        by_source_region: dict[str, dict[str, str]] = {}
        meta: dict[str, dict[str, str]] = {}
        first_seen: dict[str, date] = {}
        for r in rows:
            cid = str(r["cluster_id"])
            rday = r["day"]
            norm = float(r["norm_score"])
            agg_by_day.setdefault(cid, {})
            agg_by_day[cid][rday] = agg_by_day[cid].get(rday, 0.0) + norm
            if rday == parsed:                       # 当日快照（决定入榜 + 跨源/展示）
                by_source_today.setdefault(cid, {})[str(r["source_id"])] = norm
                # REGION-09 的地区维度**另开一键**：`by_source` 是 {源: 分值}，
                # HOTSPOT-07 的分列判据按这个形状读。往里塞一个对象，
                # 那些判据会在**读到分值的地方拿到一个 dict**——它们不会报错，
                # 只会算出一个错的列高。
                if r["region"] is not None:
                    by_source_region.setdefault(cid, {})[str(r["source_id"])] = str(
                        r["region"])
                first_seen[cid] = r["first_seen"]
                meta[cid] = {
                    "canonical_name": str(r["canonical_name"]),
                    "category_id": str(r["category_id"]), "status": str(r["status"]),
                }
        scored = []
        for cid, src_today in by_source_today.items():   # 仅当日有热度点的簇入主榜
            series = ClusterSeries(
                cluster_id=cid, first_seen=first_seen[cid],
                agg_by_day=agg_by_day[cid], by_source_today=src_today)
            scored.append((cid, series, compute_hotness(series, parsed, cfg)))
        scored.sort(key=lambda it: (-it[2].total, it[0]))   # 综合分降序、确定性
        clusters = [
            {
                "cluster_id": cid, **meta[cid],
                # SLOT-01 首见日期：这一列上面的 SQL **一直在查**（喂 ClusterSeries 算新颖度），
                # 算完就丢，于是卡面那一槽永远是空的。零迁移、零冻结件改动——只是回出去。
                # 恒 ISO 日：卡面 `<time datetime>` 与判据都按这一种写法逐字比，
                # 换成时间戳或本地化格式，前端要再解析一次，而解析失败时它**静静地不显示**。
                "first_seen": first_seen[cid].isoformat(),
                "by_source": series.by_source_today,
                "by_source_region": by_source_region.get(cid, {}),
                # REGION-12：每个源的**原文词面**（`SourceColumns` 的 `text` 槽）。
                # **NEVER 拿 `by_source` 的分值去顶这一格**：屏上会出现一列
                # 「来源说法」写着 `100.0`，而那是 `DEC-034`/`DEC-038` 反复禁的
                # 「借一个已经有主的槽去说另一件事」。
                # 查不到词面的源**不出现在这里**（不是空串）：空串在屏上与
                # 「这个源说了一句空话」长得一模一样，而真相是我们没能把它的原话找回来。
                "by_source_text": wordings.get(cid, {}),
                "total_heat": sc.agg,
                "hotness": sc.total,
                "hotness_components": {
                    "velocity": sc.velocity, "accel": sc.accel,
                    "cross_count": sc.cross_count, "multi_boost": sc.multi_boost,
                    "novelty_factor": sc.novelty_factor, "decay": sc.decay_divisor,
                },
            }
            for cid, series, sc in scored
        ]
        # H-4 弱信号早期轨（单列一轨，NEVER 混主榜）：小而在加速 + bge-m3 语义稳定 + 突发。
        wcfg = WeakSignalConfig()
        bcfg = BurstConfig()
        weak_scores = [
            weak_signal_score(
                cid, agg_by_day[cid], centroid_history.get(cid, []),
                cluster_burst(cid, agg_by_day[cid], parsed, bcfg).burst_weight,
                parsed, wcfg)
            for cid in by_source_today
        ]
        weak_signals = [
            {
                "cluster_id": w.cluster_id, **meta[w.cluster_id],
                "weak_score": w.score, "agg": w.agg, "velocity": w.velocity,
                "drift": w.drift, "burst_weight": w.burst_weight,
            }
            for w in rank_weak_signals(weak_scores)
        ]
        # CN-02 / `DEC-045`：这一区在**本版**有没有内容。
        #
        # **这一格与 `clusters` 为空是两件事**：空列表说的是「查过了，没有」，
        # 而 `region_in_scope: false` 说的是「这一版不做这个区」——
        # 前者该让用户换一天，后者该让他等下一版。合成一个之后，
        # 等下一版的人会一直刷新，而换一天的人会以为功能没做。
        #
        # 由**服务端**回答而不是让前端自己判：`CURRENT_SCOPE` 只有一处真相，
        # 前端再抄一份的话，下一版解除收窄时会有一处忘了跟上（`LOC-01` 同一条理由）。
        return JSONResponse({
            "day": day,
            "clusters": clusters,
            "weak_signals": weak_signals,
            "region_in_scope": in_scope(wanted or None),
            "scope_lifts_when": CURRENT_SCOPE.lifts_when,
        })

    @app.get("/clusters/{cluster_id}/evidence-cards")
    async def workbench(cluster_id: str) -> Response:
        conn = await asyncpg.connect(deps.dsn)
        try:
            rows = await conn.fetch(
                "SELECT card_id, cluster_id, keyword_ids, flags, top_links "
                "FROM evidence_cards WHERE cluster_id = $1 ORDER BY card_id",
                cluster_id,
            )
        finally:
            await conn.close()
        cards = [
            {
                "card_id": r["card_id"], "cluster_id": r["cluster_id"],
                "keyword_ids": json.loads(r["keyword_ids"]),
                "flags": json.loads(r["flags"]),
                "top_links": json.loads(r["top_links"]),
            }
            for r in rows
        ]
        return JSONResponse({"cluster_id": cluster_id, "evidence_cards": cards})

    @app.get("/jobs/{job_id}/verdict")
    async def gate_verdict(job_id: str) -> Response:
        conn = await asyncpg.connect(deps.dsn)
        try:
            payload: bytes | None = await conn.fetchval(
                "SELECT payload FROM snapshots WHERE snapshot_id = $1",
                f"snap-{job_id}-verdict",
            )
        finally:
            await conn.close()
        if payload is None:
            return _error(404, "NOT_FOUND", f"no Gate verdict for job {job_id}")
        return JSONResponse({"job_id": job_id, "verdict": json.loads(payload)})

    @app.get("/clusters/{cluster_id}/verdict")
    async def cluster_verdict(cluster_id: str) -> Response:
        """按**热点**取最新一条 Gate① 判定（`PERSIST-04` / `DEC-044`）。

        `docs/blocked/HOTSPOT-03.md` 当初判死的正是「自己补一个 cluster 键端点」——
        **理由是那时没有真相可查**：判定按 job 键落盘，从热点出发只能靠猜一个
        job id 去试，而猜错时用户看到的是**另一个热点的判定**。

        `DEC-044` 之后前提变了：`cluster_verdicts` 就是那个真相。
        所以补这条端点不是自作主张，是那张单等的那件事。

        **加一条读法，不是换一条**：`GET /jobs/{id}/verdict` 一行没动——
        它与这一条服务的是两种问法（「这次作业判了什么」与「这个热点判过什么」）。
        """
        conn = await asyncpg.connect(deps.dsn)
        try:
            job_id = await latest_verdict_job(conn, cluster_id)
            payload: bytes | None = (
                None if job_id is None
                else await conn.fetchval(
                    "SELECT payload FROM snapshots WHERE snapshot_id = $1",
                    f"snap-{job_id}-verdict",
                )
            )
        finally:
            await conn.close()
        if job_id is None:
            # **「没判过」这一态**：说出来，NEVER 回一个空判定——
            # 回空的话前端分不出「没判过」与「判了但内容是空的」。
            return _error(
                404, "NOT_FOUND", f"no Gate verdict for cluster {cluster_id}")
        if payload is None:
            # 关系行在、快照没了：这是**第三态**（判过、但读不回来），
            # 与「没判过」NEVER 合并——前者该去查快照哪儿去了，后者该去发起一次分析。
            return _error(
                404, "NOT_FOUND",
                f"verdict snapshot missing for job {job_id}"
                f"（这个热点判过，而那份判定读不回来）")
        return JSONResponse({
            "cluster_id": cluster_id, "job_id": job_id,
            "verdict": json.loads(payload)})

    @app.get("/topics/{topic_id}")
    async def topic_detail(topic_id: str) -> Response:
        try:
            topic = await PgTopicStore(dsn=deps.dsn).load(topic_id)
        except KeyError:
            return _error(404, "NOT_FOUND", f"unknown topic: {topic_id}")
        return JSONResponse({"topic": _topic_json(topic)})

    @app.get("/projects/{project_id}/topics")
    async def project_topics(project_id: str) -> Response:
        try:
            project = await PgProjectStore(dsn=deps.dsn).load(project_id)
        except KeyError:  # 未知 project → 空（非 404）
            return JSONResponse(
                {"project_id": project_id, "chosen_topic_id": None, "topics": []}
            )
        store = PgTopicStore(dsn=deps.dsn)
        topics: list[dict[str, object]] = []
        for topic_id in project.topic_ids:
            try:
                topics.append(_topic_json(await store.load(topic_id)))
            except KeyError:
                continue  # topic_ids 指向的 Topic 缺失 → 跳过（据实、不造）
        return JSONResponse({
            "project_id": project_id,
            "chosen_topic_id": project.chosen_topic_id,
            "topics": topics,
        })

    # ── BL-06：广场展示**主题**（Q-009 的那一段）
    #
    # 与 `/plaza/hot` 分开是本条的要点：`/plaza/hot` 出的是**簇**（日更采集层产物），
    # 这条出的是**主题**（分析产物）。合成一条的那天，界面上那一排看起来像主题，
    # 而它们其实是簇——用户会以为系统已经分析过了。
    # 所以本端点 NEVER 读 clusters / heat_points，一行都不读。
    @app.get("/plaza/topics")
    async def plaza_topics(owner_id: str, limit: int = 20) -> Response:
        if limit <= 0:
            return _error(400, "VALIDATION_FAILED", f"limit 须为正：{limit}")
        conn = await asyncpg.connect(deps.dsn)
        try:
            rows = await conn.fetch(
                "SELECT t.topic_id FROM topics t "
                "JOIN topic_seeds s ON s.seed_id = t.seed_id "
                "JOIN origins o ON o.origin_id = s.origin_id "
                "WHERE o.owner ->> 'kind' = 'user' AND o.owner ->> 'id' = $1 "
                "ORDER BY t.topic_id DESC LIMIT $2",
                owner_id, limit,
            )
        finally:
            await conn.close()
        store = PgTopicStore(dsn=deps.dsn)
        topics: list[dict[str, object]] = []
        for row in rows:
            try:
                topics.append(_topic_json(await store.load(str(row["topic_id"]))))
            except KeyError:
                continue                     # 据实、不造（与 project_topics 同口径）
        return JSONResponse({
            "owner_id": owner_id,
            "topics": topics,
            # 空态**成句说出来**：空数组在前端是一片空白，而空白既可能是「没有」
            # 也可能是「没加载出来」。NEVER 拿簇顶上（那是 /plaza/hot 的面）。
            "empty_note": "" if topics else "尚无主题：先从广场选卡建关联假设，或提交一个想法入口",
        })

    # ── BL-06：工作台展示**关联假设**（Q-010 的那一段）
    #
    # 关联假设 = combo 型 Origin/TopicSeed 的 `hypothesis`（v0.3.2 口径）。
    # 它落在 `topic_seeds.hypothesis` 上，此前没有任何读端点——
    # 「落库了但看不见」与「没落库」在界面上长得一模一样。
    @app.get("/projects/{project_id}/hypothesis")
    async def project_hypothesis(project_id: str) -> Response:
        try:
            seed = await PgTopicSeedStore(dsn=deps.dsn).load(project_id)
        except KeyError:
            return _error(404, "NOT_FOUND", f"unknown seed: {project_id}")
        return JSONResponse({
            "seed_id": seed.seed_id,
            "origin_id": seed.origin_id,
            "hypothesis": seed.hypothesis,
            "keywords": list(seed.keywords),
            # hypothesis 可空（非 combo 入口没有关联假设）——空就明说，NEVER 编一句
            "empty_note": "" if seed.hypothesis else "该入口不是 combo，没有关联假设",
        })

    return app
