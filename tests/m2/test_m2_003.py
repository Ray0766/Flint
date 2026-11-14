"""M2-003 acceptance tests: generate_structured main path + typed degradation (D9).

Acceptance (tasks.json M2-003):
  - schema-validation failure feeds the error back, retry cap 2 (counted)
  - verdict-type total failure -> job failed, never guess; section-type
    degrades to a gap; failure count lands in the GenerationRecord channel
"""
from __future__ import annotations

import httpx
import pytest

from flint.domain.models import Completion
from flint.llm.provider import AnthropicProvider
from flint.llm.structured import (
    StructuredOutputExhausted,
    VerdictStructuredFailure,
    run_structured,
    structured_loop,
    validate_schema,
)

SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "minLength": 1},
        "category_id": {"type": "string", "enum": ["cat-ai", "cat-energy"]},
    },
    "required": ["name", "category_id"],
    "additionalProperties": False,
}


def completion(payload: object = None, text: str = "") -> Completion:
    calls = (
        [{"id": "t1", "name": "emit", "arguments": payload}] if payload is not None else []
    )
    return Completion(text=text, tool_calls=calls, usage={"input_tokens": 1, "output_tokens": 1})


# ── schema validator ──────────────────────────────────────


@pytest.mark.parametrize(
    ("value", "expected_fragment"),
    [
        ({"name": "固态电池", "category_id": "cat-energy"}, None),
        ({"category_id": "cat-ai"}, "required"),
        ({"name": "x", "category_id": "cat-nope"}, "enum"),
        ({"name": 7, "category_id": "cat-ai"}, "type"),
        ({"name": "x", "category_id": "cat-ai", "extra": 1}, "additionalProperties"),
        ({"name": "", "category_id": "cat-ai"}, "minLength"),
    ],
)
def test_validator_covers_core_keywords(value: object, expected_fragment: str | None) -> None:
    errors = validate_schema(SCHEMA, value)
    if expected_fragment is None:
        assert errors == []
    else:
        assert errors and expected_fragment in " ".join(errors)


# ── retry loop semantics ──────────────────────────────────


def test_first_attempt_valid_returns_immediately() -> None:
    calls: list[str] = []

    def gen(prompt: str) -> Completion:
        calls.append(prompt)
        return completion({"name": "固态电池", "category_id": "cat-energy"})

    payload, failed = structured_loop(gen, "请命名", SCHEMA, max_retries=2)
    assert payload == {"name": "固态电池", "category_id": "cat-energy"}
    assert failed == 0
    assert len(calls) == 1


def test_invalid_feeds_error_back_then_succeeds() -> None:
    calls: list[str] = []
    outputs = [
        completion({"category_id": "cat-ai"}),  # missing required name
        completion({"name": "端侧大模型", "category_id": "cat-ai"}),
    ]

    def gen(prompt: str) -> Completion:
        calls.append(prompt)
        return outputs[len(calls) - 1]

    payload, failed = structured_loop(gen, "请命名", SCHEMA, max_retries=2)
    assert payload is not None and payload["name"] == "端侧大模型"
    assert failed == 1
    assert len(calls) == 2
    assert "required" in calls[1], "the validation error must be fed back verbatim"
    assert "请命名" in calls[1], "original instruction retained on retry"


def test_retry_cap_is_two_then_exhausted() -> None:
    calls: list[str] = []

    def gen(prompt: str) -> Completion:
        calls.append(prompt)
        return completion({"category_id": "cat-ai"})

    with pytest.raises(StructuredOutputExhausted) as exc:
        structured_loop(gen, "请命名", SCHEMA, max_retries=2)
    assert len(calls) == 3, "1 initial + 2 retries, never a third blind retry"
    assert exc.value.failed_attempts == 3


def test_text_json_fallback_when_no_tool_call() -> None:
    def gen(prompt: str) -> Completion:
        return completion(text='{"name": "低空经济", "category_id": "cat-ai"}')

    payload, failed = structured_loop(gen, "请命名", SCHEMA, max_retries=0)
    assert payload is not None and payload["name"] == "低空经济"
    assert failed == 0


# ── typed degradation (D9) ────────────────────────────────


def always_invalid(prompt: str) -> Completion:
    return completion({"category_id": "cat-ai"})


def test_verdict_type_never_guesses() -> None:
    with pytest.raises(VerdictStructuredFailure) as exc:
        run_structured(always_invalid, "判定档位", SCHEMA, call_type="verdict")
    assert "绝不猜" in str(exc.value) or "job failed" in str(exc.value)
    assert exc.value.failed_attempts == 3


def test_section_type_degrades_to_gap() -> None:
    result = run_structured(always_invalid, "写这一节", SCHEMA, call_type="section")
    assert result.payload is None
    assert result.degraded is True
    assert result.failed_attempts == 3


def test_success_reports_zero_failures() -> None:
    def gen(prompt: str) -> Completion:
        return completion({"name": "x", "category_id": "cat-ai"})

    result = run_structured(gen, "写这一节", SCHEMA, call_type="section")
    assert result.payload is not None
    assert result.degraded is False
    assert result.failed_attempts == 0


# ── provider wiring (GenerationRecord channel) ────────────


def test_provider_generate_structured_and_failure_counter() -> None:
    responses = [
        httpx.Response(
            200,
            json={
                "id": "m1", "type": "message", "role": "assistant",
                "model": "claude-sonnet-5",
                "content": [
                    {"type": "tool_use", "id": "t1", "name": "emit",
                     "input": {"category_id": "cat-ai"}},
                ],
                "stop_reason": "tool_use",
                "usage": {"input_tokens": 10, "output_tokens": 5},
            },
        ),
        httpx.Response(
            200,
            json={
                "id": "m2", "type": "message", "role": "assistant",
                "model": "claude-sonnet-5",
                "content": [
                    {"type": "tool_use", "id": "t2", "name": "emit",
                     "input": {"name": "卫星互联网", "category_id": "cat-ai"}},
                ],
                "stop_reason": "tool_use",
                "usage": {"input_tokens": 10, "output_tokens": 5},
            },
        ),
    ]
    queue = list(responses)

    def responder(request: httpx.Request) -> httpx.Response:
        return queue.pop(0)

    with httpx.Client(transport=httpx.MockTransport(responder)) as client:
        provider = AnthropicProvider(
            api_key="test-key", model="claude-sonnet-5", http_client=client
        )
        payload = provider.generate_structured("命名", SCHEMA, max_retries=2)
    assert payload == {"name": "卫星互联网", "category_id": "cat-ai"}
    assert provider.structured_output_failures == 1, "failed attempts feed GenerationRecord"
