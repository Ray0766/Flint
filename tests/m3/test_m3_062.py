"""M3-062 acceptance tests: draft alignment redline eval.

Acceptance (tasks.json M3-062):
  - full-pair alignment_rate report; <0.95 exits 1
  - de-cited claims never re-enter the statistic (denominator = original
    pairs; rerun-stable)
"""
from __future__ import annotations

from datetime import UTC, date, datetime

from eval.draft_alignment import main, run_draft_alignment_eval
from flint.align.stage1 import LLMCitationAligner
from flint.domain.models import JSON, Claim, Doc, GenerationRecord

NOW = datetime(2026, 7, 26, tzinfo=UTC)


class MarkerProvider:
    def __init__(self, bad: set[str]) -> None:
        self.bad = bad

    def generate(self, prompt: str, tools: object) -> object:
        raise NotImplementedError

    def generate_structured(self, prompt: str, schema: JSON, max_retries: int) -> JSON:
        segment = prompt.split("证据（doc_id=", 1)[1]
        doc_id = segment.split("）", 1)[0]
        return {"alignment": "unsupported" if doc_id in self.bad else "supports"}


def claim(i: int) -> Claim:
    return Claim(
        claim_id=f"c-{i}", deliverable_id="d-1", block_id="b-1",
        text_span=f"结论 {i}", confidence="cited",
        citation_ids=[f"cit-{i}"], alignment="pending",
    )


def doc(i: int) -> Doc:
    return Doc(
        doc_id=f"doc-{i}", source_id="crossref", kind="paper",
        title=f"e-{i}", url=f"https://a/{i}", published_at=date(2026, 1, 1),
        meta={"fetched_at": NOW.isoformat()}, origin="retrieved", access="public",
    )


def record() -> GenerationRecord:
    return GenerationRecord(
        record_id="r-1", deliverable_id="d-1", job_id="j-1", prompt_version="v",
        model="m", params={}, retrieval_snapshot_id="s", ledger_version=1,
        pricebook_version=None, user_evidence_verdict_optin=False,
        ts=NOW, cost=0.0,
    )


def _setup(count: int, bad: set[str]) -> tuple:
    claims = [claim(i) for i in range(count)]
    docs = {f"cit-{i}": doc(i) for i in range(count)}
    aligner = LLMCitationAligner(provider=MarkerProvider(bad))  # type: ignore[arg-type]
    return aligner, claims, docs


def test_non_empty_pairs_redline_both_sides() -> None:
    aligner, claims, docs = _setup(20, {"doc-19"})
    report = run_draft_alignment_eval(aligner, claims, docs, record())
    assert report["pairs"] == 20
    assert report["alignment_rate"] == 0.95
    assert report["meets_redline"] is True, "exactly at the line ships"

    aligner2, claims2, docs2 = _setup(10, {"doc-9"})
    below = run_draft_alignment_eval(aligner2, claims2, docs2, record())
    assert below["alignment_rate"] == 0.9
    assert below["meets_redline"] is False


def test_empty_set_never_passes() -> None:
    aligner, _c, _d = _setup(0, set())
    report = run_draft_alignment_eval(aligner, [], {}, record())
    assert report["empty_set"] is True
    assert report["meets_redline"] is False, (
        "M3-060 observation: empty-set trivial 1.0 must not count as passing"
    )


def test_de_cited_never_reenters_denominator() -> None:
    aligner, claims, docs = _setup(4, {"doc-0"})
    report = run_draft_alignment_eval(aligner, claims, docs, record())
    assert report["pairs"] == 4, "denominator = original pairs"
    assert report["de_cited_claims"] == 1
    assert report["rate_stable_on_rerun"] is True, "rerun on same inputs same rate"


def test_cli_exit_codes(capsys) -> None:  # type: ignore[no-untyped-def]
    assert main([]) == 0
    assert main(["--min", "1.01"]) == 1
