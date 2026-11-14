"""BE-10：设计工作台端点族（暴露 `flint/design` 的 13 个模块 · v2 屏 2.17）。

v0.4 花 33 张卡建的 `flint/design/` 至今**零 API 出口**。本卡把六样接出来：
探索期渲染 / 固化管道 / 模板注册表 / 生产渲染 / 导出闸门 / 陈旧提示，
外加 DEF-02 的 ephemeral 重放语义。

## 承重墙：两阶段之间只有固化这一道门

异见 B5 已判**维持**：生产渲染只收 `template_id` + `slot_values`，
**没有接受 html 的口子**。所以本模块里：

- `ProductionRenderRequest` **没有 html 字段**，且 `extra="forbid"`；
- `ExploreRenderer` 只出现在探索那条路的函数体里（判据在 AST 上钉着）。

两条路共用一个渲染器的那天，「探索期自由」就变成了「生产期也自由」，
而固化闸门（示例数字、来源残留、水印）就全成了摆设。

## 固化前先验 mock 标记

`solidify_mock` 会剥水印、拒示例残留，但**不要求水印在**——
没有水印的样板看起来就是成品，那正是 DESIGN-27 要防的。
所以本端点在调它之前先确认水印在场，用的是
`flint/design/solidify.py#WATERMARK_ATTR`（既有那份），
**NEVER 在这里新写一个正则**：占位语法的唯一真相是
`web/design/mock-identity/mock-syntax.json`，多一份表就会与前端分叉。

## 判据要跑完，不要报第一条

固化被拒与导出被阻都给**完整清单**（`SolidifyBlocked.violations` /
`GateResult.violations` 都是完整的）。只报第一条的话，用户改一条再撞一条。

## 降级要说清还能做什么

注册表不可用时固化与生产渲染阻断，但**探索仍可继续**（E6）——
报错文本原样转出 `RegistryUnavailable` 那句，否则用户以为整个设计台挂了。

## ephemeral 只走内存

DEF-02：标了 `ephemeral` 的 delta 不进 replay 日志（`persisted_events`）。
检查点没盖住它们时 `resume_text` 抛 `EphemeralNotCheckpointed`——
本端点回 409 并带上那几个 seq，**NEVER 悄悄放过**：
放过的话用户重连后看到的是少了一段的文字，而且看不出少了。

## `PERSIST-03`：碰注册表的处理函数从 `async def` 改成 `def`

注册表换成 SQL 实现（`flint/design/templates/pgregistry.py`）之后，
`registry.available` / `all()` / `append()` 都是**阻塞**调用
（本仓只有 asyncpg 一个驱动，同步接口与异步驱动之间那座桥
`flint/db/sync_bridge.py` 要阻塞调用它的线程）。

在 `async def` 里调它会把整条事件循环停住——桥会当场抛
`BlockingCallOnEventLoop`（那道检测正是为这一刻建的）。
`def`（同步）处理函数由 FastAPI 放进**它自己的线程池**跑。

三条改了：`explore_render`（它经 `_renderer()` 摸到 `registry`）·
`solidify` · `my_templates` · `production_render`。
**函数体一行未动**——它们本来就没有 `await`。
`export_check` / `stale_notices` / `replay` 三条**留在 async**：
它们各自要 `await` 一个注入的取数件。
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from fastapi import FastAPI, Header
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict

from flint.api.schemas import ErrorBody, ErrorCode
from flint.design.export_gate import GateResult, check_design_export
from flint.design.export_gate_template import check_template_solidified
from flint.design.graph_stale import notices_for_change
from flint.design.prod_render import (
    ExploreRenderer,
    ProductionRenderer,
    UnregisteredTemplate,
)
from flint.design.session import (
    EphemeralNotCheckpointed,
    ResumePoint,
    persisted_events,
    resume_text,
)
from flint.design.solidify import WATERMARK_ATTR, SolidifyBlocked, solidify_mock
from flint.design.templates.registry import (
    RegistryUnavailable,
    TemplateRegistryLike,
    list_templates,
)
from flint.domain.models import Principal

ExportInputsLoader = Callable[[str], Awaitable[tuple[Sequence[Any], Sequence[Any]] | None]]
ChangeLoader = Callable[[], Awaitable[Sequence[Any]]]
SessionLoader = Callable[[str], Awaitable[tuple[ResumePoint, Sequence[Any]] | None]]


class ExploreRenderRequest(BaseModel):
    """探索期：几乎无约束（G0/G10），拿到什么画什么。"""

    model_config = ConfigDict(extra="forbid")

    html: str


class ProductionRenderRequest(BaseModel):
    """生产渲染的入参。**这里没有 html 字段，也不会有**（异见 B5 判维持）。"""

    model_config = ConfigDict(extra="forbid")

    template_id: str
    slot_values: dict[str, str]


class SolidifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    template_id: str
    name: str
    mock_html: str
    source_deliverable_id: str | None = None


class ExportCheckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    deliverable_id: str
    export_format: str
    template_id: str | None = None


@dataclass
class DesignApiDeps:
    registry: TemplateRegistryLike
    now: Callable[[], datetime]
    load_export_inputs: ExportInputsLoader
    model: Any                       # contracts_v04.TemplateRecord
    event_model: Any                 # contracts_v04.SolidifyResult
    deliverables_by_graph: Mapping[str, list[str]]
    load_changes: ChangeLoader | None = None
    load_session: SessionLoader | None = None


def _error(status: int, code: ErrorCode, message: str,
           detail: Any = None) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content=ErrorBody(code=code, message=message, detail=detail).model_dump(
            exclude_none=True),
    )


def template_json(record: Any) -> dict[str, Any]:
    """一条模板的**元信息**。

    不回 `html`（那是渲染的事，不是列表的事），也不回 `owner`
    （调用方就是 owner，回给他自己没有信息量，却多一条把别人 id 带出去的路）。
    """
    return {
        "template_id": record.template_id,
        "name": record.name,
        "version": record.version,
        "slots": list(record.slots),
        "source_deliverable_id": record.source_deliverable_id,
        "checksum": record.checksum,
        "solidified_at": record.solidified_at.isoformat(),
        "enabled": record.enabled,
    }


def gate_json(result: GateResult) -> dict[str, Any]:
    return {
        "exportable": result.exportable,
        "violations": [
            {"criterion": v.criterion, "ref": v.ref, "action": v.action}
            for v in result.violations
        ],
    }


def create_design_app(deps: DesignApiDeps) -> FastAPI:
    app = FastAPI(title="Flint design workbench (BE-10)")

    def _renderer(owner: Principal) -> ProductionRenderer:
        return ProductionRenderer(registry=deps.registry, owner=owner)

    def _mine(template_id: str, owner: Principal) -> Any:
        for record in deps.registry.all():
            if record.template_id != template_id:
                continue
            if record.owner.kind == owner.kind and record.owner.id == owner.id:
                return record
        return None

    # ── 探索期：无约束，且**明说不是可交付物** ────────────────────────
    @app.post("/design/explore/render")
    def explore_render(
        body: ExploreRenderRequest, x_user_id: str = Header()
    ) -> Response:
        del x_user_id                     # 身份是入口要求；探索产物不落库、不按人切
        html = ExploreRenderer().render(body.html)
        # `production: false` 是一条**标记**：探索产物 NEVER 被下游当成可交付。
        return JSONResponse(status_code=200,
                            content={"html": html, "production": False})

    # ── 固化管道 ────────────────────────────────────────────────
    @app.post("/design/templates")
    def solidify(body: SolidifyRequest, x_user_id: str = Header()) -> Response:
        owner = Principal(kind="user", id=x_user_id)
        if not WATERMARK_ATTR.search(body.mock_html):
            # mock 三件套之一：没有水印的样板看起来就是成品（DESIGN-27）。
            return _error(
                422, "VALIDATION_FAILED",
                "这份样板没有 mock 水印：固化前 MUST 带 data-mock-watermark 标记",
                {"violations": ["missing_watermark"]},
            )
        try:
            event = solidify_mock(
                deps.registry, mock_html=body.mock_html,
                template_id=body.template_id, owner=owner, name=body.name,
                source_deliverable_id=body.source_deliverable_id,
                now=deps.now(), model=deps.model, event_model=deps.event_model,
            )
        except SolidifyBlocked as exc:
            # **完整清单**，不是第一条。
            return _error(422, "VALIDATION_FAILED", str(exc),
                          {"violations": exc.violations})
        except RegistryUnavailable as exc:
            # E6：说清还能做什么（原句里就写着「探索仍可继续」）。
            return _error(503, "SERVICE_UNAVAILABLE", str(exc))
        return JSONResponse(
            status_code=200,
            content={"kind": event.kind, "template_id": event.template_id,
                     "accepted": event.accepted, "reason": event.reason},
        )

    @app.get("/design/templates")
    def my_templates(x_user_id: str = Header()) -> Response:
        # `WIRE-12`：注册表不可用时**说出来**，NEVER 回 `{"items": []}`。
        # 空表与「查过了、你确实一个模板都没存」逐字相同，
        # 而真相是「模板还没有存储面（迁移里没有 templates 表），我们根本没查」。
        if not deps.registry.available:
            return JSONResponse(status_code=200, content={
                "status": "not_provided",
                "reason": "模板注册表不可用（迁移里没有 templates 表）："
                          "本端点 NEVER 拿一个空列表冒充「你确实没有模板」",
            })
        owner = Principal(kind="user", id=x_user_id)
        records = list_templates(deps.registry, owner=owner)
        return JSONResponse(status_code=200,
                            content={"items": [template_json(r) for r in records]})

    # ── 生产渲染：承重墙 ─────────────────────────────────────────
    @app.post("/design/render")
    def production_render(
        body: ProductionRenderRequest, x_user_id: str = Header()
    ) -> Response:
        owner = Principal(kind="user", id=x_user_id)
        if _mine(body.template_id, owner) is None:
            # 别人的模板与不存在**同一行**：403 会用状态码本身泄露存在性。
            return _error(404, "NOT_FOUND", "unknown template")
        try:
            html = _renderer(owner).render(body.template_id, body.slot_values)
        except UnregisteredTemplate as exc:
            # 到这儿说明模板是我的，但停用了或 checksum 对不上——那是该说清楚的事。
            return _error(422, "VALIDATION_FAILED", str(exc))
        except ValueError as exc:
            return _error(422, "VALIDATION_FAILED", str(exc))
        return JSONResponse(status_code=200, content={"html": html})

    # ── 导出闸门 ────────────────────────────────────────────────
    @app.post("/design/export-check")
    async def export_check(
        body: ExportCheckRequest, x_user_id: str = Header()
    ) -> Response:
        owner = Principal(kind="user", id=x_user_id)
        loaded = await deps.load_export_inputs(body.deliverable_id)
        if loaded is None:
            return _error(404, "NOT_FOUND", "unknown deliverable")
        blocks, edges = loaded
        base = check_design_export(blocks=list(blocks), edges=list(edges))
        # 第三条判据单独一处（既有模块），与前两条**合并成一份完整清单**。
        violations = [
            *base.violations,
            *check_template_solidified(
                export_format=body.export_format, template_id=body.template_id,
                registry=deps.registry, owner=owner,
            ),
        ]
        return JSONResponse(
            status_code=200,
            content=gate_json(GateResult(exportable=not violations,
                                         violations=violations)),
        )

    # ── 陈旧提示：是数据，不是动作 ───────────────────────────────
    @app.get("/design/stale-notices")
    async def stale_notices(x_user_id: str = Header()) -> Response:
        del x_user_id
        if deps.load_changes is None:
            # 没注入变更源 → 没查过。空列表会被读成「没有任何样板过时」。
            return JSONResponse(status_code=200,
                                content={"status": "not_checked"})
        items: list[dict[str, Any]] = []
        for change in await deps.load_changes():
            for notice in notices_for_change(change, dict(deps.deliverables_by_graph)):
                items.append({
                    "deliverable_id": notice.deliverable_id,
                    "graph_id": notice.graph_id,
                    "change_kind": notice.change_kind,
                    "occurred_at": notice.occurred_at.isoformat(),
                    "stale": notice.stale,
                    "actions": list(notice.actions),
                })
        return JSONResponse(status_code=200,
                            content={"status": "checked", "items": items})

    # ── DEF-02：ephemeral 重放 ──────────────────────────────────
    @app.get("/design/sessions/{job_id}/replay")
    async def replay(job_id: str, x_user_id: str = Header()) -> Response:
        del x_user_id
        if deps.load_session is None:
            return _error(404, "NOT_FOUND", "unknown session")
        loaded = await deps.load_session(job_id)
        if loaded is None:
            return _error(404, "NOT_FOUND", "unknown session")
        state, events = loaded
        try:
            text = resume_text(state, list(events))
        except EphemeralNotCheckpointed as exc:
            # 那几段文字既不在快照里也不在日志里——**说出来**，NEVER 悄悄少一段。
            return _error(409, "LEDGER_CONFLICT", str(exc),
                          {"uncheckpointed_seqs": exc.seqs})
        return JSONResponse(
            status_code=200,
            content={"text": text, "seq": state.seq,
                     "replayed": len(persisted_events(list(events)))},
        )

    return app
