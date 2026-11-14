"""迁移 0005：degradation_notes 落库（M1-040；E6 行 1 + M1-035 审核跟进硬条件）。

广场角标「今日缺 {源} 数据」的持久化依据；(day, source_id) 幂等 upsert。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "degradation_notes",
        sa.Column("day", sa.Date, nullable=False),
        sa.Column("source_id", sa.Text, nullable=False),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("detail", sa.Text, nullable=False),
        sa.PrimaryKeyConstraint("day", "source_id"),
        sa.CheckConstraint(
            "reason IN ('rate_limited', 'fetch_failed', 'parse_drift', 'disabled')",
            name="ck_degradation_reason",
        ),
    )


def downgrade() -> None:
    op.drop_table("degradation_notes")
