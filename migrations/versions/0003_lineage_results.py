"""迁移 0003：血缘日更批落库（M1-029，v0.4 LineageResult + owner 决策⑤⑥）。

- lineage_results：append-only；lineage_id (uuid) 主键，day 为索引列（决策⑤）；
  events/dormant/drift_audits 存判别联合序列化 JSONB（E2 总则）；三阈值参数快照。
- lineage_audit：每条 event 引用的全部簇 ID 摊开成行并建索引（决策⑥），
  自带 event JSONB 拷贝使标注导出免回表；(cluster_id, day) 复合索引即审计
  视图的查询主径。保留策略（路 A）由 store.prune_expired 执行，关系边永久
  留在 clusters 表血缘字段。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lineage_results",
        sa.Column("lineage_id", sa.Text, primary_key=True),
        sa.Column("day", sa.Date, nullable=False),
        sa.Column("events", JSONB, nullable=False),
        sa.Column(
            "dormant_cluster_ids", JSONB, nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "drift_audits", JSONB, nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("tau_match", sa.Float, nullable=False),
        sa.Column("tau_link", sa.Float, nullable=False),
        sa.Column("dormant_after_days", sa.Integer, nullable=False),
        sa.Column("generated_at", sa.TIMESTAMP(timezone=True), nullable=False),
    )
    op.create_index("ix_lineage_results_day", "lineage_results", ["day"])

    op.create_table(
        "lineage_audit",
        sa.Column(
            "lineage_id",
            sa.Text,
            sa.ForeignKey("lineage_results.lineage_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("day", sa.Date, nullable=False),
        sa.Column("event_index", sa.Integer, nullable=False),
        sa.Column("event_kind", sa.Text, nullable=False),
        sa.Column("cluster_id", sa.Text, nullable=False),
        sa.Column("role", sa.Text, nullable=False),
        sa.Column("event", JSONB, nullable=False),
    )
    op.create_index(
        "ix_lineage_audit_cluster_day", "lineage_audit", ["cluster_id", "day"]
    )


def downgrade() -> None:
    op.drop_index("ix_lineage_audit_cluster_day", table_name="lineage_audit")
    op.drop_table("lineage_audit")
    op.drop_index("ix_lineage_results_day", table_name="lineage_results")
    op.drop_table("lineage_results")
