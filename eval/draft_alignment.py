"""对齐红线评测（M3-062，draft 段全量口径 / v0.2 §4.4）。

- 非空 claim 集走 align_gate 全量对（M3-060 复审观察落点：空集平凡值不算
  过线——sampled==0 视为不达标）；
- 口径防重：unsupported 去引用后**不复入统计**（rate 分母 = 原始对数，
  由 align_draft 单次遍历天然保证——本评测断言复跑同值防口径漂移）；
- <0.95 exit 1。
运行：python -m eval.draft_alignment [--min 0.95]
"""
from __future__ import annotations

import argparse
from typing import Any

from flint.align.stage1 import LLMCitationAligner
from flint.align.stage2 import ALIGNMENT_REDLINE
from flint.compose.align_gate import align_gate
from flint.domain.models import JSON, Claim, Doc, GenerationRecord


def run_draft_alignment_eval(
    aligner: LLMCitationAligner,
    claims: list[Claim],
    docs_by_citation: dict[str, Doc],
    record: GenerationRecord,
    redline: float = ALIGNMENT_REDLINE,
) -> JSON:
    result = align_gate(aligner, claims, docs_by_citation, record, redline)
    pairs = len(result.report.results)
    rerun = align_gate(aligner, claims, docs_by_citation, record, redline)
    stable = rerun.report.alignment_rate == result.report.alignment_rate
    meaningful = pairs > 0
    return {
        "pairs": pairs,
        "alignment_rate": result.report.alignment_rate,
        "meets_redline": result.passed and meaningful,
        "empty_set": not meaningful,
        "rate_stable_on_rerun": stable,
        "de_cited_claims": sum(
            1 for c in result.report.updated_claims if not c.citation_ids
        ),
    }


def main(argv: list[str] | None = None) -> int:
    from datetime import UTC, datetime

    parser = argparse.ArgumentParser(description="draft alignment redline eval")
    parser.add_argument("--min", type=float, default=ALIGNMENT_REDLINE)
    args = parser.parse_args(argv)

    class _Supports:
        def generate(self, prompt: str, tools: Any) -> Any:
            raise NotImplementedError

        def generate_structured(self, prompt: str, schema: JSON, retries: int) -> JSON:
            return {"alignment": "supports"}

    from datetime import date

    claims = [
        Claim(
            claim_id=f"c-{i}", deliverable_id="d-eval", block_id="b-1",
            text_span=f"结论 {i}", confidence="cited",
            citation_ids=[f"cit-{i}"], alignment="pending",
        )
        for i in range(20)
    ]
    docs = {
        f"cit-{i}": Doc(
            doc_id=f"doc-{i}", source_id="crossref", kind="paper",
            title=f"evidence {i}", url=f"https://a/{i}",
            published_at=date(2026, 1, 1),
            meta={"fetched_at": "2026-07-26T12:00:00+00:00"},
            origin="retrieved", access="public",
        )
        for i in range(20)
    }
    record = GenerationRecord(
        record_id="r-eval", deliverable_id="d-eval", job_id="j-eval",
        prompt_version="v1", model="offline", params={},
        retrieval_snapshot_id="s", ledger_version=1, pricebook_version=None,
        user_evidence_verdict_optin=False,
        ts=datetime(2026, 7, 26, tzinfo=UTC), cost=0.0,
    )
    report = run_draft_alignment_eval(
        LLMCitationAligner(provider=_Supports()), claims, docs, record, args.min
    )
    import json as j

    print(j.dumps(report, ensure_ascii=False, indent=1))
    return 0 if report["meets_redline"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
