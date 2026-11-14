"""干预 API：lock / regenerate / inject / dispute（M3-048，技术方案 E3 / 审6）。

- 权限单点 may_intervene：owner_scope 为 org → role ∈ {owner, admin}；
  user 域仅本人。越权 403 PERMISSION_DENIED。
- lock/dispute 落 EditEvent（F3 七枚举内动作）；inject 不在枚举，不落。
- regenerate 提交 job（kind="report"）返回 job_id——实际再生成在 worker
  （M3-060 compose 编排）执行，且产出 MUST 与初稿同过
  draft_section_with_channels（同门原则，M3-042 复审备忘）。
- inject 走 M3-044 自动重放（≤3）；重放耗尽 → 409 LEDGER_CONFLICT。
- dispute 走 M3-046 确认语义：账本前进 → 409 LEDGER_CONFLICT（detail 携
  current_version），确认后带 confirmed_version 重提。
- optin 透传：inject 请求体 user_evidence_optin → GenerationRecord 通道
  （M3-025 复审备忘接线）。
"""
from __future__ import annotations

import json
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from flint.align.stage1 import LLMCitationAligner
from flint.api.schemas import ErrorBody, ErrorCode
from flint.domain.models import (
    Dispute,
    EditEvent,
    LedgerVersionConflict,
    Principal,
    UserEvidence,
)
from flint.intervene.dispute_retry import (
    DisputeConfirmationRequired,
    accept_with_confirmation,
    confirm_resubmit,
)
from flint.intervene.edits import PgEditService
from flint.intervene.inject_retry import inject_with_replay
from flint.intervene.lock import PgLockService
from flint.jobs.runner import PgJobRunner, RoleResolver
from flint.ledger.store import PgLedgerStore
from flint.scoring.scorer import DualScaleScorer

_INTERVENE_ROLES = frozenset({"owner", "admin"})


@dataclass
class InterventionApiDeps:
    dsn: str
    runner: PgJobRunner
    role_resolver: RoleResolver
    owner_scope_for_project: Callable[[str], Principal]
    ledger_store: PgLedgerStore
    scorer: DualScaleScorer
    aligner: LLMCitationAligner
    now: Callable[[], datetime] = lambda: datetime.now(UTC)


def may_intervene(
    scope: Principal, user_id: str, roles: RoleResolver
) -> bool:
    if scope.kind == "org":
        return roles(user_id, scope.id) in _INTERVENE_ROLES
    return user_id == scope.id


def _error(status: int, code: ErrorCode, message: str,
           detail: dict[str, object] | None = None) -> JSONResponse:
    body = ErrorBody(code=code, message=message, detail=detail)
    return JSONResponse(status_code=status,
                        content=body.model_dump(exclude_none=True))


class LockRequest(BaseModel):
    target_id: str
    scope: Literal["block", "section"]
    deliverable_id: str
    project_id: str


class InjectRequest(BaseModel):
    evidence_kind: Literal["file", "url", "text"]
    content_ref: str
    note: str = ""
    claim_text: str
    expected_version: int
    user_evidence_optin: bool = False


class DisputeRequest(BaseModel):
    dispute_id: str
    deliverable_id: str
    target_kind: Literal["block", "fact", "citation"]
    target_id: str
    reason_text: str
    expected_version: int
    confirmed_version: int | None = None


