"""迁移 0009：deliverables/blocks 表（M3-008，技术方案 E2；冻结件 Deliverable/Block）。

- deliverables：type 七枚举 CHECK；version/supersedes/stale_reasons 面齐。
- blocks：author 二枚举 CHECK（永不翻转的存储面）+ type 八枚举 CHECK +
  review_reason/severity 枚举 CHECK；content JSONB（判别联合序列化归
  flint/compose/block_io.py）；order 列名用 block_order（order 是保留字）。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

_DELIVERABLE_TYPES = (
    "('analysis', 'report', 'proposal', 'vibe_pack', 'spec', 'chart', "
    "'revalidation_report')"
)
_BLOCK_TYPES = (
    "('heading', 'paragraph', 'table', 'chart', 'declaration', 'quality_card', "
    "'citation_list', 'gap_notice')"
)


def upgrade() -> None:
    op.create_table(
        "deliverables",
        sa.Column("deliverable_id", sa.Text, primary_key=True),
        sa.Column("project_id", sa.Text, nullable=False),
        sa.Column("type", sa.Text, nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("supersedes", sa.Text, nullable=True),
        sa.Column("inputs", JSONB, nullable=False),
        sa.Column("ledger_version", sa.Integer, nullable=True),
        sa.Column("generation_record_id", sa.Text, nullable=False),
        sa.Column("stale_reasons", JSONB, nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("reproducible", sa.Boolean, nullable=False),
        sa.CheckConstraint(
            f"type IN {_DELIVERABLE_TYPES}", name="ck_deliverable_type"
        ),
    )
    op.create_index("ix_deliverables_project", "deliverables", ["project_id"])

    op.create_table(
        "blocks",
        sa.Column("block_id", sa.Text, primary_key=True),
        sa.Column(
            "deliverable_id", sa.Text,
            sa.ForeignKey("deliverables.deliverable_id"), nullable=False,
        ),
        sa.Column("section_id", sa.Text, nullable=False),
        sa.Column("block_order", sa.Integer, nullable=False),
        sa.Column("type", sa.Text, nullable=False),
        sa.Column("content", JSONB, nullable=False),
        sa.Column("claim_ids", JSONB, nullable=False),
        sa.Column("fact_ids", JSONB, nullable=False),
        sa.Column("author", sa.Text, nullable=False),
        sa.Column("revision", sa.Integer, nullable=False),
        sa.Column("locked", sa.Boolean, nullable=False),
        sa.Column("user_modified", sa.Boolean, nullable=False),
        sa.Column("needs_review", sa.Boolean, nullable=False),
        sa.Column("review_reason", sa.Text, nullable=True),
        sa.Column("review_severity", sa.Text, nullable=True),
        sa.CheckConstraint("author IN ('system', 'user')", name="ck_block_author"),
        sa.CheckConstraint(f"type IN {_BLOCK_TYPES}", name="ck_block_type"),
        sa.CheckConstraint(
            "review_reason IS NULL OR review_reason IN "
            "('fact_changed', 'fact_removed', 'fact_disputed')",
            name="ck_block_review_reason",
        ),
        sa.CheckConstraint(
            "review_severity IS NULL OR review_severity IN ('blocking', 'advisory')",
            name="ck_block_review_severity",
        ),
    )
    op.create_index(
        "ix_blocks_deliverable", "blocks",
        ["deliverable_id", "section_id", "block_order"],
    )


def downgrade() -> None:
    op.drop_index("ix_blocks_deliverable", table_name="blocks")
    op.drop_table("blocks")
    op.drop_index("ix_deliverables_project", table_name="deliverables")
    op.drop_table("deliverables")
