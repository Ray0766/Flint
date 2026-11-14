"""M3-021 acceptance tests: draft claim extraction (section-class degradation).

Acceptance (tasks.json M3-021):
  - structured claim extraction from section draft (D9 section class:
    exhaustion marks gap, never blocks)
  - claim text binds citation doc ids for the stage-2 alignment surface
"""
from __future__ import annotations

from flint.compose.claims import CLAIM_SCHEMA, extract_draft_claims
from flint.domain.models import JSON
from flint.llm.structured import validate_schema


class ScriptedProvider:
    def __init__(self, payloads: list[JSON | None]) -> None:
        self.payloads = payloads
        self.calls = 0

    def generate(self, prompt: str, tools: list[JSON] | None) -> object:
        raise NotImplementedError

    def generate_structured(self, prompt: str, schema: JSON, max_retries: int) -> JSON:
        payload = self.payloads[min(self.calls, len(self.payloads) - 1)]
        self.calls += 1
        if payload is None:
            raise RuntimeError("scripted failure")
        return payload


GOOD_PAYLOAD: JSON = {
    "claims": [
        {"text_span": "需求增速 30%", "citation_ids": ["cit-1"]},
        {"text_span": "尚无成熟竞品", "citation_ids": []},
    ]
}


def test_schema_is_valid_subset() -> None:
    assert validate_schema(CLAIM_SCHEMA, GOOD_PAYLOAD) == []


def test_extraction_binds_citations_and_ids() -> None:
    provider = ScriptedProvider([GOOD_PAYLOAD])
    result = extract_draft_claims(
        provider, deliverable_id="d-1", block_id="b-1",  # type: ignore[arg-type]
        section_text="……需求增速 30%……",
    )
    assert result.degraded is False
    assert len(result.claims) == 2
    first = result.claims[0]
    assert first.deliverable_id == "d-1" and first.block_id == "b-1"
    assert first.citation_ids == ["cit-1"]
    assert first.confidence == "cited"
    assert first.alignment == "pending", "stage-2 alignment happens later"
    second = result.claims[1]
    assert second.confidence == "speculative", "no citation -> speculative"
    assert first.claim_id != second.claim_id
    rerun = extract_draft_claims(
        ScriptedProvider([GOOD_PAYLOAD]), "d-1", "b-1", "……需求增速 30%……",  # type: ignore[arg-type]
    )
    assert [c.claim_id for c in rerun.claims] == [c.claim_id for c in result.claims], (
        "claim ids deterministic"
    )


def test_exhaustion_degrades_marks_gap_never_blocks() -> None:
    from flint.llm.structured import StructuredOutputExhausted

    class ExhaustedProvider:
        def generate(self, prompt: str, tools: list[JSON] | None) -> object:
            raise NotImplementedError

        def generate_structured(
            self, prompt: str, schema: JSON, max_retries: int
        ) -> JSON:
            raise StructuredOutputExhausted(3, ["bad json"])

    result = extract_draft_claims(
        ExhaustedProvider(), "d-1", "b-1", "text",  # type: ignore[arg-type]
    )
    assert result.degraded is True, "D9 section class: gap, not a crash"
    assert result.claims == []
    assert result.gap is not None
    assert result.gap.cause == "missing_data"
