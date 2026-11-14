"""PAY-02：计费基准落地——按对话实际 API 用量算钱，价格从配置读。

## 计费基准是**真实用量**，不是「一次运行算一次钱」

owner 2026-08-04 裁决：**计费基准 = 每次对话实际消耗的 API 用量**。
所以钱从 `flint/llm/deepseek.py#UsageRecord` 的真 token 数来——那是调用真发生后
从响应体 `usage` 里读出来的，不是估的。按次收费的话，一次问「今天几号」
与一次跑满上下文的深度分析收一样的钱。

## 配置留空 = 整条计费路径关闭

与 `flint/billing/quota.py` 同一条口径：单价、币种、口径版本**任缺其一**都算未配置，
未配置时 `price_usage` 返回 `None`——**一分钱都不算、一条账都不记**，
行为与接计费之前逐字相同。判据配阴性对照证明这一点。

## 金额恒服务端计算

`price_usage` 的签名里**没有** `amount` 参数，也没有任何地方接受调用方给的金额。
前端传来的价格连进不来这个函数——那不是「我们不信它」，是**它没有入口**。

## 汇率必须带出处与时间戳

多币种时显示价与结算价分离。汇率是 `FxRate(rate, source, at)` 三件套，
**三样都必填**：一个裸的 `6.9` 说不出它是哪天、从哪来的，
而两个月后没人能复核那笔钱算得对不对。
"""
from __future__ import annotations

import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from flint.billing.meter import (
    BILLING_OFF_NOTE,
    Charge,
    FxRate,
    MeterConfig,
    charge_event,
    price_usage,
)
from flint.domain.models import Principal
from flint.llm.deepseek import UsageRecord

NOW = datetime(2026, 8, 5, 1, 0, 0, tzinfo=UTC)
OWNER = Principal(id="u-1", kind="user")

# 一次对话的两笔真实调用（token 数照 UsageRecord 的形状）。
USAGE = [
    UsageRecord(
        call_id="c-1", model="deepseek-chat", purpose="compose",
        input_tokens=120_000, output_tokens=8_000,
        cache_hit_tokens=100_000, cache_miss_tokens=20_000,
        cost_usd=Decimal("0.0224"), pricing_version="deepseek-v4-flash@2026-08",
    ),
    UsageRecord(
        call_id="c-2", model="deepseek-chat", purpose="verify",
        input_tokens=30_000, output_tokens=2_000,
        cache_hit_tokens=0, cache_miss_tokens=30_000,
        cost_usd=Decimal("0.0048"), pricing_version="deepseek-v4-flash@2026-08",
    ),
]

CONFIGURED = MeterConfig(
    price_per_mtok_input=Decimal("2.00"),
    price_per_mtok_output=Decimal("8.00"),
    currency="USD",
    pricing_version="flint-billing@2026-08-05",
)


# ───────────────────────── 一、配置留空 = 路径关闭（acceptance②，阴性对照）


def test_an_empty_config_is_not_configured() -> None:
    assert MeterConfig().configured is False


def test_any_missing_field_counts_as_unconfigured() -> None:
    """**任缺其一**都算没配。

    半套配置比没有更危险：它会让一半的运行被算钱、另一半不算，
    而两边都以为自己是对的（与 `quota.py` 同一条口径）。
    """
    full = CONFIGURED
    for field_name in ("price_per_mtok_input", "price_per_mtok_output",
                       "currency", "pricing_version"):
        import dataclasses

        partial = dataclasses.replace(full, **{field_name: None})
        assert partial.configured is False, f"缺 {field_name} 却算配好了"


def test_pricing_with_no_config_charges_nothing_at_all() -> None:
    """阴性对照：未配置时**一分钱都不算**，返回 `None`。"""
    assert price_usage(USAGE, job_id="job-1", config=MeterConfig()) is None


def test_the_off_path_is_reported_in_words_not_silently() -> None:
    """关闭要**说出来**：静默返回 None，调用方分不出「没配」与「这次是 0 元」。"""
    event = charge_event(
        USAGE, job_id="job-1", owner=OWNER, config=MeterConfig(), at=NOW)

    assert event is None
    assert "未配置" in BILLING_OFF_NOTE


def test_a_zero_price_is_not_the_same_as_no_price() -> None:
    """配成 0 是**一次决定**，与没配不是一回事：0 要照样出一笔 0 元的账。

    分不开的话，「我们决定这一档免费」与「定价还没定」在账上长得一样。
    """
    free = MeterConfig(
        price_per_mtok_input=Decimal(0), price_per_mtok_output=Decimal(0),
        currency="USD", pricing_version="free-tier@2026-08-05")

    charge = price_usage(USAGE, job_id="job-1", config=free)

    assert charge is not None
    assert charge.settle_amount == Decimal(0)


# ───────────────────────── 二、钱从真实 token 数来（acceptance①）


