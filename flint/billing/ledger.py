"""SHIP-01：计费事件账（**append-only**、按 owner 隔离、可对账）。

## 账一旦会改，它就不是账了

同 `event_id` 二次写入直接拒绝（`LedgerImmutable`）。本类**没有** update / delete —
对账时若两版都存在过，谁也说不清哪一版是真的。

（与 `flint/design/checkpoints.py#HistoryImmutable`、`flint/fav/store.py` 同一条纪律：
历史只增不改。）

## 按 owner 隔离（D7 多租户）

`for_owner` 只返回那个 owner 的条目，且返回**副本**——改返回值 NEVER 影响账本。

## 每条要能对上账

`owner / job_id / tier / at / pricing_version` 五样缺一不可（卡面 acceptance④）：

- 没有 `job_id`，一笔钱对不上是哪次运行；
- 没有 `pricing_version`，两次定价改动之间的账混在一起就再也分不开——
  所以 `reconcile` 会把**口径版本混用**明确报出来：两个版本的钱加在一起，
  那个和没有意义。

**零真实支付**：本模块 NEVER 接任何支付网关、NEVER 持有任何密钥（S2-10 红线）。
金额从哪来是调用方的事，本模块只记。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any

from flint.domain.models import Principal


class LedgerImmutable(Exception):
    """试图改写一条已存在的计费事件。"""


@dataclass(frozen=True)
class BillingEvent:
    """一条计费事件。五个对账字段缺一不可（见模块 docstring）。"""

    event_id: str
    owner: Principal
    job_id: str
    tier: str
    at: datetime
    amount: Decimal
    currency: str
    pricing_version: str


@dataclass
class BillingLedger:
    """内存实现；SQL 实现随 E2 接入（与 `SnapshotHistoryStore` 同一房规）。"""

    _events: dict[str, BillingEvent] = field(default_factory=dict)
    _order: list[str] = field(default_factory=list)

    def append(self, event: BillingEvent, *, expect_currency: str | None = None) -> None:
        """记一条。同 id 二次写入拒绝；币种不符也拒绝。

        币种这一道是因为两种币种的钱加在一起，那个和是错的——而错在
        对账那一刻才发现时，已经分不清是哪几条串了。
        """
        if event.event_id in self._events:
            raise LedgerImmutable(
                f"计费事件 {event.event_id} 已存在：账只增不改"
            )
        if expect_currency is not None and event.currency != expect_currency:
            raise ValueError(
                f"币种不符：事件是 {event.currency}，配置是 {expect_currency}"
            )
        self._events[event.event_id] = event
        self._order.append(event.event_id)

    def for_owner(self, owner: Principal) -> list[BillingEvent]:
        """该 owner 的条目（**副本**，按写入顺序）。D7：看不见别人的账。"""
        return [
            self._events[eid] for eid in self._order
            if self._events[eid].owner == owner
        ]

    def reconcile(self, owner: Principal) -> dict[str, Any]:
        """对账：条数 + 金额合计 + 口径版本集合。空账出 0，不是报错。"""
        events = self.for_owner(owner)
        versions = sorted({e.pricing_version for e in events})
        return {
            "owner_id": owner.id,
            "count": len(events),
            "total": sum((e.amount for e in events), Decimal(0)),
            "currencies": sorted({e.currency for e in events}),
            "pricing_versions": versions,
            # 混用要报出来：两个版本的钱加在一起，那个和没有意义
            "mixed_pricing": len(versions) > 1,
        }
