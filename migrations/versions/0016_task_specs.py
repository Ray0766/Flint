"""迁移 0016：task_specs 表（M4-001，冻结件 TaskSpec）。

spec_set_id 归组（一次导出一组）；双单位字段全可空（判别由 DagValidator
执行，存储面不预设受众）。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "task_specs",
        sa.Column("spec_set_id", sa.Text, nullable=False),
        sa.Column("task_id", sa.Text, nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("inputs", JSONB, nullable=False),
        sa.Column("outputs", JSONB, nullable=False),
        sa.Column("acceptance", JSONB, nullable=False),
        sa.Column("depends_on", JSONB, nullable=False),
        sa.Column("milestone", sa.Text, nullable=False),
        sa.Column("estimate_days", sa.Float, nullable=True),
        sa.Column("estimate_cycles", sa.Float, nullable=True),
        sa.Column("oneshot", sa.Boolean, nullable=True),
        sa.Column("verify_cmd", sa.Text, nullable=True),
        sa.Column("context_refs", JSONB, nullable=True),
        sa.Column("review_gate", sa.Boolean, nullable=True),
        sa.Column("position", sa.Integer, nullable=False),
        sa.PrimaryKeyConstraint("spec_set_id", "task_id", name="pk_task_specs"),
    )
    op.create_index("ix_task_specs_set", "task_specs", ["spec_set_id", "position"])


def downgrade() -> None:
    op.drop_index("ix_task_specs_set", table_name="task_specs")
    op.drop_table("task_specs")
