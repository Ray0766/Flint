"""Analysis API 与 SSE 端点（M2-042，技术方案 E3 / D8 / 审6）。

- POST /projects/{id}/design_generate：设计生成作业的**提交入口**（ENTRY-01）。
  第 5 批建了消费者、第 6 批接进了 worker，而**没有任何端点能把它塞进队列**——
  前端 `submitJob` 打的 `POST /projects/{id}/design_generate` 回的是框架那种
  没有 `code` 的 404（= 这个能力还没挂），与「这一条不存在」长得一模一样。
- POST /projects/{id}/analysis：Idempotency-Key 幂等（(principal, key) 唯一，
  迁移 0007），重复提交返回原 job_id；提交经 PgJobRunner（状态机 M1-033）。
- GET /jobs/{id}：JobView 快照（断线重连第一步，D8）。
- GET /jobs/{id}/events：SSE，Last-Event-ID 之后 replay 补发（M1-034 流语义），
  非终态轮询续推（E3「受限网络回退轮询」的传输层v1），终态冲刷后关流。
- 审6 权限矩阵（订阅/快照同一矩阵）：initiated_by 本人；owner_scope 为 org
  时 role ∈ {owner, admin, member}（member 只读）；user 域仅本人。越权 →
  403 PERMISSION_DENIED。
- 鉴权中间件（JWT，E3）归后续接线：本层以受信 X-User-Id 头解析 Principal，
  解析点唯一（换 JWT 时只动 _caller）。
"""
from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Final, cast

import asyncpg
from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse, Response
from sse_starlette import EventSourceResponse, ServerSentEvent

from flint.api.hardening import (
    LastEventIdInvalid,
    claim_idempotency,
    parse_last_event_id,
)
from flint.api.identity import IDENTITY_HEADER, IdentityMissing, RoleMissing
from flint.api.schemas import (
    AnalysisSubmitRequest,
    AnalysisSubmitResponse,
    DesignSubmitRequest,
    ErrorBody,
    ErrorCode,
    JobView,
)
from flint.authz import ProjectNotFound
from flint.domain.models import Job, JobKind, Principal
from flint.jobs.events import PgJobEventStream
from flint.jobs.runner import PgJobRunner, RoleResolver

_VIEW_ROLES: Final[frozenset[str]] = frozenset({"owner", "admin", "member"})
_TERMINAL: Final[frozenset[str]] = frozenset({"done", "failed", "cancelled"})
# ENTRY-01：字面量只写一处——端点与判据引同一个常量，拼错时两边一起红。
DESIGN_GENERATE_KIND: Final[str] = "design_generate"


@dataclass
class AnalysisApiDeps:
    dsn: str
    runner: PgJobRunner
    events: PgJobEventStream
    owner_scope_for_project: Callable[[str], Principal]
    role_resolver: RoleResolver
    poll_seconds: float = 0.05
    # ENTRY-01：`X-User-Id 的值 -> user_id`（`flint/api/identity.py#build_user_check`）。
    # None = 本部署还没接身份闸——那时**沿用既有的受信头口径**，
    # NEVER 在这里兜一个默认身份（兜一个，所有匿名请求都会以同一个人的名义写数据）。
    user_check: Callable[[str | None], Awaitable[str]] | None = None
    # TS-006（owner #5/#8）：topic_id → 派生 keywords（chosen Topic → keywords）。
    # None = 端点不支持 topic_id 派生（向后兼容，旧部署不受影响）。
    topic_keywords_for: Callable[[str], Awaitable[list[str]]] | None = None


def _error(status: int, code: ErrorCode, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content=ErrorBody(code=code, message=message).model_dump(exclude_none=True),
    )



def _trusted_header(x_user_id: str | None) -> str:
    """没接身份闸时的回退：沿用本模块既有的受信头口径。

    仍然**拒绝空头**——空头不是「匿名用户」，是调用方漏了一样东西。
    """
    if x_user_id is None or not x_user_id.strip():
        raise IdentityMissing(IDENTITY_HEADER)
    return x_user_id.strip()


def _may_submit(user_id: str, scope: Principal, roles: RoleResolver) -> bool:
    """能不能往这个项目里塞作业。

    与 `may_view` **刻意分开**：看是一回事，写是另一回事。
    今天两者的角色集合恰好相同，但把它们写成一个函数，
    将来收紧写权限时会顺手把读权限一起收了——而那一次没人会注意到。
    """
    if scope.kind == "org":
        return roles(user_id, scope.id) in _VIEW_ROLES
    return user_id == scope.id


