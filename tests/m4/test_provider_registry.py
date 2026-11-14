"""V2-002 多提供商地基（监管夜间批 @2026-07-30，仅决策无关机制、零 key/网络/花钱）。

覆盖两件**纯机制**地基：
- flint/llm/registry.py：提供商注册表**骨架**（名→工厂映射 + tier 分组），**空**默认、
  NEVER 内置任何具体 provider/tier 映射/key——tier→provider 映射属 owner 决策③
  （docs/前端-owner决策备忘.md）。本测断言「默认为空」不变量。
- flint/llm/cloud.py：通用 OpenAI 兼容云端适配器（复用 LocalProvider 传输，差别 =
  api_key 必填 + 计费按注入 ModelPricing 非 FREE），NEVER 内置具体 provider/base_url/
  key/价目。全程 httpx.MockTransport 离线（零联网、零真 key、零花钱）。
"""
from __future__ import annotations

import httpx
import pytest

from flint.llm.cloud import CloudOpenAIProvider, CloudProviderMisconfigured
from flint.llm.production import FREE, ModelPricing
from flint.llm.registry import (
    ProviderAlreadyRegistered,
    ProviderEntry,
    ProviderNotRegistered,
    ProviderRegistry,
)

pytestmark = pytest.mark.compose

PAID = ModelPricing(usd_per_mtok_input=1.0, usd_per_mtok_output=2.0)


def _openai_json(content: str = "ok", pin: int = 1000, pout: int = 1000) -> dict:
    return {
        "choices": [{"message": {"content": content, "tool_calls": []}}],
        "usage": {"prompt_tokens": pin, "completion_tokens": pout},
    }


def _mock_client() -> httpx.Client:
    def respond(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_openai_json())
    return httpx.Client(transport=httpx.MockTransport(respond))


class _Fake:
    """最小 LLMProvider 结构桩（仅供注册表测试，不联网）。"""

    def generate(self, prompt: str, tools: list | None) -> object:
        return object()

    def generate_structured(
        self, prompt: str, schema: object, max_retries: int
    ) -> object:
        return {}


# ── 注册表骨架 ───────────────────────────────────────────────


def test_registry_empty_by_default_never_prewires_providers() -> None:
    """决策③不变量：注册表**空**默认，NEVER 内置任何具体 provider/tier 映射。"""
    assert ProviderRegistry().available() == []


def test_register_then_get_returns_factory_product() -> None:
    reg = ProviderRegistry()
    fake = _Fake()
    reg.register(ProviderEntry("acme", "paid", lambda: fake))
    assert reg.get("acme") is fake
    assert reg.available() == ["acme"]
    assert reg.tier_of("acme") == "paid"


def test_duplicate_registration_raises() -> None:
    reg = ProviderRegistry()
    reg.register(ProviderEntry("acme", "free", _Fake))
    with pytest.raises(ProviderAlreadyRegistered):
        reg.register(ProviderEntry("acme", "paid", _Fake))


def test_unknown_get_raises() -> None:
    reg = ProviderRegistry()
    with pytest.raises(ProviderNotRegistered):
        reg.get("nope")
    with pytest.raises(ProviderNotRegistered):
        reg.tier_of("nope")


def test_available_for_tier_filters_and_sorts() -> None:
    reg = ProviderRegistry()
    reg.register(ProviderEntry("z-free", "free", _Fake))
    reg.register(ProviderEntry("a-paid", "paid", _Fake))
    reg.register(ProviderEntry("m-free", "free", _Fake))
    assert reg.available_for_tier("free") == ["m-free", "z-free"]
    assert reg.available_for_tier("paid") == ["a-paid"]


# ── 通用 OpenAI 兼容云端适配器 ──────────────────────────────


def test_cloud_provider_requires_api_key() -> None:
    with pytest.raises(CloudProviderMisconfigured):
        CloudOpenAIProvider(
            base_url="https://cloud.example/v1", model="m",
            api_key="", pricing=PAID,
        )


def test_cloud_provider_meters_with_injected_pricing_not_free() -> None:
    """云端计费按注入 ModelPricing（非 FREE）：真实 cost_usd。"""
    provider = CloudOpenAIProvider(
        base_url="https://cloud.example/v1", model="m",
        api_key="test-key", pricing=PAID, http_client=_mock_client(),
    )
    completion = provider.generate("hi", tools=None)
    assert completion.text == "ok"
    # 1000 in × $1/M + 1000 out × $2/M = 0.001 + 0.002
    assert provider.meter.cost_usd == pytest.approx(0.003)
    assert provider.meter.cost_usd != FREE.usd_per_mtok_input


def test_cloud_provider_conforms_and_flows_through_registry() -> None:
    """云端适配器可经注册表工厂交付，且 LLMProvider 面完整。"""
    reg = ProviderRegistry()
    reg.register(ProviderEntry(
        "acme-cloud", "paid",
        lambda: CloudOpenAIProvider(
            base_url="https://cloud.example/v1", model="m",
            api_key="test-key", pricing=PAID, http_client=_mock_client(),
        ),
    ))
    provider = reg.get("acme-cloud")
    assert callable(provider.generate) and callable(provider.generate_structured)
    assert provider.generate("hi", tools=None).text == "ok"
