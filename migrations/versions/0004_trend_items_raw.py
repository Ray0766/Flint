"""迁移 0004：trend_items_raw 采集落地表（M1-035；E2 索引层清单尾项）。

只存元数据+链接（§3.5，M1-016 合规巡检覆盖本表）；(day, source_id) 范围内
delete+insert 幂等，供断点续跑的 fetch 步重放。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "trend_items_raw",
        sa.Column("day", sa.Date, nullable=False),
        sa.Column("source_id", sa.Text, nullable=False),
        sa.Column("item_index", sa.Integer, nullable=False),
        sa.Column("keyword", sa.Text, nullable=False),
        sa.Column("score", sa.Float, nullable=False),
        sa.Column("region", sa.Text, nullable=False),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("captured_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("day", "source_id", "item_index"),
    )


def downgrade() -> None:
    op.drop_table("trend_items_raw")
