"""迁移 0002：Job 三表（M1-004，contracts/models.py#Job/JobStep/JobEvent + E2）。

- jobs：状态机主表（state/cancel_requested/预算与成本累计/权限字段）。
- job_steps：步骤明细，snapshot_ref 指向序列化 JobCheckpoint（断点续跑）。
- job_events：SSE 事件流，(job_id, seq) 唯一——Last-Event-ID 补发依据（D8）。
  E2 的按月分区在此推迟：PG 分区表唯一约束必须包含分区键，会破坏
  (job_id, seq) 全局唯一这一验收硬条款；量级触线时按 E11 在线迁移
  （新分区新 schema）再引入，当前日增事件量远低于阈值。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

_JOB_STATES = (
    "queued", "retrieving", "judging", "drafting",
    "validating", "done", "failed", "cancelled",
)


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("job_id", sa.Text, primary_key=True),
        sa.Column("kind", sa.Text, nullable=False),
        sa.Column("project_id", sa.Text, nullable=True),
        sa.Column("owner_scope", JSONB, nullable=False),
        sa.Column("state", sa.Text, nullable=False),
        sa.Column("progress", sa.Float, nullable=False, server_default="0"),
        sa.Column("partial_output_ref", sa.Text, nullable=True),
        sa.Column("budget", sa.Float, nullable=False),
        sa.Column("cost_accum", sa.Float, nullable=False, server_default="0"),
        sa.Column(
            "cancel_requested", sa.Boolean, nullable=False, server_default=sa.false()
        ),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("initiated_by", sa.Text, nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.CheckConstraint(
            f"state IN {_JOB_STATES!s}", name="ck_jobs_state"
        ),
    )
    op.create_index("ix_jobs_state", "jobs", ["state"])

    op.create_table(
        "job_steps",
        sa.Column("job_id", sa.Text, sa.ForeignKey("jobs.job_id"), nullable=False),
        sa.Column("step_index", sa.Integer, nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("state", sa.Text, nullable=False),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("ended_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("cost", sa.Float, nullable=False, server_default="0"),
        sa.Column("snapshot_ref", sa.Text, nullable=True),
        sa.PrimaryKeyConstraint("job_id", "step_index"),
    )

    op.create_table(
        "job_events",
        sa.Column("job_id", sa.Text, sa.ForeignKey("jobs.job_id"), nullable=False),
        sa.Column("seq", sa.BigInteger, nullable=False),
        sa.Column("ts", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("payload", JSONB, nullable=False),
    )
    op.create_index(
        "uq_job_events_job_seq", "job_events", ["job_id", "seq"], unique=True
    )


def downgrade() -> None:
    op.drop_index("uq_job_events_job_seq", table_name="job_events")
    op.drop_table("job_events")
    op.drop_table("job_steps")
    op.drop_index("ix_jobs_state", table_name="jobs")
    op.drop_table("jobs")
