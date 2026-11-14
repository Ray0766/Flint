"""inject_evidence：全管道不豁免（M3-043，冻结协议 InterventionService.inject_evidence）。

- UserEvidence → Doc（origin="user_provided"、access="private"、
  source_id="user_upload"；verifiable/firsthand 缺省 0.5 走 meta——
  M2-044 校准清单口径）→ 双尺评分（user_provided 尺）→ stage="verdict"
  对齐——任一步不豁免。
- 白名单入账：仅 alignment=="supports" 才经 derive(reason="inject_evidence")
  加 fact（origin="injected"）；partial/unsupported 不入账、版本不动
  （S2-4）。
- optin 直传结果（GenerationRecord.user_evidence_verdict_optin 进账位，
  默认 False——自供证据 NEVER 默认单独支撑判 A）。
- 版本冲突（LedgerVersionConflict）原样上抛：自动重放 ≤3 归 M3-044。
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

from starlette.concurrency import run_in_threadpool

from flint.align.stage1 import LLMCitationAligner
from flint.domain.models import (
    Alignment,
    Doc,
    EvidenceScore,
    FactsLedger,
    UserEvidence,
)
from flint.ledger.read import get_ledger
from flint.ledger.store import PgLedgerStore
from flint.scoring.scorer import DualScaleScorer


@dataclass
class InjectionResult:
    doc: Doc
    score: EvidenceScore
    alignment: Alignment
    ledger: FactsLedger
    fact_added: bool
    optin_recorded: bool


def _evidence_doc(ev: UserEvidence) -> Doc:
    digest = hashlib.sha256(
        f"{ev.evidence_id}|{ev.content_ref}".encode()
    ).hexdigest()[:12]
    return Doc(
        doc_id=f"doc-user-{digest}",
        source_id="user_upload",
        kind="user_upload",
        title=ev.content_ref if ev.kind == "text" else f"用户材料 {ev.evidence_id}",
        url=f"user://{ev.evidence_id}",
        published_at=ev.created_at.date(),
        meta={
            "fetched_at": ev.created_at.isoformat(),
            "note": ev.note,
            "verifiable": 0.5,
            "firsthand": 0.5,
        },
        origin="user_provided",
        access="private",
    )


async def inject_evidence(
    store: PgLedgerStore,
    project_id: str,
    ev: UserEvidence,
    scorer: DualScaleScorer,
    aligner: LLMCitationAligner,
    claim_text: str,
    expected_version: int,
    user_evidence_optin: bool = False,
) -> InjectionResult:
    doc = _evidence_doc(ev)
    score = scorer.strength(doc)                       # 双尺不豁免（纯计算，无 IO）
    # 对齐不豁免。**MUST 挪出事件循环**：CitationAligner 的 align 是**同步**的
    # （冻结 LLMProvider 协议本就同步，LocalProvider 底层同步 httpx，一次判定可达数十秒）。
    # 它此前直接跑在本 async 函数里 → 憋死整个事件循环，所有并发请求挂住
    # ——与 DEMO-NONBLOCK 修过的是同一个 bug 类。回归测试：
    # tests/harness/test_inject_nonblocking.py（证明事件循环单次最长停顿 < 阈值）。
    alignment = await run_in_threadpool(aligner.align, claim_text, doc, "verdict")

    if alignment == "supports":
        ledger = await store.derive(
            project_id,
            expected_parent_version=expected_version,
            reason="inject_evidence",
            changes={
                "add": [
                    {
                        "fact_id": f"fact-user-{doc.doc_id[9:]}",
                        "statement": claim_text,
                        "value": None,
                        "unit": None,
                        "citation_ids": [doc.doc_id],
                        "status": "frozen",
                        "origin": "injected",
                        "created_in_version": 0,
                        "source_claim_id": None,
                        "promoted_from": None,
                    }
                ],
                "actor": ev.owner.id,
            },
        )
        fact_added = True
    else:
        ledger = await get_ledger(store.dsn, project_id, expected_version)
        fact_added = False

    return InjectionResult(
        doc=doc,
        score=score,
        alignment=alignment,
        ledger=ledger,
        fact_added=fact_added,
        optin_recorded=user_evidence_optin,
    )
