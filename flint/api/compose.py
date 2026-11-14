"""report/proposal 提交端点（M3-057，技术方案 E3 / v0.3.3 受众分叉）。

- POST /projects/{id}/proposal：audience 必选（缺失 pydantic 422）；
  受众规则复用 M3-032 plan_proposal（ai 锁 vibe_pack；混用 → 422
  VALIDATION_FAILED）；提交 kind="proposal" job。
- POST /projects/{id}/report：提交 kind="report" job（组稿编排 M3-060
  消费 payload）；幂等面复用 M3-056 claim_idempotency。
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from fastapi import FastAPI, Header
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from flint.api.hardening import claim_idempotency
from flint.api.interventions import may_intervene
from flint.api.schemas import ErrorBody, ErrorCode
from flint.compose.audience import AudienceForkError, plan_proposal
from flint.domain.models import JobKind, Principal
from flint.jobs.gate1 import analysis_product_id
from flint.jobs.runner import PgJobRunner, RoleResolver


@dataclass
class ComposeApiDeps:
    dsn: str
    runner: PgJobRunner
    owner_scope_for_project: Callable[[str], Principal]
    # WIRE-08：提交组稿是**写**操作，要与干预层同一道门（`_INTERVENE_ROLES`）。
    # **必填，NEVER 给 None 默认值**——「默认不检查」就是「默认开洞」，
    # 而这一族此前挂不上的理由正是「挂上等于人人可写」。
    role_resolver: RoleResolver


class ProposalSubmit(BaseModel):
    audience: Literal["human_reader", "ai_executor"]
    report_id: str
    template_id: str | None = None
    profile_id: str | None = None


class ReportSubmit(BaseModel):
    """成文的来源，两格**二选一**（`DEC-061`）。

    - `analysis_job_id`：发起分析时回的作业号——屏上手里有的就是它。
      服务端核过作业后调 `analysis_product_id()` 换成 claim 的 `deliverable_id`；
      `"analysis-" + 作业号` 这条规则只活在那一个函数里，前端 NEVER 自己拼。
    - `analysis_id`：现成的来源 id，原样透传。夹具那条路用它（拿一份既有交付物
      当来源，没有分析作业可给）。

    都给时 NEVER 「挑一个用」——那等于替调用方猜它想要哪一份来源。
    """
    analysis_id: str | None = None
    analysis_job_id: str | None = None
    template_id: str = "generic"


def create_compose_app(deps: ComposeApiDeps) -> FastAPI:
    app = FastAPI(title="flint-compose-api")

    def _denied(project_id: str, user_id: str) -> JSONResponse | None:
        """提交组稿 = 写。口径与 `interventions` 逐字同一道门（owner / admin）。

        改前**这两条端点一次权限都不判**：任何 `x_user_id` 都能给任意项目
        提交一份要花钱的组稿作业。`WIRE-01` 拒绝挂这一族时说的是「缺 resolver」，
        实况比那更进一步——**resolver 给了也没人问它**。
        """
        scope = deps.owner_scope_for_project(project_id)
        if not may_intervene(scope, user_id, deps.role_resolver):
            return JSONResponse(
                status_code=403,
                content=ErrorBody(
                    code="PERMISSION_DENIED",
                    message="composing requires project owner or org owner/admin",
                ).model_dump(exclude_none=True))
        return None

    async def _submit(
        kind: JobKind, project_id: str, payload: dict[str, object],
        user_id: str, idempotency_key: str | None,
    ) -> str:
        job_id = await deps.runner.submit(
            kind=kind, payload={"project_id": project_id, **payload},
            budget=0.0,
            owner_scope=deps.owner_scope_for_project(project_id),
            initiated_by=user_id,
        )
        if idempotency_key is not None:
            job_id = await claim_idempotency(
                deps.dsn, Principal(kind="user", id=user_id),
                idempotency_key, job_id,
            )
        return job_id

    @app.post("/projects/{project_id}/proposal")
    async def submit_proposal(
        project_id: str, body: ProposalSubmit, x_user_id: str = Header(),
        idempotency_key: str | None = Header(default=None),
    ) -> Response:
        refused = _denied(project_id, x_user_id)
        if refused is not None:
            return refused
        try:
            plan = plan_proposal(body.audience, body.template_id)
        except AudienceForkError as err:
            return JSONResponse(
                status_code=422,
                content=ErrorBody(
                    code="VALIDATION_FAILED", message=str(err)
                ).model_dump(exclude_none=True),
            )
        job_id = await _submit(
            "proposal", project_id,
            {
                "report_id": body.report_id,
                "template_id": plan.template_id,
                "audience": plan.audience,
                "profile_id": body.profile_id,
            },
            x_user_id, idempotency_key,
        )
        return JSONResponse({"job_id": job_id, "template_id": plan.template_id})

    @app.post("/projects/{project_id}/report")
    async def submit_report(
        project_id: str, body: ReportSubmit, x_user_id: str = Header(),
        idempotency_key: str | None = Header(default=None),
    ) -> Response:
        refused = _denied(project_id, x_user_id)
        if refused is not None:
            return refused
        source = await _report_source(project_id, body)
        if isinstance(source, JSONResponse):
            return source
        job_id = await _submit(
            "report", project_id,
            {"analysis_id": source, "template_id": body.template_id},
            x_user_id, idempotency_key,
        )
        return JSONResponse({"job_id": job_id})

    async def _report_source(project_id: str, body: ReportSubmit) -> str | JSONResponse:
        """来源 id，或一条说清原因的拒绝。

        换算之前逐条核作业：填错一个作业号，`freeze_ledger` 查到 0 条 claim——
        **不报错**，出一份全是 `gap_notice` 的报告，看起来像模型不给力。
        """
        given = [v for v in (body.analysis_id, body.analysis_job_id) if v is not None]
        if len(given) != 1:
            return _error(422, "VALIDATION_FAILED",
                          "give exactly one of analysis_id / analysis_job_id")
        if body.analysis_job_id is None:
            return given[0]
        job_id = body.analysis_job_id
        try:
            job = await deps.runner.get(job_id)
        except KeyError:
            job = None
        # 别的项目的作业与不存在的作业**对外长得一样**：差一个字就能被用来枚举作业号。
        if job is None or job.project_id != project_id:
            return _error(404, "NOT_FOUND", f"unknown analysis job: {job_id}")
        if job.kind != "gate1_analysis":
            return _error(422, "VALIDATION_FAILED",
                          f"job {job_id} is a {job.kind} job, not an analysis")
        if job.state != "done":
            return _error(422, "VALIDATION_FAILED",
                          f"analysis job {job_id} is {job.state}; only a done "
                          "analysis has claims to compose from")
        return analysis_product_id(job_id)

    def _error(status: int, code: ErrorCode, message: str) -> JSONResponse:
        return JSONResponse(
            status_code=status,
            content=ErrorBody(code=code, message=message).model_dump(exclude_none=True))

    return app
