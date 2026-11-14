"""PERSIST-02：图谱的 SQL 实现（`workbenches` / `graph_nodes` / `graph_edges`，迁移 0027）。

`flint/graph/store.py:34` 自述「内存实现；SQL 实现随 E2 的 `graph_nodes` /
`graph_edges` 两表接入」——**这就是那个接入**。四个方法的名字与语义逐字照抄内存件，
所以 `add_node` / `add_edge` / `set_node_role` 那些域函数**一行都不用改**
（判据 `test_a_dangling_edge_is_still_refused_through_sql` 就是拿这件事当证据）。

## 第五、第六个方法：`put_workbench` / `workbench`

内存件没有这两个，因为它没有第三张表——改前「这张图在不在」判的是
`nodes(graph_id)` 非空，那把**「图不存在」与「图存在但空了」合成了一件**
（迁移 0027 文件头详述）。内存件也补了这两个方法（`flint/graph/store.py`），
两边保持同形：**换实现 NEVER 换语义**。

## 从内存件抄过来的三条语义（换实现时最容易掉的正是这种）

1. **`nodes` / `edges` 返回列表副本**：内存件 `list(...)` 一层；这里每次从行重建对象，
   天生是副本。掉了的话，调用方改一下返回值就改了库里的图。
2. **顺序稳定**：内存件按插入顺序 append。这里按 `created_at, node_id` 排——
   **NEVER 不带 ORDER BY**：不带的时候 Postgres 的返回顺序是可变的，
   而画布的判据（以及 `add_edge` 的两端查找）都按下标读。
3. **别人的图读回空列表**，NEVER 抛。

## 幂等落在库里，而不是只落在读-判-写之间

`put_workbench` 与 `put_node` 都走 `ON CONFLICT DO NOTHING`。
域函数那一层已经先读后判了（`add_node` 扫一遍 `nodes()`），
但那是**读一次、写一次**的两步：两个请求同时进来时两边都读到「还没有」，
然后各写一个。改前它落在一个进程内字典上、GIL 顺手挡住了这件事；
落到库上之后没人挡——所以唯一索引与 `ON CONFLICT` 是**这一层自己的活**。

## 为什么每次开一条连接

与 `PgFavoriteStore` / `PgPrefsStore` 同一房规：连接**不在建对象时**发生，
留到真的读写时才连。应用装配阶段（`flint/api/app.py`）一次连接都不发，
库不可达时应用照样建得出来——冒烟脚本才起得来。

## 同步面 vs 异步驱动

`GraphStore` 的四个方法是**同步**的（域函数同步调它们），而 asyncpg 是异步的。
中间那一层是 `flint/db/sync_bridge.run_sync`（`PERSIST-01` 建的，
它在一条专用事件循环上跑协程，并在**已经在循环上**被调用时当场抛
`BlockingCallOnEventLoop`）。FastAPI 的 `def` 处理函数跑在线程池里，
所以端点这条路上的阻塞是被隔离的。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final

import asyncpg

from flint.db.sync_bridge import run_sync

_NODE_COLUMNS: Final[str] = (
    "node_id, graph_id, source_kind, source_id, label, "
    "position_x, position_y, created_at, is_primary"
)
_EDGE_COLUMNS: Final[str] = (
    "edge_id, graph_id, from_node_id, to_node_id, hypothesis, created_at"
)


@dataclass(frozen=True)
class WorkbenchRow:
    """`workbenches` 的一行。

    **不是冻结件里的 `WorkbenchGraph`**——那是 `DEC-051` 说的乙
    （带 `project_id` / 标题 / 归档，本批不建，等 K6）。这里是甲：
    `ENTRY-03` 那条链上的图，由 `(user_id, cluster_id)` 决定 id、不带项目。
    两者叫同一个名字是仓里的既有事实，`DEC-051` 把这件事记了下来并定了归期。
    """

    graph_id: str
    owner_id: str
    seed_cluster_id: str
    created_at: datetime
    #: NULL =「这张图还没有归属任何项目」（`DEC-051`）。
    #: NEVER 往这一列写一个编出来的项目 id。
    project_id: str | None = None


def _node_model() -> Any:
    """入台节点的类型。**从 `contracts_v04` 取**，NEVER 在这里新定义一个。

    与 `flint/api/app.py#_graph_node_model` 同一条取法（延迟 import additive 层）。
    """
    from contracts_v04.models_v04 import GraphNode

    return GraphNode


def _edge_model() -> Any:
    from contracts_v04.models_v04 import GraphEdge

    return GraphEdge


def _row_to_node(row: asyncpg.Record) -> Any:
    return _node_model()(
        node_id=row["node_id"],
        graph_id=row["graph_id"],
        source_kind=row["source_kind"],
        source_id=row["source_id"],
        label=row["label"],
        # 冻结件那一边是 tuple，库这一边是两列。**转换只在这里发生**。
        position=(row["position_x"], row["position_y"]),
        created_at=row["created_at"],
        primary=row["is_primary"],
    )


def _row_to_edge(row: asyncpg.Record) -> Any:
    return _edge_model()(
        edge_id=row["edge_id"],
        graph_id=row["graph_id"],
        from_node_id=row["from_node_id"],
        to_node_id=row["to_node_id"],
        hypothesis=row["hypothesis"],
        created_at=row["created_at"],
    )


@dataclass
class PgGraphStore:
    """`GraphStore` 的 SQL 实现。方法名与语义逐字对齐内存件。"""

    dsn: str

    # ── 图本身

    def put_workbench(
        self, *, graph_id: str, owner_id: str, seed_cluster_id: str, now: datetime,
    ) -> None:
        """建图。**同 `graph_id` 幂等**：第二次入台落回同一张图，NEVER 多出一张。

        `DO NOTHING` 而不是 `DO UPDATE`：`owner_id` 与 `seed_cluster_id` 是这张图
        **怎么来的**，它们 NEVER 因为第二次点击而被改写。
        """
        async def _go() -> None:
            conn = await asyncpg.connect(self.dsn)
            try:
                await conn.execute(
                    "INSERT INTO workbenches "
                    "(graph_id, owner_id, seed_cluster_id, created_at) "
                    "VALUES ($1, $2, $3, $4) ON CONFLICT (graph_id) DO NOTHING",
                    graph_id, owner_id, seed_cluster_id, now)
            finally:
                await conn.close()

        run_sync(_go())

    def workbench(self, graph_id: str) -> WorkbenchRow | None:
        """这张图在不在。**`None` = 没人建过**，与「建过但空了」是两件事。"""
        async def _go() -> WorkbenchRow | None:
            conn = await asyncpg.connect(self.dsn)
            try:
                row = await conn.fetchrow(
                    "SELECT graph_id, owner_id, seed_cluster_id, created_at, "
                    "project_id FROM workbenches WHERE graph_id = $1", graph_id)
            finally:
                await conn.close()
            if row is None:
                return None
            return WorkbenchRow(
                graph_id=row["graph_id"], owner_id=row["owner_id"],
                seed_cluster_id=row["seed_cluster_id"],
                created_at=row["created_at"], project_id=row["project_id"])

        return run_sync(_go())

    # ── 内存件那四个方法

    def nodes(self, graph_id: str) -> list[Any]:
        async def _go() -> list[Any]:
            conn = await asyncpg.connect(self.dsn)
            try:
                rows = await conn.fetch(
                    f"SELECT {_NODE_COLUMNS} FROM graph_nodes WHERE graph_id = $1 "
                    "ORDER BY created_at, node_id", graph_id)
            finally:
                await conn.close()
            return [_row_to_node(r) for r in rows]

        return run_sync(_go())

    def edges(self, graph_id: str) -> list[Any]:
        async def _go() -> list[Any]:
            conn = await asyncpg.connect(self.dsn)
            try:
                rows = await conn.fetch(
                    f"SELECT {_EDGE_COLUMNS} FROM graph_edges WHERE graph_id = $1 "
                    "ORDER BY created_at, edge_id", graph_id)
            finally:
                await conn.close()
            return [_row_to_edge(r) for r in rows]

        return run_sync(_go())

    def put_node(self, graph_id: str, node: Any) -> None:
        """落一个节点。冲突 `DO NOTHING`——见文件头「幂等落在库里」。"""
        async def _go() -> None:
            conn = await asyncpg.connect(self.dsn)
            try:
                await conn.execute(
                    "INSERT INTO graph_nodes "
                    f"({_NODE_COLUMNS}) "
                    "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) "
                    "ON CONFLICT DO NOTHING",
                    node.node_id, graph_id, node.source_kind, node.source_id,
                    node.label, float(node.position[0]), float(node.position[1]),
                    node.created_at, bool(node.primary))
            finally:
                await conn.close()

        run_sync(_go())

    def put_edge(self, graph_id: str, edge: Any) -> None:
        async def _go() -> None:
            conn = await asyncpg.connect(self.dsn)
            try:
                await conn.execute(
                    "INSERT INTO graph_edges "
                    f"({_EDGE_COLUMNS}) "
                    "VALUES ($1, $2, $3, $4, $5, $6) ON CONFLICT DO NOTHING",
                    edge.edge_id, graph_id, edge.from_node_id, edge.to_node_id,
                    edge.hypothesis, edge.created_at)
            finally:
                await conn.close()

        run_sync(_go())
