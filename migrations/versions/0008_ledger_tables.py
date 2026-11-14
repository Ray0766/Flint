"""迁移 0008：账本表族（M3-001，技术方案 E2；冻结件 FactsLedger/Fact/Claim）。

- facts_ledgers：版本链（(project_id, version) 唯一）+ derivation_reason
  四枚举 CHECK（审4 乐观锁的存储地基）。
- facts：按账本版本成行（账本不可变，facts 随版本快照）；status/origin
  判别 CHECK + 提升不变量的存储面兜底（promoted_claim 必带 source_claim_id）。
- claims：confidence/alignment 判别 CHECK（v0.3.2 §1：Claim 作用域 =
  本 Deliverable，不进 diff/stale）。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "facts_ledgers",
        sa.Column("ledger_id", sa.Text, primary_key=True),
        sa.Column("project_id", sa.Text, nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("parent_version", sa.Integer, nullable=True),
        sa.Column("derivation_reason", sa.Text, nullable=False),
        sa.Column("created_from", JSONB, nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("actor", sa.Text, nullable=False),
        sa.CheckConstraint(
            "derivation_reason IN ('initial', 'inject_evidence', 'dispute', "
            "'revalidation')",
            name="ck_ledger_reason",
        ),
        sa.UniqueConstraint("project_id", "version", name="uq_ledger_project_version"),
    )
    op.create_index("ix_ledger_project", "facts_ledgers", ["project_id"])

    op.create_table(
        "facts",
        sa.Column(
            "ledger_id", sa.Text,
            sa.ForeignKey("facts_ledgers.ledger_id"), nullable=False,
        ),
        sa.Column("fact_id", sa.Text, nullable=False),
        sa.Column("statement", sa.Text, nullable=False),
        sa.Column("value", JSONB, nullable=True),
        sa.Column("unit", sa.Text, nullable=True),
        sa.Column("citation_ids", JSONB, nullable=False),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("origin", sa.Text, nullable=False),
        sa.Column("created_in_version", sa.Integer, nullable=False),
        sa.Column("source_claim_id", sa.Text, nullable=True),
        sa.Column("promoted_from", sa.Text, nullable=True),
        sa.PrimaryKeyConstraint("ledger_id", "fact_id", name="pk_facts"),
        sa.CheckConstraint(
            "status IN ('frozen', 'disputed', 'retired')", name="ck_fact_status"
        ),
        sa.CheckConstraint(
            "origin IN ('promoted_claim', 'injected')", name="ck_fact_origin"
        ),
        sa.CheckConstraint(
            "origin != 'promoted_claim' OR source_claim_id IS NOT NULL",
            name="ck_fact_promotion_source",
        ),
    )

    op.create_table(
        "claims",
        sa.Column("claim_id", sa.Text, primary_key=True),
        sa.Column("deliverable_id", sa.Text, nullable=False),
        sa.Column("block_id", sa.Text, nullable=False),
        sa.Column("text_span", sa.Text, nullable=False),
        sa.Column("confidence", sa.Text, nullable=False),
        sa.Column("citation_ids", JSONB, nullable=False),
        sa.Column("alignment", sa.Text, nullable=False),
        sa.Column("promoted_fact_id", sa.Text, nullable=True),
        sa.CheckConstraint(
            "confidence IN ('cited', 'speculative')", name="ck_claim_confidence"
        ),
        sa.CheckConstraint(
            "alignment IN ('pending', 'supports', 'partial', 'unsupported')",
            name="ck_claim_alignment",
        ),
    )
    op.create_index("ix_claims_deliverable", "claims", ["deliverable_id"])


def downgrade() -> None:
    op.drop_index("ix_claims_deliverable", table_name="claims")
    op.drop_table("claims")
    op.drop_table("facts")
    op.drop_index("ix_ledger_project", table_name="facts_ledgers")
    op.drop_table("facts_ledgers")
