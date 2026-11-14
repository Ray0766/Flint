"""DESIGN-STATE：把作业推进到某个状态——**一处真相**。

## 「作业跑完没有」这件事有两个记号，它们 MUST 一起写

| 记号 | 谁读它 |
|---|---|
| `jobs.state` | 轮询 `GET /jobs/{id}` 的屏 |
| 事件流里的 `StatusChanged` | 订阅 SSE 的屏 |

**只写一个的后果实测过**（`SMOKE-01`，2026-08-11）：
`design_generate` 只往事件流里追加 `{"kind":"status","state":"done"}`，
从不碰 `jobs.state`。于是那一跑**真的产出了 192 个片段的设计稿**，
而 `jobs.state` 停在 `queued`——

> 用户侧症状是「点了生成，转圈不停，而内容其实已经出来了」。
> 看起来像卡死，实际是两块表没对上。

## 为什么搬到这里

改前这个函数在**三处**各有一份（`compose.py` · `gate1.py` · `spec_export.py`），
逻辑逐字相同、只有换行不同。而 `design_generate.py` **一份都没有**。

三份并存时没人看得出「谁在推进状态」这件事有统一口径；
第四族接进来的时候，最省事的写法就是自己再写一套——
**两套推进器会让「作业跑完没有」再长出第三个真相**（owner 逐字）。

所以这里只留一处，四族都引用它。**NEVER 在别处另写一套推进状态的代码。**

## 幂等：已经在那个状态就什么都不做

重跑同一步不会重复推事件——`StatusChanged` 是给人看进度的，
同一个状态连推两次会让屏上出现两条一样的「已完成」。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from flint.domain.models import JobState, StatusChanged


async def enter_state(
    conn: Any,
    events: Any,
    job_id: str,
    target: JobState,
    now: datetime,
) -> None:
    """把作业推进到 `target`：**库里那一行与事件流一起写**。

    `conn` 是 asyncpg 连接，`events` 是事件流（`append(job_id, payload, ts=)`）。
    两个参数都不带具体类型是刻意的：调用方各自持有自己的连接与流实现，
    而本函数只关心「这两件事一起发生」。

    幂等：`current == target` 时直接返回，NEVER 重复推事件。
    """
    current: str = await conn.fetchval(
        "SELECT state FROM jobs WHERE job_id = $1", job_id
    )
    if current == target:
        return
    await conn.execute(
        "UPDATE jobs SET state = $2, updated_at = $3 WHERE job_id = $1",
        job_id, target, now,
    )
    await events.append(
        job_id, StatusChanged(kind="status", state=target), ts=now
    )
