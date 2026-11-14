"""通用 OpenAI 兼容云端适配器（V2-002 多提供商地基）。

与 LocalProvider **同传输**（OpenAI `/chat/completions` + 结构化降级环），差别两点：
- **api_key 必填**：云端恒需鉴权，缺 → CloudProviderMisconfigured（NEVER 回显
  key 值）；只从构造参数注入（上游从环境读），NEVER 硬编码 / NEVER 写日志。
- **计费按注入的 ModelPricing**（非 FREE）：cost_usd 真实计量。价目遵
  production.py 纪律——**MUST 由配置注入，NEVER 内置价表猜价**。

**NEVER 内置任何具体 provider 名 / base_url / key / 价目**——全由构造注入。
tier→provider 映射属 owner 决策③（docs/前端-owner决策备忘.md），不在本适配器内。
"""
from __future__ import annotations

import httpx

from flint.llm.local import DEFAULT_MAX_TOKENS, DEFAULT_TIMEOUT, LocalProvider
from flint.llm.production import ModelPricing, UsageMeter


class CloudProviderMisconfigured(Exception):
    """云端适配器配置缺失（如 api_key 空）——NEVER 回显 key 值。"""


class CloudOpenAIProvider(LocalProvider):
    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str,
        pricing: ModelPricing,
        *,
        http_client: httpx.Client | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = 0.2,
        timeout: float = DEFAULT_TIMEOUT,
        disable_reasoning: bool = False,
    ) -> None:
        if not api_key:
            raise CloudProviderMisconfigured(
                "cloud provider requires api_key (env-injected upstream, "
                "NEVER hardcoded/logged)"
            )
        super().__init__(
            base_url=base_url,
            model=model,
            http_client=http_client,
            api_key=api_key,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=timeout,
            disable_reasoning=disable_reasoning,
        )
        # 覆盖 LocalProvider 的 FREE 计量：云端按注入价目真实计费
        self.meter = UsageMeter(pricing=pricing)
