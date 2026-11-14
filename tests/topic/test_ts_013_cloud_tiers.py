"""TS-013：云端档读取器 load_deepseek_tier/load_openai_tier（仿 load_anthropic_tier）。

严格读 FLINT_DEEPSEEK_*/FLINT_OPENAI_*，缺任一 → ProviderWiringError 只列缺失变量名、
NEVER 回显 key；base_url 厂商内置默认（可选 env 覆盖）。env 注入可测（CI 零联网）。
CloudOpenAIProvider（V2-002）由 tier 构造、模型无关接 combo 生成器。
"""
from __future__ import annotations

import pytest

from flint.llm.cloud import CloudOpenAIProvider
from flint.llm.production import (
    CloudTier,
    ProviderWiringError,
    load_deepseek_tier,
    load_openai_tier,
)

_DEEPSEEK = {
    "FLINT_DEEPSEEK_API_KEY": "sk-deepseek-SECRET-never-echo",
    "FLINT_DEEPSEEK_MODEL": "deepseek-chat",
    "FLINT_DEEPSEEK_USD_PER_MTOK_INPUT": "0.28",
    "FLINT_DEEPSEEK_USD_PER_MTOK_OUTPUT": "0.42",
}
_OPENAI = {
    "FLINT_OPENAI_API_KEY": "sk-openai-SECRET-never-echo",
    "FLINT_OPENAI_MODEL": "gpt-5",
    "FLINT_OPENAI_USD_PER_MTOK_INPUT": "1.25",
    "FLINT_OPENAI_USD_PER_MTOK_OUTPUT": "10.0",
}


def test_deepseek_loads_all_with_vendor_default_base_url() -> None:
    tier = load_deepseek_tier(dict(_DEEPSEEK))
    assert isinstance(tier, CloudTier)
    assert tier.api_key == "sk-deepseek-SECRET-never-echo"
    assert tier.model == "deepseek-chat"
    assert tier.usd_per_mtok_input == 0.28 and tier.usd_per_mtok_output == 0.42
    assert "deepseek.com" in tier.base_url          # 厂商内置默认


def test_openai_loads_all_with_vendor_default_base_url() -> None:
    tier = load_openai_tier(dict(_OPENAI))
    assert tier.model == "gpt-5"
    assert tier.usd_per_mtok_input == 1.25 and tier.usd_per_mtok_output == 10.0
    assert "openai.com" in tier.base_url


@pytest.mark.parametrize("drop", list(_DEEPSEEK.keys()))
def test_deepseek_missing_any_raises_listing_name(drop: str) -> None:
    env = dict(_DEEPSEEK)
    del env[drop]
    with pytest.raises(ProviderWiringError, match=drop):
        load_deepseek_tier(env)


@pytest.mark.parametrize("drop", list(_OPENAI.keys()))
def test_openai_missing_any_raises_listing_name(drop: str) -> None:
    env = dict(_OPENAI)
    del env[drop]
    with pytest.raises(ProviderWiringError, match=drop):
        load_openai_tier(env)


def test_error_never_echoes_key() -> None:
    for loader, full in ((load_deepseek_tier, _DEEPSEEK), (load_openai_tier, _OPENAI)):
        env = dict(full)
        key = env[next(k for k in env if k.endswith("_API_KEY"))]
        del env[next(k for k in env if k.endswith("_MODEL"))]
        with pytest.raises(ProviderWiringError) as exc:
            loader(env)
        assert key not in str(exc.value)


def test_non_numeric_price_raises_without_key_echo() -> None:
    env = dict(_DEEPSEEK)
    env["FLINT_DEEPSEEK_USD_PER_MTOK_INPUT"] = "not-a-number"
    with pytest.raises(ProviderWiringError) as exc:
        load_deepseek_tier(env)
    msg = str(exc.value)
    assert "sk-deepseek-SECRET-never-echo" not in msg
    assert "USD_PER_MTOK" in msg


def test_empty_string_treated_as_missing() -> None:
    env = dict(_OPENAI)
    env["FLINT_OPENAI_MODEL"] = ""
    with pytest.raises(ProviderWiringError, match="FLINT_OPENAI_MODEL"):
        load_openai_tier(env)


def test_optional_base_url_override() -> None:
    env = dict(_DEEPSEEK)
    env["FLINT_DEEPSEEK_BASE_URL"] = "https://custom.example/v1"
    assert load_deepseek_tier(env).base_url == "https://custom.example/v1"


def test_cloud_provider_builds_from_tier_model_agnostic() -> None:
    # tier → CloudOpenAIProvider（模型无关；付费按注入价目计量，不联网构造）
    from flint.llm.production import ModelPricing

    tier = load_deepseek_tier(dict(_DEEPSEEK))
    provider = CloudOpenAIProvider(
        base_url=tier.base_url, model=tier.model, api_key=tier.api_key,
        pricing=ModelPricing(tier.usd_per_mtok_input, tier.usd_per_mtok_output))
    assert provider.model == "deepseek-chat"
    # 实现冻结协议 LLMProvider（generate/generate_structured 面）
    assert hasattr(provider, "generate_structured")
