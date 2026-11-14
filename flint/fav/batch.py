"""FAV-05：收藏的批量操作（批量入台 / 批量取消），**单事务语义**。

## 为什么必须「全成或全不成」

批量入台 20 条, 第 13 条失败——若前 12 条已经落了台, 用户看到的是
「一半进去了、一半没有」, 而他**并不知道是哪一半**。再点一次批量入台,
前 12 条要么重复、要么因幂等静默跳过, 两种都让人无法确认最终状态。

所以: 要么全成, 要么全不成 + **一份说清哪条为什么失败的清单**。
清单不是可选项——**只回滚不报错, 用户会以为是自己没点到**。

## 为什么先校验全部、再统一提交

两阶段: 先把每一条都验一遍（收集**所有**失败, 不是遇到第一条就停),
全过之后才写。这样回滚不需要真的「撤销已写入的东西」——
根本没写。内存实现如此, SQL 实现同理（校验在事务内、失败即 ROLLBACK）。

## 越权项报错而不是静默跳过

别人的收藏出现在批量里, 说明调用方的选择集本身有问题。静默跳过等于
**悄悄少做了事**, 而用户以为全做了。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from flint.fav.store import FavoriteStoreLike, remove_favorite
from flint.graph.store import GraphStoreLike, add_node


@dataclass(frozen=True)
class BatchFailure:
    """一条失败：是哪条、为什么。两者缺一不可。"""

    favorite_id: str
    reason: str


class BatchRejected(Exception):
    """批量整体被拒（已回滚）。`failures` 是**完整**清单，不是第一条。"""

    def __init__(self, failures: list[BatchFailure]) -> None:
        super().__init__(
            f"批量操作整体回滚，{len(failures)} 条不可执行："
            + "；".join(f"{f.favorite_id}({f.reason})" for f in failures))
        self.failures = failures


def _owned(store: FavoriteStoreLike, favorite_id: str, owner: Any) -> tuple[Any, str | None]:
    row = store.get(favorite_id)
    if row is None:
        return None, "收藏不存在"
    if row.owner.kind != owner.kind or row.owner.id != owner.id:
        return None, "不属于当前用户（越权，NEVER 静默跳过）"
    return row, None


def batch_add_to_workbench(
    favorites: FavoriteStoreLike,
    graph: GraphStoreLike,
    *,
    favorite_ids: list[str],
    graph_id: str,
    owner: Any,
    now: datetime,
    node_model: Any,
) -> list[Any]:
    """批量入台。**先全验后全写**；任一不可执行则整体拒绝并给出完整清单。"""
    if not favorite_ids:
        raise ValueError("favorite_ids NEVER 为空：一个不含任何项的批量操作没有语义")

    checked: list[Any] = []
    failures: list[BatchFailure] = []
    for fid in favorite_ids:
        row, reason = _owned(favorites, fid, owner)
        if reason is not None:
            failures.append(BatchFailure(favorite_id=fid, reason=reason))
        else:
            checked.append(row)

    if failures:
        raise BatchRejected(failures)          # 一条都没写过 → 无须撤销

    return [
        add_node(
            graph, graph_id=graph_id, node_id=f"n-{row.favorite_id}",
            source_kind="cluster", source_id=row.target_id,
            label=row.target_id, position=(0.0, 0.0), now=now, model=node_model)
        for row in checked
    ]


def batch_remove_favorites(
    favorites: FavoriteStoreLike, *, favorite_ids: list[str], owner: Any
) -> list[str]:
    """批量取消收藏。同样先全验后全删。"""
    if not favorite_ids:
        raise ValueError("favorite_ids NEVER 为空")

    failures = [
        BatchFailure(favorite_id=fid, reason=reason)
        for fid in favorite_ids
        for _row, reason in [_owned(favorites, fid, owner)]
        if reason is not None
    ]
    if failures:
        raise BatchRejected(failures)

    for fid in favorite_ids:
        remove_favorite(favorites, favorite_id=fid)
    return list(favorite_ids)
