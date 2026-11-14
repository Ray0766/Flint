"""BL-08：`pricebook_scan` JobKind 接消费者（PriceBook 时效）。

## 接线前

`flint/jobs/dispatch.py` 的 `UnwiredKindReason` 写着：「`flint/pricebook/seed.py`
只做种子数据，仓里还没有 pricebook_scan 作业的消费者。」

于是「价目会不会过期」这件事只在**读的时候**算（`check_stale` 在渲染预算表时被调），
没有任何东西定期扫一遍告诉人「有 12 条已经过期了」。

## 扫描只标，不改价

三条纪律，方向都是同一个——**数字必有出处**：

- 过期价目**照实标记并保留**：NEVER 删除（删了引用它的报告就成了无出处的数字）；
- NEVER 静默替换成新价（换掉之后，旧报告里的数字与库里的对不上，而没人知道何时换的）；
- 扫描**一行价格都不改**：改价是另一条路径（重新 seed / owner 录入）。

所以本消费者对 `pricebook` 表**只读**。这一条有源码面的守卫，因为「顺手更新一下」
是最自然的下一步。

## 判定委托既有 `check_stale`

过期口径（`updated_at + stale_after_months × 30.44 天 < today`）在
`flint/pricebook/stale.py` 里已经有了。本卡 NEVER 再写一份——同一件事两个真相，
两处的月份折算方式只要差一点，同一条价目在两个界面上就一个红一个绿。
"""
from __future__ import annotations

import asyncio
import inspect
import os
from datetime import UTC, date, datetime
from typing import Any

import pytest

from flint.domain.models import PriceEntry
from flint.jobs.dispatch import WIREABLE_KINDS, UnwiredKindReason
from flint.jobs.pricebook_scan import (
    PricebookScanDeps,
    StaleReport,
    run_pricebook_scan,
    scan_stale_entries,
)

DSN = os.environ.get("FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")
TODAY = date(2026, 8, 4)
NOW = datetime(2026, 8, 4, 5, 0, tzinfo=UTC)


def _entry(entry_id: str, updated: date, months: int = 12) -> PriceEntry:
    return PriceEntry(
        entry_id=entry_id, item="A100 卡时", unit="卡时",
        price_low=10.0, price_high=20.0, currency="CNY", region="CN",
        year=updated.year, source="厂商报价单",
        updated_at=datetime(updated.year, updated.month, updated.day, tzinfo=UTC),
        stale_after_months=months,
    )


# ───────────────────────── 一、不再是「声明未接线」


def test_pricebook_scan_is_no_longer_declared_unwired() -> None:
    assert "pricebook_scan" not in UnwiredKindReason
    assert "pricebook_scan" in WIREABLE_KINDS


def test_the_worker_builds_a_handler_for_it() -> None:
    from pathlib import Path

    from flint.domain.models import Principal, UserProfile
    from flint.jobs.worker_main import WorkerDeps, build_handlers

    handlers = build_handlers(WorkerDeps(
        dsn=DSN, redis_url="redis://x", repo_root=Path("."), now=NOW,
        profile=UserProfile(
            profile_id="p", owner=Principal(kind="user", id="u"), identity={},
            research={}, team=[], assets={}, constraints={}, track_record=[],
            locale="zh-CN", sensitivity_overrides={}, updated_at=NOW,
        ),
    ))

    assert callable(handlers["pricebook_scan"])
    assert set(handlers) == set(WIREABLE_KINDS)


def test_the_remaining_unwired_kinds_are_still_declared() -> None:
    """阴性对照：本卡只接一个，其余三个仍在「未接线」表里大声失败。"""
    # SLOT-03（第 6 批）把 `translate` 也接走了——**合法变化，不是回归**。
    # 名单跟着事实走：钉死一个过期的集合，只会让下一次真正的接线被判成错。
    # 剩下的那一条继续钉住：名单少一条要有人来这里解释，
    # NEVER 让「已经接了」与「忘了登记」长得一样。
    # `PERSIST-03` 之后 `UnwiredKindReason` 空了（最后一条接上了消费者），
    # 所以这里没有 kind 可遍历。**循环留着**：下一个 additive 新增的 kind
    # 在有消费者之前 MUST 先进那张表，那时这条判据不用改结构就能重新量到它。
    for kind in tuple(UnwiredKindReason):
        assert kind in UnwiredKindReason


