"""迁移 0011：UserProfile 表（M3-014，冻结件 UserProfile / D10 / D12）。"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "profiles",
        sa.Column("profile_id", sa.Text, primary_key=True),
        sa.Column("owner", JSONB, nullable=False),
        sa.Column("identity", JSONB, nullable=False),
        sa.Column("research", JSONB, nullable=False),
        sa.Column("team", JSONB, nullable=False),
        sa.Column("assets", JSONB, nullable=False),
        sa.Column("constraints", JSONB, nullable=False),
        sa.Column("track_record", JSONB, nullable=False),
        sa.Column("locale", sa.Text, nullable=False),
        sa.Column("sensitivity_overrides", JSONB, nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("profiles")
