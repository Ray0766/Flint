"""定时批 cron 装配（ASM-04）：×2/日全量+增量，外加每日 revalidation 扫描。

## 接的是哪一根线

`flint/jobs/sched.py` 自述「cron 骨架：×2/日 批次定义（arq cron 于 worker 进程装配；
本模块提供 batch 定义与入口，实调度随部署任务接线）」。那句「随部署任务接线」一直没有
落地——批次定义在，没有任何进程按它触发。本模块就是那个装配处。

## 时刻只有一个真相

两个批次的时刻**取自** `sched.CRON_BATCHES`，revalidation 扫描的时刻**取自**
`revalidation.SCAN_HOUR`。本模块不写任何 cron 字面量：写第二份就有两个真相，改一处
另一处不跟，而「不跟」这件事没有任何测试会发现。

## 幂等复用既有锁

同一天同一批次重复触发只跑一次，走既有 `run_scheduled_ingest` 与
`lock:daily_ingest:{day}:{batch}`（`flint/jobs/sched.py`）。本模块不新造锁命名空间。
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date, datetime
from typing import TYPE_CHECKING, Any, Final, cast

import redis.asyncio as aioredis
from arq import cron as arq_cron
from arq.cron import CronJob

from flint.jobs import revalidation as revalidation_mod
from flint.jobs import sched as sched_mod
from flint.jobs.sched import ScheduledRunReport, run_scheduled_ingest

if TYPE_CHECKING:                                    # arq 的类型面只在检查期需要
    from arq.typing import WorkerCoroutine

REVALIDATION_JOB_NAME: Final[str] = "revalidation_scan"
_DAILY_TAIL: Final[tuple[str, str, str]] = ("*", "*", "*")


@dataclass(frozen=True)
class CronRegistration:
    """一条可取出检查的注册项——不启动真实调度也能断言注册面。"""

    name: str
    hour: int
    minute: int
    source: str          # 时刻的出处，写清楚是从哪个既有定义取的


def parse_daily_cron_expr(expr: str) -> tuple[int, int]:
    """把 `M H * * *` 解析成 (minute, hour)。非每日式一律抛，NEVER 猜。"""
    parts = expr.split()
    if len(parts) != 5 or tuple(parts[2:]) != _DAILY_TAIL:
        raise ValueError(
            f"只支持每日固定时刻的 cron 式（M H * * *），收到：{expr!r}"
        )
    try:
        minute, hour = int(parts[0]), int(parts[1])
    except ValueError as err:
        raise ValueError(f"每日 cron 式的分/时必须是整数：{expr!r}") from err
    return minute, hour


def build_cron_registrations() -> tuple[CronRegistration, ...]:
    """注册面：两个日更批次 + 一个 revalidation 扫描。时刻全部取自既有定义。"""
    regs: list[CronRegistration] = []
    for batch, expr in sched_mod.CRON_BATCHES.items():
        minute, hour = parse_daily_cron_expr(expr)
        regs.append(CronRegistration(
            name=f"daily_ingest_{batch}", hour=hour, minute=minute,
            source=f"flint.jobs.sched.CRON_BATCHES[{batch!r}]",
        ))
    regs.append(CronRegistration(
        name=REVALIDATION_JOB_NAME, hour=revalidation_mod.SCAN_HOUR, minute=0,
        source="flint.jobs.revalidation.SCAN_HOUR",
    ))
    return tuple(regs)


async def run_batch(
    client: aioredis.Redis,
    day: date,
    batch: str,
    ingest: Callable[[], Awaitable[None]],
    *,
    release: bool = True,
) -> ScheduledRunReport:
    """跑一个批次，幂等由既有 `lock:daily_ingest:{day}:{batch}` 保证。

    `release=False` 让锁留到 TTL 到期——**日更批次要的就是这个**：完成即释放的锁挡不住
    同一天的第二次触发（E4：日更幂等，晚到无意义）。`release=True` 是既有
    `run_scheduled_ingest` 的行为（完成即释放），留给要重跑的场景。
    """
    if release:
        return await run_scheduled_ingest(client, day, batch, ingest)
    lock = sched_mod.BatchLock(client, day, batch)
    if not await lock.acquire():
        return ScheduledRunReport(day=day, batch=batch, outcome="skipped")
    await ingest()
    return ScheduledRunReport(day=day, batch=batch, outcome="executed")


def build_cron_jobs(
    *,
    redis_url: str,
    day_of: Callable[[], date],
    ingest: Callable[[], Awaitable[None]],
    scan: Callable[[], Awaitable[None]],
) -> list[CronJob]:
    """把注册面变成 arq CronJob 清单，挂进 `flint/jobs/worker_main.py:build_worker`。

    `day_of` 注入当天日期（测试用固定值；生产传 `lambda: datetime.now(UTC).date()`），
    因为锁键按天分片，取日期这件事必须可注入才能被测。
    """
    def _batch_coroutine(batch: str) -> WorkerCoroutine:
        async def coroutine(_ctx: dict[Any, Any]) -> None:
            # `aioredis.Redis.from_url` 是仓内既有写法（harness/drill7.py:79）；
            # 模块级的 `aioredis.from_url` 在 redis 5.3 的桩里没有类型标注。
            client: aioredis.Redis = aioredis.Redis.from_url(redis_url)
            try:
                await run_batch(client, day_of(), batch, ingest, release=False)
            finally:
                await client.aclose()

        return cast("WorkerCoroutine", coroutine)

    async def _scan(_ctx: dict[Any, Any]) -> None:
        await scan()

    jobs: list[CronJob] = []
    for reg in build_cron_registrations():
        if reg.name == REVALIDATION_JOB_NAME:
            coroutine = cast("WorkerCoroutine", _scan)
        else:
            coroutine = _batch_coroutine(reg.name.removeprefix("daily_ingest_"))
        jobs.append(arq_cron(
            coroutine, name=reg.name, hour=reg.hour, minute=reg.minute,
            max_tries=1,          # 定时批 NEVER 靠盲重试补跑：下一次触发才是正路
            run_at_startup=False,
        ))
    return jobs


def today_utc() -> date:
    """生产用的 day_of：UTC 当天。抽成函数是为了让注入点有个明确默认值。"""
    from datetime import UTC
    return datetime.now(UTC).date()