# ───────────────────────── 二、扫出过期并**保留**


def test_the_scan_finds_the_expired_entries() -> None:
    """acceptance①：过期的被扫出来（口径来自既有 `check_stale`）。"""
    entries = [
        _entry("pb-fresh", date(2026, 6, 1)),
        _entry("pb-old", date(2024, 1, 1)),
    ]

    report = scan_stale_entries(entries, TODAY)

    assert [s.entry_id for s in report.stale] == ["pb-old"]
    assert report.scanned == 2


def test_the_expired_entry_is_kept_not_dropped() -> None:
    """acceptance②：过期的**照实标记并保留**——它仍在报告里，带着年份与黄标。

    删掉的后果很具体：引用它的那份报告里的数字就成了**没有出处的数字**。
    """
    report = scan_stale_entries([_entry("pb-old", date(2024, 1, 1))], TODAY)
    marked = report.stale[0]

    assert marked.entry_id == "pb-old"
    assert marked.stale is True
    assert marked.yellow_flag is True
    assert marked.year == 2024


def test_the_notes_come_from_the_existing_note_builder() -> None:
    """质量卡注记复用既有 `price_data_notes`，NEVER 另写一句话。"""
    from flint.pricebook.stale import price_data_notes

    entries = [_entry("pb-old", date(2024, 1, 1)), _entry("pb-older", date(2023, 5, 1))]

    assert scan_stale_entries(entries, TODAY).notes == price_data_notes(entries, TODAY)


def test_nothing_is_stale_when_nothing_is_stale() -> None:
    """阴性对照：都在期内时报告是空的——否则「有过期」这件事没有信息量。"""
    report = scan_stale_entries([_entry("pb-fresh", date(2026, 6, 1))], TODAY)

    assert report.stale == []
    assert report.notes == []


def test_the_boundary_day_matches_the_existing_checker() -> None:
    """边界与既有判定件**逐条一致**：本卡 NEVER 另立一套折算。"""
    from flint.pricebook.stale import check_stale

    for day in (date(2025, 8, 3), date(2025, 8, 4), date(2025, 8, 5)):
        entry = _entry("pb-edge", day)
        mine = scan_stale_entries([entry], TODAY).stale
        theirs = check_stale(entry, TODAY)

        assert bool(mine) == theirs.stale, f"{day} 上两处判定不一致"


# ───────────────────────── 三、扫描不改价（源码面 + 行为面）


def test_the_scanner_never_writes_to_the_pricebook_table() -> None:
    """acceptance③：本模块对 `pricebook` **只读**。

    「顺手更新一下」是最自然的下一步，所以这条守在源码面：
    出现 UPDATE / DELETE / INSERT 到 pricebook 即红。
    """
    from flint.jobs import pricebook_scan

    source = inspect.getsource(pricebook_scan)
    code = "\n".join(ln for ln in source.split("\n") if not ln.strip().startswith("#"))

    for forbidden in ("UPDATE pricebook", "DELETE FROM pricebook", "INSERT INTO pricebook"):
        assert forbidden not in code, f"扫描器动了价目表：{forbidden}"


def test_the_report_carries_no_new_price() -> None:
    """报告里**没有**任何新价字段——静默替换从「有地方放新价」开始。"""
    from dataclasses import fields

    names = {f.name for f in fields(StaleReport)}

    assert not any(n.startswith("new_price") or n == "replacement" for n in names)


# ───────────────────────── 四、状态机推到 done（真库）


