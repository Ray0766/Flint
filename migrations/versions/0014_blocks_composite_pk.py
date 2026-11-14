"""迁移 0014：blocks 主键改复合 (deliverable_id, block_id)（M3-042）。

版本语义修正：同一逻辑 block 跨 Deliverable 版本共存（受保护块随版本
原样携带，D1-b 版本 = 各 block revision 组合）——block_id 全局唯一的
0009 口径与版本复制冲突，改复合主键。
"""
from __future__ import annotations

from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("blocks_pkey", "blocks", type_="primary")
    op.create_primary_key("blocks_pkey", "blocks", ["deliverable_id", "block_id"])


def downgrade() -> None:
    op.drop_constraint("blocks_pkey", "blocks", type_="primary")
    op.create_primary_key("blocks_pkey", "blocks", ["block_id"])
