"""draft 段全量对齐接线（M3-024，红线 0.95 / v0.2 §4.4）。

- align_draft（M2-029）全量跑 (claim, citation) 对；本层把 alignment_rate
  写入 GenerationRecord 副本（原件留档）并给出红线判定。
- require_redline：<0.95 抛 AlignmentRedlineFailure（拒绝出稿）——组稿
  编排（M3-060）在渲染前调用；失败时 record 已带真实 rate（审计不缺账）。
"""
from __future__ import annotations

from dataclasses import dataclass, replace

from flint.align.stage1 import LLMCitationAligner
from flint.align.stage2 import ALIGNMENT_REDLINE, DraftAlignmentReport, align_draft
from flint.domain.models import Claim, Doc, GenerationRecord


class AlignmentRedlineFailure(Exception):
    def __init__(self, rate: float, redline: float) -> None:
        super().__init__(
            f"draft alignment rate {rate} below redline {redline}: refusing to ship"
        )
        self.rate = rate
        self.redline = redline


@dataclass
class AlignGateResult:
    report: DraftAlignmentReport
    record: GenerationRecord
    passed: bool
    redline: float


def align_gate(
    aligner: LLMCitationAligner,
    claims: list[Claim],
    docs_by_citation: dict[str, Doc],
    record: GenerationRecord,
    redline: float = ALIGNMENT_REDLINE,
) -> AlignGateResult:
    report = align_draft(aligner, claims, docs_by_citation, redline)
    return AlignGateResult(
        report=report,
        record=replace(record, alignment_rate=report.alignment_rate),
        passed=report.meets_redline,
        redline=redline,
    )


def require_redline(result: AlignGateResult) -> None:
    if not result.passed:
        raise AlignmentRedlineFailure(result.report.alignment_rate, result.redline)
