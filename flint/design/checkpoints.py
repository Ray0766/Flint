"""DESIGN-11：设计台版本历史检查点（G16）。

## 一个检查点 = 模板 VFS + 图谱状态，两份一起

设计产物与它所依据的图谱是**一起**才说得通的：同一份页面配上另一张图谱，
讲的就是另一件事。分开存两条历史，恢复时就要回答「用哪一版图谱配哪一版页面」——
那个问题没有正确答案，只有猜。所以缺一半就不是检查点，直接拒绝。

## 恢复 = 新检查点，历史只增不改

「恢复到三步前」若是把后面几步删掉，用户就再也回不到当前这一版了——
而他常常是回去看一眼、再回来。所以恢复把旧内容**抄成一个新点**，
并记下 `restored_from`：时间线上永远往前走，且看得出这一版是从哪一版抄回来的。

存储层也不留口子：同 id 二次写入直接拒绝（`HistoryImmutable`），
免得哪天有人「更新一下历史」。

## 快照与现场彻底断开

存的时候深拷贝、读的时候也回副本。浅拷贝的话，现场后来改一下嵌套结构，
「历史」里那一份跟着变——而历史一旦会变，它就不再是历史（与 FAV-01 同一条纪律）。

## 只存图谱状态，不碰活的图谱

本模块 NEVER import GraphStore、NEVER 调 add_node/add_edge：快照是**当时的样子**，
现场是**现在的样子**，把两者接在一起就会出现「回看历史顺手改了当前图」。
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import uuid4


class HistoryImmutable(Exception):
    """试图改写一个已存在的检查点。"""


class UnknownCheckpoint(KeyError):
    """引用了不存在的检查点。"""


@dataclass
class Checkpoint:
    checkpoint_id: str
    session_id: str
    vfs: dict[str, str]
    graph: dict[str, Any]
    created_at: datetime
    label: str | None = None
    # 非空 = 这一版是从哪一版抄回来的（恢复留痕）
    restored_from: str | None = None


@dataclass
class CheckpointStore:
    """内存实现；SQL 实现随 E2 的 design_checkpoints 表接入。**append-only**。"""

    _rows: dict[str, Checkpoint] = field(default_factory=dict)
    _order: list[str] = field(default_factory=list)

    def put(self, checkpoint: Checkpoint) -> None:
        if checkpoint.checkpoint_id in self._rows:
            raise HistoryImmutable(
                f"checkpoint {checkpoint.checkpoint_id} 已存在：历史只增不改"
            )
        self._rows[checkpoint.checkpoint_id] = _clone(checkpoint)
        self._order.append(checkpoint.checkpoint_id)

    def get(self, checkpoint_id: str) -> Checkpoint:
        row = self._rows.get(checkpoint_id)
        if row is None:
            raise UnknownCheckpoint(checkpoint_id)
        return _clone(row)                      # 读出去的是副本

    def ids(self) -> list[str]:
        return list(self._order)


def _clone(checkpoint: Checkpoint) -> Checkpoint:
    return Checkpoint(
        checkpoint_id=checkpoint.checkpoint_id,
        session_id=checkpoint.session_id,
        vfs=copy.deepcopy(checkpoint.vfs),
        graph=copy.deepcopy(checkpoint.graph),
        created_at=checkpoint.created_at,
        label=checkpoint.label,
        restored_from=checkpoint.restored_from,
    )


def create_checkpoint(
    store: CheckpointStore,
    *,
    session_id: str,
    vfs: dict[str, str],
    graph: dict[str, Any],
    now: datetime,
    label: str | None = None,
    restored_from: str | None = None,
) -> Checkpoint:
    """存一个检查点。两份缺一即拒。"""
    if not vfs:
        raise ValueError("vfs NEVER 为空：没有产物的检查点恢复不出任何东西")
    if not graph:
        raise ValueError(
            "graph NEVER 为空：只存页面不存图谱，恢复时就要猜配哪一版图谱"
        )
    checkpoint = Checkpoint(
        checkpoint_id=f"cp-{uuid4()}",
        session_id=session_id,
        vfs=copy.deepcopy(vfs),                 # 与现场彻底断开
        graph=copy.deepcopy(graph),
        created_at=now,
        label=label,
        restored_from=restored_from,
    )
    store.put(checkpoint)
    return store.get(checkpoint.checkpoint_id)


def restore_checkpoint(
    store: CheckpointStore, *, checkpoint_id: str, now: datetime
) -> Checkpoint:
    """恢复：把旧内容抄成**一个新点**，历史一条都不动。"""
    source = store.get(checkpoint_id)           # 不存在时抛 UnknownCheckpoint
    return create_checkpoint(
        store,
        session_id=source.session_id,
        vfs=source.vfs,
        graph=source.graph,
        now=now,
        label=source.label,
        restored_from=source.checkpoint_id,
    )


def list_checkpoints(store: CheckpointStore, *, session_id: str) -> list[Checkpoint]:
    """该会话的时间线：按写入序（同一时刻创建的也有确定顺序）。"""
    return [
        cp
        for cp in (store.get(cid) for cid in store.ids())
        if cp.session_id == session_id
    ]
