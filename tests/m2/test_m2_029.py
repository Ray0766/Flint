"""M2-029 acceptance tests: citation alignment stage 2 (pre-final draft).

Acceptance (tasks.json M2-029):
  - EVERY (claim, citation) pair judged supports/partial/unsupported
  - unsupported -> strip citation, mark speculative; alignment_rate recorded
    against the 0.95 redline
"""
from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from flint.align.stage1 import LLMCitationAligner
from flint.align.stage2 import ALIGNMENT_REDLINE, align_draft
from flint.domain.models import JSON, Claim, Doc

FETCHED = datetime(2026, 7, 28, 12, 0, 0, tzinfo=UTC).isoformat()


def make_doc(citation_id: str) -> Doc:
    return Doc(
        doc_id=f"doc-{citation_id}", source_id="crossref", kind="paper",
        title=f"evidence {citation_id}", url=f"https://example.com/{citation_id}",
        published_at=date(2026, 1, 1), meta={"fetched_at": FETCHED},
        origin="retrieved", access="public",
    )


def make_claim(claim_id: str, citation_ids: list[str]) -> Claim:
    return Claim(
        claim_id=claim_id, deliverable_id="d-1", block_id=f"b-{claim_id}",
        text_span=f"断言 {claim_id}", confidence="cited",
        citation_ids=list(citation_ids), alignment="pending",
    )


class ScriptedProvider:
    def __init__(self, verdicts: dict[str, str]) -> None:
        self.verdicts = verdicts
        self.calls: list[str] = []

    def generate(self, prompt: str, tools: list[JSON] | None) -> object:
        raise NotImplementedError

    def generate_structured(self, prompt: str, schema: JSON, max_retries: int) -> JSON:
        self.calls.append(prompt)
        for doc_id, verdict in self.verdicts.items():
            if f"doc_id={doc_id}）" in prompt:  # 定界匹配，防 doc-x1 命中 doc-x10
                return {"alignment": verdict}
        return {"alignment": "supports"}


def run_alignment(
    claims: list[Claim], verdicts: dict[str, str]
) -> tuple[object, ScriptedProvider]:
    provider = ScriptedProvider(verdicts)
    aligner = LLMCitationAligner(provider=provider)
    docs = {
        cid: make_doc(cid)
        for claim in claims
        for cid in claim.citation_ids
    }
    return align_draft(aligner, claims, docs), provider


def test_every_pair_is_judged() -> None:
    claims = [make_claim("c1", ["x1", "x2"]), make_claim("c2", ["x3"])]
    report, provider = run_alignment(claims, {})
    assert len(provider.calls) == 3, "full coverage: one call per (claim, citation) pair"
    assert len(report.results) == 3  # type: ignore[attr-defined]


def test_unsupported_strips_citation_and_marks_speculative() -> None:
    claims = [make_claim("c1", ["x1", "x2"])]
    report, _ = run_alignment(claims, {"doc-x2": "unsupported"})
    updated = report.updated_claims[0]  # type: ignore[attr-defined]
    assert updated.citation_ids == ["x1"], "unsupported citation stripped"
    assert updated.confidence == "cited", "one supporting citation remains"

    lonely = [make_claim("c2", ["x9"])]
    report2, _ = run_alignment(lonely, {"doc-x9": "unsupported"})
    updated2 = report2.updated_claims[0]  # type: ignore[attr-defined]
    assert updated2.citation_ids == []
    assert updated2.confidence == "speculative", "no citations left -> speculative"
    assert updated2.alignment == "unsupported"


def test_partial_keeps_citation_but_blocks_promotion() -> None:
    claims = [make_claim("c1", ["x1", "x2"])]
    report, _ = run_alignment(claims, {"doc-x2": "partial"})
    updated = report.updated_claims[0]  # type: ignore[attr-defined]
    assert updated.citation_ids == ["x1", "x2"], "partial keeps the citation"
    assert updated.alignment == "partial", "S2-4: partial can never be promoted to Fact"


def test_alignment_rate_and_redline() -> None:
    assert ALIGNMENT_REDLINE == 0.95
    claims = [make_claim(f"c{i}", [f"x{i}"]) for i in range(20)]
    all_good, _ = run_alignment(claims, {})
    assert all_good.alignment_rate == pytest.approx(1.0)  # type: ignore[attr-defined]
    assert all_good.meets_redline is True  # type: ignore[attr-defined]

    one_bad, _ = run_alignment(claims, {"doc-x0": "unsupported"})
    assert one_bad.alignment_rate == pytest.approx(0.95)  # type: ignore[attr-defined]
    assert one_bad.meets_redline is True, "19/20 = 0.95 sits exactly on the line"

    two_bad, _ = run_alignment(claims, {"doc-x0": "unsupported", "doc-x1": "partial"})
    assert two_bad.alignment_rate == pytest.approx(0.90)  # type: ignore[attr-defined]
    assert two_bad.meets_redline is False


def test_original_claims_not_mutated() -> None:
    claims = [make_claim("c1", ["x1"])]
    report, _ = run_alignment(claims, {"doc-x1": "unsupported"})
    assert claims[0].citation_ids == ["x1"], "input claims stay untouched"
    assert claims[0].confidence == "cited"
    assert report.updated_claims[0] is not claims[0]  # type: ignore[attr-defined]


def test_stage_is_draft_in_prompts() -> None:
    claims = [make_claim("c1", ["x1"])]
    provider = ScriptedProvider({})
    aligner = LLMCitationAligner(provider=provider)
    align_draft(aligner, claims, {"x1": make_doc("x1")})
    assert provider.calls, "aligner invoked"
