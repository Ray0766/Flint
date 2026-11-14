"""迁移 0025：`cluster_verdicts` 关系表（PERSIST-04 / DEC-044 / DEC-048）。

## 治的那一屏

判定按 **job 键**落在 `snapshots['snap-{job_id}-verdict']`，而 `Job` 没有
`cluster` 字段、`jobs` 表也没有 `cluster_id`——**从一个热点出发无从查起**。
所以热点分析屏对每一个热点永远只会说「还没有过 Gate① 判定」，
而那正是 owner 点进去看到的那一屏。

## `contracts/` 一字不动

`DEC-044` 有一条硬的：`Job` 无 `cluster` 字段这件事**保持原样**，
对应关系**落在关系表里**。不写这一句的话，最省事的实现就是给 `Job` 加个字段——
而那是 `S2-1` 判死的动作（冻结件是唯一真相，不够用要停下报 owner）。

## 为什么是**关系**表而不是 `jobs` 上的一列

一个 combo 主题由 **2~5 张卡**凑成（`Origin.payload = {card_ids, hypothesis}`），
每张卡背后是一个热点簇。「这次判定判的是哪个 cluster」的诚实答案是**一组**。

落成 `jobs.cluster_id` 一列的话，一次判定只记得住其中一个热点，
而用户从另外几个点进去仍看到「还没有判定」——**而那次判定明明也是为它跑的**。

## 主键 `(cluster_id, job_id)`

同一次判定对同一个热点只该有一行；同一个热点被判过多次则有多行——
读的时候按 `created_at` 取最新一条（`DEC-044` 定的默认）。

## 两个外键都要

- `cluster_id → clusters`：指向不存在的热点的关系行，读出来是一条查不回内容的线索；
- `job_id → jobs`：同理，而且 `jobs` 是判定快照的唯一入口。

没有外键的话这张表会攒下**看不见的孤儿**——它们在任何一屏上都读不出来，
却会让「这个热点判过没有」这个问题得到一个错误的「判过」。

## `created_at` 单独一列，NEVER 拿 `jobs.created_at` 顶

关系是**判定收尾那一刻**建立的，作业创建时间是另一回事（作业可能排了很久）。
取最新一条要按前者排；拿后者排的话，一个早提交晚完成的作业会被排到前面，
而屏上显示的就是**旧的那次判定**。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cluster_verdicts",
        sa.Column("cluster_id", sa.Text, primary_key=True),
        sa.Column("job_id", sa.Text, primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["cluster_id"], ["clusters.cluster_id"]),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.job_id"]),
    )
    # 读法是「按 cluster 取最新一条」，索引形状跟着查询形状。
    op.create_index(
        "ix_cluster_verdicts_latest", "cluster_verdicts",
        ["cluster_id", sa.text("created_at DESC")])


def downgrade() -> None:
    op.drop_index("ix_cluster_verdicts_latest", table_name="cluster_verdicts")
    op.drop_table("cluster_verdicts")
