"""M4-028 acceptance tests: fmt=pack endpoint real wiring.

Acceptance (tasks.json M4-028):
  - GET /deliverables/{id}/render?fmt=pack full chain (gate -> zip)
  - fmt=markdown single-file preview endpoint

## ROUTE-01：这条链搬到 `deliverables.py` 上跑

改前本文件建的是 `create_pack_app`——而 `pack.py` 与 `deliverables.py`
**各注册同一条 `/render`**。两个 app 分开跑时互不干扰，并成一个应用后
先挂的先匹配、后挂的静默失效，行为由文件里两行的先后决定。

owner 裁决 `deliverables.py` 赢，三与门（M4-027）连同 409 姿态搬进赢家。
本文件的三条链路判据**逐字保留原意**，只把 client 换成赢家：
门过 → zip、门拒 → 409 带 violations 分类、交付物不存在 → 404。

**`fmt=markdown` 单文件预览那条随之没了**：赢家的 `fmt=markdown` 是
Block 树渲染，两种 markdown 在一条路径上放不下。CLAUDE.md 的内容仍可读
（`GET /deliverables/{id}/pack` 逐章给），所以本文件把那条改成量
「内容还拿得到」，并在断言里写明**它不过导出门**——这不是等价替换，
要把带门禁的单文件预览接回来需要一个新的 fmt 值，那是 owner 的口径决定。
"""
from __future__ import annotations

import asyncio
import io
import os
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import asyncpg
import httpx
import pytest

from flint.api.deliverables import DeliverableApiDeps, create_deliverables_app
from flint.api.pack import GateInputs, PackApiDeps, create_pack_app
from flint.compose.deliverable import PgDeliverableStore
from flint.domain.models import DagReport, Deliverable, TaskSpec
from flint.registry.gate import RegistryGateResult
from flint.spec.contracts_copy import build_contracts_copy
from flint.spec.pack_zip import PackBundle
from flint.spec.tasks_json import export_tasks_json
from flint.spec.vibe_s5 import build_s5

pytestmark = pytest.mark.compose

DSN = os.environ.get("FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")
CONTRACTS = Path(__file__).resolve().parents[2] / "contracts"
NOW = datetime(2026, 7, 28, 12, 0, 0, tzinfo=UTC)

CLEAN = GateInputs(
    blocking_block_ids=[],
    dag_report=DagReport(acyclic=True, orphans=[], unreachable=[], errors=[]),
    registry=RegistryGateResult(violations=[], gap=None),
)
BLOCKED = GateInputs(
    blocking_block_ids=["b-1"],
    dag_report=DagReport(acyclic=True, orphans=[], unreachable=[], errors=[]),
    registry=RegistryGateResult(violations=["httpx unavailable"], gap=None),
)


def run(coro: Any) -> Any:
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def clean_slate() -> None:
    async def wipe() -> None:
        conn = await asyncpg.connect(DSN)
        try:
            await conn.execute(
                "DELETE FROM deliverables WHERE deliverable_id LIKE 'm4028-%'"
            )
        finally:
            await conn.close()

    run(wipe())


def bundle() -> PackBundle:
    tasks = [TaskSpec(
        task_id="T-1", title="任务一", inputs=["repo-skeleton"],
        outputs=["mod.T-1"], acceptance=["验收一"], depends_on=[],
        milestone="M1", estimate_days=None, estimate_cycles=1.0,
        oneshot=True, verify_cmd="pytest tests/test_T-1.py -q",
        context_refs=["contracts/models.py#TaskSpec"], review_gate=False,
    )]
    chapter = build_s5(tasks)
    return PackBundle(
        claude_md="## S1 Charter\n\n目标一\n\n" + chapter.markdown,
        human_digest="监工视图。",
        tasks_json=export_tasks_json(chapter),
        contracts=build_contracts_copy(CONTRACTS),
    )


def seed() -> None:
    run(PgDeliverableStore(dsn=DSN).save_deliverable(Deliverable(
        deliverable_id="m4028-d1", project_id="p-1", type="vibe_pack",
        version=1, supersedes=None, inputs=[], ledger_version=1,
        generation_record_id="gr-1", stale_reasons=[], created_at=NOW,
    )))