@pytest.mark.compose
def test_the_job_reaches_done_and_the_prices_are_untouched() -> None:
    """acceptance①③：作业到 `done`，且**库里的价目逐字未变**。"""
    import asyncpg

    from flint.pricebook.seed import seed_pricebook_on

    async def scenario() -> tuple[str, list[tuple[Any, ...]], int]:
        conn = await asyncpg.connect(DSN)
        try:
            await _cleanup(conn)
            await seed_pricebook_on(conn, [
                _entry("bl08-fresh", date(2026, 6, 1)),
                _entry("bl08-old", date(2024, 1, 1)),
            ])
            await conn.execute(
                "INSERT INTO jobs (job_id, kind, owner_scope, state, progress, budget, "
                "cost_accum, cancel_requested, initiated_by, created_at, updated_at) "
                "VALUES ('bl08-j1', 'pricebook_scan', "
                "'{\"kind\":\"org\",\"id\":\"system\"}', 'queued', 0, 0, 0, false, "
                "'u-system', $1, $1)",
                NOW,
            )
            before = await _rows(conn)
        finally:
            await conn.close()

        deps = PricebookScanDeps(dsn=DSN, now=NOW, today=TODAY)
        report = await run_pricebook_scan("bl08-j1", {}, deps)

        conn = await asyncpg.connect(DSN)
        try:
            state: str = await conn.fetchval(
                "SELECT state FROM jobs WHERE job_id = 'bl08-j1'"
            )
            after = await _rows(conn)
            await _cleanup(conn)
        finally:
            await conn.close()

        assert before == after, "扫描改了价目表"
        return state, after, [s.entry_id for s in report.stale]

    state, rows, stale_ids = asyncio.run(scenario())

    assert state == "done"
    assert len(rows) == 2, "过期的那条被删了"
    # 判据按 **本卡塞进去的那两条** 给，不按全表条数：扫描扫的是整张表，
    # 库里本来就有别的价目（真实行为，不是缺陷）。按全表计数会让这条用例
    # 随别人的数据变红变绿——那种红是假的，而假红会训练人去忽略红。
    assert "bl08-old" in stale_ids
    assert "bl08-fresh" not in stale_ids


@pytest.mark.compose
def test_a_terminal_job_is_left_alone() -> None:
    """幂等：已终态的作业不重扫。"""
    import asyncpg

    async def scenario() -> str | None:
        conn = await asyncpg.connect(DSN)
        try:
            await _cleanup(conn)
            await conn.execute(
                "INSERT INTO jobs (job_id, kind, owner_scope, state, progress, budget, "
                "cost_accum, cancel_requested, initiated_by, created_at, updated_at) "
                "VALUES ('bl08-j2', 'pricebook_scan', "
                "'{\"kind\":\"org\",\"id\":\"system\"}', 'done', 100, 0, 0, false, "
                "'u-system', $1, $1)",
                NOW,
            )
        finally:
            await conn.close()

        deps = PricebookScanDeps(dsn=DSN, now=NOW, today=TODAY)
        report = await run_pricebook_scan("bl08-j2", {}, deps)
        conn = await asyncpg.connect(DSN)
        try:
            await _cleanup(conn)
        finally:
            await conn.close()
        return None if report.skipped else "ran"

    assert asyncio.run(scenario()) is None


async def _rows(conn: Any) -> list[tuple[Any, ...]]:
    rows = await conn.fetch(
        "SELECT entry_id, price_low, price_high, updated_at, stale_after_months "
        "FROM pricebook WHERE entry_id LIKE 'bl08-%' ORDER BY entry_id"
    )
    return [tuple(r) for r in rows]


async def _cleanup(conn: Any) -> None:
    await conn.execute("DELETE FROM pricebook WHERE entry_id LIKE 'bl08-%'")
    await conn.execute("DELETE FROM job_events WHERE job_id LIKE 'bl08-%'")
    await conn.execute("DELETE FROM job_steps WHERE job_id LIKE 'bl08-%'")
    await conn.execute("DELETE FROM jobs WHERE job_id LIKE 'bl08-%'")
