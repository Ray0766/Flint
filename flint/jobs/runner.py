"""JobRunner 最小实现：状态机 + 权限（M1-033，contracts/protocols.py#JobRunner）。

- 状态机：线性阶段序 queued→retrieving→judging→drafting→validating→done，
  只许前进（不同 kind 可跳段）；任意非终态可落 failed/cancelled；终态封死。
  非法迁移抛 IllegalTransition（验收硬条款）。
- 取消权（审6）：initiated_by 本人，或 owner_scope 为 org 时 role∈{owner,admin}；
  owner_scope 为 user 时仅本人。越权抛 PermissionError。cancel 置
  cancel_requested，阶段边界（下一次 advance）落 cancelled——运行中阶段不打断。
- 角色解析经注入 RoleResolver（memberships 表随身份任务落库后接 SQL 实现）。
- arq 入队经可注入 enqueue 钩子；worker 消费与断点续跑归 M1-035/036。
"""
from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Final
from uuid import uuid4

import asyncpg

from flint.domain.models import JSON, Job, JobKind, JobState, Principal

RoleResolver = Callable[[str, str], str | None]
EnqueueHook = Callable[[str, JobKind, JSON], Awaitable[None]]

_STAGE_ORDER: Final[dict[JobState, int]] = {
    "queued": 0,
    "retrieving": 1,
    "judging": 2,
    "drafting": 3,
    "validating": 4,
    "done": 5,
}
_TERMINAL: Final[frozenset[JobState]] = frozenset({"done", "failed", "cancelled"})
_CANCEL_ROLES: Final[frozenset[str]] = frozenset({"owner", "admin"})


class IllegalTransition(Exception):
    def __init__(self, job_id: str, current: str, target: str) -> None:
        super().__init__(f"job {job_id}: illegal transition {current} -> {target}")


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _default_id() -> str:
    return f"job-{uuid4()}"


class PgJobRunner:
    """PostgreSQL-backed JobRunner (protocol-compatible; async methods)."""

    def __init__(
        self,
        dsn: str,
        role_resolver: RoleResolver,
        id_factory: Callable[[], str] = _default_id,
        now: Callable[[], datetime] = _utcnow,
        enqueue: EnqueueHook | None = None,
    ) -> None:
        self._dsn = dsn
        self._roles = role_resolver
        self._id_factory = id_factory
        self._now = now
        self._enqueue = enqueue

    async def submit(
        self,
        kind: JobKind,
        payload: JSON,
        budget: float,
        owner_scope: Principal,
        initiated_by: str,
    ) -> str:
        job_id = self._id_factory()
        stamp = self._now()
        conn = await asyncpg.connect(self._dsn)
        try:
            await conn.execute(
                "INSERT INTO jobs (job_id, kind, project_id, owner_scope, state, "
                "progress, partial_output_ref, budget, cost_accum, cancel_requested, "
                "error, initiated_by, created_at, updated_at) "
                "VALUES ($1, $2, $3, $4::jsonb, 'queued', 0, NULL, $5, 0, false, "
                "NULL, $6, $7, $7)",
                job_id,
                kind,
                payload.get("project_id"),
                json.dumps({"kind": owner_scope.kind, "id": owner_scope.id}),
                budget,
                initiated_by,
                stamp,
            )
        finally:
            await conn.close()
        if self._enqueue is not None:
            await self._enqueue(job_id, kind, payload)
        return job_id

    async def get(self, job_id: str) -> Job:
        conn = await asyncpg.connect(self._dsn)
        try:
            row = await conn.fetchrow("SELECT * FROM jobs WHERE job_id = $1", job_id)
        finally:
            await conn.close()
        if row is None:
            raise KeyError(f"unknown job: {job_id}")
        scope = json.loads(row["owner_scope"])
        return Job(
            job_id=row["job_id"],
            kind=row["kind"],
            project_id=row["project_id"],
            owner_scope=Principal(kind=scope["kind"], id=scope["id"]),
            state=row["state"],
            steps=[],  # step 明细随 M1-035 编排落盘后回读
            progress=row["progress"],
            partial_output_ref=row["partial_output_ref"],
            budget=row["budget"],
            cost_accum=row["cost_accum"],
            cancel_requested=row["cancel_requested"],
            error=row["error"],
            initiated_by=row["initiated_by"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _may_cancel(self, job: Job, actor_user_id: str) -> bool:
        if actor_user_id == job.initiated_by:
            return True
        if job.owner_scope.kind == "org":
            role = self._roles(actor_user_id, job.owner_scope.id)
            return role in _CANCEL_ROLES
        return actor_user_id == job.owner_scope.id

    async def cancel(self, job_id: str, actor_user_id: str) -> None:
        job = await self.get(job_id)
        if not self._may_cancel(job, actor_user_id):
            raise PermissionError(
                f"user {actor_user_id} may not cancel job {job_id} "
                "(review-6: initiator or owner/admin in owner_scope only)"
            )
        if job.state in _TERMINAL:
            return
        conn = await asyncpg.connect(self._dsn)
        try:
            if job.state == "queued":
                # 尚未开跑：立即落 cancelled（最近的阶段边界就是现在）
                await conn.execute(
                    "UPDATE jobs SET cancel_requested = true, state = 'cancelled', "
                    "updated_at = $2 WHERE job_id = $1",
                    job_id,
                    self._now(),
                )
            else:
                await conn.execute(
                    "UPDATE jobs SET cancel_requested = true, updated_at = $2 "
                    "WHERE job_id = $1",
                    job_id,
                    self._now(),
                )
        finally:
            await conn.close()

    async def advance(self, job_id: str, target: JobState) -> None:
        """Stage-boundary transition: enforces the forward-only state machine
        and honours a pending cancel at the boundary."""
        job = await self.get(job_id)
        current = job.state
        if current in _TERMINAL:
            raise IllegalTransition(job_id, current, target)
        if target in ("failed", "cancelled"):
            next_state: JobState = target
        else:
            if (
                target not in _STAGE_ORDER
                or _STAGE_ORDER[target] <= _STAGE_ORDER.get(current, -1)
            ):
                raise IllegalTransition(job_id, current, target)
            next_state = "cancelled" if job.cancel_requested else target
        conn = await asyncpg.connect(self._dsn)
        try:
            await conn.execute(
                "UPDATE jobs SET state = $2, updated_at = $3 WHERE job_id = $1",
                job_id,
                next_state,
                self._now(),
            )
        finally:
            await conn.close()
