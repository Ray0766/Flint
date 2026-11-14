"""禁导出全景评测（M4-030，技术方案 E6）。

- 三路禁导出（审11 blocking / dag 失败 / registry 不可用）各一用例，
  经 fmt=pack 端点全链断言 409 + 类别指认；
- 可恢复性：同一 deliverable 解除违规后重导 → 200 zip（门禁不留残锁）。
"""
from __future__ import annotations

from dataclasses import dataclass

import httpx

from flint.api.deliverables import DeliverableApiDeps, create_deliverables_app
from flint.api.pack import GateInputs
from flint.domain.models import DagReport
from flint.registry.gate import RegistryGateResult
from flint.spec.pack_zip import PackBundle

CLEAN_DAG = DagReport(acyclic=True, orphans=[], unreachable=[], errors=[])
CLEAN_REGISTRY = RegistryGateResult(violations=[], gap=None)


@dataclass(frozen=True)
class ExportGateEvalRow:
    name: str
    ok: bool
    detail: str


@dataclass(frozen=True)
class ExportGateEvalReport:
    rows: list[ExportGateEvalRow]
    all_ok: bool


def _scenarios() -> dict[str, GateInputs]:
    return {
        "block-review": GateInputs(
            blocking_block_ids=["b-1"], dag_report=CLEAN_DAG,
            registry=CLEAN_REGISTRY,
        ),
        "block-dag": GateInputs(
            blocking_block_ids=[],
            dag_report=DagReport(
                acyclic=False, orphans=[], unreachable=[],
                errors=["cycle: A -> B -> A"],
            ),
            registry=CLEAN_REGISTRY,
        ),
        "block-registry": GateInputs(
            blocking_block_ids=[], dag_report=CLEAN_DAG,
            registry=RegistryGateResult(
                violations=["validation unavailable — pack export banned"],
                gap=None,
            ),
        ),
    }


_CATEGORY: dict[str, str] = {
    "block-review": "review",
    "block-dag": "dag",
    "block-registry": "registry",
}


async def run_export_gate_eval(
    dsn: str, deliverable_id: str, bundle: PackBundle
) -> ExportGateEvalReport:
    state = {"inputs": GateInputs(
        blocking_block_ids=[], dag_report=CLEAN_DAG, registry=CLEAN_REGISTRY,
    )}

    async def builder(_: str) -> PackBundle:
        return bundle

    async def gate_inputs(_: str) -> GateInputs:
        return state["inputs"]

    # ROUTE-01：出件那条路收敛到 `deliverables.py`（三与门一起搬过去了）。
    # 本评测量的是**门的四种情形**，与它挂在哪个模块上无关——
    # 换成赢家之后量的是真正在跑的那条路，而不是一条已经收不到请求的。
    app = create_deliverables_app(DeliverableApiDeps(
        dsn=dsn, pack_builder=builder, pack_gate_inputs=gate_inputs,
    ))
    rows: list[ExportGateEvalRow] = []
    url = f"/deliverables/{deliverable_id}/render?fmt=pack"
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        for name, inputs in _scenarios().items():
            state["inputs"] = inputs
            response = await client.get(url)
            category_hit = False
            if response.status_code == 409:
                violations = response.json()["detail"]["violations"]
                category_hit = any(
                    v.startswith(f"{_CATEGORY[name]}:") for v in violations
                )
            rows.append(ExportGateEvalRow(
                name=name,
                ok=response.status_code == 409 and category_hit,
                detail=f"status={response.status_code}",
            ))

        state["inputs"] = GateInputs(
            blocking_block_ids=[], dag_report=CLEAN_DAG,
            registry=CLEAN_REGISTRY,
        )
        recover = await client.get(url)
        rows.append(ExportGateEvalRow(
            name="recover",
            ok=recover.status_code == 200
            and recover.headers.get("content-type") == "application/zip",
            detail=f"status={recover.status_code}",
        ))

    return ExportGateEvalReport(rows=rows, all_ok=all(r.ok for r in rows))
