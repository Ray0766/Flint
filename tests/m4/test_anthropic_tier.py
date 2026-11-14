"""付费档 Claude 读取器 load_anthropic_tier（owner 任务）：严格从四个环境
变量读，缺任一 → ProviderWiringError，报错信息 NEVER 回显 key。

env 注入可测（不读真实进程环境，CI 零外部依赖）。
"""
from __future__ import annotations

import pytest

from flint.llm.production import (
    AnthropicTier,
    ProviderWiringError,
    load_anthropic_tier,
)

_FULL = {
    "FLINT_ANTHROPIC_API_KEY": "sk-ant-SECRET-value-do-not-echo",
    "FLINT_PAID_TIER_MODEL": "claude-opus-4-8",
    "FLINT_ANTHROPIC_USD_PER_MTOK_INPUT": "5.0",
    "FLINT_ANTHROPIC_USD_PER_MTOK_OUTPUT": "25.0",
}


def test_loads_all_four_vars() -> None:
    tier = load_anthropic_tier(dict(_FULL))
    assert isinstance(tier, AnthropicTier)
    assert tier.api_key == "sk-ant-SECRET-value-do-not-echo"
    assert tier.model == "claude-opus-4-8"
    assert tier.usd_per_mtok_input == 5.0
    assert tier.usd_per_mtok_output == 25.0


@pytest.mark.parametrize("drop", [
    "FLINT_PAID_TIER_MODEL",
    "FLINT_ANTHROPIC_USD_PER_MTOK_INPUT",
    "FLINT_ANTHROPIC_USD_PER_MTOK_OUTPUT",
    "FLINT_ANTHROPIC_API_KEY",
])
def test_missing_any_var_raises_wiring_error(drop: str) -> None:
    env = dict(_FULL)
    del env[drop]
    with pytest.raises(ProviderWiringError, match=drop):
        load_anthropic_tier(env)


def test_error_never_echoes_key_value() -> None:
    # 缺 model（key 在场）：报错必须只列缺失变量名，NEVER 含 key 明文
    env = dict(_FULL)
    del env["FLINT_PAID_TIER_MODEL"]
    with pytest.raises(ProviderWiringError) as exc:
        load_anthropic_tier(env)
    assert "sk-ant-SECRET-value-do-not-echo" not in str(exc.value)


def test_non_numeric_price_raises_without_key_echo() -> None:
    env = dict(_FULL)
    env["FLINT_ANTHROPIC_USD_PER_MTOK_INPUT"] = "not-a-number"
    with pytest.raises(ProviderWiringError) as exc:
        load_anthropic_tier(env)
    msg = str(exc.value)
    assert "sk-ant-SECRET-value-do-not-echo" not in msg
    assert "USD_PER_MTOK" in msg


def test_empty_string_treated_as_missing() -> None:
    env = dict(_FULL)
    env["FLINT_PAID_TIER_MODEL"] = ""
    with pytest.raises(ProviderWiringError, match="FLINT_PAID_TIER_MODEL"):
        load_anthropic_tier(env)
