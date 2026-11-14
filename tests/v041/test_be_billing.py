"""BE-06 · 计费与额度端点 `GET /billing`（蓝本 R2「端点未建」· 接 SHIP-01 骨架）。

四条判据线：

1. **未定价时如实说未启用**——NEVER 返回 0 元或一个假额度冒充已启用
   （acceptance②）。判据钉：未启用时**连 `limit` / `currency` / `remaining`
   这些键都不给**，给了就等于说「你的免费额度是 0 次」。
2. **额度判定转调 `check_quota`**，NEVER 在端点里再写一遍阈值
   （BE-04 同一条：同一件事两个真相是本项目的老病）。
3. **钱恒是字符串**——JSON 里的浮点数会把 0.1 + 0.2 变成 0.30000000000000004，
   而这是钱。判据扫全响应：一个 float 都不许有。
4. **NEVER 泄露别人的账**——数据源投毒（按 job 查串了行）时端点自己再滤一遍
   （BE-05 变异⑨ 逼出来的那条纪律，本卡两处照用）。
"""
from __future__ import annotations

import ast
import re
from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from flint.api.billing import BillingApiDeps, create_billing_app
from flint.billing.ledger import BillingEvent
from flint.billing.meter import Charge
from flint.billing.quota import BillingConfig
from flint.domain.models import Principal

MODULE = Path("flint/api/billing.py")

ME = "u-me"
OTHER = "u-other"
MINE = Principal(kind="user", id=ME)
THEIRS = Principal(kind="user", id=OTHER)

ON = BillingConfig(
    free_quota=10, unit_price=Decimal("0.5"), currency="CNY", pricing_version="pb-1")
OFF = BillingConfig()


def _event(
    job_id: str = "job-1", owner: Principal = MINE, amount: str = "1.25",
    version: str = "pb-1",
) -> BillingEvent:
    return BillingEvent(
        event_id=f"ev-{job_id}-{owner.id}",
        owner=owner,
        job_id=job_id,
        tier="deep",
        at=datetime(2026, 3, 4, 5, 6, tzinfo=UTC),
        amount=Decimal(amount),
        currency="CNY",
        pricing_version=version,
    )


def _charge(job_id: str = "job-1") -> Charge:
    return Charge(
        job_id=job_id,
        settle_amount=Decimal("1.25"),
        settle_currency="CNY",
        display_amount=Decimal("1.25"),
        display_currency="CNY",
        fx=None,
        call_count=3,
        input_tokens=1200,
        output_tokens=340,
        cache_hit_tokens=80,
        pricing_version="pb-1",
        upstream_pricing_versions=("pb-1",),
        upstream_mixed_pricing=False,
    )


def _client(
    *,
    config: BillingConfig = ON,
    used: int | None = 3,
    events: Sequence[BillingEvent] | None = None,
    usage: Charge | None = None,
    usage_loader: bool = False,
    seen: list[Any] | None = None,
) -> TestClient:
    async def count_used(owner: Principal) -> int:
        if seen is not None:
            seen.append(owner)
        assert used is not None
        return used

    async def load_events(owner: Principal) -> Sequence[BillingEvent]:
        if seen is not None:
            seen.append(owner)
        return list(events or [])

    async def load_usage(job_id: str) -> Charge | None:
        return usage

    deps = BillingApiDeps(
        config=config,
        count_used=count_used if used is not None else None,
        load_events=load_events if events is not None else None,
        load_usage=load_usage if usage_loader else None,
    )
    return TestClient(create_billing_app(deps))


def _body(**kwargs: Any) -> dict[str, Any]:
    response = _client(**kwargs).get("/billing", headers={"X-User-Id": ME})
    assert response.status_code == 200, response.text
    out: dict[str, Any] = response.json()
    return out


# ───────────────────────── 一、未定价时如实说未启用（acceptance②）


def test_the_endpoint_exists() -> None:
    assert _client().get("/billing", headers={"X-User-Id": ME}).status_code == 200


def test_identity_is_required() -> None:
    assert _client().get("/billing").status_code == 422


def test_unconfigured_says_not_enabled() -> None:
    billing = _body(config=OFF)["billing"]

    assert billing["status"] == "not_enabled"
    assert billing["reason"]


def test_unconfigured_never_shows_a_currency_or_a_pricing_version() -> None:
    """给了币种就等于说「已经在按这个币种收钱了」。"""
    billing = _body(config=OFF)["billing"]

    assert "currency" not in billing
    assert "pricing_version" not in billing


def test_unconfigured_never_shows_a_quota_limit() -> None:
    """**NEVER 假额度**：`limit: 0` 与「还没定价」长得一模一样，而它们是两件事。"""
    quota = _body(config=OFF)["quota"]

    assert quota["status"] == "not_enabled"
    for key in ("limit", "remaining", "exhausted", "shortfall"):
        assert key not in quota, f"未启用时 NEVER 给 {key}"


