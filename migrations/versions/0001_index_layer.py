"""基线迁移 0001：索引层五表 + 向量索引（M1-003，技术方案 E2）。

- 五表 = categories / keywords / clusters / heat_points / evidence_cards
  （E2 索引层行内的 trend_items_raw 为采集落地表，随 daily_ingest 任务落库）。
- pgvector：keywords.embedding 与 clusters.centroid 均 vector(1024)，
  HNSW(m=16, ef_construction=64, cosine)（E2 参数）。
- heat_points 按 day RANGE 分区 + DEFAULT 分区兜底（月分区由日更作业按需建）。
- JSONB 列存列表/判别联合序列化（E2 总则）。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

_HNSW = {
    "postgresql_using": "hnsw",
    "postgresql_with": {"m": 16, "ef_construction": 64},
}


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "categories",
        sa.Column("category_id", sa.Text, primary_key=True),
        sa.Column("name", sa.Text, nullable=False, unique=True),
    )

    op.create_table(
        "keywords",
        sa.Column("keyword_id", sa.Text, primary_key=True),
        sa.Column("canonical", sa.Text, nullable=False),
        sa.Column("lang", sa.Text, nullable=False),
        sa.Column("aliases", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("embedding", Vector(1024), nullable=False),
        sa.Column("first_seen", sa.Date, nullable=False),
        sa.UniqueConstraint("canonical", "lang", name="uq_keywords_canonical_lang"),
    )
    op.create_index(
        "ix_keywords_embedding_hnsw",
        "keywords",
        ["embedding"],
        postgresql_ops={"embedding": "vector_cosine_ops"},
        **_HNSW,
    )

    op.create_table(
        "clusters",
        sa.Column("cluster_id", sa.Text, primary_key=True),
        sa.Column("canonical_name", sa.Text, nullable=False),
        sa.Column(
            "category_id",
            sa.Text,
            sa.ForeignKey("categories.category_id"),
            nullable=False,
        ),
        sa.Column("centroid", Vector(1024), nullable=False),
        sa.Column("status", sa.Text, nullable=False, server_default="active"),
        sa.Column("first_seen", sa.Date, nullable=False),
        sa.Column("last_active", sa.Date, nullable=False),
        sa.Column(
            "parent_cluster_ids", JSONB, nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("merged_into", sa.Text, nullable=True),
        sa.Column("aliases", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.CheckConstraint(
            "status IN ('active', 'dormant', 'merged')", name="ck_clusters_status"
        ),
    )
    op.create_index(
        "ix_clusters_centroid_hnsw",
        "clusters",
        ["centroid"],
        postgresql_ops={"centroid": "vector_cosine_ops"},
        **_HNSW,
    )
    op.create_index("ix_clusters_status", "clusters", ["status"])

    op.create_table(
        "heat_points",
        sa.Column("cluster_id", sa.Text, nullable=False),
        sa.Column("source_id", sa.Text, nullable=False),
        sa.Column("day", sa.Date, nullable=False),
        sa.Column("raw_value", sa.Float, nullable=False),
        sa.Column("norm_score", sa.Float, nullable=False),
        sa.PrimaryKeyConstraint("cluster_id", "source_id", "day"),
        postgresql_partition_by="RANGE (day)",
    )
    op.execute("CREATE TABLE heat_points_default PARTITION OF heat_points DEFAULT")

    op.create_table(
        "evidence_cards",
        sa.Column("card_id", sa.Text, primary_key=True),
        sa.Column(
            "cluster_id",
            sa.Text,
            sa.ForeignKey("clusters.cluster_id"),
            nullable=False,
        ),
        sa.Column(
            "keyword_ids", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")
        ),
        sa.Column("flags", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column(
            "top_links", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")
        ),
    )


def downgrade() -> None:
    op.drop_table("evidence_cards")
    op.execute("DROP TABLE heat_points")  # partitions dropped with the parent
    op.drop_index("ix_clusters_status", table_name="clusters")
    op.drop_index("ix_clusters_centroid_hnsw", table_name="clusters")
    op.drop_table("clusters")
    op.drop_index("ix_keywords_embedding_hnsw", table_name="keywords")
    op.drop_table("keywords")
    op.drop_table("categories")
