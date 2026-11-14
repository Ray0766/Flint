"""M2-039 acceptance tests: verdict zero-guess (D9 landing).

Acceptance (tasks.json M2-039):
  - verdict structured output fully exhausted => job failed with explanation
    (never guess)
  - failure count and degradation path land in GenerationRecord
"""
from __future__ import annotations

from datetime import UTC, datetime

import pytest

from flint.domain.models import JSON, Completion, GenerationRecord
from flint.gate.no_guess import (
    VERDICT_DEGRADATION_KEY,
    VerdictCallOutcome,
    run_verdict_structured,
)

SCHEMA: JSON = {
    "type": "object",
    "properties": {"verdict": {"type": "string", "enum": ["A", "B", "C", "D"]}},
    "required": ["verdict"],
    "additionalProperties": False,
}


def record() -> GenerationRecord:
    return GenerationRecord(
        record_id="r1", deliverable_id="d1", job_id="j1", prompt_version="v1",
        model="m", params={"seed": 7}, retrieval_snapshot_id="s1",
        ledger_version=None, pricebook_version=None,
        user_evidence_verdict_optin=False,
        ts=datetime(2026, 7, 28, tzinfo=UTC), cost=0.0,
        structured_output_failures=1,
    )


class ScriptedGenerate:
    """按脚本逐次给 Completion；记录调用次数。"""

    def __init__(self, bodies: list[str]) -> None:
        self.bodies = bodies
        self.calls = 0

    def __call__(self, prompt: str) -> Completion:
        body = self.bodies[min(self.calls, len(self.bodies) - 1)]
        self.calls += 1
        return Completion(text=body, tool_calls=[], usage={})


def test_success_path_returns_payload() -> None:
    generate = ScriptedGenerate(['{"verdict": "C"}'])
    outcome = run_verdict_structured(generate, "judge", SCHEMA, record())
    assert isinstance(outcome, VerdictCallOutcome)
    assert outcome.failed is False
    assert outcome.payload == {"verdict": "C"}
    assert outcome.record.structured_output_failures == 1, "no new failures"


def test_recovered_retry_counts_failures() -> None:
    generate = ScriptedGenerate(['not json', '{"verdict": "A"}'])
    outcome = run_verdict_structured(generate, "judge", SCHEMA, record())
    assert outcome.failed is False
    assert outcome.payload == {"verdict": "A"}
    assert outcome.record.structured_output_failures == 2, "1 prior + 1 new"


def test_exhaustion_fails_job_with_explanation_never_guesses() -> None:
    generate = ScriptedGenerate(['not json'])
    outcome = run_verdict_structured(generate, "judge", SCHEMA, record())
    assert outcome.failed is True
    assert outcome.payload is None, "no guessed verdict, structurally"
    assert outcome.failure_reason is not None
    assert "3" in outcome.failure_reason, "explanation cites attempt count"
    assert "绝不猜" in outcome.failure_reason


def test_retry_cap_exactly_three_attempts() -> None:
    generate = ScriptedGenerate(['not json'])
    run_verdict_structured(generate, "judge", SCHEMA, record())
    assert generate.calls == 3, "1 initial + 2 retries, never a fourth"


def test_failure_lands_in_generation_record() -> None:
    generate = ScriptedGenerate(['not json'])
    original = record()
    outcome = run_verdict_structured(generate, "judge", SCHEMA, original)
    assert outcome.record.structured_output_failures == 4, "1 prior + 3 new"
    degradation = outcome.record.params[VERDICT_DEGRADATION_KEY]
    assert degradation["path"] == "job_failed_no_guess"
    assert degradation["failed_attempts"] == 3
    assert degradation["errors"], "schema errors kept for the explanation"
    assert original.params == {"seed": 7}, "original record untouched"
    assert original.structured_output_failures == 1


def test_outcome_invariant_failed_never_carries_payload() -> None:
    with pytest.raises(ValueError, match="never"):
        VerdictCallOutcome(
            payload={"verdict": "C"}, failed=True,
            failure_reason="x", record=record(),
        )


def test_outcome_invariant_success_requires_payload() -> None:
    with pytest.raises(ValueError, match="payload"):
        VerdictCallOutcome(
            payload=None, failed=False, failure_reason=None, record=record()
        )
