"""Which model the demo stack talks to: the one place that decides (`NARROW-04`).

## Why this file exists

Until now both demo processes (`harness/demo_server.py` and `harness/run_worker.py`)
built the keyless local provider from `harness/local_model.py` and nothing else.
On a machine without a local endpoint every generation job fails with
`LocalProviderUnavailable` (all 18 `proposal` jobs in the demo database did).
The loaders for three hosted vendors were already in `flint/llm/production.py`;
nothing in `harness/` called them.

## The switch

`FLINT_DEMO_PROVIDER` picks the vendor. I pick it in my own `.env`; this file
picks none:

| value | provider | variables it reads (see `.env.example`) |
|---|---|---|
| unset or `local` | `LocalProvider` from `harness/local_model.py`, unchanged, no key | `FLINT_LOCAL_BASE_URL`, `FLINT_FREE_TIER_MODEL` |
| `anthropic` | `PaidTierProvider` | `load_anthropic_tier`: `FLINT_ANTHROPIC_*`, `FLINT_PAID_TIER_MODEL` |
| `deepseek` | `DeepSeekProvider` | `load_deepseek_tier` + `load_deepseek_pricing`: `FLINT_DEEPSEEK_*` |
| `openai` | `CloudOpenAIProvider` | `load_openai_tier`: `FLINT_OPENAI_*` |

Keys, model names and prices only ever come from those loaders, which read the
environment and name a missing variable without echoing any value. This file
never reads a key itself and never holds a price.

An unknown value is refused by name. Falling back to `local` would turn a typo in
`.env` into "the stack started fine and then every job failed", which looks the
same as no endpoint at all.

`transport` exists for the replay tests (`tests/v041/test_demo_model.py`): they
hand in a transport that answers from a real recorded response and refuses
anything else.
"""
from __future__ import annotations

import os
from collections.abc import Mapping

import httpx

from flint.llm.cloud import CloudOpenAIProvider
from flint.llm.deepseek import DeepSeekProvider, load_deepseek_pricing
from flint.llm.local import LocalProvider
from flint.llm.production import (
    ModelPricing,
    PaidTierProvider,
    ProviderWiringError,
    load_anthropic_tier,
    load_deepseek_tier,
    load_openai_tier,
)
from harness.local_model import TIMEOUT, build_local_provider

SELECTOR = "FLINT_DEMO_PROVIDER"
VENDORS = ("local", "anthropic", "deepseek", "openai")
#: Same output ceiling the local tier has always used (`harness/local_model.py`).
MAX_TOKENS = 4096

DemoProvider = LocalProvider | PaidTierProvider


def build_demo_provider(
    env: Mapping[str, str] | None = None,
    *,
    transport: httpx.BaseTransport | None = None,
) -> DemoProvider:
    """Build the provider `FLINT_DEMO_PROVIDER` names. Each call gets its own instance."""
    source = dict(os.environ if env is None else env)
    vendor = source.get(SELECTOR) or "local"
    if vendor not in VENDORS:
        raise ProviderWiringError(f"{SELECTOR} must be one of {list(VENDORS)}")

    if vendor == "local":
        return build_local_provider()

    if vendor == "anthropic":
        tier = load_anthropic_tier(source)
        return PaidTierProvider(
            api_key=tier.api_key, model=tier.model,
            pricing=ModelPricing(usd_per_mtok_input=tier.usd_per_mtok_input,
                                 usd_per_mtok_output=tier.usd_per_mtok_output),
            max_tokens=MAX_TOKENS,
            http_client=httpx.Client(timeout=TIMEOUT, transport=transport),
        )

    # OpenAI-compatible vendors: `LocalProvider` only puts the bearer header on the
    # client it builds itself, so a client handed in has to carry it.
    if vendor == "deepseek":
        cloud = load_deepseek_tier(source)
        return DeepSeekProvider(
            api_key=cloud.api_key, model=cloud.model,
            pricing=load_deepseek_pricing(source), base_url=cloud.base_url,
            http_client=_bearer_client(cloud.api_key, transport),
            max_tokens=MAX_TOKENS,
        )

    cloud = load_openai_tier(source)
    return CloudOpenAIProvider(
        base_url=cloud.base_url, model=cloud.model, api_key=cloud.api_key,
        pricing=ModelPricing(usd_per_mtok_input=cloud.usd_per_mtok_input,
                             usd_per_mtok_output=cloud.usd_per_mtok_output),
        http_client=_bearer_client(cloud.api_key, transport),
        max_tokens=MAX_TOKENS,
    )


def _bearer_client(api_key: str, transport: httpx.BaseTransport | None) -> httpx.Client:
    return httpx.Client(
        timeout=TIMEOUT, transport=transport,
        headers={"Authorization": f"Bearer {api_key}"})