def test_the_amount_comes_from_the_real_token_counts() -> None:
    """按用量账里的真 token 数 × 配置单价算，逐位可复核。

    输入 150000 tok × 2.00/MTok = 0.30；输出 10000 tok × 8.00/MTok = 0.08。
    """
    charge = price_usage(USAGE, job_id="job-1", config=CONFIGURED)

    assert charge is not None
    assert charge.input_tokens == 150_000
    assert charge.output_tokens == 10_000
    assert charge.settle_amount == Decimal("0.38")


def test_more_usage_costs_more() -> None:
    """按次收费与按用量收费的分界：跑得多就该多花。"""
    one = price_usage(USAGE[:1], job_id="job-1", config=CONFIGURED)
    both = price_usage(USAGE, job_id="job-1", config=CONFIGURED)

    assert one is not None and both is not None
    assert both.settle_amount > one.settle_amount


def test_an_empty_conversation_costs_zero_but_still_produces_a_charge() -> None:
    """一次调用都没发的对话算 0 元——**但仍出一笔账**，否则对账时它凭空消失。"""
    charge = price_usage([], job_id="job-1", config=CONFIGURED)

    assert charge is not None
    assert charge.settle_amount == Decimal(0)
    assert charge.input_tokens == 0


def test_the_charge_carries_the_usage_breakdown() -> None:
    """acceptance③：每笔带用量明细——没有明细的金额没法复核。"""
    charge = price_usage(USAGE, job_id="job-1", config=CONFIGURED)

    assert charge is not None
    assert charge.call_count == 2
    assert charge.cache_hit_tokens == 100_000


def test_the_charge_carries_the_job_id_and_the_pricing_version() -> None:
    """acceptance③：作业 id + 口径版本，两样缺一就对不上账。"""
    charge = price_usage(USAGE, job_id="job-77", config=CONFIGURED)

    assert charge is not None
    assert charge.job_id == "job-77"
    assert charge.pricing_version == "flint-billing@2026-08-05"


def test_mixed_upstream_pricing_versions_are_surfaced() -> None:
    """上游用量账里混了两个口径版本时要**报出来**。

    两个口径的 token 单价不同，加在一起的那个 token 合计仍然对，
    但拿它去乘一个单价得到的钱**没有意义**——调用方有权知道这件事。
    """
    import dataclasses

    other = dataclasses.replace(USAGE[1], call_id="c-3", pricing_version="other@2026-07")
    charge = price_usage([USAGE[0], other], job_id="job-1", config=CONFIGURED)

    assert charge is not None
    assert charge.upstream_mixed_pricing is True


def test_a_single_upstream_version_is_not_flagged() -> None:
    charge = price_usage(USAGE, job_id="job-1", config=CONFIGURED)

    assert charge is not None
    assert charge.upstream_mixed_pricing is False


# ───────────────────────── 三、金额恒服务端计算（acceptance③）


def test_the_pricer_has_no_way_to_accept_a_client_supplied_amount() -> None:
    """**前端传来的价格进不来这个函数**——不是「我们不信它」，是它没有入口。

    判在签名上：出现任何形似金额的入参即红。
    """
    import inspect

    names = set(inspect.signature(price_usage).parameters)

    for banned in ("amount", "price", "total", "settle_amount", "charge"):
        assert banned not in names, f"price_usage 接受了外来金额入参：{banned}"


def test_the_module_never_reads_an_amount_off_a_request() -> None:
    """模块里 NEVER 出现从请求体取金额的路径。"""
    source = (REPO / "flint" / "billing" / "meter.py").read_text(encoding="utf-8")
    code = "\n".join(
        ln for ln in source.splitlines() if not ln.strip().startswith("#"))

    for banned in ("request.", "payload[", 'body["amount"', "json()"):
        assert banned not in code, f"meter.py 从请求里读东西了：{banned}"


def test_the_charge_is_frozen() -> None:
    """算出来的金额 NEVER 在运行期被改写。"""
    import dataclasses

    charge = price_usage(USAGE, job_id="job-1", config=CONFIGURED)
    assert isinstance(charge, Charge)

    with pytest.raises(dataclasses.FrozenInstanceError):
        charge.settle_amount = Decimal(0)  # type: ignore[misc]


# ───────────────────────── 四、多币种：显示价与结算价分离（acceptance④）


def test_without_an_fx_rate_display_equals_settlement() -> None:
    """不换汇时两者同值同币种——**NEVER 凭空造一个显示价**。"""
    charge = price_usage(USAGE, job_id="job-1", config=CONFIGURED)

    assert charge is not None
    assert charge.display_amount == charge.settle_amount
    assert charge.display_currency == charge.settle_currency == "USD"
    assert charge.fx is None


def test_an_fx_rate_must_carry_its_source_and_timestamp() -> None:
    """汇率三件套缺一不可：裸的一个数说不出它是哪天、从哪来的。"""
    with pytest.raises(TypeError):
        FxRate(Decimal("7.1"))  # type: ignore[call-arg]


def test_the_display_price_is_converted_and_the_settlement_price_is_not() -> None:
    """显示价换汇、结算价不动——两者分离才对得上上游账单。"""
    fx = FxRate(rate=Decimal("7.10"), source="ECB 参考汇率", at=NOW, quote="USD/CNY")

    charge = price_usage(USAGE, job_id="job-1", config=CONFIGURED, fx=fx)

    assert charge is not None
    assert charge.settle_amount == Decimal("0.38")
    assert charge.settle_currency == "USD"
    assert charge.display_amount == Decimal("2.698")
    assert charge.display_currency == "CNY"


