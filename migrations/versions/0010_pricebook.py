"""迁移 0010：PriceBook 表（M3-011，冻结件 PriceEntry / v0.3.1 §3.2）。

source 必填且非空 CHECK——「无出处的条目不可被预算表引用」的存储面兜底。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pricebook",
        sa.Column("entry_id", sa.Text, primary_key=True),
        sa.Column("item", sa.Text, nullable=False),
        sa.Column("unit", sa.Text, nullable=False),
        sa.Column("price_low", sa.Float, nullable=False),
        sa.Column("price_high", sa.Float, nullable=False),
        sa.Column("currency", sa.Text, nullable=False),
        sa.Column("region", sa.Text, nullable=False),
        sa.Column("year", sa.Integer, nullable=False),
        sa.Column("source", sa.Text, nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column(
            "stale_after_months", sa.Integer, nullable=False, server_default="12"
        ),
        sa.CheckConstraint("source != ''", name="ck_pricebook_source_nonempty"),
        sa.CheckConstraint(
            "price_low >= 0 AND price_high >= price_low", name="ck_pricebook_range"
        ),
    )


def downgrade() -> None:
    op.drop_table("pricebook")
