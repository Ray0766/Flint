"""PriceBook 时效语义（M3-012，v0.3.1 §3.2）。

- 过期判定：updated_at + stale_after_months < today（按 30.44 天/月折算的
  日粒度口径，写死避免月份边界歧义读法）；
- 过期仍可用：yellow_flag（预算表单元格黄标位）+ 质量卡「单价数据为
  {year} 年」注记（price_data_notes，M2-048 进账面）——双重标注缺一不可。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from flint.domain.models import PriceEntry

_DAYS_PER_MONTH = 30.44


@dataclass(frozen=True)
class StaleCheck:
    entry_id: str
    stale: bool
    yellow_flag: bool
    year: int


def check_stale(entry: PriceEntry, today: date) -> StaleCheck:
    ttl = timedelta(days=entry.stale_after_months * _DAYS_PER_MONTH)
    stale = entry.updated_at.date() + ttl < today
    return StaleCheck(
        entry_id=entry.entry_id, stale=stale, yellow_flag=stale,
        year=entry.updated_at.year,
    )


def price_data_notes(entries: list[PriceEntry], today: date) -> list[str]:
    stale_years = sorted(
        {check.year for e in entries if (check := check_stale(e, today)).stale}
    )
    return [f"单价数据为 {year} 年" for year in stale_years]
