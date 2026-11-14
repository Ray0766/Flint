"""M3-024 acceptance tests: stage-2 full alignment wiring (redline 0.95).

Acceptance (tasks.json M3-024):
  - draft-stage full (claim, citation) alignment; unsupported loses the
    citation and drops to speculative
  - alignment_rate lands in GenerationRecord and <0.95 refuses to ship
"""
from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from flint.align.stage1 import LLMCitationAligner
from flint.compose.align_gate import (
    AlignmentRedlineFailure,
    align_gate,
    require_redline,
)
from flint.domain.models import JSON, Claim, Doc, GenerationRecord

NOW = datetime(2026, 7, 29, tzinfo=UTC)
FETCHED = NOW.isoformat()


def doc(doc_id: str, title: str) -> Doc:
    return Doc(
        doc_id=doc_id, source_id="crossref", kind="paper", title=title,
        url=f"https://a/{doc_id}", published_at=date(2026, 1, 1),
        meta={"fetched_at": FETCHED}, origin="retrieved", access="public",
    )


def claim(cid: str, citations: list[str]) -> Claim:
    return Claim(
        claim_id=cid, deliverable_id="d-1", block_id="b-1",
        text_span=f"结论 {cid}", confidence="cited",
        citation_ids=citations, alignment="pending",
    )


def record() -> GenerationRecord:
    return GenerationRecord(
        record_id="r-1", deliverable_id="d-1", job_id="j-1", prompt_version="v1",
        model="m", params={}, retrieval_snapshot_id="s-1", ledger_version=1,
        pricebook_version=None, user_evidence_verdict_optin=False,
        ts=NOW, cost=0.0,
    )


class MarkerProvider:
    def __init__(self, unsupported_markers: list[str]) -> None:
        self.markers = unsupported_markers

    def generate(self, prompt: str, tools: list[JSON] | None) -> object:
        raise NotImplementedError

    def generate_structured(self, prompt: str, schema: JSON, max_retries: int) -> JSON:
        segment = prompt.split("证据（doc_id=", 1)[1]
        if any(m in segment for m in self.markers):
            return {"alignment": "unsupported"}
        return {"alignment": "supports"}


def aligner(markers: list[str] | None = None) -> LLMCitationAligner:
    return LLMCitationAligner(provider=MarkerProvider(markers or []))  # type: ignore[arg-type]


def test_rate_lands_in_record_copy() -> None:
    original = record()
    result = align_gate(
        aligner(), [claim("c-1", ["cit-1"])],
        {"cit-1": doc("doc-1", "good evidence")}, original,
    )
    assert result.passed is True
    assert result.record.alignment_rate == 1.0
    assert original.alignment_rate is None, "original record untouched"


def test_unsupported_loses_citation_drops_speculative() -> None:
    result = align_gate(
        aligner(["offtopic"]),
        [claim("c-1", ["cit-1"])],
        {"cit-1": doc("doc-1", "offtopic essay")}, record(),
    )
    assert result.passed is False
    assert result.record.alignment_rate == 0.0
    updated = result.report.updated_claims[0]
    assert updated.citation_ids == [], "unsupported citation removed"
    assert updated.confidence == "speculative"


def test_below_redline_refuses_to_ship() -> None:
    claims = [claim(f"c-{i}", [f"cit-{i}"]) for i in range(10)]
    docs = {f"cit-{i}": doc(f"doc-{i}", "good") for i in range(9)}
    docs["cit-9"] = doc("doc-9", "offtopic essay")
    result = align_gate(aligner(["offtopic"]), claims, docs, record())
    assert result.record.alignment_rate == 0.9
    assert result.passed is False
    with pytest.raises(AlignmentRedlineFailure, match="0.9"):
        require_redline(result)


def test_at_redline_ships() -> None:
    claims = [claim(f"c-{i}", [f"cit-{i}"]) for i in range(20)]
    docs = {f"cit-{i}": doc(f"doc-{i}", "good") for i in range(19)}
    docs["cit-19"] = doc("doc-19", "offtopic essay")
    result = align_gate(aligner(["offtopic"]), claims, docs, record())
    assert result.record.alignment_rate == 0.95
    assert result.passed is True
    require_redline(result)  # no raise at the line
