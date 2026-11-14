"""迁移 0012：generation_records 表（M3-010，冻结件 GenerationRecord）。"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "generation_records",
        sa.Column("record_id", sa.Text, primary_key=True),
        sa.Column("deliverable_id", sa.Text, nullable=False),
        sa.Column("job_id", sa.Text, nullable=False),
        sa.Column("prompt_version", sa.Text, nullable=False),
        sa.Column("model", sa.Text, nullable=False),
        sa.Column("params", JSONB, nullable=False),
        sa.Column("retrieval_snapshot_id", sa.Text, nullable=False),
        sa.Column("ledger_version", sa.Integer, nullable=True),
        sa.Column("pricebook_version", sa.Text, nullable=True),
        sa.Column("user_evidence_verdict_optin", sa.Boolean, nullable=False),
        sa.Column("ts", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("cost", sa.Float, nullable=False),
        sa.Column("alignment_rate", sa.Float, nullable=True),
        sa.Column(
            "structured_output_failures", sa.Integer, nullable=False,
            server_default="0",
        ),
    )
    op.create_index(
        "ix_generation_records_deliverable", "generation_records",
        ["deliverable_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_generation_records_deliverable", table_name="generation_records"
    )
    op.drop_table("generation_records")
