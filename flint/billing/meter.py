"""PAY-02：计费基准落地——按对话**实际 API 用量**算钱，价格从配置读。

## 基准是真实用量，不是「一次运行算一次钱」

owner 2026-08-04 裁决（DEC-024）：**计费基准 = 每次对话实际消耗的 API 用量**。
钱从 `flint/llm/deepseek.py#UsageRecord` 的真 token 数来——那是调用真发生之后
从响应体 `usage` 里读出来的，不是估的。

按次收费的话，一次问「今天几号」与一次跑满上下文的深度分析收一样的钱：
用户看不出自己为什么被收这么多，我们也说不清。

## 配置留空 = 整条计费路径关闭

与 `flint/billing/quota.py#BillingConfig` 同一条口径：单价（输入/输出两栏）、币种、
口径版本**任缺其一**都算未配置。未配置时 `price_usage` 返回 `None`——
**一分钱不算、一条账不记**，行为与接计费之前逐字相同。

**「配成 0」与「没配」分得开**：默认值是 `None` 不是 `0`。
配成 0 是一次决定（这一档免费），它照样出一笔 0 元的账；
没配是还没决定，它什么都不出。两者在账上长得不一样，才复盘得了。

## 金额恒服务端计算

`price_usage` 的签名里**没有** `amount` / `price` / `total` 这类入参，
模块里也没有任何从请求体读数的路径。前端传来的价格连进不来这个函数——
那不是「我们不信它」，是**它没有入口**。判据打在签名与源码上。

## 汇率必须带出处与时间戳

多币种时**显示价与结算价分离**：结算价按上游计价币种（与 API 账单同币种）记账，
显示价才换汇。汇率是 `FxRate(rate, source, at, quote)` 四件套，**四样都必填**：
一个裸的 `7.1` 说不出它是哪天、从哪来的，两个月后没人能复核那笔钱算得对不对。

账本里记的**恒是结算价**：记显示价的话，汇率一变，历史账就跟着变了。

## 零网关（S2-10 红线）

本模块 NEVER 接任何支付网关、NEVER 持有任何密钥。它只回答「这次该算多少钱」。
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from flint.billing.ledger import BillingEvent

if TYPE_CHECKING:  # pragma: no cover - 仅供类型，运行期不 import
    from collections.abc import Sequence

    from flint.domain.models import Principal
    from flint.llm.deepseek import UsageRecord

_MTOK = Decimal(1_000_000)

BILLING_OFF_NOTE = (
    "计费未配置（单价/币种/口径版本任缺其一）：本次一分钱不算、一条账不记，"
    "行为与接计费之前逐字相同"
)


@dataclass(frozen=True)
class MeterConfig:
    """计费配置。四项默认 `None` = 未配置 = 整条路径关闭。

    NEVER 在这里写默认价：一个内置默认价会在没人注意时变成实际收费口径，
    而它的出处只有代码本身（与 `quota.py#BillingConfig` 同一条纪律）。
    """

    price_per_mtok_input: Decimal | None = None
    price_per_mtok_output: Decimal | None = None
    currency: str | None = None
    pricing_version: str | None = None

    @property
    def configured(self) -> bool:
        """四项**全齐**才算配好。任缺其一都按未配置处理。

        半套配置比没有更危险：它会让一半的运行被算钱、另一半不算，
        而两边都以为自己是对的。
        """
        return None not in (
            self.price_per_mtok_input, self.price_per_mtok_output,
            self.currency, self.pricing_version,
        )


@dataclass(frozen=True)
class FxRate:
    """一次汇率取值：**数、出处、时间、报价方向**四样缺一不可。

    裸的一个数说不出它是哪天、从哪来的。两个月后要复核一笔钱算得对不对，
    缺任何一样都复核不了——那时那笔钱就只能认了。
    """

    rate: Decimal
    source: str
    at: datetime
    quote: str          # 形如 "USD/CNY"：从结算币种换到显示币种

    def __post_init__(self) -> None:
        if not self.source.strip():
            raise ValueError("汇率没有出处：NEVER 用一个来路不明的汇率算钱")
        if self.rate <= 0:
            raise ValueError(f"汇率必须为正，收到 {self.rate}")
        if "/" not in self.quote:
            raise ValueError(f"报价方向要写成 基准/目标（如 USD/CNY），收到 {self.quote}")

    @property
    def base(self) -> str:
        return self.quote.split("/", 1)[0]

    @property
    def target(self) -> str:
        return self.quote.split("/", 1)[1]


@dataclass(frozen=True)
class Charge:
    """一次对话该算的钱。frozen：算出来的金额 NEVER 在运行期被改写。

    结算价与显示价分离；用量明细一并带着——没有明细的金额没法复核。
    """

    job_id: str
    settle_amount: Decimal
    settle_currency: str
    display_amount: Decimal
    display_currency: str
    fx: FxRate | None
    call_count: int
    input_tokens: int
    output_tokens: int
    cache_hit_tokens: int
    pricing_version: str
    upstream_pricing_versions: tuple[str, ...]
    upstream_mixed_pricing: bool


def price_usage(
    usage: Sequence[UsageRecord],
    *,
    job_id: str,
    config: MeterConfig,
    fx: FxRate | None = None,
) -> Charge | None:
    """按真实用量算这次对话的钱。未配置返回 `None`（整条路径关闭）。

    **签名里没有金额入参**——调用方给不进来一个价格（acceptance③）。
    """
    if not config.configured:
        return None
    assert config.price_per_mtok_input is not None      # configured 已保证
    assert config.price_per_mtok_output is not None
    assert config.currency is not None
    assert config.pricing_version is not None

    records = list(usage)
    input_tokens = sum(r.input_tokens for r in records)
    output_tokens = sum(r.output_tokens for r in records)
    settle = (
        Decimal(input_tokens) / _MTOK * config.price_per_mtok_input
        + Decimal(output_tokens) / _MTOK * config.price_per_mtok_output
    )

    display_amount, display_currency = settle, config.currency
    if fx is not None:
        if fx.base != config.currency:
            raise ValueError(
                f"汇率报价方向对不上结算币种：结算 {config.currency}，"
                f"而汇率是 {fx.quote}。拿错方向的汇率算出来的显示价是个假数"
            )
        display_amount, display_currency = settle * fx.rate, fx.target

    versions = tuple(sorted({r.pricing_version for r in records}))
    return Charge(
        job_id=job_id,
        settle_amount=settle,
        settle_currency=config.currency,
        display_amount=display_amount,
        display_currency=display_currency,
        fx=fx,
        call_count=len(records),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_hit_tokens=sum(r.cache_hit_tokens for r in records),
        pricing_version=config.pricing_version,
        upstream_pricing_versions=versions,
        # 上游混了两个口径时报出来：两个口径的 token 单价不同，
        # token 合计仍然对，但拿它去乘一个单价得到的钱没有意义。
        upstream_mixed_pricing=len(versions) > 1,
    )


def charge_event_id(*, job_id: str, owner: Principal, pricing_version: str) -> str:
    """计费事件 id **由作业决定**，不是每次算钱新造一个。

    新造一个的话，同一次作业重放会写进两条账（重复扣费）。
    由作业决定之后，第二次落账在 `BillingLedger.append` 那里直接被拒
    （`LedgerImmutable`）——幂等的完整形态在 PAY-03，这里先把 id 钉死。
    """
    digest = hashlib.sha256(
        f"{owner.kind}:{owner.id}|{job_id}|{pricing_version}".encode()
    ).hexdigest()[:16]
    return f"bill-{digest}"


def charge_event(
    usage: Sequence[UsageRecord],
    *,
    job_id: str,
    owner: Principal,
    config: MeterConfig,
    at: datetime,
    fx: FxRate | None = None,
) -> BillingEvent | None:
    """算钱 → 落成一条既有账本认识的 `BillingEvent`。未配置返回 `None`。

    复用 `flint/billing/ledger.py` 的事件类型，**NEVER 另起一本账**：
    两本账迟早对不上，而对账时谁也说不清该信哪一本。

    记的是**结算价**：记显示价的话，汇率一变历史账就跟着变了。
    """
    charge = price_usage(usage, job_id=job_id, config=config, fx=fx)
    if charge is None:
        return None
    return BillingEvent(
        event_id=charge_event_id(
            job_id=job_id, owner=owner, pricing_version=charge.pricing_version),
        owner=owner,
        job_id=job_id,
        # 计费档位就是上游用量的口径：一次对话用了哪个档，账上要看得出来。
        tier=charge.upstream_pricing_versions[0] if charge.upstream_pricing_versions
        else "no_usage",
        at=at,
        amount=charge.settle_amount,
        currency=charge.settle_currency,
        pricing_version=charge.pricing_version,
    )