def make_client(inputs: GateInputs) -> httpx.AsyncClient:
    async def builder(deliverable_id: str) -> PackBundle:
        return bundle()

    async def gate_inputs(deliverable_id: str) -> GateInputs:
        return inputs

    app = create_deliverables_app(DeliverableApiDeps(
        dsn=DSN, pack_builder=builder, pack_gate_inputs=gate_inputs,
    ))
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://t"
    )


def make_content_client() -> httpx.AsyncClient:
    """读内容那条路（`pack.py` 保留的独有端点）。**不过导出门。**"""
    async def builder(deliverable_id: str) -> PackBundle:
        return bundle()

    async def gate_inputs(deliverable_id: str) -> GateInputs:
        return CLEAN

    async def owner(deliverable_id: str) -> str | None:
        return "m4028-user"

    async def ready(deliverable_id: str) -> bool:
        return True

    app = create_pack_app(PackApiDeps(
        dsn=DSN, bundle_builder=builder, gate_inputs=gate_inputs,
        pack_owner=owner, pack_ready=ready,
    ))
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://t"
    )


def test_full_chain_gate_then_zip() -> None:
    seed()

    async def scenario() -> None:
        async with make_client(CLEAN) as client:
            response = await client.get("/deliverables/m4028-d1/render?fmt=pack")
            assert response.status_code == 200
            assert response.headers["content-type"] == "application/zip"
            with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
                assert "CLAUDE.md" in archive.namelist()
                assert "tasks.json" in archive.namelist()

    run(scenario())


def test_the_pack_markdown_is_still_readable_through_the_content_path() -> None:
    """CLAUDE.md 的内容仍拿得到——**换了一条路，且那条路不算导出**。

    改前这条量的是 `?fmt=markdown` 单文件预览（带门禁）。`ROUTE-01` 之后
    那条路没了（见文件头），内容改由 `/pack` 逐章给。

    **这不是等价替换**，差别写在这里：`/pack` 走的是归属判定
    （`X-User-Id` 对不上就 404），**不过三与门**——按 `pack.py` 的口径
    「看内容不是导出」。带门禁的单文件预览要回来，需要一个新的 fmt 值。
    """
    seed()

    async def scenario() -> None:
        async with make_content_client() as client:
            response = await client.get(
                "/deliverables/m4028-d1/pack", headers={"X-User-Id": "m4028-user"})
            assert response.status_code == 200
            chapters = {c["id"]: c["body"] for c in response.json()["chapters"]}
            assert chapters["S1"].startswith("## S1 Charter")
            assert "S5" in chapters

    run(scenario())


def test_gate_refusal_blocks_the_export() -> None:
    """门拒 → 409 带 violations 分类。

    改前这条判 `pack` 与 `markdown` **两种 fmt 同门**（审11：预览与出件同门）。
    `ROUTE-01` 之后赢家的 `markdown` 是 Block 树渲染、走的是 `guarded_render`
    那道门，两者本来就不该共用三与门——所以本条只判出件那一种，
    并**顺带钉住 markdown 不被三与门误伤**（下一条断言）。
    """
    seed()

    async def scenario() -> None:
        async with make_client(BLOCKED) as client:
            response = await client.get("/deliverables/m4028-d1/render?fmt=pack")
            assert response.status_code == 409
            violations = response.json()["detail"]["violations"]
            assert {v.split(":")[0] for v in violations} == {"review", "registry"}

            # Block 树那侧不看三与门：报告导出被 pack 的门拦住是另一个 bug。
            other = await client.get("/deliverables/m4028-d1/render?fmt=markdown")
            assert other.status_code == 200, other.text

    run(scenario())


def test_unknown_deliverable_404() -> None:
    async def scenario() -> None:
        async with make_client(CLEAN) as client:
            response = await client.get("/deliverables/m4028-nope/render?fmt=pack")
            assert response.status_code == 404

    run(scenario())