def test_unconfigured_still_reports_the_run_count() -> None:
    """计数一直在跑（它不需要定价）——如实报，但**不给上限**。"""
    assert _body(config=OFF)["quota"]["used"] == 3


def test_a_half_configured_price_is_not_enabled() -> None:
    """四项任缺其一都算未配置（`BillingConfig.configured` 的口径）。

    半套配置比没有更危险：一半的运行被拦、另一半照跑，两边都以为自己是对的。
    """
    half = BillingConfig(free_quota=10, unit_price=Decimal("0.5"), currency="CNY")

    assert _body(config=half)["billing"]["status"] == "not_enabled"


def test_configured_reports_the_currency_and_the_pricing_version() -> None:
    assert _body()["billing"] == {
        "status": "enabled", "currency": "CNY", "pricing_version": "pb-1"}


# ───────────────────────── 二、额度转调既有闸门（acceptance①）


def test_the_quota_delegates_to_the_existing_gate() -> None:
    """端点里 NEVER 再写一遍阈值：两处各判各的，横幅说还有额度而提交被拦。

    判据钉的是**阈值比较本身**：模块里不许出现任何拿额度量做大小比较的表达式。
    只扫 `<` 拦不住换个方向写的 `used >= limit`——那是同一件事的第二个真相，
    而且它多半是「对的」，于是更难被发现。
    """
    assert "check_quota" in _identifiers()

    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    quantities = {"used", "limit", "free_quota", "remaining", "shortfall"}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        if not any(isinstance(op, ast.Lt | ast.Gt | ast.LtE | ast.GtE)
                   for op in node.ops):
            continue
        touched = {n.id for n in ast.walk(node) if isinstance(n, ast.Name)} | {
            n.attr for n in ast.walk(node) if isinstance(n, ast.Attribute)}
        assert not touched & quantities, f"模块里自己比了一次额度：{sorted(touched)}"


def test_the_remaining_is_computed_server_side() -> None:
    """前端零计算：余量是后端给的数，不是前端拿 limit 减 used。"""
    quota = _body(used=3)["quota"]

    assert quota == {"status": "enabled", "used": 3, "limit": 10,
                     "remaining": 7, "exhausted": False, "shortfall": 0}


def test_an_exhausted_quota_says_how_short_it_is() -> None:
    """只说「超额」的话，用户不知道是差 1 次还是差 100 次。"""
    quota = _body(used=12)["quota"]

    assert quota["exhausted"] is True
    assert quota["remaining"] == 0
    assert quota["shortfall"] == 3


def test_remaining_zero_and_exhausted_never_disagree() -> None:
    """余量与超额判定来自同一件事，NEVER 出现「余量 0 但没超额」。"""
    for used in range(14):
        quota = _body(used=used)["quota"]
        assert (quota["remaining"] == 0) == quota["exhausted"], f"used={used}"


def test_without_a_counter_the_quota_is_not_checked() -> None:
    """没注入计数源 → 没查过。NEVER 拿 0 冒充「你一次都没用」。"""
    quota = _body(used=None)["quota"]

    assert quota == {"status": "not_checked"}


# ───────────────────────── 三、计费事件可对账（acceptance③）


def test_without_a_ledger_the_events_are_not_checked() -> None:
    events = _body()["events"]

    assert events == {"status": "not_checked"}


def test_an_empty_ledger_is_an_empty_list_not_404() -> None:
    events = _body(events=[])["events"]

    assert events["status"] == "checked"
    assert events["items"] == []
    assert events["reconciliation"]["count"] == 0


def test_each_event_carries_the_five_reconciliation_fields() -> None:
    item = _body(events=[_event()])["events"]["items"][0]

    assert item["job_id"] == "job-1"
    assert item["tier"] == "deep"
    assert item["at"] == "2026-03-04T05:06:00+00:00"
    assert item["pricing_version"] == "pb-1"
    assert item["amount"] == "1.25"
    assert item["currency"] == "CNY"


def test_every_amount_is_a_string_never_a_float() -> None:
    """钱 NEVER 走 JSON 浮点：0.1 + 0.2 会变成 0.30000000000000004。"""
    body = _body(events=[_event(amount="0.1"), _event(job_id="job-2", amount="0.2")])

    def floats(node: Any) -> list[Any]:
        if isinstance(node, dict):
            return [f for v in node.values() for f in floats(v)]
        if isinstance(node, list):
            return [f for v in node for f in floats(v)]
        return [node] if isinstance(node, float) else []

    assert floats(body) == []
    assert body["events"]["reconciliation"]["total"] == "0.3"


