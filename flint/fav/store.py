"""FAV-01：收藏写路径 + 快照冻结（基线内嵌）。

## 冻结靠的是内嵌，不是保护

SCHEMA-09 定的基线是**内嵌** `evidence_snapshot`: 收藏时把内容**抄一份**带走。
于是「源被改了 / 被删了 / 被 180 天周删清了」都影响不到它——
**冻结是结构性的**, 不依赖任何人记得去保护被引对象。

抄的时候必须**深拷贝**: 浅拷贝会漏——顶层键抄了, 嵌套的 list/dict 还是同一个对象,
调用方 append 一下就改了「冻结」的快照。读出去的也是副本, 否则拿到返回值改一下
就改了库里的东西。

## P1 采纳位（pin 路径）

# —— §9-P1 采纳位（提案, owner 未采纳 → 本轮 NEVER 实现）——
# P1 的做法: 把内嵌换成 snapshot_id 引用, 并给被引 snapshot **pin**（钉住）,
# 让 E2 的 180 天周删任务跳过被收藏的那些。采纳时在此处新增
#     def pin_snapshot(snapshot_id: str) -> None
# 并同步 E2 周删条件与 Favorite 的字段。在那之前它只是注释, NEVER 成为真实现。

## 越权

列表按 owner 过滤: 别人的收藏 NEVER 出现在我的列表里。
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol


class FavoriteStoreLike(Protocol):
    """收藏存储的**形状**。内存件与 SQL 件（`flint/fav/pgstore.py`）各实现一份。

    `PERSIST-01` 加的。改前这三个函数的形参写死成 `FavoriteStore`（内存件本体），
    于是 SQL 实现在类型上过不去——而**「SQL 实现随 favorites 表接入」
    是这个文件自己在 35 行写下的计划**，形参本来就该是形状而不是那一个类。

    只有四个方法：多一个都会把「换一个实现」变难，而这四个正是端点与
    `stale.py` / `batch.py` 用到的全部。
    """

    def put(self, favorite: Any) -> None: ...

    def get(self, favorite_id: str) -> Any: ...

    def drop(self, favorite_id: str) -> bool: ...

    def all(self) -> list[Any]: ...


@dataclass
class FavoriteStore:
    """内存实现；SQL 实现随 E2 的 `favorites` 表接入。"""

    _rows: dict[str, Any] = field(default_factory=dict)

    def put(self, favorite: Any) -> None:
        self._rows[favorite.favorite_id] = favorite

    def get(self, favorite_id: str) -> Any:
        """返回**副本**：调用方改返回值 NEVER 影响库里的快照。"""
        row = self._rows.get(favorite_id)
        return copy.deepcopy(row) if row is not None else None

    def drop(self, favorite_id: str) -> bool:
        return self._rows.pop(favorite_id, None) is not None

    def all(self) -> list[Any]:
        return [copy.deepcopy(r) for r in self._rows.values()]


def add_favorite(
    store: FavoriteStoreLike,
    *,
    favorite_id: str,
    owner: Any,
    target_kind: str,
    target_id: str,
    evidence_snapshot: dict[str, Any],
    now: datetime,
    model: Any,
) -> Any:
    """收藏（POST /favorites）。快照**深拷贝**入库；同 id 幂等。"""
    if not evidence_snapshot:
        raise ValueError(
            "evidence_snapshot NEVER 为空: 空快照的收藏就是一个指向空处的壳, "
            "而内嵌基线的全部意义就是不让它变成壳")

    existing = store.get(favorite_id)
    if existing is not None:
        return existing

    favorite = model(
        favorite_id=favorite_id, owner=owner, target_kind=target_kind,
        target_id=target_id,
        evidence_snapshot=copy.deepcopy(evidence_snapshot),   # 抄一份, 与源彻底断开
        created_at=now,
    )
    store.put(favorite)
    return store.get(favorite_id)


def remove_favorite(store: FavoriteStoreLike, *, favorite_id: str) -> bool:
    """取消收藏（DELETE /favorites/{id}）。幂等: 不存在时返回 False, NEVER 抛错。"""
    return store.drop(favorite_id)


def list_favorites(store: FavoriteStoreLike, *, owner: Any) -> list[Any]:
    """我的收藏（GET /favorites）。**按 owner 过滤**——别人的 NEVER 出现在我的列表里。"""
    return [
        f for f in store.all()
        if f.owner.kind == owner.kind and f.owner.id == owner.id
    ]
