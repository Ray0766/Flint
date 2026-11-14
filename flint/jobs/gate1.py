"""gate1_analysis 编排 + 断点续跑 + SSE（M2-040，技术方案 E4）。

- 4 步线性：plan → retrieve → judge → validate；每步结束在**同一事务**里写
  job_steps 行（snapshot_ref 内联序列化 AnalysisCheckpoint）——步数据与
  job_steps 记录同事务提交，kill -9 不留半条；重跑读 job_steps 跳过已完成步。
- checkpoint.phase 语义 = 下一待跑相位（plan 完成 → "retrieve"，retrieve 完成
  → "judge"，judge/validate 完成 → "validate"，冻结 Literal 三值封顶）。
- 状态机随相位推进（queued→retrieving→judging→validating→done），
  StatusChanged / StepEvent 经 PgJobEventStream 落事件日志（seq 单调，SSE
  Last-Event-ID 补发依据）；**步边界崩溃**下续跑只补发缺失事件，全序与一次
  跑完一致（end 事件在步事务之外：崩溃恰落在「事务已提交、end 未写」间隙
  或步中时，事件序可能缺 end / 重复 start——已知边界，记 v0.4 备忘）。
- 确定性：注入固定时钟 + 确定性 searcher/provider + 确定性 snapshot_id
  （snap-{job_id}-{step}）→ 续跑产物与一次跑完按内容 diff 为空（验收硬条款）。
- 离线回放零 LLM（S2-7）：_DeterministicJudgeProvider 按 prompt 族分派
  确定性结果（术语/扩展/相关性/对齐/竞品抽取五族）。
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Final, Literal, cast

import asyncpg
from starlette.concurrency import run_in_threadpool

from flint.align.stage1 import LLMCitationAligner, align_key_evidence
from flint.competitor.coverage import QueryExecution, assess_coverage
from flint.competitor.extract import CompetitorRecord, extract_competitors
from flint.competitor.signals import SignalInputs, derive_signals
from flint.competitor.strength import Strength, build_competitor
from flint.compose.claims import claim_id_for as compose_claim_id
from flint.compose.refute_claims import build_refute_pairs
from flint.domain.models import (
    JSON,
    Alignment,
    AnalysisCheckpoint,
    Claim,
    Competitor,
    Completion,
    Doc,
    JobState,
    Query,
    StepEvent,
)
from flint.domain.protocols import LLMProvider
from flint.evidence.compliance import check_provenance, restore_docs, serialize_docs
from flint.gate.engine import decide
from flint.gate.rule_a import evaluate_rule_a
from flint.gate.rule_b import evaluate_rule_b
from flint.gate.rule_c import evaluate_rule_c
from flint.gate.rule_d import derive_gaps
from flint.jobs.checkpoints import serialize_checkpoint
from flint.jobs.cluster_verdict import clusters_for_topic, record_cluster_verdicts
from flint.jobs.events import PgJobEventStream
from flint.jobs.state import enter_state
from flint.llm.cache import LLMJudgmentCache
from flint.norm.terms import TermMap, load_term_map
from flint.retrieval.query_builder import FourStepQueryBuilder
from flint.retrieval.relevance import THETA_REL, LLMRelevanceJudge

STEP_ORDER: Final[list[str]] = ["plan", "retrieve", "judge", "validate"]

_STEP_STATE: Final[dict[str, JobState]] = {
    "plan": "retrieving",
    "retrieve": "retrieving",
    "judge": "judging",
    "validate": "validating",
}
_NEXT_PHASE: Final[dict[str, Literal["retrieve", "judge", "validate"]]] = {
    "plan": "retrieve",
    "retrieve": "judge",
    "judge": "validate",
    "validate": "validate",
}

Searcher = Callable[[Query], list[Doc]]


def query_id_for(query: Query) -> str:
    digest = hashlib.sha256(f"{query.intent}|{query.text}".encode()).hexdigest()
    return f"q-{digest[:12]}"


def claim_id_for(claim: str) -> str:
    return f"claim-{hashlib.sha256(claim.encode()).hexdigest()[:12]}"


# ── CHAIN-01：判定 → claims 那一跳 ───────────────────────────

# **分析产物 id 的命名空间**。`claims` 表按交付物索引，而 gate1 的产出
# 不是一份交付物——它是一次判定。所以给它一个自己的前缀：
# 交付物是 `del-{job}`，分析产物是 `analysis-{job}`，两者永远撞不上。
#
# `claims.deliverable_id` **没有外键**（`migrations/0008`），
# 所以这个 id 不需要、也 NEVER 去 `deliverables` 表建一行假记录——
# 建了的话，交付物列表里会多出一份没人能打开的「报告」。
ANALYSIS_PRODUCT_PREFIX: Final[str] = "analysis-"
# 「对齐器根本没判过这一对」的表示。**NEVER 与 `unsupported` 合并**：
# 后者是「查过了，证据不支持」，前者是「超出 K 上限，没查」。
PENDING_ALIGNMENT: Final[Alignment] = "pending"


def analysis_product_id(job_id: str) -> str:
    return f"{ANALYSIS_PRODUCT_PREFIX}{job_id}"


@dataclass(frozen=True)
class ClaimRow:
    """一条落盘用的 claim。**逐字对齐冻结件 `Claim` 的字段**（S3）。"""

    claim_id: str
    deliverable_id: str
    block_id: str
    text_span: str
    confidence: Literal["cited", "speculative"]
    citation_ids: list[str]
    alignment: Alignment

    def to_claim(self) -> Claim:
        return Claim(
            claim_id=self.claim_id, deliverable_id=self.deliverable_id,
            block_id=self.block_id, text_span=self.text_span,
            confidence=self.confidence, citation_ids=list(self.citation_ids),
            alignment=self.alignment, promoted_fact_id=None,
        )


def claim_rows_from(
    product_id: str,
    support_claims: list[JSON],
    alignment_by: dict[tuple[str, str], Alignment],
    cited_docs: dict[str, str],
) -> list[ClaimRow]:
    """judge 的 support_claims → 可落盘的 claim 行。

    三处**不肯含糊**的地方：

    1. **对齐器没判过的写 `pending`**，NEVER 写 `unsupported`——
       后者读起来是「查过了，证据不支持」，而真相是「超出 K 上限，没查」；
    2. **`cited` 要库里真有那条 citation**（`cited_docs` 是实测到的映射）。
       编一个 id 的话，下游解引用会失败，而那种失败读起来像「引用坏了」，
       真相是「引用从没入过库」；
    3. **claim_id 走 `flint.compose.claims.claim_id_for`**（三段哈希，
       含 product_id）——只由文本决定的话，两次判定会共用一行，
       而它们可能判得不一样。
    """
    block_id = f"{product_id}#judge"     # 判定步的名字，NEVER 指向一个 block 行
    rows: list[ClaimRow] = []
    for item in support_claims:
        text = str(item["claim"])
        doc_id = str(item["doc_id"])
        citation_id = cited_docs.get(doc_id)
        rows.append(ClaimRow(
            claim_id=compose_claim_id(product_id, block_id, text),
            deliverable_id=product_id,
            block_id=block_id,
            text_span=text,
            confidence="cited" if citation_id else "speculative",
            citation_ids=[citation_id] if citation_id else [],
            alignment=alignment_by.get((text, doc_id), PENDING_ALIGNMENT),
        ))
    return rows


async def _cited_docs(conn: asyncpg.Connection, doc_ids: list[str]) -> dict[str, str]:
    """哪些 doc **真的**有 citation 行。查不到就是没有，NEVER 猜一个 id。"""
    if not doc_ids:
        return {}
    rows = await conn.fetch(
        "SELECT doc_id, citation_id FROM citations WHERE doc_id = ANY($1::text[]) "
        "ORDER BY citation_id",
        doc_ids,
    )
    return {str(r["doc_id"]): str(r["citation_id"]) for r in rows}


async def _write_claim_rows(
    conn: asyncpg.Connection, rows: list[ClaimRow]
) -> None:
    """幂等落盘：同一 job 重跑 NEVER 产生重复行。

    **不靠 arq 按 job id 去重兜底**（那条第 3 批已登记）：落盘这一层
    自己要是幂等的，否则任何一次重放都会把结论翻倍。

    `promoted_fact_id` **不在更新列里**：重跑时抹掉它，账本里那条 Fact
    就找不回它的来源 claim，而「这条事实从哪来」是三条铁律要答的问题。
    """
    if not rows:
        return
    await conn.executemany(
        "INSERT INTO claims (claim_id, deliverable_id, block_id, text_span, "
        "confidence, citation_ids, alignment, promoted_fact_id) "
        "VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, NULL) "
        "ON CONFLICT (claim_id) DO UPDATE SET "
        "deliverable_id = EXCLUDED.deliverable_id, block_id = EXCLUDED.block_id, "
        "text_span = EXCLUDED.text_span, confidence = EXCLUDED.confidence, "
        "citation_ids = EXCLUDED.citation_ids, alignment = EXCLUDED.alignment",
        [(r.claim_id, r.deliverable_id, r.block_id, r.text_span, r.confidence,
          json.dumps(r.citation_ids), r.alignment) for r in rows],
    )


# ── 离线确定性依赖（回放态，S2-7 零联网零 LLM）─────────────


class _DeterministicJudgeProvider:
    """五族 prompt 分派，纯函数于 prompt 内容（回放确定性）。"""

    def generate(self, prompt: str, tools: list[JSON] | None) -> Completion:
        raise RuntimeError("offline replay: free-form generation disabled")

    def generate_structured(self, prompt: str, schema: JSON, max_retries: int) -> JSON:
        if "broader（上位）" in prompt:
            term = prompt.rsplit("术语：", 1)[1].strip()
            return {"synonyms": [f"{term} alternative"], "broader": [], "narrower": []}
        if "转成英文学术检索术语" in prompt:
            term = prompt.rsplit("关键词：", 1)[1].strip()
            digest = hashlib.sha256(term.encode()).hexdigest()[:8]
            return {"english": f"topic-{digest}"}
        if "判定检索相关性" in prompt:
            abstract = prompt.split("文摘（doc_id=", 1)[1]
            return {"relevant": "offtopic" not in abstract}
        if "判定引用对齐" in prompt:
            evidence = prompt.split("证据（doc_id=", 1)[1]
            supports = "weakclaim" not in evidence
            return {"alignment": "supports" if supports else "unsupported"}
        if "抽取竞品记录" in prompt:
            competitors = []
            for line in prompt.splitlines():
                if not line.startswith("- doc_id="):
                    continue
                parts = line[2:].split(" | ")
                doc_id = parts[0].removeprefix("doc_id=")
                title, url = parts[1], parts[2]
                if title.startswith("Vendor"):
                    competitors.append(
                        {"name": title, "url": url, "source_doc_ids": [doc_id]}
                    )
            return {"competitors": competitors}
        raise RuntimeError(f"offline replay: unrecognized prompt family: {prompt[:40]}")


_VENDORS: Final[list[tuple[str, str]]] = [
    ("alpha", "Vendor Alpha"),
    ("beta", "Vendor Beta"),
    ("gamma", "Vendor Gamma"),
]


def _offline_searcher(fetched_at: str) -> Searcher:
    def search(query: Query) -> list[Doc]:
        if query.intent == "landscape":
            return [
                Doc(
                    doc_id=f"doc-vendor-{slug}", source_id="webscan", kind="product",
                    title=name, url=f"https://{slug}.example/product",
                    published_at=date(2026, 6, 1),
                    meta={"fetched_at": fetched_at, "last_activity": "2026-07-01"},
                    origin="retrieved", access="public",
                )
                for slug, name in _VENDORS
            ]
        digest = hashlib.sha256(f"{query.intent}|{query.text}".encode()).hexdigest()[:10]
        # 标题不内嵌 query 文本：refute 模板族自带证伪标记词（failed
        # replication 一类），内嵌会让普通检索结果被误判为证伪证据形态
        # （M3-025 构造器口径）——离线 B 场景须保持无证伪证据
        return [
            Doc(
                doc_id=f"doc-{digest}-{i}", source_id="crossref", kind="paper",
                title=f"{query.intent} finding {i} on topic {digest}",
                url=f"https://papers.example/{digest}/{i}",
                published_at=date(2026, 5, 1), meta={"fetched_at": fetched_at},
                origin="retrieved", access="public",
            )
            for i in range(2)
        ]

    return search


@dataclass
class Gate1Deps:
    dsn: str
    provider: LLMProvider
    searcher: Searcher
    term_map: TermMap
    now: datetime
    theta: float = THETA_REL
    k_cap: int = 8


@dataclass
class Gate1Report:
    job_id: str
    steps_run: list[str] = field(default_factory=list)


def build_offline_deps(dsn: str, repo_root: Path) -> Gate1Deps:
    fixed_now = datetime(2026, 7, 26, 12, 0, 0, tzinfo=UTC)
    return Gate1Deps(
        dsn=dsn,
        provider=_DeterministicJudgeProvider(),
        searcher=_offline_searcher(fetched_at=fixed_now.isoformat()),
        term_map=load_term_map(repo_root / "assets" / "term-map.yaml"),
        now=fixed_now,
    )


def build_live_deps(
    dsn: str,
    repo_root: Path,
    provider: LLMProvider,
    searcher: Searcher,
    now: datetime,
) -> Gate1Deps:
    """真实源 Gate① deps（Feature B 生产切换）：注入真实 provider（如免费本地 qwen）+ 真实
    searcher（GithubArxivSearcher，门 2=R1）替换 `.example` 占位。run_gate1 内核不变、Gate1Deps
    字段照冻结不改。CI 仍走 build_offline_deps / 录制回放（S2-7 零联网）；生产按此构造走真实源。
    现状（owner @2026-07-31 切换完成）：main 默认即走此（live），`--offline` 回退合成占位。
    """
    return Gate1Deps(
        dsn=dsn, provider=provider, searcher=searcher,
        term_map=load_term_map(repo_root / "assets" / "term-map.yaml"), now=now,
    )


# ── SQL helpers（先例 M1-035）──────────────────────────────


async def _ensure_job(conn: asyncpg.Connection, job_id: str, now: datetime) -> str:
    await conn.execute(
        "INSERT INTO jobs (job_id, kind, owner_scope, state, progress, budget, "
        "cost_accum, cancel_requested, initiated_by, created_at, updated_at) "
        "VALUES ($1, 'gate1_analysis', '{\"kind\":\"user\",\"id\":\"u-owner\"}', "
        "'queued', 0, 0, 0, false, 'u-owner', $2, $2) "
        "ON CONFLICT (job_id) DO NOTHING",
        job_id, now,
    )
    state: str = await conn.fetchval("SELECT state FROM jobs WHERE job_id = $1", job_id)
    return state


#: `DESIGN-STATE`：**推进状态只有一处真相**（`flint/jobs/state.py`）。
#: 改前这个函数在 compose / gate1 / spec_export 三处各有一份、逐字相同，
#: 而 `design_generate` 一份都没有——于是它只写事件流，`jobs.state` 停在 queued。
#: 这里保留同名别名，既有调用点一个都不用改。
_enter_state = enter_state


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
    checkpoint: AnalysisCheckpoint,
    now: datetime,
) -> None:
    await conn.execute(
        "INSERT INTO job_steps (job_id, step_index, name, state, started_at, "
        "ended_at, cost, snapshot_ref) VALUES ($1, $2, $3, 'done', $4, $4, 0, $5)",
        job_id, index, name, now, serialize_checkpoint(checkpoint),
    )


async def _put_snapshot(
    conn: asyncpg.Connection, snapshot_id: str, payload: bytes, now: datetime
) -> None:
    await conn.execute(
        "INSERT INTO snapshots (snapshot_id, payload, created_at) VALUES ($1, $2, $3)",
        snapshot_id, payload, now,
    )


async def _get_snapshot(conn: asyncpg.Connection, snapshot_id: str) -> bytes:
    payload: bytes = await conn.fetchval(
        "SELECT payload FROM snapshots WHERE snapshot_id = $1", snapshot_id
    )
    return payload


# ── 相位纯计算 ─────────────────────────────────────────────


def _plan_queries(deps: Gate1Deps, keywords: list[str], locale: str) -> list[Query]:
    """三 intent 全量计划；plan 为纯函数，续跑重算得到同一清单。"""
    builder = FourStepQueryBuilder(
        term_map=deps.term_map, provider=deps.provider, cache=LLMJudgmentCache()
    )
    queries: list[Query] = []
    for intent in ("support", "refute", "landscape"):
        queries.extend(builder.build(keywords, intent, locale))
    return queries


def _fetch_docs_by_query(
    deps: Gate1Deps, plan: list[Query]
) -> dict[str, list[Doc]]:
    """**整跑只在这里取一次数**：每条 query 的文档，按 query_id 索引。

    ## 这个函数为什么存在（`GATE1-DEDUP`）

    改前 retrieve 与 judge **各把整个 plan 取了一遍**：
    `_collect_docs` 要的是「全部文档去重后的一份平铺清单」，
    `_judge_payload` 要的是「每条 query 各自的那一份」（refute 命中率、
    landscape 逐条抽竞品都按 query 分组）。

    **两处要的东西不一样，但都能从同一份 `docs_by_query` 里得到**——
    平铺清单是它的去重并集。所以这里取一次，两处共享同一批结果。

    NEVER 在 searcher 外面加一层缓存了事（`DEC-057` 那一跑的单据逐字）：
    缓存会把「取了两次」变成「看起来取了一次」，
    而**两处各自要什么**这件事仍然没人说得清。

    ## 去重的键是 **query 身份**，NEVER 是检索文本

    第一版这里按 `query.text` 共享——理由是「`github_search_url` /
    `arxiv_search_url` 只吃 text，两条同文本的 query 问上游的是同一个问题」。

    **那是错的，而且当场把判定改了。**

    `Searcher` 是一个**协议**，不是那一个实现。`build_offline_deps` 里的
    `_offline_searcher` 就按 `query.intent` 分支：`landscape` 回竞品清单，
    其余回论文。按文本共享之后，`support` 先跑并占住了那段文本，
    随后同文本的 `landscape` 拿到的是**论文而不是竞品**——
    竞品数归零，判定从 `B_red_ocean` 翻成 `C_opportunity`
    （`tests/m2/test_m2_040` / `test_m2_049` 当场抓住）。

    > 一个「只是少打几发网络」的改动**改变了判定结论**。
    > 少打几发是省钱，改判定是产品事故——两者绝不能混在一次改动里。

    所以这里的键是 `query_id_for(query)`：**对任何 Searcher 实现都安全**。
    同一条 query 在整跑里只问一次，而两条不同的 query 各问各的。

    「同文本的两条还是问了两次」那一半**留着**，见
    `docs/blocked/GATE1-SAME-TEXT-TWO-INTENTS.md`——
    它要在**知道 URL 怎么算出来的那一层**（searcher 自己）解决，
    而不是在这里猜。
    """
    out: dict[str, list[Doc]] = {}
    for query in plan:
        key = query_id_for(query)
        if key not in out:
            out[key] = deps.searcher(query)
    return out


def _flatten_docs(plan: list[Query], docs_by_query: dict[str, list[Doc]]) -> list[Doc]:
    """retrieve 要的那一份：**全部文档去重后的平铺清单**，保持首见顺序。

    去重按 `doc_id`——同一篇论文被两条 query 都搜到时只留一份，
    而**它在哪几条 query 下出现过**这件事留在 `docs_by_query` 里，没有丢。
    """
    seen: set[str] = set()
    docs: list[Doc] = []
    for query in plan:
        for doc in docs_by_query.get(query_id_for(query), ()):
            if doc.doc_id not in seen:
                seen.add(doc.doc_id)
                docs.append(doc)
    return docs


def _judge_payload(
    deps: Gate1Deps, keywords: list[str], plan: list[Query], docs: list[Doc],
    docs_by_query: dict[str, list[Doc]],
) -> JSON:
    """`docs_by_query` **由调用方传进来**（`GATE1-DEDUP`）。

    改前这里自己又取了一遍——与 retrieve 那一遍**内容完全相同**，
    只是多打了一整轮网络。现在整跑只在 `_fetch_docs_by_query` 取一次。
    """
    relevance = LLMRelevanceJudge(
        provider=deps.provider, cache=LLMJudgmentCache()
    )
    refute_queries = [q for q in plan if q.intent == "refute"]
    refute_docs = [
        d for q in refute_queries for d in docs_by_query[query_id_for(q)]
    ]
    refute_hit_rate = (
        relevance.hit_rate(refute_queries[0], refute_docs) if refute_queries else 0.0
    )

    # 竞品线：landscape query 逐条执行，边际新竞品计数（M2-033 素材）
    landscape_queries = [q for q in plan if q.intent == "landscape"]
    seen_names: set[str] = set()
    executions: list[JSON] = []
    records: list[CompetitorRecord] = []
    for query in landscape_queries:
        batch = extract_competitors(
            deps.provider, docs_by_query[query_id_for(query)]
        )
        fresh = [r for r in batch if r.name not in seen_names]
        seen_names.update(r.name for r in batch)
        records.extend(fresh)
        executions.append(
            {"query_text": query.text, "executed": True, "new": len(fresh)}
        )

    today = deps.now.date()
    competitors: list[JSON] = []
    for record in records:
        source_docs = [d for d in docs if d.doc_id in record.source_doc_ids]
        last_activity = None
        for doc in source_docs:
            raw = doc.meta.get("last_activity")
            if raw:
                last_activity = date.fromisoformat(str(raw))
        evaluation = derive_signals(
            SignalInputs(
                funding_docs=[], pricing_records=[], same_target_user=None,
                last_activity=last_activity, today=today,
            )
        )
        built = build_competitor(record, evaluation, pricing_records=[])
        competitors.append(
            {
                "name": built.name, "url": built.url, "strength": built.strength,
                "strength_signals": list(built.strength_signals),
            }
        )

    # 支持向关键证据对（每关键词一条 claim + 首条 support doc）
    support_claims: list[JSON] = []
    support_queries = [q for q in plan if q.intent == "support"]
    for keyword in keywords:
        claim = f"方向「{keyword}」存在市场支持证据"
        for query in support_queries:
            candidates = docs_by_query[query_id_for(query)]
            if candidates:
                support_claims.append(
                    {"claim": claim, "doc_id": candidates[0].doc_id}
                )
                break

    # 证伪 claim 对（M3-025：只有证伪证据形态的 refute doc 才成对）
    refute_claims: list[JSON] = [
        {"claim": claim, "doc_id": doc.doc_id}
        for claim, doc in build_refute_pairs(keywords, refute_docs)
    ]

    return {
        "refute_executed": bool(refute_queries),
        "refute_hit_rate": refute_hit_rate,
        "executions": executions,
        "total_competitors": len(records),
        "competitors": competitors,
        "support_claims": support_claims,
        "refute_claims": refute_claims,
    }


def _validate_verdict(
    deps: Gate1Deps, judge: JSON, docs: list[Doc],
    alignment_out: dict[tuple[str, str], Alignment] | None = None,
) -> JSON:
    """判定负载。`alignment_out` 是 **CHAIN-01 加的旁路出口**：

    每一对 (claim, doc) 的对齐结论要落进 claims 行，而它只在这里算得出来。
    做成可选出参而不是改返回类型，是因为另外三个调用点
    （`gate/replay.py` / `revalidate/run.py` / `tests/m3`）都在本卡 outputs 之外——
    **NEVER 为了一处方便去改三处签名**。

    也 NEVER 把它塞进返回的 payload：那份 payload 被 `/jobs/{id}/verdict`
    原样发给前端，多一个键就是多一处对外契约。
    """
    executions = [
        QueryExecution(
            query_text=str(e["query_text"]),
            executed=bool(e["executed"]),
            new_competitors=int(e["new"]),
        )
        for e in judge["executions"]
    ]
    coverage = assess_coverage(
        executions,
        total_competitors=int(judge["total_competitors"]),
        hit_rate=float(judge["refute_hit_rate"]),
        theta=deps.theta,
    )
    competitors = [
        Competitor(
            name=str(c["name"]), url=str(c["url"]),
            strength=cast(Strength, c["strength"]),
            strength_signals=list(c["strength_signals"]),
            pricing=None,
        )
        for c in judge["competitors"]
    ]
    docs_by_id = {d.doc_id: d for d in docs}
    support_pairs = [
        (str(item["claim"]), docs_by_id[str(item["doc_id"])])
        for item in judge["support_claims"]
    ]
    aligner = LLMCitationAligner(provider=deps.provider, cache=LLMJudgmentCache())
    # M3-025：证伪 claim 对进 rule A（M2 出口遗留 4 收口）——judge 相位由
    # build_refute_pairs 构造，无证伪证据形态 doc 时自然为空
    refute_pairs = [
        (str(item["claim"]), docs_by_id[str(item["doc_id"])])
        for item in judge.get("refute_claims", [])
    ]
    rule_a = evaluate_rule_a(
        aligner, refute_pairs,
        user_evidence_optin=bool(judge.get("user_evidence_optin", False)),
        k_cap=deps.k_cap,
    )
    rule_b = evaluate_rule_b(competitors)
    rule_c = evaluate_rule_c(
        aligner, support_pairs,
        refute_executed=bool(judge["refute_executed"]),
        refute_hit_rate=float(judge["refute_hit_rate"]),
        coverage=coverage, competitors=competitors,
        theta=deps.theta, k_cap=deps.k_cap,
    )
    if alignment_out is not None:
        # **同一个 aligner 实例**：它带 `LLMJudgmentCache`，键是
        # (stage, claim, doc_id)——rule C 刚判过的这几对全是缓存命中，
        # 这里零额外模型调用。超出 K 上限的那些不在 `checked` 里，
        # 于是它们在 claims 行里落成 `pending`（没查过），
        # 而不是 `unsupported`（查过了、不支持）。
        for claim_text, doc_id, alignment in align_key_evidence(
                aligner, support_pairs, deps.k_cap).checked:
            alignment_out[(claim_text, doc_id)] = alignment

    demoted = rule_a.demote_to_d or rule_c.demote_to_d
    lands_on_d = demoted or not (
        rule_a.satisfied or rule_b.satisfied or rule_c.satisfied
    )
    gaps = (
        derive_gaps(
            rule_c, coverage, competitors, missing_scopes=[],
            alignment_demoted=demoted,
        )
        if lands_on_d
        else []
    )
    # `decide` 吃的是冻结件那一份；`DerivedGap` 只是把机器那一半并排放着，
    # **判定语义一字不动**（FIX-12 的 acceptance④）。
    verdict = decide(
        rule_a, rule_b, rule_c, gaps=[d.hint for d in gaps],
        competitors=competitors)
    return {
        "verdict": verdict.verdict,
        "all_satisfied": list(verdict.all_satisfied),
        "key_citation_ids": list(verdict.key_citation_ids),
        "rationale_fact_ids": list(verdict.rationale_fact_ids),
        "competitors": [
            {
                "name": c.name, "url": c.url, "strength": c.strength,
                "strength_signals": list(c.strength_signals), "pricing": None,
            }
            for c in verdict.competitors
        ],
        "constraints_checked": verdict.constraints_checked,
        # FIX-12：人话与原因码**各占一格**。`GapHint` 是冻结件（加字段是 S2-1
        # 禁止的），所以结构化的那一半加在这里——这个 dict 不是冻结件。
        "gaps": [
            {
                "missing_what": d.hint.missing_what, "cause": d.hint.cause,
                "suggested_sources": list(d.hint.suggested_sources),
                "action": d.hint.action,
                "target_count": d.hint.target_count,
                "required_scope": d.hint.required_scope,
                "reason_code": d.reason_code,
                "params": dict(d.params),
            }
            for d in gaps
        ],
    }


def _canonical(payload: JSON) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")


# ── orchestrator ──────────────────────────────────────────


async def run_gate1(
    job_id: str,
    keywords: list[str],
    locale: str,
    deps: Gate1Deps,
    crash_after: str | None = None,
    topic_id: str | None = None,
) -> Gate1Report:
    """`topic_id` 可省（默认 `None`）：不给就不写 cluster 关系行。

    `PERSIST-04` 加的这个形参放在**最后**且带默认值——既有调用点一个都不用改，
    而这条链路上「不知道判的是哪个热点」本来就是一种真实状态
    （不带 topic_id 的旧提交路径）。**NEVER 让它必填**：
    必填会逼出一个占位值，而占位值会写出一行指向错误热点的关系。
    """
    report = Gate1Report(job_id=job_id)
    events = PgJobEventStream(dsn=deps.dsn)
    conn = await asyncpg.connect(deps.dsn)
    try:
        state = await _ensure_job(conn, job_id, deps.now)
        if state in ("done", "failed", "cancelled"):
            return report
        completed = await _completed_steps(conn, job_id)

        # 同步 provider/searcher（~秒级/更长）MUST 挪出事件循环，否则后台 job
        # 憋死整个 loop → 并发读端点（/plaza 等）全挂（DEMO-NONBLOCK 回归）。
        plan = await run_in_threadpool(_plan_queries, deps, keywords, locale)
        executed_ids = [query_id_for(q) for q in plan]
        docs_snapshot_id = f"snap-{job_id}-docs"
        docs: list[Doc] = []
        # `GATE1-DEDUP`：整跑只取一次数，retrieve 与 judge 共享这一份。
        docs_by_query: dict[str, list[Doc]] = {}
        draft_claim_ids: list[str] = []

        for index, name in enumerate(STEP_ORDER):
            await _enter_state(conn, events, job_id, _STEP_STATE[name], deps.now)
            if name in completed:
                continue
            await events.append(
                job_id, StepEvent(kind="step", step_name=name, phase="start", cost=None),
                ts=deps.now,
            )
            # 步数据与 job_steps 记录同事务提交（先例 M1-035）：kill -9
            # 不留半条，重放窗口为零
            async with conn.transaction():
                if name == "plan":
                    checkpoint_executed: list[str] = []
                elif name == "retrieve":
                    docs_by_query = await run_in_threadpool(
                        _fetch_docs_by_query, deps, plan)
                    docs = _flatten_docs(plan, docs_by_query)
                    violations = check_provenance(docs)
                    if violations:
                        raise RuntimeError(f"provenance violations: {violations}")
                    await _put_snapshot(
                        conn, docs_snapshot_id, serialize_docs(docs), deps.now
                    )
                    await conn.execute(
                        "UPDATE jobs SET partial_output_ref = $2, updated_at = $3 "
                        "WHERE job_id = $1",
                        job_id, docs_snapshot_id, deps.now,
                    )
                    checkpoint_executed = executed_ids
                elif name == "judge":
                    if not docs:
                        docs = restore_docs(await _get_snapshot(conn, docs_snapshot_id))
                    if not docs_by_query:
                        # **续跑路径**：retrieve 那一步在上一个进程里跑过，
                        # 而快照里存的是**平铺去重后的 docs**，没有「哪条 query 出了哪些」
                        # 这一层映射。所以这里重取一次。
                        #
                        # 这仍然比改前好：改前是**每跑一次都取两遍**，
                        # 现在只有「跑到一半断了再续」才会多取一遍。
                        # 把映射也存进快照是另一件事（要定它的格式与体积），
                        # 不在 `GATE1-DEDUP` 的范围里。
                        docs_by_query = await run_in_threadpool(
                            _fetch_docs_by_query, deps, plan)
                    judge = await run_in_threadpool(
                        _judge_payload, deps, keywords, plan, docs, docs_by_query)
                    draft_claim_ids = [
                        claim_id_for(str(item["claim"]))
                        for item in judge["support_claims"]
                    ]
                    await _put_snapshot(
                        conn, f"snap-{job_id}-judge", _canonical(judge), deps.now
                    )
                    checkpoint_executed = executed_ids
                else:  # validate
                    if not docs:
                        docs = restore_docs(await _get_snapshot(conn, docs_snapshot_id))
                    judge = json.loads(
                        (await _get_snapshot(conn, f"snap-{job_id}-judge")).decode()
                    )
                    draft_claim_ids = [
                        claim_id_for(str(item["claim"]))
                        for item in judge["support_claims"]
                    ]
                    alignment_by: dict[tuple[str, str], Alignment] = {}
                    verdict_payload = await run_in_threadpool(
                        _validate_verdict, deps, judge, docs, alignment_by)
                    # CHAIN-01：判定 → claims 那一跳。**在同一个事务里**——
                    # 分两次提交的话，kill -9 卡在中间会留下「步已记完、
                    # claim 没写」，续跑会跳过那步，那批结论就永远丢了。
                    support_claims = list(judge["support_claims"])
                    await _write_claim_rows(conn, claim_rows_from(
                        product_id=analysis_product_id(job_id),
                        support_claims=support_claims,
                        alignment_by=alignment_by,
                        cited_docs=await _cited_docs(
                            conn,
                            [str(item["doc_id"]) for item in support_claims]),
                    ))
                    verdict_snapshot_id = f"snap-{job_id}-verdict"
                    await _put_snapshot(
                        conn, verdict_snapshot_id, _canonical(verdict_payload), deps.now
                    )
                    await conn.execute(
                        "UPDATE jobs SET partial_output_ref = $2, updated_at = $3 "
                        "WHERE job_id = $1",
                        job_id, verdict_snapshot_id, deps.now,
                    )
                    # PERSIST-04：判定 → 热点那一跳。**在同一个事务里**——
                    # 与上面 CHAIN-01 的 claims 同一条理由：分两次提交的话，
                    # kill -9 卡在中间会留下「判定落了、关系没写」，
                    # 而续跑会跳过这一步，那次判定就永远查不回来了。
                    # 没有 topic_id / 非 combo / 卡查不回簇 → 空集 → 一行都不写。
                    if topic_id is not None:
                        await record_cluster_verdicts(
                            conn, job_id=job_id,
                            cluster_ids=await clusters_for_topic(conn, topic_id),
                            now=deps.now,
                        )
                    checkpoint_executed = executed_ids
                checkpoint = AnalysisCheckpoint(
                    kind="gate1_analysis",
                    executed_query_ids=checkpoint_executed,
                    phase=_NEXT_PHASE[name],
                    draft_claim_ids=draft_claim_ids,
                )
                await _record_step(conn, job_id, index, name, checkpoint, deps.now)
            completed.append(name)
            report.steps_run.append(name)
            await events.append(
                job_id, StepEvent(kind="step", step_name=name, phase="end", cost=0.0),
                ts=deps.now,
            )
            if crash_after == name:
                os._exit(137)  # kill -9 semantics: no cleanup beyond this point

        await _enter_state(conn, events, job_id, "done", deps.now)
    finally:
        await conn.close()
    return report


def _default_live_deps(dsn: str, repo_root: Path, model: str, ollama_url: str) -> Gate1Deps:
    """生产默认 deps（真实源）：免费本地 qwen + 真实 github/arxiv（门 2=R1）。

    在 main 内构造以避免顶层耦合 evidence.search / llm.local。CI/单测不经 main——直接用
    build_offline_deps（S2-7 零联网），故本切换不影响 CI。github unauth 搜索限流大量跑须配
    token（问题单登记），本处 resilient 单源降级兜底。
    """
    import httpx

    from flint.evidence.search import GithubArxivSearcher
    from flint.llm.local import LocalProvider

    now = datetime.now(UTC)
    provider = LocalProvider(
        base_url=ollama_url, model=model,
        http_client=httpx.Client(timeout=600.0), disable_reasoning=True, max_tokens=4096)
    searcher = GithubArxivSearcher(
        httpx.Client(timeout=30.0, follow_redirects=True), now,
        per_source=3, resilient=True)
    return build_live_deps(dsn, repo_root, provider, searcher, now)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="flint gate1_analysis driver")
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--keywords", required=True)
    parser.add_argument("--locale", default="zh-CN")
    parser.add_argument("--crash-after", default=None)
    # 生产默认真实源（owner @2026-07-31 切换完成）：免费本地 qwen + 真实 github/arxiv。
    # --offline 回退合成占位（不发网/LLM，本地冒烟用）。CI/单测直接用 build_offline_deps。
    parser.add_argument("--offline", action="store_true",
                        help="回退合成占位 deps（不切真实源）")
    parser.add_argument("--model", default="qwen3.6:35b-a3b")
    parser.add_argument("--ollama-url", default="http://localhost:11434/v1")
    args = parser.parse_args(argv)
    repo_root = Path(__file__).resolve().parents[2]
    deps = (
        build_offline_deps(dsn=args.dsn, repo_root=repo_root) if args.offline
        else _default_live_deps(args.dsn, repo_root, args.model, args.ollama_url)
    )
    async def _drive() -> None:
        await run_gate1(
            job_id=args.job_id, keywords=args.keywords.split(","),
            locale=args.locale, deps=deps, crash_after=args.crash_after)
        if not args.offline:  # 生产真实源：Step 1 钉 quote_span 到 verdict 被引论文
            from flint.evidence.enrich import pin_verdict_citations
            await pin_verdict_citations(args.dsn, args.job_id, deps.now)

    asyncio.run(_drive())


if __name__ == "__main__":
    main()
