"""deliverable 读取与 render 端点（M3-058，技术方案 E3 / 审11 经 API 面）。

- GET /deliverables/{id}：元信息；/deliverables/{id}/blocks：结构化 Block 树
  JSON（前端 L0 只读渲染器读契约，逐块原生渲染而非已渲染 markdown/html）；
  /render?fmt=markdown|html|pdf|docx|pack
  （fmt=pack：M4-010 接线 zip 出件；PackGate 挂钩位 M4-030 接实调——
  builder 未接线 → 503，E6 姿态明说不可用）。
- 门禁：guarded_render（M3-037）拒绝 → 409 EXPORT_BLOCKED（detail 携
  违规 block 清单）。
- pdf：引擎不可用（Q-003 GTK 缺失）→ 503 SERVICE_UNAVAILABLE（E6 姿态：
  明说不可用，不装死不崩溃）；GTK 就绪后 weasyprint 路径自动生效。
"""
from __future__ import annotations

import importlib
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass
from typing import Literal

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response

from flint.api.pack import GateInputs
from flint.api.schemas import ErrorBody, ErrorCode
from flint.compose.blocks import PgBlockStore
from flint.compose.deliverable import PgDeliverableStore
from flint.render.docx import render_docx
from flint.render.gatekeeper import ExportBlocked, guarded_render
from flint.render.html import render_html
from flint.render.markdown import render_markdown
from flint.spec.export_gate import vibe_export_gate
from flint.spec.pack_zip import PackBundle, PackExportBlocked, PackGate, build_zip

PackBuilder = Callable[[str], Awaitable[PackBundle]]
# ROUTE-01：三与门（M4-027）的三个输入由调用方实时取——
# 本层只装配判定，不认识库表（同 `pack.py` 原来的做法，逐字搬过来）。
PackGateInputsFetcher = Callable[[str], Awaitable[GateInputs]]


@dataclass
class DeliverableApiDeps:
    dsn: str
    pack_builder: PackBuilder | None = None
    pack_gate: PackGate | None = None
    # ROUTE-01：`pack.py` 的 render 被删掉之后，它身上那道三与门搬到这里。
    # **默认 `None` 不等于放行**——不注入时 `fmt=pack` 回 503 明说不可用。
    pack_gate_inputs: PackGateInputsFetcher | None = None


def _error(status: int, code: ErrorCode, message: str,
           detail: dict[str, object] | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content=ErrorBody(
            code=code, message=message, detail=detail
        ).model_dump(exclude_none=True),
    )


def _pdf_available() -> bool:
    try:
        importlib.import_module("weasyprint")
    except OSError:
        return False
    except ImportError:
        return False
    return True


def create_deliverables_app(deps: DeliverableApiDeps) -> FastAPI:
    app = FastAPI(title="flint-deliverables-api")
    blocks_store = PgBlockStore(dsn=deps.dsn)
    deliverable_store = PgDeliverableStore(dsn=deps.dsn)

    @app.get("/deliverables/{deliverable_id}")
    async def read(deliverable_id: str) -> Response:
        try:
            deliverable = await deliverable_store.load_deliverable(deliverable_id)
        except KeyError:
            return _error(404, "NOT_FOUND", f"unknown deliverable: {deliverable_id}")
        return JSONResponse({
            "deliverable_id": deliverable.deliverable_id,
            "type": deliverable.type,
            "version": deliverable.version,
            "ledger_version": deliverable.ledger_version,
            "reproducible": deliverable.reproducible,
        })

    @app.get("/deliverables/{deliverable_id}/blocks")
    async def blocks(deliverable_id: str) -> Response:
        """结构化 Block 树 JSON（前端 L0 只读渲染器读契约）。稳定序
        (section_id, block_order)；content 判别联合逐字带出（kind 判别字段），
        保护标志（locked/author/user_modified）与 needs_review 一并输出——
        前端只读渲染、NEVER 回写（Block 树是唯一真相 [D3]）。"""
        try:
            await deliverable_store.load_deliverable(deliverable_id)
        except KeyError:
            return _error(404, "NOT_FOUND", f"unknown deliverable: {deliverable_id}")
        tree = await blocks_store.load_tree(deliverable_id)
        return JSONResponse({
            "deliverable_id": deliverable_id,
            "blocks": [asdict(block) for block in tree],
        })

    @app.get("/deliverables/{deliverable_id}/render")
    async def render(
        deliverable_id: str,
        fmt: Literal["markdown", "html", "pdf", "docx", "pack"],
    ) -> Response:
        try:
            await deliverable_store.load_deliverable(deliverable_id)
        except KeyError:
            return _error(404, "NOT_FOUND", f"unknown deliverable: {deliverable_id}")
        if fmt == "pack":
            if deps.pack_builder is None:
                return _error(
                    503, "SERVICE_UNAVAILABLE",
                    "pack builder not wired (vibe_pack compose line)",
                )
            if deps.pack_gate_inputs is None:
                # **没配门禁 NEVER 等于门禁放行**。这条路是导出面（审11：
                # 预览与出件同门），三个输入取不到时唯一诚实的答复是
                # 「这套部署现在出不了 pack」——直接出件等于绕过三与门。
                return _error(
                    503, "SERVICE_UNAVAILABLE",
                    "vibe export gate inputs not wired (M4-027)",
                )
            gate_inputs = await deps.pack_gate_inputs(deliverable_id)
            verdict = vibe_export_gate(
                gate_inputs.blocking_block_ids, gate_inputs.dag_report,
                gate_inputs.registry,
            )
            if not verdict.allowed:
                return _error(
                    409, "EXPORT_BLOCKED", "vibe export gate refused",
                    detail={"violations": verdict.violations},
                )
            bundle = await deps.pack_builder(deliverable_id)
            try:
                payload = build_zip(bundle, gate=deps.pack_gate)
            except PackExportBlocked as blocked_pack:
                return _error(
                    409, "EXPORT_BLOCKED", "pack gate refused export",
                    detail={"violations": blocked_pack.violations},
                )
            return Response(content=payload, media_type="application/zip")
        tree = await blocks_store.load_tree(deliverable_id)
        try:
            if fmt == "markdown":
                return PlainTextResponse(guarded_render(tree, render_markdown))
            if fmt == "html":
                return HTMLResponse(guarded_render(tree, render_html))
            if fmt == "docx":
                payload = guarded_render(tree, render_docx)
                return Response(
                    content=payload,
                    media_type=(
                        "application/vnd.openxmlformats-officedocument"
                        ".wordprocessingml.document"
                    ),
                )
            if not _pdf_available():
                return _error(
                    503, "SERVICE_UNAVAILABLE",
                    "pdf engine unavailable (GTK runtime missing, Q-003)",
                )
            from flint.render.pdf import render_pdf

            return Response(
                content=guarded_render(tree, render_pdf),
                media_type="application/pdf",
            )
        except ExportBlocked as blocked:
            return _error(
                409, "EXPORT_BLOCKED", "blocking reviews open",
                detail={"blocking_block_ids": blocked.blocking_block_ids},
            )

    return app
