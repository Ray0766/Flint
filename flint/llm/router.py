"""分级模型路由与成本记账（M2-005，技术方案 E5）。

- 判别类（相关性判定/簇命名一类）走小模型，生成类（verdict/章节/任务卡）
  走大模型；模型名配置化并随结果返回（GenerationRecord.model 进账通道）。
- 成本：usage 实数 × 每千 token 价目（配置化）→ cost_cny；add_job_cost 把
  每次调用累入 Job.cost_accum 并按 step 粒度落 JobStep.cost（B7 预算降级的
  记账地基）。
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, Protocol

import asyncpg

from flint.domain.models import JSON, Completion

CallClass = Literal["judgment", "generation"]


class _ProviderLike(Protocol):
    def generate(self, prompt: str, tools: list[JSON] | None) -> Completion: ...


@dataclass(frozen=True)
class ModelPricing:
    input_per_1k_cny: float
    output_per_1k_cny: float


@dataclass(frozen=True)
class ModelRoutingConfig:
    judgment_model: str
    generation_model: str
    pricing: dict[str, ModelPricing]

    def model_for(self, call_class: CallClass) -> str:
        return self.judgment_model if call_class == "judgment" else self.generation_model


@dataclass(frozen=True)
class RoutedCompletion:
    completion: Completion
    model: str            # -> GenerationRecord.model
    cost_cny: float


def estimate_cost_cny(usage: JSON, pricing: ModelPricing) -> float:
    input_tokens = float(usage.get("input_tokens", 0))
    output_tokens = float(usage.get("output_tokens", 0))
    return (
        input_tokens / 1000.0 * pricing.input_per_1k_cny
        + output_tokens / 1000.0 * pricing.output_per_1k_cny
    )


class RoutedLLM:
    def __init__(
        self,
        provider_factory: Callable[[str], _ProviderLike],
        config: ModelRoutingConfig,
    ) -> None:
        self._factory = provider_factory
        self._config = config

    def call(
        self, call_class: CallClass, prompt: str, tools: list[JSON] | None
    ) -> RoutedCompletion:
        model = self._config.model_for(call_class)
        completion = self._factory(model).generate(prompt, tools)
        pricing = self._config.pricing[model]
        return RoutedCompletion(
            completion=completion,
            model=model,
            cost_cny=estimate_cost_cny(completion.usage, pricing),
        )


async def add_job_cost(
    dsn: str, job_id: str, step_index: int, cost_cny: float
) -> None:
    """逐调用记账：Job.cost_accum 累加 + JobStep.cost 步粒度累加（同事务）。"""
    conn = await asyncpg.connect(dsn)
    try:
        async with conn.transaction():
            await conn.execute(
                "UPDATE jobs SET cost_accum = cost_accum + $2, updated_at = now() "
                "WHERE job_id = $1",
                job_id, cost_cny,
            )
            await conn.execute(
                "UPDATE job_steps SET cost = cost + $3 "
                "WHERE job_id = $1 AND step_index = $2",
                job_id, step_index, cost_cny,
            )
    finally:
        await conn.close()
