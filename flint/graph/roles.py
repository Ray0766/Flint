"""GRAPH-06：节点角色与「图内主唯一」的运行时（I12-1）。

契约里 `set_primary`（contracts_v04）定的是**规则**：设新主、旧主自动降 secondary。
本模块是它的**运行时落点**——规则在一个列表上成立不等于在并发写下成立：
两个写入方各自「读全图 → 改自己那一个 → 写回」，两次都会成功，
于是图里出现两个 primary，而 UI 只会显示其中一个是主，另一个悄悄也是主。
那之后「这张图在讲哪件事」这个问题就没有答案了。

## 原子性

写入在**一个临界区**内完成「清掉旧主 → 立新主」。内存实现用一把锁；
SQL 实现的等价物是同一事务 + `graph_nodes` 上的部分唯一索引
（`UNIQUE (graph_id) WHERE primary`）——两者语义相同：**同一时刻只有一个写入方
能改动这张图的主**，后到者看到的是前一个写完之后的世界。

## 自动降级而不是报错（NEVER 确认对话框）

用户点第二个节点设主，意思很明确。让他先去取消上一个，是把系统的洁癖变成
用户的负担；弹一个「确定要替换吗」的对话框同样——他刚刚已经说了要什么。
降级发生了就**如实告诉他**（返回被降级的那个 id，UI 出 toast）。
"""
from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any, Final, Literal

from flint.graph.store import GraphStoreLike

NodeRole = Literal["primary", "secondary", "auxiliary"]
_ROLES: Final[frozenset[str]] = frozenset({"primary", "secondary", "auxiliary"})

# 一张图一把锁的替代：store 级锁。图数量小、写入稀疏，粒度不是瓶颈；
# 真正要紧的是 NEVER 出现两个写入方同时处在「清旧主 → 立新主」中间。
_LOCKS: dict[int, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()


def _lock_for(store: GraphStoreLike) -> threading.Lock:
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(id(store), threading.Lock())


@dataclass(frozen=True)
class RoleChange:
    """一次角色变更的结果。`demoted_node_id` 非空 = 有一个旧主被降级（UI 出 toast）。"""

    node_id: str
    role: NodeRole
    demoted_node_id: str | None


def set_node_role(
    store: GraphStoreLike, *, graph_id: str, node_id: str, role: NodeRole
) -> RoleChange:
    """设角色。role=="primary" 时在临界区内保证图内主唯一。"""
    if role not in _ROLES:
        raise ValueError(f"未知角色 {role!r}：角色集恒为 {sorted(_ROLES)}")

    with _lock_for(store):
        nodes = store.nodes(graph_id)
        target = next((n for n in nodes if n.node_id == node_id), None)
        if target is None:
            raise KeyError(f"node {node_id} 不在图 {graph_id} 里，无从设角色")

        if role != "primary":
            demoted = None
            target.primary = False
        else:
            previous = next(
                (n for n in nodes if n.primary and n.node_id != node_id), None
            )
            demoted = previous.node_id if previous is not None else None
            for node in nodes:                      # 清旧主与立新主在同一临界区内
                node.primary = node.node_id == node_id
        return RoleChange(node_id=node_id, role=role, demoted_node_id=demoted)


def primary_count(store: GraphStoreLike, *, graph_id: str) -> int:
    """图内 primary 计数。I12-1 恒 ≤1。"""
    return sum(1 for n in store.nodes(graph_id) if n.primary)


def naive_set_primary_unsafe(store: GraphStoreLike, *, graph_id: str, node_id: str) -> None:
    """**反例探针，NEVER 用于生产路径**：读全图 → 改自己那一个 → 写回，不进临界区。

    留它在这里只有一个用途：让并发测试证明自己**认得出**主唯一被破坏的样子。
    一把见谁都放行的尺子量不出任何东西。
    """
    nodes: list[Any] = store.nodes(graph_id)
    target = next((n for n in nodes if n.node_id == node_id), None)
    if target is None:
        raise KeyError(node_id)
    target.primary = True
