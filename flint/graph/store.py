"""GRAPH-02：图谱数据层（有向图存储 + 入台 + H8 假设通道复用）。

## 入台幂等按 (graph_id, source_kind, source_id) 判

「同一个热点被拖进同一张图两次」应当回到**同一个节点**, 而不是并排出现两个
一模一样的卡片。按 node_id 判是不够的: 用户第二次拖入时不会带着上次的 node_id。

作用域是**一张图**: 同一个热点当然可以出现在两张图里, 那是两个独立的思考。
`source_kind` 也进键: 同 id 不同类（cluster c-1 与 topic c-1）不是同一个东西。

## 悬空边 NEVER 入库

一条指向不存在节点的边, 在画布上就是一根断线; 存进去之后每个读图的人都要
自己判断「这根线算不算数」。两端必须都在。

## H8：假设校验复用 combo 通道

边上的 hypothesis 与 combo 的关联假设是**同一个东西**——都是「为什么把这两样连起来」。
校验因此 import 自 `flint/topic/create.py` 的 `_require_str`, NEVER 新写一份:
两份实现就是两种口径, 用户会遇到「在 combo 里能提交、在图谱里被拒」这种事。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

from flint.topic.create import _require_str  # H8: 复用 combo 的 hypothesis 校验语义


class GraphStoreLike(Protocol):
    """图存储的**面**。内存件与 SQL 件都满足它。

    为什么加这个 Protocol 而不是让 `PgGraphStore` 继承 `GraphStore`：
    继承会把内存件那三个字典也带过去——一个连着库、同时还揣着一份永远为空的
    进程内副本的对象，读它的人分不清哪一份是真的。
    这与 `PERSIST-01` 给收藏/链接/偏好三族用的是同一条办法。
    """

    def put_workbench(
        self, *, graph_id: str, owner_id: str, seed_cluster_id: str, now: datetime,
    ) -> None: ...

    def workbench(self, graph_id: str) -> Any: ...

    def nodes(self, graph_id: str) -> list[Any]: ...

    def edges(self, graph_id: str) -> list[Any]: ...

    def put_node(self, graph_id: str, node: Any) -> None: ...

    def put_edge(self, graph_id: str, edge: Any) -> None: ...


@dataclass
class WorkbenchRow:
    """一张图本身。PERSIST-02 加，与 `flint/graph/pgstore.py#WorkbenchRow` 同形。"""

    graph_id: str
    owner_id: str
    seed_cluster_id: str
    created_at: datetime
    project_id: str | None = None


@dataclass
class GraphStore:
    """内存实现；SQL 实现见 `flint/graph/pgstore.py`（PERSIST-02 接入，迁移 0027）。

    ## PERSIST-02 给它加了第三个字典

    改前「这张图在不在」判的是 `nodes(graph_id)` 非空，那把两件事合成了一件：
    **图不存在**（没人建过）与**图存在但空了**（建过，节点删光）。
    第二种一旦发生，入台会回 404「没有这张工作台」——**而那张工作台明明在**。

    这个内存件因此也补上 `put_workbench` / `workbench`：**两边保持同形**。
    只给 SQL 那边加的话，注内存件的调用方（既有测试、冒烟脚本）
    会在端点里撞上 `AttributeError`——那是换实现换出的新故障，而不是原有的病。
    """

    _nodes: dict[str, list[Any]] = field(default_factory=dict)
    _edges: dict[str, list[Any]] = field(default_factory=dict)
    _benches: dict[str, WorkbenchRow] = field(default_factory=dict)

    def put_workbench(
        self, *, graph_id: str, owner_id: str, seed_cluster_id: str, now: datetime,
    ) -> None:
        """建图。**同 graph_id 幂等**，且 NEVER 改写既有那一行的来历。"""
        if graph_id in self._benches:
            return
        self._benches[graph_id] = WorkbenchRow(
            graph_id=graph_id, owner_id=owner_id,
            seed_cluster_id=seed_cluster_id, created_at=now)

    def workbench(self, graph_id: str) -> WorkbenchRow | None:
        return self._benches.get(graph_id)

    def nodes(self, graph_id: str) -> list[Any]:
        return list(self._nodes.get(graph_id, []))

    def edges(self, graph_id: str) -> list[Any]:
        return list(self._edges.get(graph_id, []))

    def put_node(self, graph_id: str, node: Any) -> None:
        self._nodes.setdefault(graph_id, []).append(node)

    def put_edge(self, graph_id: str, edge: Any) -> None:
        self._edges.setdefault(graph_id, []).append(edge)


def add_node(
    store: GraphStoreLike, *, graph_id: str, node_id: str, source_kind: str, source_id: str,
    label: str, position: tuple[float, float], now: datetime, model: Any,
) -> Any:
    """入台。同 (graph_id, source_kind, source_id) **幂等**返回既有节点。"""
    for existing in store.nodes(graph_id):
        if existing.source_kind == source_kind and existing.source_id == source_id:
            return existing
    node = model(
        node_id=node_id, graph_id=graph_id, source_kind=source_kind,
        source_id=source_id, label=label, position=position, created_at=now)
    store.put_node(graph_id, node)
    return node


def add_edge(
    store: GraphStoreLike, *, graph_id: str, edge_id: str, from_node_id: str,
    to_node_id: str, hypothesis: str, now: datetime, model: Any,
) -> Any:
    """建边。两端必须存在；hypothesis 走 combo 同一校验；同 (from,to) 幂等。"""
    known = {n.node_id for n in store.nodes(graph_id)}
    for endpoint in (from_node_id, to_node_id):
        if endpoint not in known:
            raise ValueError(
                f"节点 {endpoint} 不在图 {graph_id} 里: 悬空边 NEVER 入库——"
                "画布上那就是一根断线")

    # H8: 与 combo 的关联假设是同一个东西, 用同一个校验器
    _require_str({"hypothesis": hypothesis}, "hypothesis")

    for existing in store.edges(graph_id):
        if existing.from_node_id == from_node_id and existing.to_node_id == to_node_id:
            return existing

    edge = model(
        edge_id=edge_id, graph_id=graph_id, from_node_id=from_node_id,
        to_node_id=to_node_id, hypothesis=hypothesis, created_at=now)
    store.put_edge(graph_id, edge)
    return edge


def neighbors(store: GraphStoreLike, *, graph_id: str, node_id: str) -> list[str]:
    """出边邻居。**有向**: 反方向查不到（方向不可逆）。"""
    return [e.to_node_id for e in store.edges(graph_id) if e.from_node_id == node_id]
