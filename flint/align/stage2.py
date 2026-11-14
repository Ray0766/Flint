"""引用对齐 · 第二段（终稿前全量，M2-029；PDD v0.2 §4.4 / v0.3.1 §2.1）。

- 全量 (claim, citation) 对逐一判 supports / partial / unsupported——零抽样。
- 处置：unsupported → 去引用；引用清空 → confidence 降 speculative；
  partial → 保留引用但 claim.alignment=partial（S2-4：partial 永不可提升 Fact）。
- alignment_rate = supports 对数 / 总对数，记入 GenerationRecord 通道；
  红线 >=0.95（draft 段，v0.2 §4.4 初值）。
- 输入 claims 不被就地修改：产出 updated_claims 副本（原件供 diff/审计）。
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Final

from flint.align.stage1 import LLMCitationAligner
from flint.domain.models import Alignment, Claim, Doc

ALIGNMENT_REDLINE: Final[float] = 0.95

_SEVERITY: Final[dict[Alignment, int]] = {
    "supports": 0,
    "pending": 0,
    "partial": 1,
    "unsupported": 2,
}


@dataclass(frozen=True)
class PairResult:
    claim_id: str
    citation_id: str
    alignment: Alignment


@dataclass
class DraftAlignmentReport:
    results: list[PairResult] = field(default_factory=list)
    updated_claims: list[Claim] = field(default_factory=list)
    alignment_rate: float = 1.0
    meets_redline: bool = True


def align_draft(
    aligner: LLMCitationAligner,
    claims: list[Claim],
    docs_by_citation: dict[str, Doc],
    redline: float = ALIGNMENT_REDLINE,
) -> DraftAlignmentReport:
    report = DraftAlignmentReport()
    supports = 0
    total = 0
    for claim in claims:
        kept_citations: list[str] = []
        worst: Alignment = "supports"
        for citation_id in claim.citation_ids:
            doc = docs_by_citation[citation_id]
            alignment = aligner.align(claim.text_span, doc, stage="draft")
            report.results.append(
                PairResult(claim_id=claim.claim_id, citation_id=citation_id,
                           alignment=alignment)
            )
            total += 1
            if alignment == "supports":
                supports += 1
            if alignment != "unsupported":
                kept_citations.append(citation_id)  # unsupported 去引用
            if _SEVERITY[alignment] > _SEVERITY[worst]:
                worst = alignment
        confidence = claim.confidence
        if not kept_citations:
            confidence = "speculative"  # 引用清空 → 降 speculative（§4.4）
        report.updated_claims.append(
            replace(
                claim,
                citation_ids=kept_citations,
                confidence=confidence,
                alignment=worst,
            )
        )
    report.alignment_rate = (supports / total) if total else 1.0
    report.meets_redline = report.alignment_rate >= redline
    return report
