"""JUDGE-01：DeepSeek 适配器（付费档）+ 用量账本。

## 不新建调用路径

DeepSeek 是 **OpenAI 兼容**端点，而仓里已经有一个 OpenAI 兼容适配器：
`flint/llm/local.py#LocalProvider`（免费本地档走的就是它）。本类**继承**它——
再写一条请求路径的话，两条路径的重试语义、错误分类、栅栏剥离迟早会分叉，
而分叉之后没人知道哪条是对的。

本类只加 `LocalProvider` 没有的三件事：

1. **真价目**：`LocalProvider` 写死 `UsageMeter(pricing=FREE)`——对本地是对的
   （本地推理零 API 费），对付费档是错的；
2. **缓存命中分开记**：`LocalProvider` 把 usage 压成 input/output 两项，
   丢掉了 `prompt_cache_hit_tokens`。DeepSeek 的命中价比未命中低两个数量级，
   混在一起记出来的账会与账单对不上；
3. **用途标签 + append-only 账本**：一笔钱要能对上是哪次运行、干什么用的。

拿到原始 usage 的办法是**注入一个会记住上一次响应体的 client**
（`_RecordingClient`），而不是去 `local.py` 里开一个钩子——那超出本卡的改动面。

## 价目 NEVER 内置

三项单价全从环境读（`FLINT_DEEPSEEK_USD_PER_MTOK_INPUT` / `_OUTPUT` /
`_CACHE_HIT`）。账上的钱的出处 = 环境变量单价 × API 返回的 usage，
两头都能查（S2：数字必有出处）。

**没配命中价却出现了命中 → 报错**，NEVER 按未命中价顶上：顶上去的账会**高于**
真实账单，而账对不上时最难查的正是这种「差一点」。

## key

只从环境变量读（`FLINT_DEEPSEEK_API_KEY`），永不进代码、仓库、日志、账本。
缺配置时报错**只列变量名**，NEVER 回显任何值。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Final, cast

from flint.domain.models import JSON, Completion
from flint.llm.cloud import CloudOpenAIProvider
from flint.llm.production import ModelPricing, ProviderWiringError, UsageMeter, load_deepseek_tier
from flint.llm.registry import ProviderEntry, ProviderRegistry

if TYPE_CHECKING:
    import httpx

DEEPSEEK_PROVIDER_ID: Final[str] = "deepseek"
DEEPSEEK_BASE_URL: Final[str] = "https://api.deepseek.com"

_MTOK: Final[Decimal] = Decimal(1_000_000)


class CachePriceUnknown(Exception):
    """出现了缓存命中，但没配命中价——NEVER 按未命中价顶上。"""


@dataclass(frozen=True)
class DeepSeekPricing:
    """三项单价 + 口径版本。**版本由单价算出**：改了价，版本自动就变了，

    否则「口径版本」会变成一个要人记得手动改的字段，而没人会记得。
    """

    usd_per_mtok_input: float
    usd_per_mtok_output: float
    usd_per_mtok_cache_hit: float | None

    @property
    def version(self) -> str:
        hit = "none" if self.usd_per_mtok_cache_hit is None else self.usd_per_mtok_cache_hit
        return f"deepseek:{self.usd_per_mtok_input}/{self.usd_per_mtok_output}/{hit}"


def load_deepseek_pricing(
    env: dict[str, str] | None = None, *, require_key: bool = False
) -> DeepSeekPricing:
    """从环境读三项单价。命中价**可缺**——只在真出现命中时才成为必需。

    `require_key` 只在需要连带校验 key 时打开；报错只列变量名。
    """
    import os

    source = env if env is not None else dict(os.environ)
    missing = [
        name for name in ("FLINT_DEEPSEEK_USD_PER_MTOK_INPUT",
                          "FLINT_DEEPSEEK_USD_PER_MTOK_OUTPUT")
        if not source.get(name)
    ]
    if require_key and not source.get("FLINT_DEEPSEEK_API_KEY"):
        missing.append("FLINT_DEEPSEEK_API_KEY")
    if missing:
        # NEVER 回显任何变量的值（尤其 key）——只列缺失变量名
        raise ProviderWiringError(f"deepseek 档缺配置：{missing}")
    raw_hit = source.get("FLINT_DEEPSEEK_USD_PER_MTOK_CACHE_HIT")
    try:
        return DeepSeekPricing(
            usd_per_mtok_input=float(source["FLINT_DEEPSEEK_USD_PER_MTOK_INPUT"]),
            usd_per_mtok_output=float(source["FLINT_DEEPSEEK_USD_PER_MTOK_OUTPUT"]),
            usd_per_mtok_cache_hit=float(raw_hit) if raw_hit else None,
        )
    except ValueError as err:
        raise ProviderWiringError(
            "deepseek 单价必须是数字（FLINT_DEEPSEEK_USD_PER_MTOK_INPUT / "
            "_OUTPUT / _CACHE_HIT）"
        ) from err


@dataclass(frozen=True)
class UsageBreakdown:
    """一次调用的 token 分解。**命中与未命中分两栏**，加起来等于输入总数。"""

    input_tokens: int
    output_tokens: int
    cache_hit_tokens: int
    cache_miss_tokens: int


def breakdown_from_usage(usage: Any) -> UsageBreakdown:
    """按**录制件里的真实字段**解析（`fixtures/deepseek/`）。

    响应里没有缓存字段时两栏记 0 / 全部算未命中——**NEVER 编一个命中数**：
    编出来的数会让账看起来比真实更省。
    """
    raw = usage if isinstance(usage, dict) else {}
    prompt = int(raw.get("prompt_tokens", 0))
    completion = int(raw.get("completion_tokens", 0))
    has_cache_fields = "prompt_cache_hit_tokens" in raw or "prompt_cache_miss_tokens" in raw
    hit = int(raw.get("prompt_cache_hit_tokens", 0))
    miss = int(raw.get("prompt_cache_miss_tokens", prompt if not has_cache_fields else 0))
    if hit + miss != prompt:
        raise ValueError(
            f"命中 {hit} + 未命中 {miss} 对不上输入总数 {prompt}："
            "对不上就是解析错了，NEVER 静默放行"
        )
    return UsageBreakdown(
        input_tokens=prompt, output_tokens=completion,
        cache_hit_tokens=hit, cache_miss_tokens=miss,
    )


def cost_for(breakdown: UsageBreakdown, pricing: DeepSeekPricing) -> Decimal:
    """一次调用的钱。命中按命中价、未命中按未命中价、输出按输出价。

    用 `Decimal` 而不是 float：账要能相加对得上，而 float 的加法不满足结合律。
    """
    if breakdown.cache_hit_tokens and pricing.usd_per_mtok_cache_hit is None:
        raise CachePriceUnknown(
            f"这次调用有 {breakdown.cache_hit_tokens} 个命中 token，"
            "但没配 FLINT_DEEPSEEK_USD_PER_MTOK_CACHE_HIT。"
            "按未命中价顶上会让账高于真实账单——NEVER 那么做"
        )
    hit_price = Decimal(str(pricing.usd_per_mtok_cache_hit or 0))
    return (
        Decimal(breakdown.cache_miss_tokens) * Decimal(str(pricing.usd_per_mtok_input))
        + Decimal(breakdown.cache_hit_tokens) * hit_price
        + Decimal(breakdown.output_tokens) * Decimal(str(pricing.usd_per_mtok_output))
    ) / _MTOK


class LedgerImmutable(Exception):
    """试图改写一条已存在的用量记录。"""


@dataclass(frozen=True)
class UsageRecord:
    """一次调用的账。八项缺一不可——少任何一项，这笔就对不上账。"""

    call_id: str
    model: str
    purpose: str
    input_tokens: int
    output_tokens: int
    cache_hit_tokens: int
    cache_miss_tokens: int
    cost_usd: Decimal
    pricing_version: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "call_id": self.call_id, "model": self.model, "purpose": self.purpose,
            "input_tokens": self.input_tokens, "output_tokens": self.output_tokens,
            "cache_hit_tokens": self.cache_hit_tokens,
            "cache_miss_tokens": self.cache_miss_tokens,
            "cost_usd": str(self.cost_usd), "pricing_version": self.pricing_version,
        }


@dataclass
class UsageLedger:
    """append-only 用量账（与 `flint/billing/ledger.py` 同一条纪律：只增不改）。

    **没有** update / delete——对账时若两版都存在过，谁也说不清哪一版是真的。
    """

    _records: dict[str, UsageRecord] = field(default_factory=dict)
    _order: list[str] = field(default_factory=list)

    def append(self, record: UsageRecord) -> None:
        if record.call_id in self._records:
            raise LedgerImmutable(f"用量记录 {record.call_id} 已存在：账只增不改")
        self._records[record.call_id] = record
        self._order.append(record.call_id)

    def records(self) -> list[UsageRecord]:
        """**副本**，按写入顺序——改返回值 NEVER 影响账本。"""
        return [self._records[cid] for cid in self._order]

    def reconcile(self) -> dict[str, Any]:
        """对账：笔数 + 金额合计 + token 合计 + 口径版本集合。"""
        items = self.records()
        versions = sorted({r.pricing_version for r in items})
        return {
            "count": len(items),
            "total_usd": sum((r.cost_usd for r in items), Decimal(0)),
            "input_tokens": sum(r.input_tokens for r in items),
            "output_tokens": sum(r.output_tokens for r in items),
            "cache_hit_tokens": sum(r.cache_hit_tokens for r in items),
            "pricing_versions": versions,
            # 混用要报出来：两个口径的钱加在一起，那个和没有意义
            "mixed_pricing": len(versions) > 1,
        }


class _RecordingClient:
    """记住上一次响应体的 client 包装。

    存在的理由：`LocalProvider` 把 usage 压成 input/output 两项就丢掉了缓存字段，
    而本卡要按命中/未命中分开计价。包一层比在 `local.py` 里开钩子改动面小，
    且**请求路径一个字没变**。
    """

    def __init__(self, inner: Any) -> None:
        self._inner = inner
        self.posts: list[dict[str, Any]] = []
        self.last_usage: Any = None

    def post(self, url: str, json: dict[str, Any]) -> Any:
        response = self._inner.post(url, json=json)
        self.posts.append({"url": url, "body": json})
        if getattr(response, "status_code", 0) == 200:
            payload = response.json()
            self.last_usage = payload.get("usage") if isinstance(payload, dict) else None
        return response


@dataclass
class _CacheAwareMeter(UsageMeter):
    """累计计量：在既有 `UsageMeter` 上加两栏缓存 token，并按三档价算钱。

    继承而不是另写一个：`calls` / `input_tokens` / `output_tokens` 的语义
    与别的 provider 保持一致，报表那边不用分两种读法。
    """

    deepseek_pricing: DeepSeekPricing | None = None
    cache_hit_tokens: int = 0
    cache_miss_tokens: int = 0

    @property
    def cost_usd(self) -> float:
        if self.deepseek_pricing is None:
            return 0.0
        return float(cost_for(UsageBreakdown(
            input_tokens=self.input_tokens, output_tokens=self.output_tokens,
            cache_hit_tokens=self.cache_hit_tokens,
            cache_miss_tokens=self.cache_miss_tokens,
        ), self.deepseek_pricing))


class DeepSeekProvider(CloudOpenAIProvider):
    """DeepSeek 付费档。请求路径与云端纪律都继承自 `CloudOpenAIProvider`，

    本类只管**缓存分栏**与**逐笔账**。
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        pricing: DeepSeekPricing,
        base_url: str = DEEPSEEK_BASE_URL,
        http_client: Any = None,
        **kwargs: Any,
    ) -> None:
        import httpx

        inner = http_client or httpx.Client(
            timeout=600.0, headers={"Authorization": f"Bearer {api_key}"}
        )
        self.recorder = _RecordingClient(inner)
        model_pricing = ModelPricing(
            usd_per_mtok_input=pricing.usd_per_mtok_input,
            usd_per_mtok_output=pricing.usd_per_mtok_output,
        )
        super().__init__(
            # 形参标的是 httpx.Client，实参是等价的转发包装（只用到 `.post`）——
            # 包一层是为了拿到原始 usage，见 `_RecordingClient` 的 docstring
            base_url=base_url, model=model,
            http_client=cast("httpx.Client", self.recorder),
            api_key=api_key, pricing=model_pricing, **kwargs,
        )
        self.pricing = pricing
        self.ledger = UsageLedger()
        # 覆盖父类的两档计量：DeepSeek 的命中价是第三档，`ModelPricing` 放不下
        self.meter: _CacheAwareMeter = _CacheAwareMeter(
            pricing=model_pricing, deepseek_pricing=pricing)

    def generate_with_purpose(self, prompt: str, *, purpose: str) -> Completion:
        """带用途标签调用一次并记一笔账。

        `purpose` 是必填关键字：没有它，账本上会出现一笔说不清干什么用的钱，
        而那正是对账时最先被问到的一笔。
        """
        completion = self.generate(prompt, tools=None)
        breakdown = breakdown_from_usage(self.recorder.last_usage)
        cost = cost_for(breakdown, self.pricing)
        self.meter.cache_hit_tokens += breakdown.cache_hit_tokens
        self.meter.cache_miss_tokens += breakdown.cache_miss_tokens
        self.ledger.append(UsageRecord(
            call_id=f"{self.model}#{len(self.ledger.records()) + 1}",
            model=self.model, purpose=purpose,
            input_tokens=breakdown.input_tokens, output_tokens=breakdown.output_tokens,
            cache_hit_tokens=breakdown.cache_hit_tokens,
            cache_miss_tokens=breakdown.cache_miss_tokens,
            cost_usd=cost, pricing_version=self.pricing.version,
        ))
        return completion

    def structured_with_purpose(
        self, prompt: str, schema: JSON, max_retries: int, *, purpose: str
    ) -> JSON:
        """结构化路径同样记账。重试会多发几次请求，**每一次都记**——

        只记最后一次的话，账会低于真实账单，而重试正是费用最容易涨的地方。
        """
        before = len(self.recorder.posts)
        payload = self.generate_structured(prompt, schema, max_retries)
        attempts = len(self.recorder.posts) - before
        breakdown = breakdown_from_usage(self.recorder.last_usage)
        self.ledger.append(UsageRecord(
            call_id=f"{self.model}#{len(self.ledger.records()) + 1}",
            model=self.model, purpose=f"{purpose}(structured×{attempts})",
            input_tokens=breakdown.input_tokens, output_tokens=breakdown.output_tokens,
            cache_hit_tokens=breakdown.cache_hit_tokens,
            cache_miss_tokens=breakdown.cache_miss_tokens,
            cost_usd=cost_for(breakdown, self.pricing),
            pricing_version=self.pricing.version,
        ))
        return payload


def register_deepseek(
    registry: ProviderRegistry,
    *,
    env: dict[str, str] | None = None,
    http_client: Any = None,
) -> None:
    """注册进**既有** registry，tier=paid，工厂零参（配置在闭包里）。

    key 在闭包里，registry 本身不触碰它（`registry.py` 的原话：
    「本表不触碰 key，NEVER 读/存/记 key」）。
    """
    tier = load_deepseek_tier(env)
    pricing = load_deepseek_pricing(env)

    def factory() -> Any:
        return DeepSeekProvider(
            api_key=tier.api_key, model=tier.model, pricing=pricing,
            base_url=tier.base_url, http_client=http_client,
        )

    registry.register(ProviderEntry(
        provider_id=DEEPSEEK_PROVIDER_ID, tier="paid", factory=factory,
    ))
