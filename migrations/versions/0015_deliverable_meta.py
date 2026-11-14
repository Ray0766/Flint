"""迁移 0015：deliverables.meta JSONB（M3-032，技术方案 E3）。

E3 明文：同一 report 双受众版本互链字段 sibling_deliverable_id 存 JSONB
meta——冻结 Deliverable 域对象不含该字段（存储/API 层元数据，非域语义）。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "deliverables",
        sa.Column("meta", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
    )


def downgrade() -> None:
    op.drop_column("deliverables", "meta")