def may_view(job: Job, user_id: str, roles: RoleResolver) -> bool:
    if user_id == job.initiated_by:
        return True
    if job.owner_scope.kind == "org":
        return roles(user_id, job.owner_scope.id) in _VIEW_ROLES
    return user_id == job.owner_scope.id


async def _idempotent_lookup(
    dsn: str, principal: Principal, key: str
) -> str | None:
    conn = await asyncpg.connect(dsn)
    try:
        job_id: str | None = await conn.fetchval(
            "SELECT job_id FROM idempotency_keys WHERE principal_kind = $1 "
            "AND principal_id = $2 AND idem_key = $3",
            principal.kind, principal.id, key,
        )
        return job_id
    finally:
        await conn.close()


async def _idempotent_store(
    dsn: str, principal: Principal, key: str, job_id: str
) -> None:
    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute(
            "INSERT INTO idempotency_keys (principal_kind, principal_id, idem_key, "
            "job_id, created_at) VALUES ($1, $2, $3, $4, $5) "
            "ON CONFLICT ON CONSTRAINT pk_idempotency DO NOTHING",
            principal.kind, principal.id, key, job_id, datetime.now(UTC),
        )
    finally:
        await conn.close()


def create_analysis_app(deps: AnalysisApiDeps) -> FastAPI:
    app = FastAPI(title="flint-analysis-api")

    @app.post("/projects/{project_id}/analysis")
    async def submit(
        project_id: str,
        body: AnalysisSubmitRequest,
        x_user_id: str = Header(),
        idempotency_key: str | None = Header(default=None),
    ) -> Response:
        caller = Principal(kind="user", id=x_user_id)
        if idempotency_key is not None:
            existing = await _idempotent_lookup(deps.dsn, caller, idempotency_key)
            if existing is not None:
                return JSONResponse(
                    AnalysisSubmitResponse(job_id=existing).model_dump()
                )
        # TS-006（#5/#8）：带 topic_id → 由 chosen Topic 派生 keywords；不带 →
        # body.keywords（旧路径不变）。派生后照原样喂 gate1，内核逐字不变。
        keywords = list(body.keywords)
        if body.topic_id is not None and deps.topic_keywords_for is not None:
            keywords = await deps.topic_keywords_for(body.topic_id)
        job_id = await deps.runner.submit(
            kind="gate1_analysis",
            payload={
                "project_id": project_id,
                "keywords": keywords,
                "locale": body.locale,
                # `PERSIST-04`：判定收尾时要沿 topic 反查这次判的是哪几个热点
                # （`DEC-044` 的关系表）。**这里不放的话，`run_gate1` 手上
                # 没有任何可以反查的东西**，`cluster_verdicts` 会是一张永远空着的表，
                # 而热点分析屏照旧说「还没有判定」。
                # 不带 topic_id 的旧路径照旧传 None——**查不到就不写行**。
                "topic_id": body.topic_id,
            },
            budget=body.budget_cny,
            owner_scope=deps.owner_scope_for_project(project_id),
            initiated_by=x_user_id,
        )
        if idempotency_key is not None:
            # M3-056 硬化：ON CONFLICT 后回读胜者（并发同键仅一 job 可见，
            # 败者孤儿 job 即时取消）
            job_id = await claim_idempotency(
                deps.dsn, caller, idempotency_key, job_id
            )
        return JSONResponse(AnalysisSubmitResponse(job_id=job_id).model_dump())

    @app.post("/projects/{project_id}/design_generate")
    async def submit_design(
        project_id: str,
        body: DesignSubmitRequest,
        x_user_id: str | None = Header(default=None),
    ) -> Response:
        """ENTRY-01：把「说一句话出一个设计」塞进队列。

        ## 四种拒绝各说各的（`AUTH-03`）

        缺头 401 `IDENTITY_MISSING` · 身份查不到 401 `IDENTITY_UNKNOWN` ·
        有身份无角色 403 `PERMISSION_DENIED` · 项目不存在 404 `NOT_FOUND`。

        混成一句的后果：拿到 403 的人会去要权限，而真相可能是他把项目 id 打错了。

        ## 顺序不能倒：先认人，再找项目，最后判角色

        先查项目的话，一个**没有身份**的调用方也能靠 404/200 的差别
        探出「哪些项目 id 存在」——那是一条靠错误码泄露存在性的路。
        """
        caller_id = (
            await deps.user_check(x_user_id) if deps.user_check is not None
            else _trusted_header(x_user_id)
        )
        # 项目不存在 → **本端点自己翻成 404**，NEVER 依赖装配处的那个处理器。
        # 装配处确实装了一个（`flint/api/app.py`），但那是**挂载之后**才生效的：
        # 子应用被单独起来时（判据面、或将来换一种装配）同一条路径会 500。
        # 一条「项目 id 打错了」以 500 收场，读起来是「服务器坏了」——
        # 那会让人去翻栈，而要做的只是改一个 id。
        try:
            scope = deps.owner_scope_for_project(project_id)
        except ProjectNotFound:
            return _error(404, "NOT_FOUND", f"unknown project: {project_id}")
        if not _may_submit(caller_id, scope, deps.role_resolver):
            raise RoleMissing(caller_id, scope.id)
        job_id = await deps.runner.submit(
            # `design_generate` 在 **v0.4 冻结加件**的 `JobKind` 里，而
            # `flint/domain/models.py#JobKind`（运行期那一份）是 v0.3 的七值——
            # 两份契约都在被引用，`flint/jobs/dispatch.py#known_job_kinds` 取的正是并集。
            # 这里 cast 而**不改冻结件**（S2-1）；拼错藏不住：
            # 判据断言这个值在 `known_job_kinds()` 里。
            kind=cast(JobKind, DESIGN_GENERATE_KIND),
            payload={
                "project_id": project_id,
                # **键名逐字照作业读的那一个**（`design_generate.py:118`
                # 读的是 `payload["prompt"]`）。`SMOKE-01` 第一次真跑这一族时
                # 撞见的就是这里：提交写 `"brief"`、作业读 `"prompt"`，
                # 于是每一条设计作业都以「没有 prompt」失败——
                # **这一族从来没有跑通过一次**。
                #
                # 请求体那一格仍叫 `brief`（那是用户那一侧的说法，`schemas.py`
                # 的既有字段），改的只是**进 payload 时的键**：
                # 两个名字说的是同一件东西，而只有一处能是真相。
                "prompt": body.brief,
                "template_id": body.template_id,
            },
            budget=body.budget_cny,
            owner_scope=scope,
            # 订阅那一头判的是 `initiated_by` **或** owner-scope 成员，
            # 所以这里两样都带上——少一样会变成「提交成功、订阅 403」，
            # 而屏上看起来是作业不见了。
            initiated_by=caller_id,
        )
        return JSONResponse({"job_id": job_id})

    @app.get("/jobs/{job_id}")
    async def snapshot(job_id: str, x_user_id: str = Header()) -> Response:
        try:
            job = await deps.runner.get(job_id)
        except KeyError:
            return _error(404, "NOT_FOUND", f"unknown job: {job_id}")
        if not may_view(job, x_user_id, deps.role_resolver):
            return _error(
                403, "PERMISSION_DENIED",
                "job snapshot requires initiator or owner-scope membership",
            )
        return JSONResponse(JobView.from_domain(job).model_dump(mode="json"))

    @app.get("/jobs/{job_id}/events")
    async def stream(job_id: str, request: Request, x_user_id: str = Header()) -> Response:
        try:
            job = await deps.runner.get(job_id)
        except KeyError:
            return _error(404, "NOT_FOUND", f"unknown job: {job_id}")
        if not may_view(job, x_user_id, deps.role_resolver):
            return _error(
                403, "PERMISSION_DENIED",
                "SSE subscription requires initiator or owner-scope membership",
            )
        try:  # M3-056 硬化：畸形头 400，绝不 500
            after = parse_last_event_id(request.headers.get("Last-Event-ID"))
        except LastEventIdInvalid as invalid:
            return _error(400, "VALIDATION_FAILED", str(invalid))

        async def generate() -> AsyncIterator[ServerSentEvent]:
            cursor = after
            while True:
                for event in await deps.events.replay(job_id, cursor):
                    cursor = event.seq
                    yield ServerSentEvent(
                        id=str(event.seq),
                        data=json.dumps(asdict(event.payload), ensure_ascii=False),
                    )
                current = await deps.runner.get(job_id)
                if current.state in _TERMINAL:
                    return
                await asyncio.sleep(deps.poll_seconds)

        return EventSourceResponse(generate())

    return app