def create_interventions_app(deps: InterventionApiDeps) -> FastAPI:
    app = FastAPI(title="flint-interventions-api")
    edits = PgEditService(dsn=deps.dsn)
    locks = PgLockService(dsn=deps.dsn)

    def _denied(project_id: str, user_id: str) -> JSONResponse | None:
        scope = deps.owner_scope_for_project(project_id)
        if not may_intervene(scope, user_id, deps.role_resolver):
            return _error(
                403, "PERMISSION_DENIED",
                "interventions require project owner or org owner/admin",
            )
        return None

    @app.post("/interventions/lock", status_code=204)
    async def lock(body: LockRequest, x_user_id: str = Header()) -> Response:
        denied = _denied(body.project_id, x_user_id)
        if denied is not None:
            return denied
        try:
            await locks.lock(body.target_id, scope=body.scope)
        except KeyError:
            return _error(404, "NOT_FOUND", f"unknown {body.scope}: {body.target_id}")
        await edits.record(EditEvent(
            event_id=f"ev-{uuid4().hex[:12]}",
            deliverable_id=body.deliverable_id,
            section_id=body.target_id if body.scope == "section" else None,
            block_id=body.target_id if body.scope == "block" else None,
            action="lock", before=None, after={"locked": True},
            user_id=x_user_id, ts=deps.now(),
        ))
        return Response(status_code=204)

    @app.post("/deliverables/{deliverable_id}/sections/{section_id}/regenerate")
    async def regenerate(
        deliverable_id: str, section_id: str, project_id: str,
        request: Request, x_user_id: str = Header(),
    ) -> Response:
        denied = _denied(project_id, x_user_id)
        if denied is not None:
            return denied
        # 可选 body {block_id, guidance}（FE-CORE-007 块级指令式重生成）。缺 body（L2
        # 章节级）→ 章节级，向后兼容。guidance 只引导方向——组稿通道门保证 NEVER 编造
        # 出处（账本外事实拒稿，FE-CORE-006）；worker 消费见 flint/jobs/regenerate_worker。
        body: dict[str, object] = {}
        raw = await request.body()
        if raw:
            with suppress(json.JSONDecodeError):
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    body = parsed
        block_id = body.get("block_id")
        guidance = body.get("guidance")
        payload: dict[str, object] = {
            "action": "regenerate_block" if block_id else "regenerate_section",
            "deliverable_id": deliverable_id,
            "section_id": section_id,
            "project_id": project_id,
        }
        if isinstance(block_id, str) and block_id:
            payload["block_id"] = block_id
        if isinstance(guidance, str) and guidance:
            payload["guidance"] = guidance
        job_id = await deps.runner.submit(
            kind="report", payload=payload, budget=0.0,
            owner_scope=deps.owner_scope_for_project(project_id),
            initiated_by=x_user_id,
        )
        return JSONResponse({"job_id": job_id})

    @app.post("/projects/{project_id}/evidence")
    async def inject(
        project_id: str, body: InjectRequest, x_user_id: str = Header(),
    ) -> Response:
        denied = _denied(project_id, x_user_id)
        if denied is not None:
            return denied
        ev = UserEvidence(
            evidence_id=f"ue-{uuid4().hex[:12]}",
            owner=Principal(kind="user", id=x_user_id),
            kind=body.evidence_kind, content_ref=body.content_ref,
            note=body.note, created_at=deps.now(),
        )
        try:
            replayed = await inject_with_replay(
                store=deps.ledger_store, project_id=project_id, ev=ev,
                scorer=deps.scorer, aligner=deps.aligner,
                claim_text=body.claim_text,
                initial_expected_version=body.expected_version,
                user_evidence_optin=body.user_evidence_optin,
            )
        except LedgerVersionConflict as conflict:
            return _error(
                409, "LEDGER_CONFLICT", "auto-replay exhausted",
                detail={"current_version":
                        getattr(conflict, "current_version", None)},
            )
        result = replayed.result
        return JSONResponse({
            "alignment": result.alignment,
            "fact_added": result.fact_added,
            "ledger_version": result.ledger.version,
            "score_axis": result.score.axis,
            "user_evidence_verdict_optin": result.optin_recorded,
            "attempts": replayed.attempts,
        })

    @app.post("/projects/{project_id}/disputes")
    async def dispute(
        project_id: str, body: DisputeRequest, x_user_id: str = Header(),
    ) -> Response:
        denied = _denied(project_id, x_user_id)
        if denied is not None:
            return denied
        d = Dispute(
            dispute_id=body.dispute_id, deliverable_id=body.deliverable_id,
            target_kind=body.target_kind, target_id=body.target_id,
            reason_text=body.reason_text, status="open",
            created_by=x_user_id, created_at=deps.now(),
        )
        try:
            if body.confirmed_version is not None:
                outcome = await confirm_resubmit(
                    deps.ledger_store, project_id, d,
                    confirmed_version=body.confirmed_version, blocks=[],
                )
            else:
                outcome = await accept_with_confirmation(
                    deps.ledger_store, project_id, d,
                    expected_version=body.expected_version, blocks=[],
                )
        except DisputeConfirmationRequired as needed:
            return _error(
                409, "LEDGER_CONFLICT",
                "ledger moved: confirm against the current version",
                detail={"current_version": needed.current_version},
            )
        from flint.domain.models import EditEvent

        await edits.record(EditEvent(
            event_id=f"ev-{uuid4().hex[:12]}",
            deliverable_id=body.deliverable_id, section_id=None,
            block_id=body.target_id if body.target_kind == "block" else None,
            action="dispute", before=None,
            after={"target_id": body.target_id, "status": "disputed"},
            user_id=x_user_id, ts=deps.now(),
        ))
        return JSONResponse({"ledger_version": outcome.ledger.version})

    return app
