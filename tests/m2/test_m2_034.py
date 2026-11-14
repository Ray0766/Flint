"""M2-034 acceptance tests: rule A (refutation hard threshold).

Acceptance (tasks.json M2-034):
  - >=1 refute evidence passing stage-1 alignment required for A
  - user_provided-only support needs explicit optin, backfilled to
    GenerationRecord.user_evidence_verdict_optin
"""
from __future__ import annotations

from datetime import UTC, date, datetime

from flint.align.stage1 import LLMCitationAligner
from flint.domain.models import JSON, Doc, EvidenceOrigin, GenerationRecord
from flint.gate.rule_a import RuleAResult, backfill_optin, evaluate_rule_a

FETCHED = datetime(2026, 7, 28, 12, 0, 0, tzinfo=UTC).isoformat()


def make_doc(i: int, title: str, origin: EvidenceOrigin = "retrieved") -> Doc:
    return Doc(
        doc_id=f"doc-{i}", source_id="crossref", kind="paper", title=title,
        url=f"https://a/{i}", published_at=date(2026, 1, 1),
        meta={"fetched_at": FETCHED}, origin=origin,
        access="public" if origin == "retrieved" else "private",
    )


class AlignProvider:
    """按证据段标记给对齐结论（只看文摘段，防断言文本串扰）。"""

    def __init__(self, failing_markers: list[str], verdict: str = "partial") -> None:
        self.failing_markers = failing_markers
        self.failing_verdict = verdict

    def generate(self, prompt: str, tools: list[JSON] | None) -> object:
        raise NotImplementedError

    def generate_structured(self, prompt: str, schema: JSON, max_retries: int) -> JSON:
        segment = prompt.split("证据（doc_id=", 1)[1]
        if any(m in segment for m in self.failing_markers):
            return {"alignment": self.failing_verdict}
        return {"alignment": "supports"}


def aligner(failing: list[str] | None = None) -> LLMCitationAligner:
    return LLMCitationAligner(provider=AlignProvider(failing or []))  # type: ignore[arg-type]


def test_retrieved_refute_evidence_satisfies_a() -> None:
    pairs = [("路线 X 不可行", make_doc(1, "failed replication of X"))]
    result = evaluate_rule_a(aligner(), pairs, user_evidence_optin=False)
    assert isinstance(result, RuleAResult)
    assert result.satisfied is True
    assert result.refute_doc_ids == ["doc-1"]
    assert result.used_user_evidence_only is False


def test_alignment_failure_demotes_to_d() -> None:
    pairs = [("路线 X 不可行", make_doc(1, "vague survey"))]
    result = evaluate_rule_a(aligner(["vague"]), pairs, user_evidence_optin=False)
    assert result.satisfied is False
    assert result.demote_to_d is True, "never judge on failed key alignment"


def test_no_refute_evidence_not_satisfied() -> None:
    result = evaluate_rule_a(aligner(), [], user_evidence_optin=False)
    assert result.satisfied is False and result.demote_to_d is False


def test_user_provided_only_blocked_without_optin() -> None:
    pairs = [("路线 X 不可行", make_doc(2, "internal test failed", origin="user_provided"))]
    result = evaluate_rule_a(aligner(), pairs, user_evidence_optin=False)
    assert result.satisfied is False
    assert result.blocked_pending_optin is True


def test_user_provided_only_passes_with_optin() -> None:
    pairs = [("路线 X 不可行", make_doc(2, "internal test failed", origin="user_provided"))]
    result = evaluate_rule_a(aligner(), pairs, user_evidence_optin=True)
    assert result.satisfied is True
    assert result.used_user_evidence_only is True
    assert result.refute_doc_ids == ["doc-2"]


def test_mixed_origin_without_optin_cites_retrieved_only() -> None:
    pairs = [
        ("路线 X 不可行", make_doc(1, "failed replication of X")),
        ("路线 X 不可行", make_doc(2, "internal memo", origin="user_provided")),
    ]
    result = evaluate_rule_a(aligner(), pairs, user_evidence_optin=False)
    assert result.satisfied is True
    assert result.refute_doc_ids == ["doc-1"], "unconfirmed user evidence never cited"


def test_backfill_optin_updates_generation_record() -> None:
    record = GenerationRecord(
        record_id="r1", deliverable_id="d1", job_id="j1", prompt_version="v1",
        model="m", params={}, retrieval_snapshot_id="s1", ledger_version=None,
        pricebook_version=None, user_evidence_verdict_optin=False,
        ts=datetime(2026, 7, 28, tzinfo=UTC), cost=0.0,
    )
    updated = backfill_optin(record)
    assert updated.user_evidence_verdict_optin is True
    assert record.user_evidence_verdict_optin is False, "original left intact for audit"
