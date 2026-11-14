"""迁移 0027：`workbenches` · `graph_nodes` · `graph_edges` 三张表（PERSIST-02 / DEC-051）。

## 为什么现在建

`DEC-048` 记的实况里，八张表一张都不存在。前四张已由 `PERSIST-01/03/04` 建齐，
剩下的三张在这里。`flint/graph/store.py:34` 自述「内存实现；SQL 实现随 E2 的
`graph_nodes` / `graph_edges` 两表接入」——**这就是那个接入**。

改前**入台拿得到 `ok`**（`ENTRY-03` 早把两条端点挂上了），只是那张工作台
活不过一次进程重启。这与「拿不到 ok」是两种不同的坏：
后者用户当场就知道没成，前者他以为存下了，下次打开发现没了。

## `workbenches` 是第三张表，而不是「有节点就算有图」

改前「这张图在不在」判的是 `nodes(graph_id)` 非空
（`flint/api/workbenches.py` 原话「NEVER 见图就建」）。那个判法把两件事合成了一件：
**图不存在**（没人建过）与**图存在但空了**（建过，节点删光）。
第二种今天还不会发生，而它一旦发生，入台会回 404「没有这张工作台」——
**而那张工作台明明在**。所以图的存在性有自己的一行。

## `project_id` 可空，`NULL` 是什么意思写死在这里

`DEC-051`：仓里有**两个都叫「工作台」的东西**。这张表是甲——
`ENTRY-03` 那条链上的图，由 `(user_id, cluster_id)` 决定 id，**不带项目**；
乙是 `flint/graph/multi.py` 的 `WorkbenchGraph`（`graph_id` + `project_id` + 标题 +
归档），本批**不建**，等 K6。

这一列先留着，语义逐字如下：

    NULL =「这张图还没有归属任何项目」

**NEVER 往这一列写一个编出来的项目 id**。今天这一列没有任何写入方——
到 K6 交互稿落地时它由一次 `UPDATE` 填上，**而不是由一次迁移回填**。
一列全是 `NULL` 而没人说得清 `NULL` 是什么意思的话，下一个人会做两件错事里的一件：
把它当「没做完」去补一个假 id，或者把它当「不需要」直接删掉。

## 三条外键，方向都是「零件不能没有它所属的整体」

节点挂在图上、边挂在图和两端节点上，全部 `ON DELETE CASCADE`。

没有外键的话 `graph_nodes` 会攒下一批**孤儿节点**：它们在任何一张图里都读不到，
却占着 `node_id`，而下一次同名节点入台时会撞主键——报的错与「重复入台」一模一样，
于是排查的人会去查幂等逻辑，而问题根本不在那里。

边的两端也是外键：一条指向不存在节点的边在画布上就是一根断线，
存进去之后每个读图的人都要自己判断「这根线算不算数」
（`flint/graph/store.py` 的既有口径「悬空边 NEVER 入库」，这里是它在库这一层的形状）。

## `is_primary` 而不是 `primary`

`primary` 是 SQL 保留字，建成那个名字之后每一条碰它的语句都要加引号——
而**总有一条会忘**，那一条报的是语法错，看起来与这一列毫无关系。

那条 `UNIQUE (graph_id) WHERE is_primary` 的部分唯一索引就是冻结件
`GraphNode.primary` 那句「图内计数恒 ≤1 (I12-1)」在库这一层的写法
（`flint/graph/roles.py` 文件头逐字提过这个索引）。
放在库里而不是只放在代码里：两个并发请求各自读到「现在没有 primary」再各自写一个,
代码那一层拦不住，索引拦得住。

## 幂等键 `(graph_id, source_kind, source_id)` 也进索引

`add_node` 的既有口径是「同一个热点被拖进同一张图两次 → 回到同一个节点」。
改前那是一次列表线性扫描；换成 SQL 之后每次入台都要问库一次「这个热点在不在这张图里」，
没有索引就是一次全表扫。**索引形状跟着查询形状走**（`0023` 的同一条理由）。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workbenches",
        sa.Column("graph_id", sa.Text, primary_key=True),
        sa.Column("owner_id", sa.Text, nullable=False),
        sa.Column("seed_cluster_id", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        # NULL =「这张图还没有归属任何项目」（DEC-051，见文件头）。
        # NEVER 往这一列写一个编出来的项目 id。
        sa.Column("project_id", sa.Text, nullable=True),
    )
    # 「我的工作台」按人取。
    op.create_index("ix_workbenches_owner", "workbenches", ["owner_id"])

    op.create_table(
        "graph_nodes",
        sa.Column("node_id", sa.Text, primary_key=True),
        sa.Column("graph_id", sa.Text,
                  sa.ForeignKey("workbenches.graph_id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("source_kind", sa.Text, nullable=False),
        sa.Column("source_id", sa.Text, nullable=False),
        sa.Column("label", sa.Text, nullable=False),
        # 坐标拆两列而不是一个 jsonb：画布按范围取节点时它们要能进索引。
        sa.Column("position_x", sa.Double, nullable=False),
        sa.Column("position_y", sa.Double, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_primary", sa.Boolean, nullable=False,
                  server_default=sa.text("false")),
    )
    op.create_index(
        "ux_graph_nodes_source", "graph_nodes",
        ["graph_id", "source_kind", "source_id"], unique=True)
    # I12-1：一张图里最多一个 primary。见文件头。
    op.create_index(
        "ux_graph_nodes_primary", "graph_nodes", ["graph_id"],
        unique=True, postgresql_where=sa.text("is_primary"))

    op.create_table(
        "graph_edges",
        sa.Column("edge_id", sa.Text, primary_key=True),
        sa.Column("graph_id", sa.Text,
                  sa.ForeignKey("workbenches.graph_id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("from_node_id", sa.Text,
                  sa.ForeignKey("graph_nodes.node_id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("to_node_id", sa.Text,
                  sa.ForeignKey("graph_nodes.node_id", ondelete="CASCADE"),
                  nullable=False),
        # 非空：冻结件 `GraphEdge.__post_init__` 拒空 hypothesis，
        # 库这一层同一口径——一条没有假设的边说不出两端为什么被连起来。
        sa.Column("hypothesis", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_graph_edges_graph", "graph_edges", ["graph_id"])


def downgrade() -> None:
    # 先边后节点再工作台：外键方向决定删除顺序。
    op.drop_table("graph_edges")
    op.drop_table("graph_nodes")
    op.drop_table("workbenches")
