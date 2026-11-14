"""真 LLM provider 接线（M4-039，生产口径地基 / 技术方案 E5）。

- 配置分流：mode=offline → 注入的确定性 provider（CI 恒走此路，S2-7）；
  mode=anthropic → AnthropicProvider（M2-002 面原样复用）。
- 记账：UsageMeter 累计 input/output tokens，cost = tokens × 显式配置
  价目（usd_per_mtok）——**价目 MUST 由配置提供，NEVER 内置价表猜价**
  （数字必有出处：cost 实值的出处是配置项 + API 返回 usage）。
- MeteredAnthropicProvider 在 generate 面记账：generate_structured 内部
  经 self.generate（M2-003 结构），故结构化调用同样入账。
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal, cast

import anthropic
import httpx
from tenacity import (
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from flint.domain.models import JSON, Completion
from flint.domain.protocols import LLMProvider
from flint.llm.provider import DEFAULT_MAX_TOKENS, AnthropicProvider

if TYPE_CHECKING:
    from flint.llm.local import LocalProvider as LocalProviderT


class ProviderWiringError(Exception):
    pass


@dataclass(frozen=True)
class ModelPricing:
    usd_per_mtok_input: float
    usd_per_mtok_output: float


FREE = ModelPricing(usd_per_mtok_input=0.0, usd_per_mtok_output=0.0)


@dataclass
class UsageMeter:
    pricing: ModelPricing
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0

    def add(self, usage: JSON) -> None:
        self.calls += 1
        if not isinstance(usage, dict):
            return
        raw_in = usage.get("input_tokens")
        raw_out = usage.get("output_tokens")
        if isinstance(raw_in, int):
            self.input_tokens += raw_in
        if isinstance(raw_out, int):
            self.output_tokens += raw_out

    @property
    def cost_usd(self) -> float:
        return (
            self.input_tokens * self.pricing.usd_per_mtok_input
            + self.output_tokens * self.pricing.usd_per_mtok_output
        ) / 1_000_000


class MeteredAnthropicProvider(AnthropicProvider):
    def __init__(
        self,
        api_key: str,
        model: str,
        pricing: ModelPricing,
        http_client: httpx.Client | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> None:
        super().__init__(
            api_key=api_key, model=model, http_client=http_client,
            max_tokens=max_tokens,
        )
        self.meter = UsageMeter(pricing=pricing)

    def generate(self, prompt: str, tools: list[JSON] | None) -> Completion:
        completion = super().generate(prompt, tools)
        self.meter.add(completion.usage)
        return completion


class PaidTierProvider(MeteredAnthropicProvider):
    """付费档跑批 provider（owner 任务）：
    - 组稿走 generate（可配 max_tokens）；判分走 generate_structured 用 Claude
      **原生结构化输出 output_config.format**（JSON 干净、非 tool-use 往返）；
    - thinking 可关（disable_thinking=True → 请求带 thinking={"type":"disabled"}；
      Sonnet 5 省略 thinking 会自适应思考，故显式关以控成本/防截断）——本次
      跑批口径写入 trail；
    - 记账继承 MeteredAnthropicProvider（generate 面）；结构化面本类自记账 +
      structured_output_failures。
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        pricing: ModelPricing,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        disable_thinking: bool = True,
        http_client: httpx.Client | None = None,
    ) -> None:
        super().__init__(
            api_key=api_key, model=model, pricing=pricing,
            http_client=http_client, max_tokens=max_tokens,
        )
        self._disable_thinking = disable_thinking

    def _thinking_kwargs(self) -> dict[str, Any]:
        if self._disable_thinking:
            return {"thinking": {"type": "disabled"}}
        return {}

    def _call_once(
        self, prompt: str, tools: list[JSON] | None
    ) -> anthropic.types.Message:
        client = cast("Any", self._client)
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self._max_tokens,
            "messages": [{"role": "user", "content": prompt}],
            **self._thinking_kwargs(),
        }
        if tools is not None:
            kwargs["tools"] = tools
        message: anthropic.types.Message = client.messages.create(**kwargs)
        return message

    def generate_structured(
        self, prompt: str, schema: JSON, max_retries: int
    ) -> JSON:
        # 原生结构化：output_config.format（输出保证合法 JSON，无 tool-use
        # 往返）；限流/退避/记账与 generate 面同源。max_retries 保留签名——
        # 原生路径不做回喂重试，非法 JSON 记为一次失败并抛（防御路径）。
        from flint.llm.structured import StructuredOutputExhausted

        self._limiter.acquire(max(1, len(prompt) // 4) + self._max_tokens)
        client = cast("Any", self._client)
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self._max_tokens,
            "messages": [{"role": "user", "content": prompt}],
            "output_config": {
                "format": {"type": "json_schema", "schema": schema}
            },
            **self._thinking_kwargs(),
        }
        retrying = Retrying(
            stop=stop_after_attempt(self._config.max_attempts),
            wait=wait_exponential(multiplier=1, min=1, max=30),
            retry=retry_if_exception_type((
                anthropic.RateLimitError,
                anthropic.APITimeoutError,
                anthropic.APIConnectionError,
            )),
            sleep=self._backoff_sleep,
            reraise=True,
        )
        message: anthropic.types.Message = retrying(
            lambda: client.messages.create(**kwargs)
        )
        self.meter.add({
            "input_tokens": message.usage.input_tokens,
            "output_tokens": message.usage.output_tokens,
        })
        text = "".join(
            b.text for b in message.content if b.type == "text"
        )
        try:
            payload = json.loads(text)
        except ValueError as err:
            self.structured_output_failures += 1
            raise StructuredOutputExhausted(
                failed_attempts=1,
                errors=["output_config.format returned non-JSON text"],
            ) from err
        if not isinstance(payload, dict):
            self.structured_output_failures += 1
            raise StructuredOutputExhausted(
                failed_attempts=1,
                errors=["output_config.format payload was not a JSON object"],
            )
        return cast("JSON", payload)


@dataclass
class MeteredOfflineProvider:
    """确定性 provider 的记账包装（cost 恒 0：FREE 价目，非估算）。"""

    inner: LLMProvider
    model: str = "offline-deterministic"
    meter: UsageMeter = field(default_factory=lambda: UsageMeter(pricing=FREE))
    structured_output_failures: int = 0

    def generate(self, prompt: str, tools: list[JSON] | None) -> Completion:
        completion = self.inner.generate(prompt, tools)
        self.meter.add(completion.usage)
        return completion

    def generate_structured(
        self, prompt: str, schema: JSON, max_retries: int
    ) -> JSON:
        payload = self.inner.generate_structured(prompt, schema, max_retries)
        self.meter.add({})
        return payload


@dataclass(frozen=True)
class LLMWiring:
    # local = 免费档本地模型（owner 裁决：产品分层级；本地路径零 API 费）
    mode: Literal["offline", "anthropic", "local"]
    model: str | None = None
    api_key: str | None = None
    usd_per_mtok_input: float | None = None
    usd_per_mtok_output: float | None = None
    base_url: str | None = None  # mode=local 必填（OpenAI 兼容端点）


@dataclass(frozen=True)
class LocalTier:
    """免费档本地模型清单（全部来自运行环境配置，NEVER 硬编码）。"""

    base_url: str
    models: tuple[str, ...]
    default_model: str
    api_key: str | None


def load_local_tier(env: dict[str, str] | None = None) -> LocalTier:
    source = env if env is not None else dict(os.environ)
    base_url = source.get("FLINT_LOCAL_BASE_URL")
    models_raw = source.get("FLINT_LOCAL_MODELS")
    default_model = source.get("FLINT_FREE_TIER_MODEL")
    missing = [
        name
        for name, value in (
            ("FLINT_LOCAL_BASE_URL", base_url),
            ("FLINT_LOCAL_MODELS", models_raw),
            ("FLINT_FREE_TIER_MODEL", default_model),
        )
        if not value
    ]
    if missing:
        raise ProviderWiringError(
            f"local tier requires runtime config: missing {missing}"
        )
    assert base_url is not None and models_raw is not None
    assert default_model is not None
    models = tuple(m.strip() for m in models_raw.split(",") if m.strip())
    if default_model not in models:
        raise ProviderWiringError(
            f"FLINT_FREE_TIER_MODEL {default_model!r} not in "
            f"FLINT_LOCAL_MODELS {list(models)}"
        )
    return LocalTier(
        base_url=base_url, models=models, default_model=default_model,
        api_key=source.get("FLINT_LOCAL_API_KEY") or None,
    )


@dataclass(frozen=True)
class AnthropicTier:
    """付费档 Claude 配置（全部来自运行环境，NEVER 硬编码；价目 NEVER 内置
    价表——cost 实值出处 = 环境变量单价 + API 返回 usage）。"""

    api_key: str
    model: str
    usd_per_mtok_input: float
    usd_per_mtok_output: float


def load_anthropic_tier(env: dict[str, str] | None = None) -> AnthropicTier:
    """严格从四个环境变量读付费档配置；缺任一 → ProviderWiringError。
    报错只列缺失变量名，NEVER 回显 key 明文；key NEVER 写日志/硬编码。"""
    source = env if env is not None else dict(os.environ)
    api_key = source.get("FLINT_ANTHROPIC_API_KEY")
    model = source.get("FLINT_PAID_TIER_MODEL")
    price_in = source.get("FLINT_ANTHROPIC_USD_PER_MTOK_INPUT")
    price_out = source.get("FLINT_ANTHROPIC_USD_PER_MTOK_OUTPUT")
    missing = [
        name
        for name, value in (
            ("FLINT_ANTHROPIC_API_KEY", api_key),
            ("FLINT_PAID_TIER_MODEL", model),
            ("FLINT_ANTHROPIC_USD_PER_MTOK_INPUT", price_in),
            ("FLINT_ANTHROPIC_USD_PER_MTOK_OUTPUT", price_out),
        )
        if not value
    ]
    if missing:
        # NEVER 回显任何变量的值（尤其 key）——只列缺失变量名
        raise ProviderWiringError(
            f"anthropic (paid) tier requires runtime config: missing {missing}"
        )
    assert api_key is not None and model is not None
    assert price_in is not None and price_out is not None
    try:
        usd_in = float(price_in)
        usd_out = float(price_out)
    except ValueError as err:
        raise ProviderWiringError(
            "anthropic price vars must be numeric usd_per_mtok "
            "(FLINT_ANTHROPIC_USD_PER_MTOK_INPUT / _OUTPUT)"
        ) from err
    return AnthropicTier(
        api_key=api_key, model=model,
        usd_per_mtok_input=usd_in, usd_per_mtok_output=usd_out,
    )


@dataclass(frozen=True)
class CloudTier:
    """通用 OpenAI 兼容云端档配置（DeepSeek/GPT，V2-002）。

    全部来自运行环境；base_url 厂商内置默认（可选 env 覆盖）；价目双项是 cost 记账
    出处，NEVER 内置价表。key NEVER 硬编码/写日志/回显。
    """

    api_key: str
    model: str
    base_url: str
    usd_per_mtok_input: float
    usd_per_mtok_output: float


_DEEPSEEK_DEFAULT_BASE_URL = "https://api.deepseek.com"
_OPENAI_DEFAULT_BASE_URL = "https://api.openai.com/v1"


def _load_cloud_tier(
    source: dict[str, str], prefix: str, default_base_url: str
) -> CloudTier:
    """严格读 {prefix}_API_KEY/MODEL/USD_PER_MTOK_INPUT/_OUTPUT；base_url 厂商默认
    （{prefix}_BASE_URL 可选覆盖）。缺任一/非数字价 → ProviderWiringError，报错只列
    变量名，NEVER 回显任何值（尤其 key）。"""
    api_key = source.get(f"{prefix}_API_KEY")
    model = source.get(f"{prefix}_MODEL")
    price_in = source.get(f"{prefix}_USD_PER_MTOK_INPUT")
    price_out = source.get(f"{prefix}_USD_PER_MTOK_OUTPUT")
    missing = [
        name
        for name, value in (
            (f"{prefix}_API_KEY", api_key),
            (f"{prefix}_MODEL", model),
            (f"{prefix}_USD_PER_MTOK_INPUT", price_in),
            (f"{prefix}_USD_PER_MTOK_OUTPUT", price_out),
        )
        if not value
    ]
    if missing:
        # NEVER 回显任何变量的值（尤其 key）——只列缺失变量名
        raise ProviderWiringError(
            f"{prefix} cloud tier requires runtime config: missing {missing}"
        )
    assert api_key is not None and model is not None
    assert price_in is not None and price_out is not None
    try:
        usd_in = float(price_in)
        usd_out = float(price_out)
    except ValueError as err:
        raise ProviderWiringError(
            f"{prefix} price vars must be numeric usd_per_mtok "
            f"({prefix}_USD_PER_MTOK_INPUT / _OUTPUT)"
        ) from err
    base_url = source.get(f"{prefix}_BASE_URL") or default_base_url
    return CloudTier(
        api_key=api_key, model=model, base_url=base_url,
        usd_per_mtok_input=usd_in, usd_per_mtok_output=usd_out,
    )


def load_deepseek_tier(env: dict[str, str] | None = None) -> CloudTier:
    """DeepSeek 云端档（FLINT_DEEPSEEK_*；base_url 默认 api.deepseek.com）。"""
    source = env if env is not None else dict(os.environ)
    return _load_cloud_tier(source, "FLINT_DEEPSEEK", _DEEPSEEK_DEFAULT_BASE_URL)


def load_openai_tier(env: dict[str, str] | None = None) -> CloudTier:
    """OpenAI 云端档（FLINT_OPENAI_*；base_url 默认 api.openai.com/v1）。"""
    source = env if env is not None else dict(os.environ)
    return _load_cloud_tier(source, "FLINT_OPENAI", _OPENAI_DEFAULT_BASE_URL)


def wire_provider(
    wiring: LLMWiring,
    offline_inner: LLMProvider,
    http_client: httpx.Client | None = None,
) -> MeteredOfflineProvider | MeteredAnthropicProvider | LocalProviderT:
    if wiring.mode == "offline":
        return MeteredOfflineProvider(inner=offline_inner)
    if wiring.mode == "local":
        from flint.llm.local import LocalProvider

        local_missing = [
            name
            for name, value in (
                ("model", wiring.model), ("base_url", wiring.base_url),
            )
            if value is None
        ]
        if local_missing:
            raise ProviderWiringError(
                f"local mode requires explicit config: missing {local_missing}"
            )
        assert wiring.model is not None and wiring.base_url is not None
        return LocalProvider(
            base_url=wiring.base_url, model=wiring.model,
            http_client=http_client, api_key=wiring.api_key,
        )
    missing = [
        name
        for name, value in (
            ("model", wiring.model),
            ("api_key", wiring.api_key),
            ("usd_per_mtok_input", wiring.usd_per_mtok_input),
            ("usd_per_mtok_output", wiring.usd_per_mtok_output),
        )
        if value is None
    ]
    if missing:
        raise ProviderWiringError(
            "anthropic mode requires explicit config (cost accounting has "
            f"no built-in price table): missing {missing}"
        )
    assert wiring.model is not None and wiring.api_key is not None
    assert wiring.usd_per_mtok_input is not None
    assert wiring.usd_per_mtok_output is not None
    return MeteredAnthropicProvider(
        api_key=wiring.api_key,
        model=wiring.model,
        pricing=ModelPricing(
            usd_per_mtok_input=wiring.usd_per_mtok_input,
            usd_per_mtok_output=wiring.usd_per_mtok_output,
        ),
        http_client=http_client,
    )
