"""迁移 0018：每日簇质心快照表（搜热点弱信号 H-4，Phase ③）。

弱信号早期轨须**每日簇质心历史**（bge-m3 漂移检测 BERTrend/Snapchat 路线）——现冻结
`Cluster.centroid` 只存当前质心（无历史）。**owner @2026-07-31 授权走新内部表、NEVER 改冻结
Cluster**（S2-1）。本表 = 内部派生存储（day×cluster_id → 当日质心 vector(1024)），日更管线写入、
弱信号轨读时算。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cluster_centroid_daily",
        sa.Column("day", sa.Date, nullable=False),
        sa.Column("cluster_id", sa.Text, nullable=False),
        sa.Column("centroid", Vector(1024), nullable=False),
        sa.PrimaryKeyConstraint("day", "cluster_id", name="pk_cluster_centroid_daily"),
    )
    op.create_index(
        "ix_ccd_cluster_day", "cluster_centroid_daily", ["cluster_id", "day"]
    )


def downgrade() -> None:
    op.drop_index("ix_ccd_cluster_day", table_name="cluster_centroid_daily")
    op.drop_table("cluster_centroid_daily")
