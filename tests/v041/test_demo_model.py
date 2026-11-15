"""NARROW-04 · the demo stack can run on a keyed hosted model, picked by environment.

## Why

Every `proposal` job in the demo database failed (18 of 18, 0 done) with
`LocalProviderUnavailable: local endpoint unreachable for qwen3.6:35b-a3b`:
the demo stack only knew one model, a local Ollama endpoint, and this Mac does
not run one. The loaders for three hosted vendors were already in
`flint/llm/production.py`, but nothing in `harness/` called them.

`harness/demo_model.py` is now the one place the demo picks a model:

- `FLINT_DEMO_PROVIDER` unset or `local` → the same keyless `LocalProvider` as before;
- `anthropic` / `deepseek` / `openai` → that vendor's existing loader, which reads
  its own `FLINT_*` variables (key, model, prices) from the environment.

The vendor is the owner's call; nothing here picks one.

## How this is proven without a real request

Each keyed case replays a response that was **really recorded** from that vendor
(`fixtures/topic_runs/*/combo.json`, recorded by `harness/topic_caliber.py`).
The replay transport answers only the recorded method + URL and raises on
anything else, so a request to any other host fails the test instead of leaving
the machine. The key is a made-up string; no real key is read.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from flint.llm.production import ProviderWiringError
from flint.testing.replay import ReplayMiss, load_fixture

REPO = Path(__file__).resolve().parents[2]
RUNS = REPO / "fixtures" / "topic_runs"
FAKE_KEY = "replay-only-not-a-real-key"


class _Replay(httpx.BaseTransport):
    """Answer the first recorded exchange of one fixture; refuse everything else."""

    def __init__(self, fixture: Path) -> None:
        self.exchange = load_fixture(fixture)[0]
        self.seen: list[httpx.Request] = []

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        self.seen.append(request)
        if request.method != self.exchange.method or str(request.url) != self.exchange.url:
            raise ReplayMiss(f"no recorded exchange for {request.method} {request.url}")
        return httpx.Response(
            self.exchange.status_code,
            content=self.exchange.body_text.encode("utf-8"),
            headers={"content-type": self.exchange.content_type or "application/json"},
        )


def _env(vendor: str, **extra: str) -> dict[str, str]:
    prefix = {"anthropic": "FLINT_ANTHROPIC", "deepseek": "FLINT_DEEPSEEK",
              "openai": "FLINT_OPENAI"}[vendor]
    env = {
        "FLINT_DEMO_PROVIDER": vendor,
        f"{prefix}_API_KEY": FAKE_KEY,
        f"{prefix}_USD_PER_MTOK_INPUT": "1.5",
        f"{prefix}_USD_PER_MTOK_OUTPUT": "6",
    }
    env["FLINT_PAID_TIER_MODEL" if vendor == "anthropic" else f"{prefix}_MODEL"] = "replay-model"
    env.update(extra)
    return env


# ───────────────────────── unset stays exactly what it was


def test_unset_means_the_keyless_local_endpoint_as_before() -> None:
    from flint.llm.local import LocalProvider
    from harness.demo_model import build_demo_provider
    from harness.local_model import MODEL, OLLAMA

    for env in ({}, {"FLINT_DEMO_PROVIDER": "local"}):
        provider = build_demo_provider(env)
        assert type(provider) is LocalProvider
        assert provider.model == MODEL
        assert provider._base_url == OLLAMA.rstrip("/")
        assert "authorization" not in provider._client.headers


def test_an_unknown_vendor_is_refused_by_name() -> None:
    from harness.demo_model import VENDORS, build_demo_provider

    with pytest.raises(ProviderWiringError) as err:
        build_demo_provider({"FLINT_DEMO_PROVIDER": "anthropc"})
    assert "FLINT_DEMO_PROVIDER" in str(err.value)
    assert all(v in str(err.value) for v in VENDORS)


@pytest.mark.parametrize("vendor", ["anthropic", "deepseek", "openai"])
def test_a_keyed_vendor_with_a_missing_variable_names_it_and_echoes_no_value(
    vendor: str,
) -> None:
    from harness.demo_model import build_demo_provider

    env = _env(vendor)
    dropped = next(k for k in env if k.endswith("_USD_PER_MTOK_OUTPUT"))
    del env[dropped]
    with pytest.raises(ProviderWiringError) as err:
        build_demo_provider(env)
    assert dropped in str(err.value)
    assert FAKE_KEY not in str(err.value)


# ───────────────────────── the three vendors, each against its own recording


def test_anthropic_carries_the_key_and_reads_a_recorded_claude_reply() -> None:
    from flint.llm.production import PaidTierProvider
    from harness.demo_model import build_demo_provider

    replay = _Replay(RUNS / "claude-sonnet-5" / "combo.json")
    provider = build_demo_provider(_env("anthropic"), transport=replay)

    assert isinstance(provider, PaidTierProvider)
    assert provider.model == "replay-model"
    completion = provider.generate(
        "x", tools=[{"name": "emit", "description": "", "input_schema": {"type": "object"}}])

    (request,) = replay.seen
    assert request.headers["x-api-key"] == FAKE_KEY
    assert json.loads(request.content)["model"] == "replay-model"
    recorded = json.loads(replay.exchange.body_text)
    tool_input = next(b["input"] for b in recorded["content"] if b["type"] == "tool_use")
    assert completion.tool_calls[0]["name"] == "emit"
    assert completion.tool_calls[0]["arguments"] == tool_input
    # cost = env prices x the usage the vendor returned, never a built-in price table
    usage = recorded["usage"]
    expected = (usage["input_tokens"] * 1.5 + usage["output_tokens"] * 6) / 1_000_000
    assert provider.meter.cost_usd == pytest.approx(expected)


@pytest.mark.parametrize(("vendor", "run"), [("deepseek", "deepseek-chat"),
                                             ("openai", "gpt-4o-mini")])
def test_openai_compatible_vendors_carry_a_bearer_key_and_parse_a_recorded_reply(
    vendor: str, run: str,
) -> None:
    from flint.llm.cloud import CloudOpenAIProvider
    from harness.demo_model import build_demo_provider

    replay = _Replay(RUNS / run / "combo.json")
    provider = build_demo_provider(_env(vendor), transport=replay)

    assert isinstance(provider, CloudOpenAIProvider)
    payload = provider.generate_structured("x", {"type": "object"}, max_retries=0)

    (request,) = replay.seen
    assert request.headers["authorization"] == f"Bearer {FAKE_KEY}"
    assert json.loads(request.content)["model"] == "replay-model"
    assert payload["one_liner"], payload
    assert provider.meter.cost_usd > 0


def test_a_request_to_any_other_address_never_leaves_the_machine() -> None:
    """The replay is the only network these tests have: an unrecorded URL fails."""
    from harness.demo_model import build_demo_provider

    env = _env("openai", FLINT_OPENAI_BASE_URL="https://elsewhere.invalid/v1")
    replay = _Replay(RUNS / "gpt-4o-mini" / "combo.json")
    provider = build_demo_provider(env, transport=replay)
    with pytest.raises(Exception) as err:
        provider.generate("x", tools=None)
    assert isinstance(err.value.__cause__ or err.value, ReplayMiss | httpx.HTTPError)
    assert [r.url.host for r in replay.seen] == ["elsewhere.invalid"]


# ───────────────────────── both demo processes take it from the one place


def _keyed_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name, value in _env("anthropic").items():
        monkeypatch.setenv(name, value)


def test_the_worker_composes_with_the_keyed_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    from flint.llm.production import PaidTierProvider
    from harness import run_worker

    _keyed_env(monkeypatch)
    deps = run_worker.build_deps()

    assert isinstance(deps.compose_provider, PaidTierProvider)
    assert deps.compose_provider.model == "replay-model"
    assert deps.design_generate_deps is not None
    assert deps.design_generate_deps.provider is deps.compose_provider


def test_the_api_process_hands_combo_the_keyed_provider_and_its_model_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from flint.llm.production import PaidTierProvider
    from harness import demo_server

    _keyed_env(monkeypatch)
    seen: dict[str, Any] = {}
    real = demo_server.create_app

    def spy(dsn: str, **kwargs: Any) -> Any:
        seen.update(kwargs)
        return real(dsn, **kwargs)

    monkeypatch.setattr(demo_server, "create_app", spy)
    demo_server.build_app()

    assert isinstance(seen["combo_provider"], PaidTierProvider)
    assert seen["combo_model"] == "replay-model"
