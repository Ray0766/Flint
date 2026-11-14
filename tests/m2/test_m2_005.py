"""M2-005 acceptance tests: model tier routing + cost accounting.

Acceptance (tasks.json M2-005):
  - judgment calls take the small model, generation calls the large model
    (configurable, model name lands in the GenerationRecord channel)
  - usage accumulates into Job.cost_accum per call; step granularity lands
    in JobStep.cost
"""
from __future__ import annotations

import asyncio
import os
from typing import Any

import asyncpg
import pytest

from flint.domain.models import JSON, Completion
from flint.llm.router import (
    ModelPricing,
    ModelRoutingConfig,
    RoutedLLM,
    add_job_cost,
    estimate_cost_cny,
)

DSN = os.environ.get("FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")


class RecordingProvider:
    def __init__(self, model: str) -> None:
        self.model = model
        self.calls = 0

    def generate(self, prompt: str, tools: list[JSON] | None) -> Completion:
        self.calls += 1
        return Completion(
            text=f"answer from {self.model}", tool_calls=[],
            usage={"input_tokens": 1000, "output_tokens": 500},
        )

    def generate_structured(self, prompt: str, schema: JSON, max_retries: int) -> JSON:
        self.calls += 1
        return {"ok": True}


def make_router() -> tuple[RoutedLLM, dict[str, RecordingProvider]]:
    providers: dict[str, RecordingProvider] = {}

    def factory(model: str) -> RecordingProvider:
        providers.setdefault(model, RecordingProvider(model))
        return providers[model]

    config = ModelRoutingConfig(
        judgment_model="claude-haiku-4-5",
        generation_model="claude-sonnet-5",
        pricing={
            "claude-haiku-4-5": ModelPricing(input_per_1k_cny=0.006, output_per_1k_cny=0.03),
            "claude-sonnet-5": ModelPricing(input_per_1k_cny=0.02, output_per_1k_cny=0.10),
        },
    )
    return RoutedLLM(provider_factory=factory, config=config), providers


def test_judgment_routes_to_small_model() -> None:
    router, providers = make_router()
    result = router.call("judgment", "判定相关性", tools=None)
    assert result.model == "claude-haiku-4-5", "model name feeds GenerationRecord.model"
    assert providers["claude-haiku-4-5"].calls == 1
    assert "claude-sonnet-5" not in providers


def test_generation_routes_to_large_model() -> None:
    router, providers = make_router()
    result = router.call("generation", "写章节", tools=None)
    assert result.model == "claude-sonnet-5"
    assert providers["claude-sonnet-5"].calls == 1


def test_routing_is_configurable() -> None:
    config = ModelRoutingConfig(
        judgment_model="claude-haiku-4-5",
        generation_model="claude-opus-5",
        pricing={
            "claude-haiku-4-5": ModelPricing(0.006, 0.03),
            "claude-opus-5": ModelPricing(0.05, 0.25),
        },
    )
    providers: dict[str, RecordingProvider] = {}
    router = RoutedLLM(
        provider_factory=lambda m: providers.setdefault(m, RecordingProvider(m)),
        config=config,
    )
    assert router.call("generation", "x", tools=None).model == "claude-opus-5"


def test_cost_computed_from_usage_and_pricing() -> None:
    pricing = ModelPricing(input_per_1k_cny=0.02, output_per_1k_cny=0.10)
    cost = estimate_cost_cny({"input_tokens": 1000, "output_tokens": 500}, pricing)
    assert cost == pytest.approx(0.02 + 0.05)

    router, _ = make_router()
    result = router.call("generation", "写章节", tools=None)
    assert result.cost_cny == pytest.approx(0.02 + 0.05)


@pytest.mark.compose
def test_cost_accumulates_into_job_and_step() -> None:
    def run(coro: Any) -> Any:
        return asyncio.run(coro)

    async def setup() -> None:
        conn = await asyncpg.connect(DSN)
        try:
            await conn.execute("DELETE FROM job_steps WHERE job_id = 'm2005-job'")
            await conn.execute("DELETE FROM jobs WHERE job_id = 'm2005-job'")
            await conn.execute(
                "INSERT INTO jobs (job_id, kind, owner_scope, state, progress, budget, "
                "cost_accum, cancel_requested, initiated_by, created_at, updated_at) "
                "VALUES ('m2005-job', 'gate1_analysis', '{\"kind\":\"user\",\"id\":\"u1\"}', "
                "'retrieving', 0, 10, 0, false, 'u1', now(), now())"
            )
            await conn.execute(
                "INSERT INTO job_steps (job_id, step_index, name, state, started_at, "
                "ended_at, cost, snapshot_ref) VALUES ('m2005-job', 0, 'judge', "
                "'done', now(), now(), 0, NULL)"
            )
        finally:
            await conn.close()

    run(setup())
    run(add_job_cost(DSN, "m2005-job", step_index=0, cost_cny=0.07))
    run(add_job_cost(DSN, "m2005-job", step_index=0, cost_cny=0.03))

    async def readback() -> tuple[float, float]:
        conn = await asyncpg.connect(DSN)
        try:
            job_cost: float = await conn.fetchval(
                "SELECT cost_accum FROM jobs WHERE job_id = 'm2005-job'"
            )
            step_cost: float = await conn.fetchval(
                "SELECT cost FROM job_steps WHERE job_id = 'm2005-job' AND step_index = 0"
            )
            return job_cost, step_cost
        finally:
            await conn.close()

    job_cost, step_cost = run(readback())
    assert job_cost == pytest.approx(0.10), "per-call accumulation into Job.cost_accum"
    assert step_cost == pytest.approx(0.10), "step-granularity into JobStep.cost"
