"""FB-05：解引用端点② `GET /price-entries/{id}?quantity=N` —— 单价 × 数量 = 金额 + 出处。

## 金额由后端算

「数字必有出处」是三条铁律之一。前端自己相乘的话，屏幕上那个金额就没有出处——
它是前端算的，而前端不进账本、不留痕、也不会在单价变了之后告诉任何人。
所以本端点**把乘法做完再给出去**，并把参与运算的每一项（单价区间、数量、币种、出处）
一并返回，让那个金额随时能被复算。

## PriceBook 时效：过期照实标记，NEVER 静默用旧价（D13）

`flint/pricebook/stale.py` 的既有口径：`updated_at + stale_after_months < today` 即过期，
**过期仍可用**，但要 `yellow_flag` + 质量卡注记双重标注。本端点照这个口径回，
NEVER 悄悄把过期价当新价给出去——**用户看到一个 2024 年的单价而不知道它是 2024 年的**，
比看不到这个数字更糟。

## 币种照实返回，换算不实现

K8 汇率策略未定。**NEVER 编造汇率**：一条编出来的汇率会让整张预算表的数字全部失去出处，
而且没人看得出来。本端点只回 `currency` 字段本身。

## 多租户：这张表**没有归属**（口径收窄，见 trace §3）

卡面 acceptance④ 写「多租户隔离，同 FB-04」，但 `pricebook` 表**没有 owner 列**
（`migrations/0010_pricebook.py` 全 11 列逐个核过）——它是**全局参考数据**，
不是每个租户各有一份。所以这里能做也该做的是「要求身份、只读」，
而不是把一张共享表按 owner 切开。收窄理由与实证写在 trace，NEVER 假装隔离了什么。
"""
from __future__ import annotations

import asyncio
import os
import re
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import asyncpg
import pytest
from fastapi.testclient import TestClient

from flint.api.deref import DerefApiDeps, create_deref_app

pytestmark = pytest.mark.compose

REPO = Path(__file__).resolve().parents[2]
DSN = os.environ.get("FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")
PREFIX = "fb05-"
USER = "fb05-user"
TODAY = date(2026, 8, 4)

FRESH = f"{PREFIX}entry-fresh"
STALE = f"{PREFIX}entry-stale"


def run(coro: Any) -> Any:
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def clean_slate() -> None:
    async def wipe() -> None:
        conn = await asyncpg.connect(DSN)
        try:
            await conn.execute(f"DELETE FROM pricebook WHERE entry_id LIKE '{PREFIX}%'")
            await conn.executemany(
                "INSERT INTO pricebook (entry_id, item, unit, price_low, price_high, "
                "currency, region, year, source, updated_at, stale_after_months) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)",
                [
                    (FRESH, "向量库托管", "月", 100.0, 150.0, "CNY", "CN", 2026,
                     "https://example.invalid/pricing", datetime(2026, 7, 1, tzinfo=UTC), 12),
                    # updated_at 2023 + 12 个月 TTL → 相对 TODAY(2026-08-04) 早就过期
                    (STALE, "推理算力", "千次", 20.0, 20.0, "USD", "US", 2023,
                     "https://example.invalid/gpu", datetime(2023, 1, 1, tzinfo=UTC), 12),
                ],
            )
        finally:
            await conn.close()

    run(wipe())


def client() -> TestClient:
    return TestClient(create_deref_app(DerefApiDeps(dsn=DSN, today=lambda: TODAY)))


def get(entry_id: str, quantity: Any = 3, *, user: str | None = USER) -> Any:
    headers = {"X-User-Id": user} if user is not None else {}
    params = {} if quantity is None else {"quantity": quantity}
    return client().get(f"/price-entries/{entry_id}", params=params, headers=headers)


# ───────────────────────── acceptance①：单价 × 数量 = 金额 + 出处


def test_the_backend_does_the_multiplication_and_shows_its_working() -> None:
    """金额由后端算，且参与运算的每一项都一并给出——那个数字随时能被复算。"""
    body = get(FRESH, 3).json()

    assert body["price_low"] == 100.0
    assert body["price_high"] == 150.0
    assert body["quantity"] == 3.0
    assert body["amount_low"] == 300.0
    assert body["amount_high"] == 450.0
    assert body["unit"] == "月"
    assert body["item"] == "向量库托管"


def test_the_provenance_travels_with_the_number() -> None:
    """出处随数字一起走——没有 source 的数字在这套系统里不许被引用。"""
    body = get(FRESH).json()

    assert body["source"] == "https://example.invalid/pricing"
    assert body["source"].strip() != ""
    assert body["channel"] == "price", "响应要自报通道（三通道 NEVER 混用）"
    assert body["price_entry_id"] == FRESH


