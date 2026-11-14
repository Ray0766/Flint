"""revalidation：扫描器（M3-055）+ **per-job 消费者**（BL-07）。

- run_revalidation_scan：到期清单（M3-049 阶梯）逐项 submit
  kind="revalidation"（payload 携 project_id / due_on / trigger=scheduled）。
- run_revalidation：**消费**那些作业——此前它们只被塞进队列没人取，
  于是「到期复核」在系统里看起来「有」，实际一次都没跑过。

## 三条命名空间互不干扰

| 锁 | 键 |
|---|---|
| 日更批次（既有） | `lock:daily_ingest:{day}:{batch}` |
| 复核扫描（既有） | `lock:revalidation_scan:{day}` |
| **复核单项（本卡）** | `lock:revalidation:{project_id}:{due_on}` |

三族键构造上不可能相等（前缀不同）。撞上的后果很具体：一次日更批次会把当天的
复核锁顶掉（或反过来），而两者都会以为自己拿到了锁。

## stale 判定**委托**既有 Revalidator

判定件默认就是 `flint/revalidate/report.py#build_report`（→ `rerun_verdict` →
完整 gate1 三相位重跑）。本模块 **NEVER 再写一份判定**：同一件事两个真相是本仓
一路在防的老病，`build_shift` 是全仓唯一的 VerdictShift 构造点。
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Final

import asyncpg

from flint.domain.models import JSON, Principal
from flint.jobs.runner import PgJobRunner
from flint.revalidate.schedule import due_projects

SCAN_HOUR: Final[int] = 4


def scan_lock_key(day: date) -> str:
    return f"lock:revalidation_scan:{day.isoformat()}"


def revalidation_lock_key(project_id: str, due_on: date) -> str:
    """单项复核锁。与 `lock:daily_ingest:*` / `lock:revalidation_scan:*` 前缀互斥。"""
    return f"lock:revalidation:{project_id}:{due_on.isoformat()}"


async def run_revalidation_scan(
    runner: PgJobRunner,
    projects: list[tuple[str, date, date | None]],
    today: date,
) -> list[str]:
    submitted: list[str] = []
    for due in due_projects(projects, today):
        job_id = await runner.submit(
            kind="revalidation",
            payload={
                "project_id": due.project_id,
                "due_on": due.due_on.isoformat(),
                "trigger": "scheduled",
            },
            budget=0.0,
            owner_scope=Principal(kind="org", id="system"),
            initiated_by="u-system",
        )
        submitted.append(job_id)
    return submitted


# ═════════════════════ per-job 消费者（BL-07）

Revalidator = Callable[[JSON], JSON]


def default_revalidator(payload: JSON) -> JSON:
    """默认判定件 = 既有 Revalidator。

    这里是**一层薄壳**，不是第二份判定：真正干活的是
    `flint/revalidate/report.py#build_report`（→ `rerun_verdict` → 完整 gate1
    三相位重跑）。壳的存在只为把 job payload 的形状与判定件的签名隔开——
    判定逻辑一行都不在这里。
    """
    raise NotImplementedError(
        "default_revalidator 需要 Gate1Deps（provider + searcher）才跑得起来："
        "调用方 MUST 注入 RevalidationDeps.revalidator。"
        "本壳存在的意义是指明判定件是 flint/revalidate/report.py#build_report，"
        "NEVER 在本模块另写一份判定。"
    )


# 判定件的出处写在函数对象上，供守卫核对（源码字符串会被注释骗，属性不会）。
default_revalidator.__wrapped__ = None  # type: ignore[attr-defined]


def _bind_default() -> None:
    from flint.revalidate.report import build_report

    default_revalidator.__wrapped__ = build_report  # type: ignore[attr-defined]


_bind_default()


@dataclass
class RevalidationDeps:
    """消费者的注入面。`redis=None` = 不加锁（单进程/测试口径）。"""

    dsn: str
    now: datetime
    redis: Any | None
    revalidator: Revalidator


async def run_revalidation(job_id: str, payload: JSON, deps: RevalidationDeps) -> str:
    """消费一条 revalidation 作业。返回 `"executed"` / `"skipped"`。

    幂等有两道：① 作业已在终态 → 不重跑（重放与重试都会撞上这一步）；
    ② 同一 (project_id, due_on) 的锁被别人持有 → 跳过。
    """
    project_id = payload.get("project_id")
    if not project_id:
        raise ValueError(
            f"作业 {job_id} 的 payload 缺 project_id——"
            "静默通过会让一批本该复核的项目永远排不上，而作业状态是 done。"
        )
    due_on = date.fromisoformat(str(payload.get("due_on") or deps.now.date().isoformat()))

    conn = await asyncpg.connect(deps.dsn)
    try:
        state: str | None = await conn.fetchval(
            "SELECT state FROM jobs WHERE job_id = $1", job_id
        )
        if state in ("done", "failed", "cancelled"):
            return "skipped"

        lock_token: str | None = None
        if deps.redis is not None:
            key = revalidation_lock_key(str(project_id), due_on)
            lock_token = f"{job_id}:{deps.now.isoformat()}"
            got = await deps.redis.set(key, lock_token, nx=True, ex=_LOCK_TTL_SECONDS)
            if not got:
                return "skipped"                 # 别人在跑同一项，晚到的无意义

        try:
            await conn.execute(
                # `running` 不是本仓的 job 状态（`ck_jobs_state` 只认 queued /
                # retrieving / judging / drafting / validating / done / failed /
                # cancelled）。复核= 完整 gate1 重跑，第一步是检索 → `retrieving`。
                # 中间三相不逐个上报：判定件是委托出去的，它不回报相位（trace §8 登记）。
                "UPDATE jobs SET state = 'retrieving', updated_at = $2 WHERE job_id = $1",
                job_id, deps.now,
            )
            deps.revalidator(payload)            # 判定**委托**，见模块头
            await conn.execute(
                "UPDATE jobs SET state = 'done', progress = 100, updated_at = $2 "
                "WHERE job_id = $1",
                job_id, deps.now,
            )
        finally:
            if deps.redis is not None and lock_token is not None:
                # 令牌不符的 release 是 no-op（与 sched.BatchLock 同口径：不误放他人锁）
                await deps.redis.eval(
                    _RELEASE_LUA, 1,
                    revalidation_lock_key(str(project_id), due_on), lock_token,
                )
        return "executed"
    finally:
        await conn.close()


_LOCK_TTL_SECONDS: Final[int] = 2 * 60 * 60      # 与 sched.DEFAULT_TTL_SECONDS 同值
_RELEASE_LUA: Final[str] = (
    "if redis.call('get', KEYS[1]) == ARGV[1] then "
    "return redis.call('del', KEYS[1]) else return 0 end"
)
