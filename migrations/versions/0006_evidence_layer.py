"""迁移 0006：证据层四表（M2-001，技术方案 E2；冻结件 Doc/Citation/PricingRecord）。

- docs：kind 七枚举 + origin/access 判别 CHECK（审5/审7 的类型层地基）。
- citations：doc 外键；locator/quote_span 可空。
- pricing_records：代理主键 record_id；confidence ∈ [0,1] CHECK（B5：
  禁止无置信度数字的存储面兜底）。
- snapshots：payload BYTEA（冻结协议 SnapshotStore 以 bytes 为契约；E2 的
  JSONB 表述以冻结件为准，差异记 trace）+ created_at 驱动 180 天清理。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import BYTEA, JSONB

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

_DOC_KINDS = "('paper', 'patent', 'news', 'product', 'repo', 'webpage', 'user_upload')"


def upgrade() -> None:
    op.create_table(
        "docs",
        sa.Column("doc_id", sa.Text, primary_key=True),
        sa.Column("source_id", sa.Text, nullable=False),
        sa.Column("kind", sa.Text, nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("published_at", sa.Date, nullable=True),
        sa.Column("meta", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("origin", sa.Text, nullable=False),
        sa.Column("access", sa.Text, nullable=False),
        sa.CheckConstraint(f"kind IN {_DOC_KINDS}", name="ck_docs_kind"),
        sa.CheckConstraint(
            "origin IN ('retrieved', 'user_provided')", name="ck_docs_origin"
        ),
        sa.CheckConstraint("access IN ('public', 'private')", name="ck_docs_access"),
    )
    op.create_index("ix_docs_source", "docs", ["source_id"])

    op.create_table(
        "citations",
        sa.Column("citation_id", sa.Text, primary_key=True),
        sa.Column("doc_id", sa.Text, sa.ForeignKey("docs.doc_id"), nullable=False),
        sa.Column("locator", sa.Text, nullable=True),
        sa.Column("quote_span", sa.Text, nullable=True),
    )

    op.create_table(
        "pricing_records",
        sa.Column("record_id", sa.Text, primary_key=True),
        sa.Column("plan", sa.Text, nullable=False),
        sa.Column("price", sa.Float, nullable=True),
        sa.Column("currency", sa.Text, nullable=False),
        sa.Column("region", sa.Text, nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("captured_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("url", sa.Text, nullable=False),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1", name="ck_pricing_confidence"
        ),
    )

    op.create_table(
        "snapshots",
        sa.Column("snapshot_id", sa.Text, primary_key=True),
        sa.Column("payload", BYTEA, nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
    )
    op.create_index("ix_snapshots_created", "snapshots", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_snapshots_created", table_name="snapshots")
    op.drop_table("snapshots")
    op.drop_table("pricing_records")
    op.drop_table("citations")
    op.drop_index("ix_docs_source", table_name="docs")
    op.drop_table("docs")
