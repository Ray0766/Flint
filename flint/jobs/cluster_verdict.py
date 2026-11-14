"""PERSIST-04：cluster ↔ 判定的写法与读法（`cluster_verdicts` 表，迁移 0025）。

## 为什么要有这个模块

判定按 **job 键**落盘，从一个热点出发无从查起（`DEC-044` / `docs/blocked/HOTSPOT-03.md`）。
本模块把「这次判定是为哪几个热点跑的」记下来，并提供反过来查的那一步。

## 三个函数各管一件事

- `clusters_for_topic` —— **数据从哪来**：沿四跳把主题查回热点簇；
- `record_cluster_verdicts` —— 写关系行（幂等）；
- `latest_verdict_job` —— 按热点取**最新一条**判定的 job。

## 四跳链路，最后一跳穿 jsonb

```
topics.topic_id → topics.seed_id
                → topic_seeds.origin_id
                → origins.payload->'card_ids'      ← 只有 kind='combo' 才有
                → evidence_cards.cluster_id
```

**`topic_seeds` 没有 `card_ids` 列**（开工时实查 `information_schema` 确认过，
写这段之前先猜过一次，猜错了）——`card_ids` 在 `origins.payload` 里，
是 combo 建 Origin 时写进去的。

**`kind = 'combo'` 这个过滤 NEVER 省**：`OriginKind` 还有
`idea` / `domain` / `competitor` / `document` 四种，它们的 payload 里
**根本没有 `card_ids`**。不过滤的话，一个形状不同的 payload 会静静地回空，
而「这条 origin 不是 combo」与「这个 combo 一张卡都没有」在结果上长得一模一样。

## 查不到就不写行

不带 `topic_id` 的旧提交路径、非 combo 的 origin、卡查不回簇——三种都回空集，
于是**一行都不写**，分析屏对那些热点仍然如实说「还没有判定」。

**NEVER 为了让表不空而猜一个 cluster**：猜错时用户看到的是**另一个热点的判定**，
并会把它引进计划书。这与「猜 job id 那条路」当初被判死是同一个理由
（`DEC-044` 原话）——变的是前提（现在有真相可查了），纪律没变。

## 关系行与判定快照在同一个事务里

调用点在 `flint/jobs/gate1.py` 的 `validate` 步内，**与判定快照同一个事务**。
分两次提交的话，`kill -9` 卡在中间会留下「判定落了、关系没写」，
而续跑会跳过那一步——那次判定就永远查不回来了。
`CHAIN-01` 在同一处对 claims 用的是同一条理由。

所以本模块的函数**都吃 `conn` 而不是 `dsn`**：自己开连接就等于自己开事务，
那正好把上面那条纪律绕过去。
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import asyncpg

#: 只有这一种 origin 的 payload 里有 `card_ids`（`contracts_v04#Origin` 的注释）。
COMBO_KIND = "combo"


async def clusters_for_topic(conn: asyncpg.Connection, topic_id: str) -> list[str]:
    """沿四跳把主题查回热点簇。查不到就是查不到——**NEVER 猜**。

    回的是**去重且有序**的一组：一次判定对应一组热点（见模块 docstring）。
    """
    row = await conn.fetchrow(
        "SELECT o.kind AS kind, o.payload AS payload "
        "FROM topics t "
        "JOIN topic_seeds s ON s.seed_id = t.seed_id "
        "JOIN origins o ON o.origin_id = s.origin_id "
        "WHERE t.topic_id = $1",
        topic_id,
    )
    if row is None or row["kind"] != COMBO_KIND:
        # 主题不在库里，或者这条 origin 根本不是 combo（它没有 card_ids）。
        # **NEVER 抛**：关系写不下只是「查不回来」，那次判定本身是有效的，
        # 为此让整个作业失败是把一件小事变成一件大事。
        return []

    payload = row["payload"]
    parsed: Any = json.loads(payload) if isinstance(payload, str) else payload
    card_ids = parsed.get("card_ids") if isinstance(parsed, dict) else None
    if not isinstance(card_ids, list) or not card_ids:
        return []

    found = await conn.fetch(
        "SELECT DISTINCT cluster_id FROM evidence_cards WHERE card_id = ANY($1::text[])",
        [str(card) for card in card_ids],
    )
    return sorted(r["cluster_id"] for r in found if r["cluster_id"])


async def record_cluster_verdicts(
    conn: asyncpg.Connection, *, job_id: str, cluster_ids: list[str], now: datetime,
) -> None:
    """写关系行。**幂等**：续跑同一个作业 NEVER 写出第二行。

    `DO NOTHING` 而不是 `DO UPDATE`：`created_at` 记的是**这段关系建立的时刻**，
    续跑不该把它往后推——推了之后「取最新一条」会把一次续跑当成一次新判定。
    """
    for cluster_id in cluster_ids:
        await conn.execute(
            "INSERT INTO cluster_verdicts (cluster_id, job_id, created_at) "
            "VALUES ($1, $2, $3) ON CONFLICT (cluster_id, job_id) DO NOTHING",
            cluster_id, job_id, now,
        )


# `latest_verdict_job` **搬去了 `flint/repo/cluster_verdict.py`**：
# 读端点 NEVER import 生成通道（`flint.jobs.*`）——
# v0.4 那把封版尺子 `test_read_module_imports_no_generation_channel` 判的就是这条，
# 而它是对的：**打开一屏去看，NEVER 该牵动生成那一侧**。
# 写这半留在这里（`gate1` 收尾时调它），两半共用一张表，没有第二套口径。
