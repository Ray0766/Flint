"""SHIP-01：支付骨架——免费额度计数 + 配额门 + 计费事件账（**零定价、零真实支付**）。

## 本卡只建三样

**算得清**（额度计数）· **拦得住**（配额门）· **记得下**（计费事件账）。
定价与真实支付**都不在本卡面上**：

- **零定价**：单价、免费额度上限、币种、计费口径版本全部**从配置读**。
  K7/K8 未定 → **配置留空 = 整条计费路径关闭**，行为与今天**逐字相同**；
- **零真实支付**：NEVER 接任何支付网关、NEVER 触碰付费开通（S2-10 红线）。

## 拦要拦在 submit 之前

超额时**在建作业之前**拒绝——先建再发现没额度，那个作业就成了一次
既没记账、也没人知道该去取消谁的运行（`deep_job.py` 的 `ChargeLandingMissing`
早就是这个形状：**先于提交检查**）。

拒绝时要说**还差多少**：只说「超额」的话，用户不知道是差 1 次还是差 100 次。

## 账要按 owner 隔离且只增不改

D7 多租户：`for_owner` 只返回那个 owner 的条目。
append-only：同 `event_id` 二次写入直接拒绝——账一旦会改，它就不是账了。
"""
from __future__ import annotations

import ast
import inspect
import re
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from flint.billing.ledger import BillingEvent, BillingLedger, LedgerImmutable
from flint.billing.quota import (
    BillingConfig,
    QuotaExceeded,
    check_quota,
    guard_before_submit,
)
from flint.domain.models import Principal

NOW = datetime(2026, 8, 4, 6, 0, tzinfo=UTC)
OWNER = Principal(kind="user", id="u-1")
OTHER = Principal(kind="user", id="u-2")

CONFIGURED = BillingConfig(
    free_quota=3, unit_price=Decimal("9.90"), currency="CNY", pricing_version="v1",
)
UNSET = BillingConfig()


def _event(event_id: str, owner: Principal = OWNER, job_id: str = "job-1") -> BillingEvent:
    return BillingEvent(
        event_id=event_id, owner=owner, job_id=job_id, tier="deep", at=NOW,
        amount=Decimal("9.90"), currency="CNY", pricing_version="v1",
    )


# ───────────────────────── 一、零定价：配置留空 = 整条路径关闭


def test_an_unset_config_is_not_configured() -> None:
    """四项**任缺其一**就算未配置——半套配置比没有更危险。"""
    assert UNSET.configured is False
    assert BillingConfig(free_quota=3).configured is False
    assert BillingConfig(free_quota=3, unit_price=Decimal(1)).configured is False
    assert CONFIGURED.configured is True


def test_no_price_is_baked_into_the_code() -> None:
    """acceptance②：**模块里 NEVER 藏默认价**。

    一个内置默认价会在没人注意时变成实际收费口径，而它的出处只有代码本身。
    """
    from flint.billing import ledger, quota

    for module in (quota, ledger):
        code = "\n".join(
            ln for ln in inspect.getsource(module).split("\n")
            if not ln.strip().startswith("#")
        )
        # 判据是**带数字的 Decimal 字面量**，不是「出现 Decimal 这个词」——
        # 后者会把类型标注也算进去。`Decimal("0")` 是求和的种子，不是价。
        priced = [m for m in re.findall(r'Decimal\(\s*"([^"]*)"', code) if m != "0"]

        assert priced == [], f"{module.__name__} 里藏了价：{priced}"


def test_the_config_fields_have_no_defaults_other_than_none() -> None:
    """四个字段的默认值都是 `None`——「没配」与「配成 0」必须分得开。

    默认成 0 的话，「免费额度 0 次」与「还没定价」长得一模一样。
    """
    import dataclasses

    for field in dataclasses.fields(BillingConfig):
        assert field.default is None, f"{field.name} 有一个不是 None 的默认值"


def test_with_no_config_the_gate_lets_everything_through() -> None:
    """acceptance②：配置留空 → 路径关闭，**行为与今天逐字相同**（阴性对照）。"""
    decision = check_quota(used=999, owner=OWNER, config=UNSET)

    assert decision.allowed is True
    assert decision.limit is None
    assert "未配置" in decision.note


