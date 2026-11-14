"""FAV-SNAPSHOT / `DEC-055`：收藏时点的证据快照，**由后端自取**。

## 为什么这一份存在

`POST /favorites` 的 `evidence_snapshot` 此前必填，而广场那个收藏动作
手上只有热点卡面（`cluster_id` / 名称 / 热度）——**它拼不出真快照**。
前端拼一份就是编一份证据（`FAV-WRITES` acceptance④ 逐字禁止），
于是它送 `{}`，屏上每一条都说「内容不在了」：
那句是实话，而真相是**没有人往里面放东西**。

`DEC-055` 的裁决：前端只发 `target_kind` / `target_id`，
后端按它取当刻的证据卡组，组一份**内嵌**快照。

## 内嵌，不是引用

冻结件 `Favorite` 的语义**一字未动**：快照是本体，不是 `snapshot_id`。
它防的是「被引 snapshot 被 180 天周删清掉之后收藏变成空壳」。
本模块改的是**谁来放**，不是放什么。

## 取不着的时候 NEVER 编一份

四种目标里今天只有 `cluster` 有真的证据卡表可查。其余三种**照实回空**——
调用方（`flint/api/favorites.py#_snapshot_for`）会把空翻译成
**502 `EVIDENCE_FETCH_FAILED`**，收藏不会存下去。

**NEVER 在这里造一份「至少有个 id」的最小快照**：那样收藏会成功，
而用户翻回去时看到的是一份我们自己编的证据。
"""
from __future__ import annotations

import json
from typing import Any

import asyncpg

from flint.db.sync_bridge import run_sync

#: 快照里记「这份是什么时候、按什么口径取的」。
#: **NEVER 只存卡片数组**：翻回来的人要能看出这是收藏那一刻的样子。
SNAPSHOT_SCHEMA = "favorite-evidence/1"


async def _cluster_face(dsn: str, cluster_id: str) -> dict[str, Any]:
    """这条热点的**卡面**：标题 / 首见日 / 地区 / 当日热度。

    ## 为什么快照里要存这几格（`FAV-CARD-01`）

    `DEC-055` 的语义是**内嵌**：收藏要能长期翻回，所以它自带内容、
    不依赖被引的东西活着。

    改前这里只存了证据卡（`card_id` / `keyword_ids` / `top_links`）——
    那是**证据**，不是**卡面**。于是收藏屏没有标题可显示，
    只好印那个裸的簇 id（`c-20260810-002`）。

    卡面这几格与证据卡一起存下，收藏屏才能用与广场**同一个** `HotspotCard`
    把它渲染出来。**NEVER 让收藏屏去实时查簇**：那样一条被清掉的热点
    会让收藏变成空壳，而内嵌基线的全部意义就是不让它变成壳。
    """
    conn = await asyncpg.connect(dsn)
    try:
        row = await conn.fetchrow(
            "SELECT canonical_name, first_seen, region FROM clusters "
            "WHERE cluster_id = $1", cluster_id)
        if row is None:
            return {}
        heat = await conn.fetchval(
            "SELECT sum(norm_score) FROM heat_points WHERE cluster_id = $1 "
            "AND day = (SELECT max(day) FROM heat_points WHERE cluster_id = $1)",
            cluster_id)
    finally:
        await conn.close()
    return {
        "cluster_id": cluster_id,
        "canonical_name": row["canonical_name"],
        # 日期存成 ISO 串：`Favorite.evidence_snapshot` 是 `JSON`，
        # 而 `date` 不是 JSON 类型——存进去会在序列化那一步炸。
        "first_seen": row["first_seen"].isoformat() if row["first_seen"] else None,
        "region": row["region"],
        "heat": float(heat) if heat is not None else None,
    }


async def _cards_for_cluster(dsn: str, cluster_id: str) -> list[dict[str, Any]]:
    conn = await asyncpg.connect(dsn)
    try:
        rows = await conn.fetch(
            "SELECT card_id, cluster_id, keyword_ids, flags, top_links "
            "FROM evidence_cards WHERE cluster_id = $1 ORDER BY card_id",
            cluster_id,
        )
    finally:
        await conn.close()
    return [
        {
            "card_id": row["card_id"],
            "cluster_id": row["cluster_id"],
            # `jsonb` 过来是字符串：**在这里解一次**，NEVER 把一段 JSON 文本
            # 当成值存进快照——翻回来的人会拿到一个字符串而不是一组链接。
            "keyword_ids": _loads(row["keyword_ids"]),
            "flags": _loads(row["flags"]),
            "top_links": _loads(row["top_links"]),
        }
        for row in rows
    ]


def _loads(value: Any) -> Any:
    return json.loads(value) if isinstance(value, str) else value


def build_snapshot_source(dsn: str) -> Any:
    """装出 `FavoritesApiDeps.snapshot_for`。

    回 `{}` = **取不着**（调用方据此 502 并且不存）。
    NEVER 抛给调用方一个空 dict 之外的「空」形状：那一侧只认真假。
    """

    def snapshot_for(target_kind: str, target_id: str) -> dict[str, Any]:
        if target_kind != "cluster":
            # 其余三种（topic / deliverable / card）今天没有取证面。
            # **照实回空**而不是编一份：`DEC-055` 边界逐字。
            return {}
        cards = run_sync(_cards_for_cluster(dsn, target_id))
        if not cards:
            return {}
        face = run_sync(_cluster_face(dsn, target_id))
        return {
            "schema": SNAPSHOT_SCHEMA,
            "target_kind": target_kind,
            "target_id": target_id,
            # **卡面与证据分两格**：`cluster` 是「这条热点长什么样」，
            # `cards` 是「凭什么这么说」。合成一格的话，
            # 收藏屏要从证据里反推标题，而那是猜。
            "cluster": face,
            "cards": cards,
        }

    return snapshot_for