def test_mixed_pricing_versions_are_reported() -> None:
    """两个口径的钱加在一起，那个和没有意义——所以混用 MUST 报出来。"""
    body = _body(events=[_event(), _event(job_id="job-2", version="pb-2")])

    assert body["events"]["reconciliation"]["mixed_pricing"] is True
    assert body["events"]["reconciliation"]["pricing_versions"] == ["pb-1", "pb-2"]


def test_without_a_usage_source_the_detail_is_not_checked() -> None:
    """冻结件 `BillingEvent` **没有用量字段**——没注入用量源就说没查过，NEVER 编。"""
    item = _body(events=[_event()])["events"]["items"][0]

    assert item["usage"] == {"status": "not_checked"}


def test_a_known_usage_detail_is_reported() -> None:
    item = _body(events=[_event()], usage_loader=True, usage=_charge())[
        "events"]["items"][0]

    assert item["usage"] == {
        "status": "known", "call_count": 3, "input_tokens": 1200,
        "output_tokens": 340, "cache_hit_tokens": 80}


def test_a_usage_record_for_another_job_is_dropped() -> None:
    """用量源串了行（按 owner 查而不是按 job 查）→ 丢掉。

    把别的作业的 token 数贴在这一笔账上，对账时会得出一个查不出错的错数。
    """
    item = _body(events=[_event()], usage_loader=True, usage=_charge("job-9"))[
        "events"]["items"][0]

    assert item["usage"] == {"status": "no_record"}


# ───────────────────────── 四、只读 · 多租户 · NEVER 造字段（acceptance④⑤⑥）


def test_another_owners_event_is_dropped() -> None:
    """数据源投毒 → 端点自己再滤一遍。多租户隔离 NEVER 只靠调用方查对了。"""
    body = _body(events=[_event(), _event(job_id="job-2", owner=THEIRS)])

    assert [i["job_id"] for i in body["events"]["items"]] == ["job-1"]
    assert OTHER not in str(body)


def test_the_sources_are_asked_only_about_the_caller() -> None:
    seen: list[Any] = []
    _body(events=[], seen=seen)

    # 冻结件 `Principal` 不是 frozen dataclass（`__hash__` 是 None），进不了 set。
    assert {(p.kind, p.id) for p in seen} == {("user", ME)}


def test_the_route_has_no_path_parameter() -> None:
    """越权在结构上不可达：没有 id 入参，就没有「取他人资源」这个动作。"""
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    routes = [
        d.args[0].value
        for node in ast.walk(tree)
        if isinstance(node, ast.AsyncFunctionDef | ast.FunctionDef)
        for d in node.decorator_list
        if isinstance(d, ast.Call) and d.args
        and isinstance(d.args[0], ast.Constant) and isinstance(d.args[0].value, str)
        and d.args[0].value.startswith("/")
    ]

    assert routes == ["/billing"]
    assert "{" not in routes[0]


def _identifiers() -> set[str]:
    """模块**真正用到**的标识符（import + Name + Attribute）。

    NEVER 拿全文扫词：docstring 里写一句「NEVER 调 `price_usage`」也会命中，
    于是判据被自己的注释喂饱了（本轮第七次撞上这个形状）。
    """
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    return {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {
        n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)} | {
        a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names
    } | {a.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)
         for a in n.names}


def test_the_module_never_writes() -> None:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    docstrings = {ast.get_docstring(n) for n in ast.walk(tree)
                  if isinstance(n, ast.Module | ast.ClassDef | ast.FunctionDef
                                | ast.AsyncFunctionDef)}
    literals = " ".join(
        node.value for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
        and node.value not in docstrings
    )

    for verb in ("INSERT", "UPDATE", "DELETE", "DROP", "ALTER"):
        assert not re.search(rf"\b{verb}\b", literals, re.IGNORECASE), f"模块里有 {verb}"

    # 判在结构上而不是 `.append(` 这个词上：拼一个本地列表也叫 append，
    # 而那不是写库。真正的写入口是 `BillingLedger.append`——**本模块拿不到那个对象**，
    # 它只收一串已经读出来的 `BillingEvent`。拿不到就写不进去。
    assert "BillingLedger" not in _identifiers()


def test_the_module_never_prices_anything_itself() -> None:
    """金额恒服务端算，且**算在 meter 里**——本模块一处乘除都没有。"""
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    ops = [n for n in ast.walk(tree)
           if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Mult | ast.Div)]

    assert ops == []
    assert "price_usage" not in _identifiers()


def test_the_response_shape_is_exactly_four_things() -> None:
    body = _body(events=[])

    assert set(body) == {"principal", "billing", "quota", "events"}


def test_no_payment_field_is_synthesised() -> None:
    """账单屏最容易被顺手加上「去支付/卡号/发票」——那三样这里一个都不该有。

    真实支付是 S2-10 红线，本端点只读。
    """
    body = _body(events=[_event()], used=12)

    assert not re.search(
        r"pay_url|checkout|card|invoice|receipt|gateway|merchant",
        str(body), re.IGNORECASE)
