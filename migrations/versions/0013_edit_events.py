"""迁移 0013：edit_events 表（M3-047，冻结件 EditEvent / F3）。"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None

_ACTIONS = (
    "('delete_claim', 'edit_text', 'remove_citation', 'reorder', "
    "'choose_topic', 'lock', 'dispute')"
)


def upgrade() -> None:
    op.create_table(
        "edit_events",
        sa.Column("event_id", sa.Text, primary_key=True),
        sa.Column("deliverable_id", sa.Text, nullable=False),
        sa.Column("section_id", sa.Text, nullable=True),
        sa.Column("block_id", sa.Text, nullable=True),
        sa.Column("action", sa.Text, nullable=False),
        sa.Column("before", JSONB, nullable=True),
        sa.Column("after", JSONB, nullable=True),
        sa.Column("user_id", sa.Text, nullable=False),
        sa.Column("ts", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.CheckConstraint(f"action IN {_ACTIONS}", name="ck_edit_action"),
    )
    op.create_index(
        "ix_edit_events_deliverable", "edit_events", ["deliverable_id", "ts"]
    )


def downgrade() -> None:
    op.drop_index("ix_edit_events_deliverable", table_name="edit_events")
    op.drop_table("edit_events")
