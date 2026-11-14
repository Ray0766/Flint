"""LLMProvider anthropic 适配器（M2-002，技术方案 E5）。

- 限流：进程内双桶（请求数 + token 数，默认 30 req / 200k tok 每分钟，
  配置化；时钟与 sleep 注入可测）。
- 超时：单调用 120s（配置化）；SDK 自带重试关闭（max_retries=0），
  429/超时统一走 tenacity 指数退避（退避 sleep 注入可测）。
- generate_structured 主路与分级降级归 M2-003（本卡占位显式抛错）。
"""
from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, cast

import anthropic
import httpx
from tenacity import (
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from flint.domain.models import JSON, Completion

DEFAULT_MAX_TOKENS = 1024


@dataclass(frozen=True)
class LLMRateConfig:
    requests_per_minute: int = 30
    tokens_per_minute: int = 200_000
    timeout_seconds: float = 120.0
    max_attempts: int = 4  # 首次 + 3 次退避重试（网络层；D9 的结构化重试另计）


class _Bucket:
    def __init__(self, capacity: float, per_minute: float, now: Callable[[], float]) -> None:
        self._capacity = capacity
        self._rate = per_minute / 60.0
        self._now = now
        self._level = capacity
        self._stamp = now()

    def _refill(self) -> None:
        current = self._now()
        self._level = min(self._capacity, self._level + (current - self._stamp) * self._rate)
        self._stamp = current

    def deficit_seconds(self, amount: float) -> float:
        self._refill()
        if self._level >= amount:
            return 0.0
        return (amount - self._level) / self._rate

    def drain(self, amount: float) -> None:
        self._refill()
        self._level = max(0.0, self._level - amount)


@dataclass
class DualRateLimiter:
    """请求桶 + token 桶并联；任一不足按缺口补睡（假时钟单测）。"""

    config: LLMRateConfig = field(default_factory=LLMRateConfig)
    now: Callable[[], float] = time.monotonic
    sleep: Callable[[float], None] = time.sleep

    def __post_init__(self) -> None:
        self._requests = _Bucket(
            float(self.config.requests_per_minute),
            float(self.config.requests_per_minute),
            self.now,
        )
        self._tokens = _Bucket(
            float(self.config.tokens_per_minute),
            float(self.config.tokens_per_minute),
            self.now,
        )

    def acquire(self, estimated_tokens: int) -> None:
        wait = max(
            self._requests.deficit_seconds(1.0),
            self._tokens.deficit_seconds(float(estimated_tokens)),
        )
        if wait > 0:
            self.sleep(wait)
        self._requests.drain(1.0)
        self._tokens.drain(float(estimated_tokens))


def _estimate_tokens(prompt: str, max_tokens: int) -> int:
    return max(1, len(prompt) // 4) + max_tokens


class AnthropicProvider:
    """冻结协议 LLMProvider 的 anthropic 实现（generate 面；structured 归 M2-003）。"""

    def __init__(
        self,
        api_key: str,
        model: str,
        http_client: httpx.Client | None = None,
        config: LLMRateConfig | None = None,
        limiter: DualRateLimiter | None = None,
        backoff_sleep: Callable[[float], None] | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> None:
        self._config = config or LLMRateConfig()
        self._limiter = limiter or DualRateLimiter(self._config)
        self._backoff_sleep = backoff_sleep or time.sleep
        self._max_tokens = max_tokens
        self.model = model
        self.structured_output_failures = 0  # GenerationRecord 进账通道（D9）
        self._client = anthropic.Anthropic(
            api_key=api_key,
            http_client=http_client,
            max_retries=0,  # 重试策略统一收口到 tenacity
            timeout=self._config.timeout_seconds,
        )

    def _call_once(self, prompt: str, tools: list[JSON] | None) -> anthropic.types.Message:
        if tools is None:
            return self._client.messages.create(
                model=self.model,
                max_tokens=self._max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
        return self._client.messages.create(
            model=self.model,
            max_tokens=self._max_tokens,
            messages=[{"role": "user", "content": prompt}],
            tools=cast("Any", tools),
        )

    def generate(self, prompt: str, tools: list[JSON] | None) -> Completion:
        self._limiter.acquire(_estimate_tokens(prompt, self._max_tokens))
        retrying = Retrying(
            stop=stop_after_attempt(self._config.max_attempts),
            wait=wait_exponential(multiplier=1, min=1, max=30),
            retry=retry_if_exception_type(
                (anthropic.RateLimitError, anthropic.APITimeoutError, anthropic.APIConnectionError)
            ),
            sleep=self._backoff_sleep,
            reraise=True,
        )
        message = retrying(self._call_once, prompt, tools)

        text_parts: list[str] = []
        tool_calls: list[JSON] = []
        for block in message.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(
                    {"id": block.id, "name": block.name, "arguments": block.input}
                )
        return Completion(
            text="".join(text_parts),
            tool_calls=tool_calls,
            usage={
                "input_tokens": message.usage.input_tokens,
                "output_tokens": message.usage.output_tokens,
            },
        )

    def generate_structured(self, prompt: str, schema: JSON, max_retries: int) -> JSON:
        """D9 主路（M2-003）：tool use + 本方 schema 校验；失败回喂重试
        <= max_retries；耗尽抛 StructuredOutputExhausted（调用点分级降级见
        flint.llm.structured.run_structured）。失败尝试数累入
        structured_output_failures（GenerationRecord 进账通道）。"""
        from flint.llm.structured import StructuredOutputExhausted, structured_loop

        tool: JSON = {
            "name": "emit",
            "description": "输出符合 schema 的结构化结果",
            "input_schema": schema,
        }
        try:
            payload, failed = structured_loop(
                lambda p: self.generate(p, tools=[tool]), prompt, schema, max_retries
            )
        except StructuredOutputExhausted as err:
            self.structured_output_failures += err.failed_attempts
            raise
        self.structured_output_failures += failed
        assert payload is not None
        return payload