def test_with_no_config_the_guard_never_raises() -> None:
    """路径关闭时 `guard_before_submit` 一次都不抛——今天的行为就是不拦。"""
    guard_before_submit(used=10**6, owner=OWNER, config=UNSET)


# ───────────────────────── 二、算得清 + 拦得住


def test_inside_the_free_quota_is_allowed() -> None:
    decision = check_quota(used=2, owner=OWNER, config=CONFIGURED)

    assert decision.allowed is True
    assert (decision.used, decision.limit) == (2, 3)


def test_the_boundary_is_the_last_free_run() -> None:
    """用了 2 次（还剩 1 次）→ 放行；用满 3 次 → 拦。边界写死，省得下次重新猜。"""
    assert check_quota(used=2, owner=OWNER, config=CONFIGURED).allowed is True
    assert check_quota(used=3, owner=OWNER, config=CONFIGURED).allowed is False


def test_being_over_says_how_much_short() -> None:
    """acceptance①：拒绝时说**还差多少**。

    只说「超额」的话，用户不知道是差 1 次还是差 100 次。
    """
    decision = check_quota(used=5, owner=OWNER, config=CONFIGURED)

    assert decision.allowed is False
    assert decision.shortfall == 3
    assert "3" in decision.note


def test_the_guard_raises_before_anything_is_submitted() -> None:
    """acceptance①：超额 → **在 submit 之前**抛，NEVER 先建作业再发现没额度。"""
    with pytest.raises(QuotaExceeded) as err:
        guard_before_submit(used=5, owner=OWNER, config=CONFIGURED)

    assert "u-1" in str(err.value)
    # 判「还差多少」要判那个**专有的数与词**：用 `"3" in message` 的话，
    # 「已用 3/3」里的 3 就把断言喂饱了（变异考实测：抽掉 shortfall 那句照样绿）。
    assert err.value.shortfall == 3
    assert "还差 3 次" in str(err.value)


