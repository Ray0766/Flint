"""JUDGE-04：GPT-5.6 三档接入（第二校准点与仲裁票）。

## 复用，不另建

请求路径继承 `flint/llm/cloud.py#CloudOpenAIProvider`（它自己继承 `LocalProvider`，
加的是「api_key 必填 + 按注入价目真实计费」）。本模块只加**角色分工**、
**逐笔账**与**余额闸**。

## 三档按用途分工，NEVER 同级互校

| 角色 | 模型 | 用途 |
|---|---|---|
| `bulk` | `gpt-5.6-luna` | 大批量低难度分类；DeepSeek 的**产能备胎** |
| `calibration` | `gpt-5.6-terra` | **校准票**（默认） |
| `arbitration` | `gpt-5.6-sol` | **仲裁票**，三家分歧时才动 |

**校准票为什么不能用 Luna**：校准票是「当裁判的裁判」，必须至少与被校准者
同级或更强。Luna 与 DeepSeek V4 Flash 同级——拿它校准，**一致也不代表对、
不一致也无法归因**。而整批只需 1~3 次校准，Luna 相对 Terra 只省不到 3 美元，
换不来这个代价。

模型 id 是 steward 2026-08-04 实测确认账号内可见的三个，**NEVER 再猜**。

## 价目 NEVER 内置：没配价的档 = 不可用

三档单价全从环境读（`FLINT_OPENAI_{ROLE}_USD_PER_MTOK_INPUT/_OUTPUT`）。
**NEVER 拿卡面上的数当默认值**：卡面是人写的一句话，环境变量是这台机器的事实，
两者不是一回事——把卡面的数当默认，账就会按一个没人确认过的价记。

## 本地备胎优先于云端备胎

产能不够时先用本机 `deepseek-r1:32b`（零成本），`gpt-5.6-luna` 是**第二**备胎。
两个都不可用时返回**空**，NEVER 回落到某个默认模型。

## 余额将尽照实降级

`BalanceGuard` 在花超前拦下并**标注降级原因**；真花超了抛错——
静默花超会让账单上出现没人预期的一笔。
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Final, cast

from flint.llm.cloud import CloudOpenAIProvider
from flint.llm.deepseek import UsageLedger, UsageRecord, _RecordingClient, breakdown_from_usage
from flint.llm.production import ModelPricing, ProviderWiringError
from flint.llm.registry import ProviderEntry, ProviderRegistry

if TYPE_CHECKING:
    import httpx

ROLE_BULK: Final[str] = "bulk"
ROLE_CALIBRATION: Final[str] = "calibration"
ROLE_ARBITRATION: Final[str] = "arbitration"

OPENAI_BASE_URL: Final[str] = "https://api.openai.com/v1"

# steward 2026-08-04 实测确认账号内可见的三个 id。**NEVER 再猜。**
GPT_MODELS: Final[dict[str, str]] = {
    ROLE_BULK: "gpt-5.6-luna",
    ROLE_CALIBRATION: "gpt-5.6-terra",
    ROLE_ARBITRATION: "gpt-5.6-sol",
}

ROLE_PURPOSE: Final[dict[str, str]] = {
    ROLE_BULK: "大批量低难度分类（如英文文案初筛）与 DeepSeek 的产能备胎",
    ROLE_CALIBRATION: "校准票（默认）：当裁判的裁判，须至少与被校准者同级或更强",
    ROLE_ARBITRATION: "仲裁票：只在三家分歧时才动，它的价就是它的使用纪律",
}

ROLE_WHEN: Final[dict[str, str]] = {
    ROLE_BULK: "bulk_or_backup",
    ROLE_CALIBRATION: "default_calibration",
    ROLE_ARBITRATION: "three_way_disagreement",
}

# owner 指定的本机备胎（已在 ollama 里，零成本）
LOCAL_BACKUP: Final[str] = "local:deepseek-r1:32b"


class GptRoleUnavailable(KeyError):
    """这一档没配价，因此不可用——NEVER 拿卡面上的数顶上。"""


@dataclass(frozen=True)
class GptRoleSpec:
    role: str
    model: str
    pricing: ModelPricing
    purpose: str
    when: str


class _RoleTable(dict[str, GptRoleSpec]):
    """取不到的档报错时**说清缺哪个变量**，而不是一个光秃秃的 KeyError。"""

    def __missing__(self, role: str) -> GptRoleSpec:
        raise GptRoleUnavailable(
            f"{role} 档不可用：缺 FLINT_OPENAI_{role.upper()}_USD_PER_MTOK_INPUT "
            f"/ _OUTPUT。没配价的档 NEVER 按卡面上的数记账"
        )


def load_gpt_roles(
    env: dict[str, str] | None = None, *, require_key: bool = False
) -> _RoleTable:
    """读三档配置。**只收齐了价的档进表**；key 只在 `require_key` 时一并校验。"""
    import os

    source = env if env is not None else dict(os.environ)
    if require_key and not source.get("FLINT_OPENAI_API_KEY"):
        # NEVER 回显任何值（尤其 key）——只列缺失变量名
        raise ProviderWiringError("gpt 档缺配置：['FLINT_OPENAI_API_KEY']")
    table = _RoleTable()
    for role, model in GPT_MODELS.items():
        raw_in = source.get(f"FLINT_OPENAI_{role.upper()}_USD_PER_MTOK_INPUT")
        raw_out = source.get(f"FLINT_OPENAI_{role.upper()}_USD_PER_MTOK_OUTPUT")
        if not raw_in or not raw_out:
            continue
        try:
            pricing = ModelPricing(usd_per_mtok_input=float(raw_in),
                                   usd_per_mtok_output=float(raw_out))
        except ValueError as err:
            raise ProviderWiringError(
                f"gpt {role} 档单价必须是数字"
                f"（FLINT_OPENAI_{role.upper()}_USD_PER_MTOK_INPUT / _OUTPUT）"
            ) from err
        table[role] = GptRoleSpec(
            role=role, model=source.get(f"FLINT_OPENAI_{role.upper()}_MODEL") or model,
            pricing=pricing, purpose=ROLE_PURPOSE[role], when=ROLE_WHEN[role])
    return table


def choose_capacity_backup(*, local_available: bool, cloud_available: bool) -> list[str]:
    """产能备胎的**顺序**：本机在前，云端在后。

    两个都不可用时返回空清单——NEVER 回落到某个默认模型：
    回落等于替 owner 决定了这笔钱花在哪。
    """
    order: list[str] = []
    if local_available:
        order.append(LOCAL_BACKUP)
    if cloud_available:
        order.append(GPT_MODELS[ROLE_BULK])
    return order


class BalanceExhausted(Exception):
    """余额花光了还要花——静默花超会让账单上出现没人预期的一笔。"""


@dataclass
class BalanceGuard:
    """余额闸。`degraded` 与 `note` 是**给产物看的**：降级要照实标注。"""

    budget_usd: Decimal
    spent_usd: Decimal = Decimal(0)
    reserve_usd: Decimal = Decimal("0.5")
    degraded: bool = False
    note: str = ""

    def may_spend(self, amount: Decimal) -> bool:
        """还花得起吗。花不起就**标降级并写清原因**，NEVER 静默返回 False。"""
        if self.spent_usd + amount + self.reserve_usd <= self.budget_usd:
            return True
        self.degraded = True
        self.note = (
            f"余额将尽：预算 ${self.budget_usd}、已花 ${self.spent_usd}、"
            f"本次需 ${amount}（留 ${self.reserve_usd} 备用）。"
            "降级为不调用该档，产物照实标注未校准"
        )
        return False

    def charge(self, amount: Decimal) -> None:
        if self.spent_usd + amount > self.budget_usd:
            raise BalanceExhausted(
                f"预算 ${self.budget_usd} 已花 ${self.spent_usd}，再花 ${amount} 会超")
        self.spent_usd += amount


class OpenAICompatProvider(CloudOpenAIProvider):
    """GPT 三档共用的适配器。请求路径继承自 `CloudOpenAIProvider`。

    与 `DeepSeekProvider` 同一本账（同一个 `UsageLedger` 类型）——
    两本账会让「这个月一共花了多少」变成一道加法题，而加法题会算错。
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        pricing: ModelPricing,
        role: str = ROLE_CALIBRATION,
        base_url: str = OPENAI_BASE_URL,
        http_client: Any = None,
        guard: BalanceGuard | None = None,
        **kwargs: Any,
    ) -> None:
        import httpx as _httpx

        inner = http_client or _httpx.Client(
            timeout=600.0, headers={"Authorization": f"Bearer {api_key}"})
        self.recorder = _RecordingClient(inner)
        super().__init__(
            base_url=base_url, model=model,
            http_client=cast("httpx.Client", self.recorder),
            api_key=api_key, pricing=pricing, **kwargs)
        self.role = role
        self.guard = guard
        self.ledger = UsageLedger()

    def generate_with_purpose(self, prompt: str, *, purpose: str) -> Any:
        """带用途标签调用一次并记一笔账。**账上带档位**——三档单价差 25 倍，

        混在一起没法归因「这个月的钱花在哪一档上」。
        """
        completion = self.generate(prompt, tools=None)
        breakdown = breakdown_from_usage(self.recorder.last_usage)
        cost = (
            Decimal(breakdown.input_tokens)
            * Decimal(str(self.pricing_in))
            + Decimal(breakdown.output_tokens) * Decimal(str(self.pricing_out))
        ) / Decimal(1_000_000)
        if self.guard is not None:
            self.guard.charge(cost)
        self.ledger.append(UsageRecord(
            call_id=f"{self.model}#{len(self.ledger.records()) + 1}",
            model=f"{self.model}({self.role})", purpose=purpose,
            input_tokens=breakdown.input_tokens, output_tokens=breakdown.output_tokens,
            cache_hit_tokens=0, cache_miss_tokens=breakdown.input_tokens,
            cost_usd=cost, pricing_version=f"gpt:{self.role}:"
                                           f"{self.pricing_in}/{self.pricing_out}",
        ))
        return completion

    @property
    def pricing_in(self) -> float:
        return self.meter.pricing.usd_per_mtok_input

    @property
    def pricing_out(self) -> float:
        return self.meter.pricing.usd_per_mtok_output


def register_gpt_roles(
    registry: ProviderRegistry,
    *,
    env: dict[str, str] | None = None,
    http_client: Any = None,
) -> None:
    """把**配齐了价的档**注册进既有 registry。

    没配价的档 NEVER 进表——注册了却不能用，比没注册更难查。
    """
    import os

    source = env if env is not None else dict(os.environ)
    api_key = source.get("FLINT_OPENAI_API_KEY") or ""
    for role, spec in load_gpt_roles(source).items():
        def factory(spec: GptRoleSpec = spec, role: str = role) -> Any:
            return OpenAICompatProvider(
                api_key=api_key, model=spec.model, pricing=spec.pricing,
                role=role, http_client=http_client)

        registry.register(ProviderEntry(
            provider_id=f"gpt:{role}", tier="paid", factory=factory))
