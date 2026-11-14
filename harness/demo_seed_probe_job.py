"""demo 夹具：给取证探针种一条**属于它自己**的作业（opt-in，NEVER 自动跑）。

## 为什么需要它

第 4 批把鉴权接上之后，`GET /jobs/{id}` 判的是「发起人本人，或 owner-scope 成员」。
而 `harness/fe_smoke.py` 的样例 id `m1004-j` 是**鉴权之前**从库里查出来的：

```
job_id       m1004-j
initiated_by u-sys                ← 不是探针那个人
owner_scope  {"kind":"org","id":"sys"}
```

探针不发 `X-User-Id`，demo 后端的中间件给它注 `demo-user`。于是端点回 **403**——
**那是正确行为**，屏上留下一条控制台报错，四条既有判据跟着红。

`DEC-037`（owner 2026-08-08）裁的是：**改取证样例，不改产品**。

## NEVER 把那条 403 加进控制台噪声白名单

加进去等于**把鉴权正确工作的证据当成噪声吞掉**——而下一次鉴权真的坏了时，
那条判据不会响。所以这里换的是样例，不是判据的容忍度。

## 这条作业是什么

一条**已完成**的 `daily_ingest`，发起人就是探针那个身份。选 `daily_ingest` 是因为
demo 库里本来就有一族同类（`drill-2026-*`），形状经过验证；选 `done` 是因为
取证要的是一屏稳定内容，而 `queued` 的作业屏上只有一行状态。

## 事件也要种，否则 SSE 那条判据只会跳过

`GET /jobs/{id}/events` 对一条**终态且没有事件**的作业，冲刷之后直接关流——
一个 `data:` 都不发。`tests/v041/test_sse_live.py` 于是走进
「demo 栈没起」那个 skip 分支，而那句话是**假的**：栈起着，是这条作业没有话说。

**跳过比红更坏**：红了有人会去看，跳过只是少了一行。所以这里连事件一起种，
形状逐字照 `flint/jobs/events.py` 的契约（每条 payload 带 `kind`），
用的是库里既有那族 `drill-*` 已经验证过的 `step` 形状。

**owner_scope 用 user 域指向探针自己**：用 org 域的话，能不能看取决于
`memberships` 表里有没有那一行——那就把「样例属于探针」这件事又押在另一张表上。

## 边界（读这段再决定要不要跑）

- **只写 `jobs` 一行**，不碰任何既有行；重复跑幂等（`ON CONFLICT DO NOTHING`）；
- 连的是 `FLINT_DEMO_DSN`（默认本机 55432 的 `flint`）——**NEVER 指向生产**；
- 不删任何东西。`m1004-j` **原样留着**：它是「不属于我的作业」的活样本，
  屏上该显示「无权查看」这件事将来要靠它来量
  （单据 `docs/blocked/JOB-SCREEN-HAS-NO-DENIED-STATE.md`）。

跑法：

    .venv/Scripts/python.exe -m harness.demo_seed_probe_job
"""
from __future__ import annotations

import asyncio
import json
import os
from datetime import UTC, datetime

import asyncpg

DSN = os.environ.get("FLINT_DEMO_DSN", "postgresql://flint:flint@localhost:55432/flint")
# demo 后端的 `_InjectUserMiddleware` 在没有 `X-User-Id` 时注的就是这个 id，
# 而探针（playwright）不发那个头。**一处真相**：改这里之前先改那个中间件。
PROBE_USER = "demo-user"
PROBE_JOB_ID = "probe-owned-ingest"


async def seed(dsn: str = DSN) -> str:
    """种下（或确认已有）那条属于探针的作业，返回它的 id。"""
    now = datetime.now(UTC)
    conn = await asyncpg.connect(dsn)
    try:
        # 探针那个身份必须真的是一行 users——鉴权的第一道判的就是这个
        # （`IdentityUnknown`）。没有它的话，端点回的是 401 而不是 200，
        # 而 401 与 403 在屏上长得不一样，取证会指向一个不存在的缺陷。
        exists: bool = await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM users WHERE user_id = $1)", PROBE_USER)
        if not exists:
            raise RuntimeError(
                f"库里没有 {PROBE_USER} 这一行 users——先跑 AUTH-05 那份种子。"
                "NEVER 在这里顺手插一个用户：身份表是鉴权的根，"
                "由本脚本悄悄补一行，等于让取证自己给自己发身份。"
            )
        await conn.execute(
            "INSERT INTO jobs (job_id, kind, project_id, owner_scope, state, progress, "
            "partial_output_ref, budget, cost_accum, cancel_requested, error, "
            "initiated_by, created_at, updated_at) "
            "VALUES ($1, 'daily_ingest', NULL, $2::jsonb, 'done', 1.0, NULL, 0.0, 0.0, "
            "false, NULL, $3, $4, $4) ON CONFLICT (job_id) DO NOTHING",
            PROBE_JOB_ID,
            json.dumps({"kind": "user", "id": PROBE_USER}, ensure_ascii=False),
            PROBE_USER, now)
        # 事件：一对 step 开始/结束 + 一条终态。`ON CONFLICT DO NOTHING` 保幂等，
        # seq 从 1 起（与既有 `drill-*` 一族同形）。
        events = [
            {"kind": "step", "phase": "start", "step_name": "fetch:weibo",
             "cost": None},
            {"kind": "step", "phase": "end", "step_name": "fetch:weibo", "cost": 0.0},
            {"kind": "status", "state": "done"},
        ]
        for seq, payload in enumerate(events, start=1):
            await conn.execute(
                "INSERT INTO job_events (job_id, seq, ts, payload) "
                "VALUES ($1, $2, $3, $4::jsonb) ON CONFLICT DO NOTHING",
                PROBE_JOB_ID, seq, now,
                json.dumps(payload, ensure_ascii=False))
    finally:
        await conn.close()
    return PROBE_JOB_ID


def main() -> int:
    job_id = asyncio.run(seed())
    print(f"probe-owned job ready: {job_id} (initiated_by={PROBE_USER})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