def _code_face(module: object) -> str:
    """剥掉注释与 docstring，只留代码（口径同 BL-03 的 `code_face`）。

    只剥 `#` 的话，`quota.py` 的 docstring 里那句「这里没有 runner、没有 submit」
    会被判成**有** runner——本仓第十一次同型：判据不该与留痕互相取消。
    """
    tree = ast.parse(inspect.getsource(module))  # type: ignore[arg-type]
    for node in ast.walk(tree):
        if not isinstance(
            node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef
        ):
            continue
        body = node.body
        if (
            body and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            body[0].value.value = ""
    return ast.unparse(tree)


def test_the_guard_never_touches_a_runner() -> None:
    """源码面：配额模块里**没有**调提交面的痕迹。

    「拦在提交之前」这件事，靠的是这个模块根本不认识提交那一侧。
    """
    from flint.billing import quota

    code = _code_face(quota)

    # 判的是**调提交面**（`.submit(`）与拿 runner，不是函数名里带 submit 三个字母——
    # `guard_before_submit` 这个名字本身就是在说「拦在提交之前」。
    for forbidden in (".submit(", "runner", "JobRunner"):
        assert forbidden not in code, f"配额门碰了提交面：{forbidden}"


# ───────────────────────── 三、零真实支付（acceptance③）


def test_no_payment_gateway_anywhere_in_the_package() -> None:
    """**NEVER 接任何支付网关**：包里不出现任何网关/密钥/HTTP 的痕迹。"""
    from flint.billing import ledger, quota

    for module in (quota, ledger):
        code = "\n".join(
            ln for ln in inspect.getsource(module).split("\n")
            if not ln.strip().startswith("#")
        )
        for forbidden in (
            "httpx", "requests", "wechat", "alipay", "stripe", "paypal",
            "api_key", "secret", "merchant",
        ):
            assert forbidden not in code.lower(), f"{module.__name__} 里出现了：{forbidden}"


# ───────────────────────── 四、账：append-only + 按 owner 隔离


def test_an_event_carries_all_five_reconcilable_fields() -> None:
    """acceptance④：每条带 owner / 作业 / 档位 / 时间 / 计费口径版本。"""
    event = _event("e-1")

    assert (event.owner, event.job_id, event.tier, event.at, event.pricing_version) == (
        OWNER, "job-1", "deep", NOW, "v1",
    )


def test_appending_the_same_event_twice_is_refused() -> None:
    """append-only：同 `event_id` 二次写入直接拒绝。

    账一旦会改，它就不是账了——对账时谁也说不清哪一版是真的。
    """
    ledger = BillingLedger()
    ledger.append(_event("e-1"))

    with pytest.raises(LedgerImmutable):
        ledger.append(_event("e-1"))


def test_the_ledger_has_no_update_or_delete() -> None:
    """源码面：账本上**没有**改与删的方法。"""
    assert not hasattr(BillingLedger, "update")
    assert not hasattr(BillingLedger, "delete")
    assert not hasattr(BillingLedger, "remove")


def test_one_owner_never_sees_another_owners_events() -> None:
    """D7 多租户：`for_owner` 只返回那个 owner 的条目。"""
    ledger = BillingLedger()
    ledger.append(_event("e-1", owner=OWNER))
    ledger.append(_event("e-2", owner=OTHER))

    assert [e.event_id for e in ledger.for_owner(OWNER)] == ["e-1"]
    assert [e.event_id for e in ledger.for_owner(OTHER)] == ["e-2"]


def test_for_owner_returns_a_copy() -> None:
    """返回副本：改返回值 NEVER 影响账本（与 FAV-01 / SnapshotPins 同款口径）。"""
    ledger = BillingLedger()
    ledger.append(_event("e-1"))

    ledger.for_owner(OWNER).clear()

    assert len(ledger.for_owner(OWNER)) == 1


def test_reconcile_sums_only_that_owner() -> None:
    """对账：条数 + 金额合计 + 口径版本集合，**只算那个 owner 的**。"""
    ledger = BillingLedger()
    ledger.append(_event("e-1", owner=OWNER))
    ledger.append(_event("e-2", owner=OWNER, job_id="job-2"))
    ledger.append(_event("e-3", owner=OTHER))

    report = ledger.reconcile(OWNER)

    assert report["count"] == 2
    assert report["total"] == Decimal("19.80")
    assert report["pricing_versions"] == ["v1"]


def test_reconcile_reports_mixed_pricing_versions() -> None:
    """口径版本混用要**报出来**——两个版本的钱加在一起，那个和没有意义。"""
    ledger = BillingLedger()
    ledger.append(_event("e-1"))
    ledger.append(
        BillingEvent(
            event_id="e-2", owner=OWNER, job_id="job-2", tier="deep", at=NOW,
            amount=Decimal("12.00"), currency="CNY", pricing_version="v2",
        )
    )

    report = ledger.reconcile(OWNER)

    assert report["pricing_versions"] == ["v1", "v2"]
    assert report["mixed_pricing"] is True


def test_a_single_version_is_not_flagged_as_mixed() -> None:
    """阴性对照：只有一个版本时不报混用，否则那个标记会被读成噪音。"""
    ledger = BillingLedger()
    ledger.append(_event("e-1"))

    assert ledger.reconcile(OWNER)["mixed_pricing"] is False


def test_an_empty_ledger_reconciles_to_zero_not_an_error() -> None:
    """没有任何计费事件时对账出 0——不是报错，也不是空 dict。"""
    report = BillingLedger().reconcile(OWNER)

    assert report["count"] == 0
    assert report["total"] == Decimal(0)


def test_currency_must_match_the_config_currency() -> None:
    """币种不一致要当场拒——两种币种的钱加在一起，那个和是错的。"""
    ledger = BillingLedger()

    with pytest.raises(ValueError, match="币种"):
        ledger.append(
            BillingEvent(
                event_id="e-1", owner=OWNER, job_id="job-1", tier="deep", at=NOW,
                amount=Decimal(1), currency="USD", pricing_version="v1",
            ),
            expect_currency="CNY",
        )
