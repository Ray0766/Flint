"""迁移 0007：幂等键表（M2-042，技术方案 E3）。

(principal, key) 唯一 → 重复提交返回原 job_id；principal 拆 kind/id 两列
与 Principal 冻结结构对应。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "idempotency_keys",
        sa.Column("principal_kind", sa.Text, nullable=False),
        sa.Column("principal_id", sa.Text, nullable=False),
        sa.Column("idem_key", sa.Text, nullable=False),
        sa.Column("job_id", sa.Text, sa.ForeignKey("jobs.job_id"), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint(
            "principal_kind", "principal_id", "idem_key", name="pk_idempotency"
        ),
    )


def downgrade() -> None:
    op.drop_table("idempotency_keys")
