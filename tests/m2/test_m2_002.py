"""M2-002 acceptance tests: LLMProvider anthropic adapter (throttle+timeout+backoff).

Acceptance (tasks.json M2-002):
  - in-process token bucket (30 req / 200k tok per minute, configurable) takes
    effect under a fake clock
  - 429/timeout retreat via tenacity backoff; record/replay dual mode passes
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import anthropic
import httpx
import pytest

from flint.domain.models import Completion
from flint.llm.provider import AnthropicProvider, DualRateLimiter, LLMRateConfig
from flint.testing.replay import HttpReplay, fixture_path

API_URL = "https://api.anthropic.com/v1/messages"
DAY = date(2026, 7, 28)


def anthropic_json(text: str = "四类判定完成") -> dict[str, object]:
    return {
        "id": "msg_01",
        "type": "message",
        "role": "assistant",
        "model": "claude-sonnet-5",
        "content": [{"type": "text", "text": text}],
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 120, "output_tokens": 45},
    }


def fake_api(responses: list[httpx.Response] | None = None) -> httpx.MockTransport:
    queue = list(responses or [])

    def responder(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/messages"
        if queue:
            return queue.pop(0)
        return httpx.Response(
            200, json=anthropic_json(),
            headers={"content-type": "application/json"},
        )

    return httpx.MockTransport(responder)


def make_provider(
    client: httpx.Client,
    limiter: DualRateLimiter | None = None,
    backoff_sleeps: list[float] | None = None,
) -> AnthropicProvider:
    return AnthropicProvider(
        api_key="test-key",
        model="claude-sonnet-5",
        http_client=client,
        limiter=limiter,
        backoff_sleep=(backoff_sleeps.append if backoff_sleeps is not None else None),
    )


# ── dual token bucket (fake clock) ────────────────────────


def test_request_bucket_paces_at_configured_rpm() -> None:
    clock = [0.0]
    waits: list[float] = []

    def sleep(seconds: float) -> None:
        waits.append(seconds)
        clock[0] += seconds

    limiter = DualRateLimiter(
        LLMRateConfig(requests_per_minute=2, tokens_per_minute=1_000_000),
        now=lambda: clock[0], sleep=sleep,
    )
    limiter.acquire(estimated_tokens=10)
    limiter.acquire(estimated_tokens=10)
    assert waits == [], "burst capacity covers the first two"
    limiter.acquire(estimated_tokens=10)
    assert len(waits) == 1 and waits[0] > 0, "third request must wait for refill"


def test_token_bucket_paces_at_configured_tpm() -> None:
    clock = [0.0]
    waits: list[float] = []

    def sleep(seconds: float) -> None:
        waits.append(seconds)
        clock[0] += seconds

    limiter = DualRateLimiter(
        LLMRateConfig(requests_per_minute=1_000, tokens_per_minute=100),
        now=lambda: clock[0], sleep=sleep,
    )
    limiter.acquire(estimated_tokens=90)
    assert waits == []
    limiter.acquire(estimated_tokens=90)  # exceeds the per-minute token budget
    assert len(waits) == 1 and waits[0] > 0


def test_default_config_is_e5_values() -> None:
    config = LLMRateConfig()
    assert config.requests_per_minute == 30
    assert config.tokens_per_minute == 200_000


# ── generate + record/replay dual mode ────────────────────


def run_scenario(provider: AnthropicProvider) -> None:
    completion = provider.generate("判定这个方向的可行性", tools=None)
    assert isinstance(completion, Completion)
    assert completion.text == "四类判定完成"
    assert completion.usage["input_tokens"] == 120
    assert completion.usage["output_tokens"] == 45


def test_record_then_replay_same_assertions(tmp_path: Path) -> None:
    fixture = fixture_path(tmp_path, source_id="anthropic", day=DAY)

    with (
        HttpReplay(fixture, mode="record", live_transport=fake_api()) as session,
        session.client() as client,
    ):
        run_scenario(make_provider(client))
    assert fixture.exists()
    recorded = json.loads(fixture.read_text(encoding="utf-8"))
    assert recorded[0]["method"] == "POST"

    with (
        HttpReplay(fixture, mode="replay") as session,
        session.client() as client,
    ):
        run_scenario(make_provider(client))  # identical assertions, offline


# ── tenacity backoff on 429 / timeout ─────────────────────


def test_429_retried_with_backoff_then_succeeds() -> None:
    responses = [
        httpx.Response(429, json={"error": {"type": "rate_limit_error"}}),
        httpx.Response(429, json={"error": {"type": "rate_limit_error"}}),
        httpx.Response(200, json=anthropic_json()),
    ]
    sleeps: list[float] = []
    with httpx.Client(transport=fake_api(responses)) as client:
        provider = make_provider(client, backoff_sleeps=sleeps)
        run_scenario(provider)
    assert len(sleeps) == 2, "two 429s -> two backoff waits"
    assert sleeps[0] < sleeps[1], "exponential backoff grows"


def test_timeout_retried_then_succeeds() -> None:
    calls = [0]

    def responder(request: httpx.Request) -> httpx.Response:
        calls[0] += 1
        if calls[0] == 1:
            raise httpx.ReadTimeout("slow upstream", request=request)
        return httpx.Response(200, json=anthropic_json())

    sleeps: list[float] = []
    with httpx.Client(transport=httpx.MockTransport(responder)) as client:
        provider = make_provider(client, backoff_sleeps=sleeps)
        run_scenario(provider)
    assert calls[0] == 2
    assert len(sleeps) == 1


def test_retry_budget_exhausted_raises() -> None:
    responses = [httpx.Response(429, json={"error": {"type": "rate_limit_error"}})] * 10
    sleeps: list[float] = []
    with httpx.Client(transport=fake_api(responses)) as client:
        provider = make_provider(client, backoff_sleeps=sleeps)
        with pytest.raises(anthropic.RateLimitError):
            provider.generate("x", tools=None)
    assert len(sleeps) >= 2, "backoff attempted before giving up"
