"""调度与重叠保护：cron ×2/日 + 分布式锁（M1-036，技术方案 E4）。

- 锁：`lock:daily_ingest:{day}:{batch}`（E4 命名），SET NX EX + 持有者令牌；
  TTL 兜底崩溃释放（E4 初值 2h），完成即释放；令牌不符的 release 是 no-op
  （不误放他人锁）。
- 重叠保护：同批次并发触发只有拿到锁的一个执行，其余 skip 并告警
  （E4：日更幂等，晚到无意义）。
- cron 骨架：×2/日 批次定义（arq cron 于 worker 进程装配；本模块提供
  batch 定义与入口，实调度随部署任务接线）。
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date
from typing import Any, Final, Literal, cast
from uuid import uuid4

import redis.asyncio as aioredis

from flint.obs import get_logger

DEFAULT_TTL_SECONDS: Final[int] = 2 * 60 * 60  # E4: TTL 2h

# ×2/日：清晨全量批 + 午后增量批（时刻为 arq cron 装配参数）
CRON_BATCHES: Final[dict[str, str]] = {"am": "0 3 * * *", "pm": "0 15 * * *"}

_RELEASE_LUA: Final[str] = (
    "if redis.call('get', KEYS[1]) == ARGV[1] then "
    "return redis.call('del', KEYS[1]) else return 0 end"
)

BatchOutcome = Literal["executed", "skipped"]


def lock_key(day: date, batch: str) -> str:
    return f"lock:daily_ingest:{day.isoformat()}:{batch}"


@dataclass(frozen=True)
class ScheduledRunReport:
    day: date
    batch: str
    outcome: BatchOutcome


class BatchLock:
    def __init__(
        self,
        client: aioredis.Redis,
        day: date,
        batch: str,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ) -> None:
        self._client = client
        self._key = lock_key(day, batch)
        self._ttl = ttl_seconds
        self._token = uuid4().hex

    async def acquire(self) -> bool:
        ok = await cast(
            "Awaitable[Any]",
            self._client.set(self._key, self._token, nx=True, ex=self._ttl),
        )
        return bool(ok)

    async def release(self) -> bool:
        """Token-checked release: only the holder's token deletes the key."""
        removed = await cast(
            "Awaitable[Any]",
            self._client.eval(_RELEASE_LUA, 1, self._key, self._token),
        )
        return bool(removed)


async def run_scheduled_ingest(
    client: aioredis.Redis,
    day: date,
    batch: str,
    ingest: Callable[[], Awaitable[None]],
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> ScheduledRunReport:
    lock = BatchLock(client, day, batch, ttl_seconds=ttl_seconds)
    if not await lock.acquire():
        get_logger("flint.jobs.sched").warning(
            "ingest_batch_skipped_overlap", day=day.isoformat(), batch=batch
        )
        return ScheduledRunReport(day=day, batch=batch, outcome="skipped")
    try:
        await ingest()
    finally:
        await lock.release()
    return ScheduledRunReport(day=day, batch=batch, outcome="executed")
