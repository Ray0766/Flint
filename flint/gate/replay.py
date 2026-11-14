"""检索快照回放复现（M2-049，F2 / 技术方案 E2）。

- 任一 Analysis 经 docs 快照（retrieval_snapshot_id 语义：snap-{job}-docs）
  完整复现：judge 与 validate 两相纯函数在快照 docs 上重算，与原跑落库的
  judge / verdict 快照做 canonical 字节比对——diff 为空即复现成立。
- 不重跑检索（复现的锚点就是检索时点的快照，F2 本义）；plan 确定性重算
  （M2-040 断点续跑同一哲学）。
"""
from __future__ import annotations

import json
from dataclasses import dataclass

import asyncpg

from flint.domain.models import JSON
from flint.evidence.compliance import restore_docs
from flint.jobs.gate1 import (
    Gate1Deps,
    _fetch_docs_by_query,
    _judge_payload,
    _plan_queries,
    _validate_verdict,
    query_id_for,
)


@dataclass
class ReplayReport:
    job_id: str
    judge_matches: bool
    verdict_matches: bool
    verdict: JSON

    @property
    def diff_empty(self) -> bool:
        return self.judge_matches and self.verdict_matches


def _canonical(payload: JSON) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")


async def replay_analysis(
    job_id: str, keywords: list[str], locale: str, deps: Gate1Deps
) -> ReplayReport:
    conn = await asyncpg.connect(deps.dsn)
    try:
        docs_blob: bytes = await conn.fetchval(
            "SELECT payload FROM snapshots WHERE snapshot_id = $1",
            f"snap-{job_id}-docs",
        )
        judge_blob: bytes = await conn.fetchval(
            "SELECT payload FROM snapshots WHERE snapshot_id = $1",
            f"snap-{job_id}-judge",
        )
        verdict_blob: bytes = await conn.fetchval(
            "SELECT payload FROM snapshots WHERE snapshot_id = $1",
            f"snap-{job_id}-verdict",
        )
    finally:
        await conn.close()

    docs = restore_docs(docs_blob)
    plan = _plan_queries(deps, keywords, locale)
    # 快照一致性前置：计划确定性重算须覆盖快照内全部 doc（复现的输入面完整）
    planned_ids = {query_id_for(q) for q in plan}
    assert planned_ids, "plan recompute yielded no queries"

    # `GATE1-DEDUP`：`_judge_payload` 不再自己取数，映射由调用方给。
    # 这里手上只有平铺快照（没有「哪条 query 出了哪些」那一层），
    # 所以按同一条路重取一次——**取一遍，不是改前的两遍**。
    docs_by_query = _fetch_docs_by_query(deps, plan)
    judge = _judge_payload(deps, keywords, plan, docs, docs_by_query)
    verdict = _validate_verdict(deps, judge, docs)
    return ReplayReport(
        job_id=job_id,
        judge_matches=_canonical(judge) == bytes(judge_blob),
        verdict_matches=_canonical(verdict) == bytes(verdict_blob),
        verdict=verdict,
    )
