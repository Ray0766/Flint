"""DESIGN-25：图谱变更 → 样板 stale（§6-H1 第三个薄适配器；G33 不自动重跑）。

## NEVER 自动重跑

用户在图谱上挪了一个节点、加了一条边，样板就自己重新生成一遍——他刚调好的版式、
刚手改过的那句话，全没了。而他并没有要求重做，他只是在整理关系。

「变了」与「要不要重做」是两个问题，第二个**只有用户能回答**。所以这一层只产出
**通知**（标黄）+ 两条出路（看差异 / 主动重新生成），一次生成都不发起：
本模块不 import runner、不构造 payload、不入队（有 AST 断言盯着）。

## 派生规则来自契约

「什么算结构性变更」由 `contracts_v04.models_v04.derive_stale`（I12-3）定：
`node_moved` 不算——画布上挪个位置没有改变任何论断，把布局变动也算成 stale
会让「陈旧」这个信号迅速失去意义。本模块**不另写一套**（§6-H1：
比对与判定的口径只有一处）。

## 未知变更类型报错

悄悄当成「不算结构性」放过的话，将来新增一种真会影响内容的变更时，
样板不会标黄，而用户以为它是最新的。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

# 两条出路：看差异、主动重新生成。**顺序即界面顺序**：先看清再决定。
STALE_ACTIONS: tuple[str, ...] = ("view_diff", "regenerate")


@dataclass(frozen=True)
class GraphStaleNotice:
    """一条「这份样板可能过时了」的通知。**是数据，不是动作**。"""

    deliverable_id: str
    graph_id: str
    change_kind: str
    occurred_at: datetime
    stale: bool
    actions: tuple[str, ...]


def notices_for_change(
    change: Any, deliverables_by_graph: dict[str, list[str]]
) -> list[GraphStaleNotice]:
    """图变 → 受影响样板的通知列表。**只算不改**，一次生成都不发起。"""
    from typing import get_args

    from contracts_v04.models_v04 import (
        _STRUCTURAL_CHANGES,
        GraphChangeKind,
        derive_stale,
    )

    if change.kind not in get_args(GraphChangeKind):
        raise ValueError(
            f"未知图谱变更类型 {change.kind!r}：NEVER 当成「不算结构性」悄悄放过——"
            "放过的话，新增一种真会影响内容的变更时，样板不会标黄而用户以为它是最新的"
        )
    del _STRUCTURAL_CHANGES          # 结构性判定归 derive_stale，此处不复读一遍

    affected = derive_stale(change, deliverables_by_graph)
    return [
        GraphStaleNotice(
            deliverable_id=deliverable_id,
            graph_id=change.graph_id,
            change_kind=change.kind,
            occurred_at=change.occurred_at,
            stale=True,
            actions=STALE_ACTIONS,
        )
        for deliverable_id in sorted(affected)
    ]
