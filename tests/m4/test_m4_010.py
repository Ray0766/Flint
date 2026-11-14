"""M4-010 acceptance tests: zip pack export.

Acceptance (tasks.json M4-010):
  - zip = CLAUDE.md form + tasks.json + contracts copy (the E3 three pieces)
  - fmt=pack endpoint serves it; gate hook site ready (M4-030 wires real
    validation)
"""
from __future__ import annotations

import asyncio
import io
import json
import os
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import asyncpg
import httpx
import pytest

from flint.api.deliverables import DeliverableApiDeps, create_deliverables_app
from flint.api.pack import GateInputs
from flint.compose.deliverable import PgDeliverableStore
from flint.domain.models import DagReport, Deliverable, TaskSpec
from flint.registry.gate import RegistryGateResult
from flint.spec.contracts_copy import build_contracts_copy
from flint.spec.pack_zip import PackBundle, PackExportBlocked, build_zip
from flint.spec.tasks_json import export_tasks_json
from flint.spec.vibe_s5 import build_s5

pytestmark = pytest.mark.compose

DSN = os.environ.get("FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")
CONTRACTS = Path(__file__).resolve().parents[2] / "contracts"
NOW = datetime(2026, 7, 28, 12, 0, 0, tzinfo=UTC)
# ROUTE-01：`fmt=pack` 现在先过三与门（M4-027，原在 `pack.py` 的 render 上）。
# 本文件量的是 zip 出件本身，所以给一份**放行**的输入——
# 门的两侧由 `tests/v041/test_render_route_owner.py` 覆盖。
CLEAN = GateInputs(
    blocking_block_ids=[],
    dag_report=DagReport(acyclic=True, orphans=[], unreachable=[], errors=[]),
    registry=RegistryGateResult(violations=[], gap=None),
)


async def clean_gate(deliverable_id: str) -> GateInputs:
    return CLEAN


def run(coro: Any) -> Any:
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def clean_slate() -> None:
    async def wipe() -> None:
        conn = await asyncpg.connect(DSN)
        try:
            await conn.execute(
                "DELETE FROM deliverables WHERE deliverable_id LIKE 'm4010-%'"
            )
        finally:
            await conn.close()

    run(wipe())


def bundle() -> PackBundle:
    tasks = [
        TaskSpec(
            task_id="T-1", title="任务一", inputs=["repo-skeleton"],
            outputs=["mod.T-1"], acceptance=["验收一"], depends_on=[],
            milestone="M1", estimate_days=None, estimate_cycles=1.0,
            oneshot=True, verify_cmd="pytest tests/test_T-1.py -q",
            context_refs=["contracts/models.py#TaskSpec"], review_gate=False,
        )
    ]
    chapter = build_s5(tasks)
    return PackBundle(
        claude_md="## S1 Charter\n\n目标一\n\n" + chapter.markdown,
        human_digest="监工视图：看 progress.jsonl 尾部。",
        tasks_json=export_tasks_json(chapter),
        contracts=build_contracts_copy(CONTRACTS),
    )


EXPECTED_NAMES = {
    "CLAUDE.md", "tasks.json", "HUMAN_DIGEST.md",
    "contracts/models.py", "contracts/protocols.py",
    "contracts/README.md", "contracts/MANIFEST.sha256",
}


def test_zip_carries_e3_three_pieces() -> None:
    payload = build_zip(bundle())
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        assert set(archive.namelist()) == EXPECTED_NAMES
        claude_md = archive.read("CLAUDE.md").decode("utf-8")
        assert "## S5 Task DAG" in claude_md
        assert "监工视图" not in claude_md, "digest sidecar, not in CLAUDE.md"
        data = json.loads(archive.read("tasks.json").decode("utf-8"))
        assert data["dag_report"]["acyclic"] is True
        assert archive.read("contracts/models.py") == (
            (CONTRACTS / "models.py").read_bytes()
        )


def test_gate_hook_blocks_export() -> None:
    with pytest.raises(PackExportBlocked, match="registry"):
        build_zip(bundle(), gate=lambda b: ["registry: httpx unavailable"])


def test_tampered_contracts_block_zip() -> None:
    b = bundle()
    broken = PackBundle(
        claude_md=b.claude_md, human_digest=b.human_digest,
        tasks_json=b.tasks_json,
        contracts=type(b.contracts)(
            files={**b.contracts.files, "models.py": b"tampered"},
            manifest=b.contracts.manifest, readme=b.contracts.readme,
        ),
    )
    with pytest.raises(PackExportBlocked, match="drifted"):
        build_zip(broken)


def seed_deliverable() -> None:
    run(PgDeliverableStore(dsn=DSN).save_deliverable(Deliverable(
        deliverable_id="m4010-d1", project_id="p-1", type="vibe_pack",
        version=1, supersedes=None, inputs=[], ledger_version=1,
        generation_record_id="gr-1", stale_reasons=[], created_at=NOW,
    )))


def test_endpoint_serves_zip_and_503_when_unwired() -> None:
    seed_deliverable()

    async def builder(deliverable_id: str) -> PackBundle:
        assert deliverable_id == "m4010-d1"
        return bundle()

    async def scenario() -> None:
        wired = create_deliverables_app(
            DeliverableApiDeps(
                dsn=DSN, pack_builder=builder, pack_gate_inputs=clean_gate)
        )
        transport = httpx.ASGITransport(app=wired)
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
            response = await c.get("/deliverables/m4010-d1/render?fmt=pack")
            assert response.status_code == 200
            assert response.headers["content-type"] == "application/zip"
            with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
                assert set(archive.namelist()) == EXPECTED_NAMES

        unwired = create_deliverables_app(DeliverableApiDeps(dsn=DSN))
        transport2 = httpx.ASGITransport(app=unwired)
        async with httpx.AsyncClient(transport=transport2, base_url="http://t") as c:
            response = await c.get("/deliverables/m4010-d1/render?fmt=pack")
            assert response.status_code == 503

    run(scenario())


def test_endpoint_gate_refusal_409() -> None:
    seed_deliverable()

    async def builder(deliverable_id: str) -> PackBundle:
        return bundle()

    async def scenario() -> None:
        app = create_deliverables_app(DeliverableApiDeps(
            dsn=DSN, pack_builder=builder, pack_gate_inputs=clean_gate,
            pack_gate=lambda b: ["dag: cycle detected"],
        ))
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
            response = await c.get("/deliverables/m4010-d1/render?fmt=pack")
            assert response.status_code == 409
            body = response.json()
            assert body["code"] == "EXPORT_BLOCKED"
            assert body["detail"]["violations"] == ["dag: cycle detected"]

    run(scenario())
