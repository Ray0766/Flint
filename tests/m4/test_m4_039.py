"""M4-039 acceptance tests: production LLM provider wiring.

Acceptance (tasks.json M4-039):
  - AnthropicProvider wired into the compose chain via config; offline CI
    keeps the deterministic provider
  - call accounting flows into GenerationRecord (real model/cost values)
"""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from flint.domain.models import JSON, Completion, GenerationRecord
from flint.jobs.compose import ComposeDeps, _aligner_provider, _SupportsAligner
from flint.llm.production import (
    LLMWiring,
    MeteredAnthropicProvider,
    MeteredOfflineProvider,
    ProviderWiringError,
    wire_provider,
)

pytestmark = pytest.mark.compose

NOW = datetime(2026, 7, 28, 12, 0, 0, tzinfo=UTC)


class SpyProvider:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def generate(self, prompt: str, tools: list[JSON] | None) -> Completion:
        self.calls.append(prompt)
        return Completion(text="ok", tool_calls=[], usage={})

    def generate_structured(
        self, prompt: str, schema: JSON, max_retries: int
    ) -> JSON:
        self.calls.append(prompt)
        return {"alignment": "supports"}


def anthropic_message(input_tokens: int, output_tokens: int) -> dict[str, object]:
    return {
        "id": "msg_1", "type": "message", "role": "assistant",
        "model": "claude-sonnet-5", "stop_reason": "end_turn",
        "stop_sequence": None,
        "content": [{"type": "text", "text": "回答"}],
        "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
    }


def test_offline_mode_keeps_deterministic_provider() -> None:
    spy = SpyProvider()
    provider = wire_provider(LLMWiring(mode="offline"), offline_inner=spy)
    assert isinstance(provider, MeteredOfflineProvider)
    result = provider.generate_structured("对齐", {"type": "object"}, 2)
    assert result == {"alignment": "supports"} and spy.calls == ["对齐"]
    assert provider.meter.cost_usd == 0.0, "offline cost is real zero, not estimate"
    assert provider.meter.calls == 1


def test_anthropic_mode_meters_real_usage_and_cost() -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=anthropic_message(1000, 500))

    provider = wire_provider(
        LLMWiring(
            mode="anthropic", model="claude-sonnet-5", api_key="sk-test",
            usd_per_mtok_input=3.0, usd_per_mtok_output=15.0,
        ),
        offline_inner=SpyProvider(),
        http_client=httpx.Client(transport=httpx.MockTransport(respond)),
    )
    assert isinstance(provider, MeteredAnthropicProvider)
    completion = provider.generate("你好", tools=None)
    assert completion.text == "回答"
    meter = provider.meter
    assert (meter.input_tokens, meter.output_tokens) == (1000, 500)
    assert meter.cost_usd == pytest.approx(
        (1000 * 3.0 + 500 * 15.0) / 1_000_000
    )


def test_accounting_flows_into_generation_record() -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=anthropic_message(2000, 100))

    provider = wire_provider(
        LLMWiring(
            mode="anthropic", model="claude-sonnet-5", api_key="sk-test",
            usd_per_mtok_input=3.0, usd_per_mtok_output=15.0,
        ),
        offline_inner=SpyProvider(),
        http_client=httpx.Client(transport=httpx.MockTransport(respond)),
    )
    assert isinstance(provider, MeteredAnthropicProvider)
    provider.generate("组稿", tools=None)
    record = GenerationRecord(
        record_id="gr-1", deliverable_id="d-1", job_id="j-1",
        prompt_version="v1", model=provider.model, params={},
        retrieval_snapshot_id="rs-1", ledger_version=1,
        pricebook_version=None, user_evidence_verdict_optin=False,
        ts=NOW, cost=provider.meter.cost_usd,
        structured_output_failures=provider.structured_output_failures,
    )
    assert record.model == "claude-sonnet-5"
    assert record.cost == pytest.approx((2000 * 3.0 + 100 * 15.0) / 1_000_000)
    assert record.cost > 0.0, "real value, not placeholder"


def test_anthropic_mode_requires_explicit_config() -> None:
    with pytest.raises(ProviderWiringError, match="api_key"):
        wire_provider(
            LLMWiring(mode="anthropic", model="claude-sonnet-5",
                      usd_per_mtok_input=3.0, usd_per_mtok_output=15.0),
            offline_inner=SpyProvider(),
        )
    with pytest.raises(ProviderWiringError, match="usd_per_mtok"):
        wire_provider(
            LLMWiring(mode="anthropic", model="claude-sonnet-5",
                      api_key="sk-test"),
            offline_inner=SpyProvider(),
        )


def test_compose_seam_selects_by_config() -> None:
    base: dict[str, object] = {
        "dsn": "postgresql://x", "template_path": Path("t.yaml"),
        "profile": None, "now": NOW,
        "generator_factory": lambda s, d: None,
    }
    offline_deps = ComposeDeps(**base)  # type: ignore[arg-type]
    assert isinstance(_aligner_provider(offline_deps), _SupportsAligner), (
        "None -> deterministic aligner (CI path unchanged)"
    )
    spy = SpyProvider()
    wired_deps = ComposeDeps(**base, aligner_provider=spy)  # type: ignore[arg-type]
    assert _aligner_provider(wired_deps) is spy
