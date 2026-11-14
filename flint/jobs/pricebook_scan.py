"""BL-08：`pricebook_scan` 作业的 per-job 消费者（PriceBook 时效）。

## 接线前

`flint/jobs/dispatch.py` 的 `UnwiredKindReason` 写着「`flint/pricebook/seed.py`
只做种子数据，仓里还没有 pricebook_scan 作业的消费者」。于是「价目会不会过期」
只在**读的时候**算（渲染预算表时调 `check_stale`），没有任何东西定期扫一遍
告诉人「有 12 条已经过期了」。

## 只标，不改价

三条纪律方向一致——**数字必有出处**：

- 过期价目**照实标记并保留**：删了，引用它的那份报告里的数字就成了没有出处的数字；
- **NEVER 静默替换成新价**：换掉之后旧报告里的数字与库里对不上，而没人知道何时换的；
- 扫描**一行价格都不改**：改价是另一条路径（重新 seed / owner 录入）。

所以本模块对 `pricebook` 表**只读**——「顺手更新一下」是最自然的下一步，
所以这条在测试里有源码面守卫。

## 判定委托既有 `check_stale`

过期口径（`updated_at + stale_after_months × 30.44 天 < today`）在
`flint/pricebook/stale.py` 里已经有了，注记也有（`price_data_notes`）。
本模块 NEVER 再写一份：两处的月份折算只要差一点，同一条价目在两个界面上
就会一个红一个绿。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

import asyncpg

from flint.domain.models import JSON, PriceEntry
from flint.pricebook.stale import StaleCheck, check_stale, price_data_notes


@dataclass(frozen=True)
class StaleReport:
    """一次扫描的结果。**没有任何新价字段**——静默替换从「有地方放新价」开始。"""

    scanned: int
    stale: list[StaleCheck] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    skipped: bool = False


@dataclass
class PricebookScanDeps:
    dsn: str
    now: datetime
    today: date


def scan_stale_entries(entries: list[PriceEntry], today: date) -> StaleReport:
    """扫出过期价目。判定与注记**都**来自 `flint/pricebook/stale.py`。"""
    checks = [check_stale(entry, today) for entry in entries]
    return StaleReport(
        scanned=len(entries),
        stale=[c for c in checks if c.stale],
        notes=price_data_notes(entries, today),
    )


async def _load_entries(conn: asyncpg.Connection) -> list[PriceEntry]:
    rows = await conn.fetch(
        "SELECT entry_id, item, unit, price_low, price_high, currency, region, "
        "year, source, updated_at, stale_after_months FROM pricebook ORDER BY entry_id"
    )
    return [
        PriceEntry(
            entry_id=str(r["entry_id"]), item=str(r["item"]), unit=str(r["unit"]),
            price_low=float(r["price_low"]), price_high=float(r["price_high"]),
            currency=str(r["currency"]), region=str(r["region"]), year=int(r["year"]),
            source=str(r["source"]), updated_at=r["updated_at"],
            stale_after_months=int(r["stale_after_months"]),
        )
        for r in rows
    ]


async def run_pricebook_scan(
    job_id: str, payload: JSON, deps: PricebookScanDeps
) -> StaleReport:
    """消费一条 pricebook_scan 作业：读全表 → 标时效 → 状态机到 `done`。

    已终态的作业不重扫（`skipped=True`）——重放与重试都会撞上这一步。
    """
    conn = await asyncpg.connect(deps.dsn)
    try:
        state: str | None = await conn.fetchval(
            "SELECT state FROM jobs WHERE job_id = $1", job_id
        )
        if state in ("done", "failed", "cancelled"):
            return StaleReport(scanned=0, skipped=True)

        # `running` 不是本仓的 job 状态（`ck_jobs_state`）；扫描的第一步是读表 →
        # `retrieving`（与 BL-07 的复核消费者同口径）。
        await conn.execute(
            "UPDATE jobs SET state = 'retrieving', updated_at = $2 WHERE job_id = $1",
            job_id, deps.now,
        )
        report = scan_stale_entries(await _load_entries(conn), deps.today)
        await conn.execute(
            "UPDATE jobs SET state = 'done', progress = 100, updated_at = $2 "
            "WHERE job_id = $1",
            job_id, deps.now,
        )
        return report
    finally:
        await conn.close()