def test_a_fractional_quantity_still_multiplies_exactly() -> None:
    """小数数量照算（0.5 个月的托管费是真实场景），NEVER 悄悄取整。"""
    body = get(FRESH, 0.5).json()

    assert body["quantity"] == 0.5
    assert body["amount_low"] == 50.0
    assert body["amount_high"] == 75.0


def test_a_missing_quantity_is_rejected_not_defaulted_to_one() -> None:
    """不给 quantity 直接拒，NEVER 默认成 1。

    默认成 1 会让「忘了传数量」和「真的只要一份」长得一模一样，
    而算出来的金额照样看起来像个正经数字。
    """
    assert get(FRESH, None).status_code == 422


def test_a_negative_quantity_is_rejected() -> None:
    """负数量拒掉：预算表里没有「负 3 个月」这种东西。"""
    assert get(FRESH, -1).status_code == 422


# ───────────────────────── acceptance②：时效照实标记


def test_a_stale_entry_is_returned_but_marked() -> None:
    """过期条目**照实标记并返回**，NEVER 静默用旧价（D13）。

    用户看到一个 2023 年的单价而不知道它是 2023 年的，比看不到这个数字更糟。
    """
    body = get(STALE).json()

    assert body["stale"] is True
    assert body["yellow_flag"] is True
    assert body["price_year"] == 2023
    assert body["amount_low"] == 60.0, "过期不影响算术，只影响标注"
    assert "2023" in body["price_data_note"]


def test_a_fresh_entry_is_not_marked_stale() -> None:
    """正例：没过期的不带黄标（否则上一条等于恒真）。"""
    body = get(FRESH).json()

    assert body["stale"] is False
    assert body["yellow_flag"] is False
    assert body["price_data_note"] is None


def test_staleness_uses_the_existing_house_rule() -> None:
    """时效判定复用 `flint/pricebook/stale.py`，NEVER 在端点里另写一套 TTL 算法。

    另写一套的那天，预算表上的黄标与质量卡上的注记会开始各说各的。
    """
    from flint.domain.models import PriceEntry
    from flint.pricebook.stale import check_stale

    entry = PriceEntry(
        entry_id=STALE, item="推理算力", unit="千次", price_low=20.0, price_high=20.0,
        currency="USD", region="US", year=2023, source="x",
        updated_at=datetime(2023, 1, 1, tzinfo=UTC), stale_after_months=12,
    )
    house = check_stale(entry, TODAY)
    body = get(STALE).json()

    assert body["stale"] is house.stale
    assert body["yellow_flag"] is house.yellow_flag
    assert body["price_year"] == house.year


# ───────────────────────── acceptance③：币种照实，换算不实现


def test_the_currency_is_returned_as_stored() -> None:
    """币种照实返回，两条不同币种的条目各回各的。"""
    assert get(FRESH).json()["currency"] == "CNY"
    assert get(STALE).json()["currency"] == "USD"


def test_no_exchange_rate_is_invented() -> None:
    """K8 未定 → **NEVER 编造汇率**。响应里不许出现任何换算结果。

    一条编出来的汇率会让整张预算表的数字全部失去出处，而且没人看得出来。
    """
    body = get(STALE).json()
    forbidden = ("rate", "exchange", "converted", "amount_cny", "cny_equivalent", "fx")

    leaked = [k for k in body if any(f in k.lower() for f in forbidden)]
    assert leaked == [], f"出现了换算字段：{leaked}"

    source = (REPO / "flint" / "api" / "deref.py").read_text(encoding="utf-8")
    code = re.sub(r'"""[\s\S]*?"""', "", source)
    assert not re.search(r"\b(6\.\d|7\.\d)\d*\s*[*/]", code), "代码里疑似写死了汇率"


# ───────────────────────── acceptance④：只读 + 要求身份


def test_identity_is_required() -> None:
    """要求 `X-User-Id`：这张表虽然全局共享，读它的人仍然要有身份。"""
    assert get(FRESH, user=None).status_code == 422


def test_an_unknown_entry_is_404() -> None:
    assert get(f"{PREFIX}entry-nope").status_code == 404


def test_the_endpoint_module_never_writes() -> None:
    """只读（与 FB-04 同一个检测器口径，含剥注释）。"""
    from tests.v041.test_deref_fact import _write_statements

    source = (REPO / "flint" / "api" / "deref.py").read_text(encoding="utf-8")
    assert _write_statements(source) == []
