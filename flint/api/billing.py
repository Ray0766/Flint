"""BE-06：计费与额度端点 `GET /billing`（蓝本 R2「端点未建」· 接 SHIP-01 骨架）。

蓝本路由表 R2 行写的是「端点未建 · billing_enabled: false」。本卡把它建起来——
而 `billing_enabled` 那一位**不是写死的 false，是配置算出来的**。

## 未定价时说未启用，NEVER 拿 0 冒充

`BillingConfig.configured` 的口径原样沿用：四项任缺其一都算未配置。
未启用时本端点**连 `limit` / `remaining` / `currency` 这些键都不给**：

- 给 `limit: 0`，前端会显示「免费额度 0 次」——而真相是还没定价；
- 给 `currency`，等于说「已经在按这个币种收钱了」。

（`quota.py` 的模块 docstring 把这条写死了：「没配」与「配成 0」必须分得开。）

## 额度判定转调既有闸门

`check_quota` 是提交前那道门用的同一个函数。端点里 NEVER 再写一遍阈值——
两处各判各的，就会出现横幅说「还有额度」而提交被拦（BE-04 同一条纪律）。

余量与是否超额**都由后端给**（蓝本铁律：前端零计算），且两者同源：
`remaining == 0` 与 `exhausted` NEVER 相互矛盾。

## 钱恒是字符串

`Decimal` 走 JSON 浮点会把 0.1 + 0.2 变成 0.30000000000000004，而这是钱。
本模块**一处乘除都没有**：金额算在 `meter.price_usage` 里，这里只转述。

## 用量明细：冻结件里没有，所以只能经注入

冻结件 `BillingEvent` 有 owner / job_id / tier / at / amount / currency /
pricing_version 七样，**没有用量字段**——用量在 `meter.Charge` 上，而 `Charge`
当前不落库。所以用量明细经注入取，没注入就说没查过，NEVER 编一组 token 数。

## 两处「再滤一遍」

数据源投毒（按 org 查、按 owner 查串了行）时，端点自己再滤一遍：
账目按 owner、用量按 job_id。多租户隔离 NEVER 只靠调用方查对了
（BE-05 变异⑨ 逼出来的那条纪律）。

**零真实支付**：本模块 NEVER 接任何支付网关、NEVER 持有任何密钥（S2-10 红线）。
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from fastapi import FastAPI, Header
from fastapi.responses import JSONResponse, Response

from flint.billing.ledger import BillingEvent
from flint.billing.meter import Charge
from flint.billing.quota import BillingConfig, check_quota
from flint.domain.models import Principal

UsedCounter = Callable[[Principal], Awaitable[int]]
EventLoader = Callable[[Principal], Awaitable[Sequence[BillingEvent]]]
UsageLoader = Callable[[str], Awaitable[Charge | None]]


@dataclass
class BillingApiDeps:
    """配置恒在；三个数据源 **MAY 缺席**——缺席时如实说没查过。"""

    config: BillingConfig
    count_used: UsedCounter | None = None
    load_events: EventLoader | None = None
    load_usage: UsageLoader | None = None


def _billing(config: BillingConfig) -> dict[str, Any]:
    if not config.configured:
        return {
            "status": "not_enabled",
            "reason": "计费未配置（免费额度/单价/币种/口径版本任缺其一）："
                      "本端点 NEVER 拿一个 0 元或一个假额度冒充已启用",
        }
    return {
        "status": "enabled",
        "currency": config.currency,
        "pricing_version": config.pricing_version,
    }


def _quota(
    used: int | None, owner: Principal, config: BillingConfig
) -> dict[str, Any]:
    if used is None:
        # 没注入计数源。拿 0 冒充「你一次都没用」，与「没查过」是两件事。
        return {"status": "not_checked"}
    if not config.configured:
        # 计数一直在跑（它不需要定价），但**没有上限**这回事。
        return {"status": "not_enabled", "used": used}
    decision = check_quota(used=used, owner=owner, config=config)
    assert decision.limit is not None                  # configured 已保证
    return {
        "status": "enabled",
        "used": decision.used,
        "limit": decision.limit,
        # 前端零计算：余量是后端给的数。超额与否直接来自同一次判定，
        # NEVER 让前端拿 remaining 自己再判一次。
        "remaining": max(decision.limit - decision.used, 0),
        "exhausted": not decision.allowed,
        "shortfall": decision.shortfall,
    }


def _usage(charge: Charge | None, job_id: str, *, checked: bool) -> dict[str, Any]:
    if not checked:
        return {"status": "not_checked"}
    if charge is None or charge.job_id != job_id:
        # 用量源串了行 → 丢掉。把别的作业的 token 数贴在这一笔账上，
        # 对账时会得出一个查不出错的错数。
        return {"status": "no_record"}
    return {
        "status": "known",
        "call_count": charge.call_count,
        "input_tokens": charge.input_tokens,
        "output_tokens": charge.output_tokens,
        "cache_hit_tokens": charge.cache_hit_tokens,
    }


def event_json(event: BillingEvent, usage: dict[str, Any]) -> dict[str, Any]:
    """一条账。五个对账字段（`ledger.py` 的口径）一样不少。"""
    return {
        "job_id": event.job_id,
        "tier": event.tier,
        "at": event.at.isoformat(),
        "amount": str(event.amount),        # 钱恒是字符串（见模块 docstring）
        "currency": event.currency,
        "pricing_version": event.pricing_version,
        "usage": usage,
    }


def reconciliation_json(events: Sequence[BillingEvent]) -> dict[str, Any]:
    """对账口径与 `BillingLedger.reconcile` 一致：条数 + 合计 + 版本集合 + 混用标记。"""
    versions = sorted({e.pricing_version for e in events})
    return {
        "count": len(events),
        # 与 `reconcile` 逐字同形：空账出 0，不是报错。
        "total": str(sum((e.amount for e in events), Decimal(0))),
        "currencies": sorted({e.currency for e in events}),
        "pricing_versions": versions,
        # 混用要报出来：两个版本的钱加在一起，那个和没有意义。
        "mixed_pricing": len(versions) > 1,
    }


def create_billing_app(deps: BillingApiDeps) -> FastAPI:
    app = FastAPI(title="Flint billing & quota (BE-06)")

    @app.get("/billing")
    async def billing(x_user_id: str = Header()) -> Response:
        owner = Principal(kind="user", id=x_user_id)
        used = await deps.count_used(owner) if deps.count_used else None

        events: dict[str, Any] = {"status": "not_checked"}
        if deps.load_events is not None:
            rows = [e for e in await deps.load_events(owner) if e.owner == owner]
            items = []
            for row in rows:
                charge = (
                    await deps.load_usage(row.job_id) if deps.load_usage else None
                )
                items.append(event_json(
                    row, _usage(charge, row.job_id, checked=deps.load_usage is not None)
                ))
            events = {
                "status": "checked",
                "items": items,
                "reconciliation": reconciliation_json(rows),
            }

        return JSONResponse(
            status_code=200,
            content={
                "principal": {"kind": owner.kind, "id": owner.id},
                "billing": _billing(deps.config),
                "quota": _quota(used, owner, deps.config),
                "events": events,
            },
        )

    return app