def test_the_charge_keeps_the_rate_its_source_and_when_it_was_taken() -> None:
    """acceptance④：汇率取值带出处与时间戳，一路留在这笔账上。"""
    fx = FxRate(rate=Decimal("7.10"), source="ECB 参考汇率", at=NOW, quote="USD/CNY")

    charge = price_usage(USAGE, job_id="job-1", config=CONFIGURED, fx=fx)

    assert charge is not None and charge.fx is not None
    assert charge.fx.source == "ECB 参考汇率"
    assert charge.fx.at == NOW
    assert charge.fx.rate == Decimal("7.10")


def test_an_fx_rate_without_a_source_is_refused() -> None:
    """**NEVER 用没有出处的汇率**：空出处直接拒绝，而不是记一条来路不明的账。"""
    with pytest.raises(ValueError, match="出处"):
        FxRate(rate=Decimal("7.10"), source="  ", at=NOW, quote="USD/CNY")


def test_a_non_positive_fx_rate_is_refused() -> None:
    """0 或负汇率算出来的显示价是个假数，直接拒绝。"""
    with pytest.raises(ValueError, match="汇率"):
        FxRate(rate=Decimal(0), source="ECB", at=NOW, quote="USD/CNY")


def test_the_quote_must_start_from_the_settlement_currency() -> None:
    """汇率的报价方向要对得上结算币种：拿 EUR/CNY 去换 USD 结算的账是错的。"""
    fx = FxRate(rate=Decimal("7.10"), source="ECB", at=NOW, quote="EUR/CNY")

    with pytest.raises(ValueError, match="报价方向"):
        price_usage(USAGE, job_id="job-1", config=CONFIGURED, fx=fx)


# ───────────────────────── 五、落进既有计费账本（acceptance③，复用）


def test_the_charge_becomes_a_billing_event_on_the_existing_ledger() -> None:
    """复用 `flint/billing/ledger.py#BillingEvent`，NEVER 另起一本账。"""
    from flint.billing.ledger import BillingEvent, BillingLedger

    event = charge_event(USAGE, job_id="job-9", owner=OWNER, config=CONFIGURED, at=NOW)

    assert isinstance(event, BillingEvent)
    ledger = BillingLedger()
    ledger.append(event, expect_currency="USD")
    summary = ledger.reconcile(OWNER)

    assert summary["count"] == 1
    assert summary["total"] == Decimal("0.38")


def test_the_event_id_is_derived_from_the_job_so_a_replay_cannot_double_charge() -> None:
    """同一次作业算两遍 → 同一个 `event_id` → 账本第二次直接拒绝。

    幂等键的完整形态在 PAY-03；这里先保证**id 由作业决定**，
    而不是每次算钱都新造一个（那样重放就会重复扣）。
    """
    from flint.billing.ledger import BillingLedger, LedgerImmutable

    first = charge_event(USAGE, job_id="job-9", owner=OWNER, config=CONFIGURED, at=NOW)
    second = charge_event(USAGE, job_id="job-9", owner=OWNER, config=CONFIGURED, at=NOW)
    assert first is not None and second is not None
    assert first.event_id == second.event_id

    ledger = BillingLedger()
    ledger.append(first)
    with pytest.raises(LedgerImmutable):
        ledger.append(second)


def test_different_jobs_get_different_event_ids() -> None:
    a = charge_event(USAGE, job_id="job-a", owner=OWNER, config=CONFIGURED, at=NOW)
    b = charge_event(USAGE, job_id="job-b", owner=OWNER, config=CONFIGURED, at=NOW)

    assert a is not None and b is not None
    assert a.event_id != b.event_id


def test_the_event_settles_in_the_settlement_currency_not_the_display_one() -> None:
    """账本记的是**结算价**：记显示价的话，汇率一变历史账就跟着变了。"""
    fx = FxRate(rate=Decimal("7.10"), source="ECB", at=NOW, quote="USD/CNY")

    event = charge_event(
        USAGE, job_id="job-9", owner=OWNER, config=CONFIGURED, at=NOW, fx=fx)

    assert event is not None
    assert event.currency == "USD"
    assert event.amount == Decimal("0.38")


# ───────────────────────── 六、零网关（红线）


def test_the_meter_touches_no_payment_gateway() -> None:
    """本模块 NEVER 接任何支付网关、NEVER 持有任何密钥（S2-10）。"""
    source = (REPO / "flint" / "billing" / "meter.py").read_text(encoding="utf-8")
    code = "\n".join(
        ln for ln in source.splitlines() if not ln.strip().startswith("#"))

    for banned in ("httpx", "requests", "api.mch.weixin.qq.com", "openapi.alipay.com",
                   "api-m.paypal.com", "secret", "api_key"):
        assert banned not in code.lower(), f"meter.py 碰了 {banned}"
