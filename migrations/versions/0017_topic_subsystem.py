"""迁移 0017：主题子系统持久化（TS-001，冻结件 Origin/TopicSeed/Topic/Project）。

从零落库入口→种子→主题：origins / topic_seeds / topics / projects。照冻结类型；
topics.embedding vector(1024)（与 keywords/clusters 同尺 bge-m3）+ HNSW cosine 索引。
关联假设(combo hypothesis) 经 topic_seeds.hypothesis 持久化（了结 Q-010）；主题经
topics 表持久化（了结 Q-009）。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "origins",
        sa.Column("origin_id", sa.Text, nullable=False),
        sa.Column("kind", sa.Text, nullable=False),
        sa.Column("owner", JSONB, nullable=False),      # Principal
        sa.Column("payload", JSONB, nullable=False),    # combo:{card_ids,hypothesis}
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("origin_id", name="pk_origins"),
    )
    op.create_table(
        "topic_seeds",
        sa.Column("seed_id", sa.Text, nullable=False),
        sa.Column("origin_id", sa.Text, nullable=False),
        sa.Column("keywords", JSONB, nullable=False),
        sa.Column("hypothesis", sa.Text, nullable=True),  # combo 必填、其余可空
        sa.Column("context_text", sa.Text, nullable=False),
        sa.PrimaryKeyConstraint("seed_id", name="pk_topic_seeds"),
        sa.ForeignKeyConstraint(["origin_id"], ["origins.origin_id"],
                                name="fk_topic_seeds_origin"),
    )
    op.create_table(
        "topics",
        sa.Column("topic_id", sa.Text, nullable=False),
        sa.Column("seed_id", sa.Text, nullable=False),
        sa.Column("one_liner", sa.Text, nullable=False),
        sa.Column("target_user_tag", sa.Text, nullable=False),   # [C1]
        sa.Column("form_factor_tag", sa.Text, nullable=False),   # [C1]
        sa.Column("why_now", JSONB, nullable=False),             # WhyNow [C2]
        sa.Column("keyword_mapping", JSONB, nullable=False),
        sa.Column("embedding", Vector(1024), nullable=False),
        sa.PrimaryKeyConstraint("topic_id", name="pk_topics"),
        sa.ForeignKeyConstraint(["seed_id"], ["topic_seeds.seed_id"],
                                name="fk_topics_seed"),
    )
    op.create_index("ix_topics_seed", "topics", ["seed_id"])
    op.create_index(
        "ix_topics_embedding_hnsw", "topics", ["embedding"],
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.create_table(
        "projects",
        sa.Column("project_id", sa.Text, nullable=False),
        sa.Column("owner", JSONB, nullable=False),               # Principal
        sa.Column("origin_id", sa.Text, nullable=False),
        sa.Column("topic_ids", JSONB, nullable=False),
        sa.Column("chosen_topic_id", sa.Text, nullable=True),
        sa.Column("deliverable_ids", JSONB, nullable=False),
        sa.Column("change_log", JSONB, nullable=False),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("project_id", name="pk_projects"),
    )


def downgrade() -> None:
    op.drop_table("projects")
    op.drop_index("ix_topics_embedding_hnsw", table_name="topics")
    op.drop_index("ix_topics_seed", table_name="topics")
    op.drop_table("topics")
    op.drop_table("topic_seeds")
    op.drop_table("origins")
