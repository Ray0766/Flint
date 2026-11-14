"""ROUTE-01 · `GET /deliverables/{id}/render` 只能有一个模块注册。

## 静默遮蔽是这里唯一要治的病

`deliverables.py:97` 与 `pack.py:147` 各注册了同一条路径。
**FastAPI 对重复注册不报错**：先注册的先匹配，后注册的那个永远收不到请求。

- 先挂 `deliverables` → `pack.py` 的 render 是死代码；
- 先挂 `pack` → markdown/html/pdf/docx **四种格式全部**落到只认 pack 的处理函数。

两种都不会有任何报错。**挂载顺序 NEVER 用来保证语义**——
它是文件里两行的先后，改一次顺序就换一种行为，而没有任何东西会说话。

## 归属：`deliverables.py` 赢，但要把门禁一起接过来

赢家覆盖五种 `fmt`；输家 `pack.py` 的 `/deliverables/{id}/pack`（读内容）**照常挂**，
整个模块没有被连坐丢掉。

但 `pack.py` 的 render 身上有一样赢家没有的东西：**M4-027 三与门禁**
（blocking 审查 ∧ DagReport ∧ registry 门）。只把路由删掉的话，
`fmt=pack` 会变成一条**不过导出门的出件路**——那比路由撞车严重得多。
所以本卡把门禁接进赢家，两侧用例（放行 200 / 拒绝 409）都覆盖。

## 门禁没注入时 NEVER 直接出件

「没配门禁」与「门禁放行了」是两件相反的事。没注入 → 503 明说不可用，
NEVER 当成放行——那正是本批一路在治的同一条。
"""
from __future__ import annotations

import asyncio
import io
import os
import zipfile
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import asyncpg
import httpx
import pytest

from flint.api.app import KNOWN_COLLISIONS, create_app, mounted_route_table
from flint.api.deliverables import DeliverableApiDeps, create_deliverables_app
from flint.api.pack import GateInputs
from flint.compose.deliverable import PgDeliverableStore
from flint.domain.models import DagReport, Deliverable, TaskSpec
from flint.registry.gate import RegistryGateResult
from flint.spec.contracts_copy import build_contracts_copy
from flint.spec.pack_zip import PackBundle
from flint.spec.tasks_json import export_tasks_json
from flint.spec.vibe_s5 import build_s5
from tools.check_fe_be_parity import backend_routes, normalise_path

pytestmark = pytest.mark.compose

REPO = Path(__file__).resolve().parents[2]
API_DIR = REPO / "flint" / "api"
CONTRACTS = REPO / "contracts"
DSN = os.environ.get(
    "FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")
TICKET = REPO / "docs" / "blocked" / "RENDER-ROUTE-CLAIMED-BY-TWO-MODULES.md"
RENDER = "/deliverables/{deliverable_id}/render"
NOW = datetime(2026, 8, 6, 12, 0, 0, tzinfo=UTC)

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


def _bundle() -> PackBundle:
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


@pytest.fixture(autouse=True)
def seeded() -> Any:
    async def wipe() -> None:
        conn = await asyncpg.connect(DSN)
        try:
            await conn.execute(
                "DELETE FROM deliverables WHERE deliverable_id LIKE 'route01-%'")
        finally:
            await conn.close()

    run(wipe())
    run(PgDeliverableStore(dsn=DSN).save_deliverable(Deliverable(
        deliverable_id="route01-d1", project_id="p-1", type="vibe_pack",
        version=1, supersedes=None, inputs=[], ledger_version=1,
        generation_record_id="gr-1", stale_reasons=[], created_at=NOW,
    )))
    yield
    run(wipe())


def _client(inputs: GateInputs | None, *, builder: bool = True) -> httpx.AsyncClient:
    async def build(deliverable_id: str) -> PackBundle:
        return _bundle()

    async def gate_inputs(deliverable_id: str) -> GateInputs:
        assert inputs is not None
        return inputs

    app = create_deliverables_app(DeliverableApiDeps(
        dsn=DSN,
        pack_builder=build if builder else None,
        pack_gate_inputs=gate_inputs if inputs is not None else None,
    ))
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://t")


# ───────────────────────── acceptance②：撞车即红，NEVER 靠挂载顺序


def test_no_path_is_claimed_by_two_modules() -> None:
    """**全仓扫描**：同 method+path 被两个模块注册即红。

    这条判的是**源码里的注册面**，不是装配后的结果——
    装配后只剩一条是「谁赢了」，而两个模块都写着那条路径这件事本身
    就是下一次静默遮蔽的材料。
    """
    by_key: dict[tuple[str, str], set[str]] = defaultdict(set)
    for route in backend_routes(API_DIR):
        by_key[(route.method, normalise_path(route.path))].add(route.module)
    collisions = {k: sorted(v) for k, v in by_key.items() if len(v) > 1}

    assert collisions == {}, f"还有模块在抢同一条路径：{collisions}"


def test_the_collision_register_is_empty_now() -> None:
    """登记面跟着空掉。

    `WIRE-01` 时这里登记着一处（winner=deliverables.py）——那是**临时处置**，
    单子上写着「等 owner 一句话」。本卡按 owner 的裁决把冲突真正解掉，
    登记面就该空。留着一条空登记等于说「还有一处静默遮蔽」。
    """
    assert KNOWN_COLLISIONS == ()


def test_the_assembled_app_has_exactly_one_render_route() -> None:
    """装配后 `GET …/render` **只有一个** route 对象。

    两个的话，行为由挂载顺序决定——而顺序是文件里两行的先后。
    """
    app = create_app("postgresql://x@127.0.0.1:1/y")
    renders = [r for r in mounted_route_table(app)
               if r.path == RENDER and "GET" in r.methods]

    assert len(renders) == 1, f"有 {len(renders)} 条 render 路由"


def test_the_duplicate_detector_still_bites() -> None:
    """**阴性对照**：造一对真的抢同一条路径的模块 → 必须被检出。

    没有这条，上面那个 `== {}` 与「扫描面塌了、什么都没扫到」长得一模一样。
    """
    import tempfile

    module = (
        "from fastapi import FastAPI\n"
        "app = FastAPI()\n"
        '@app.get("/twins")\n'
        "async def twins() -> list[str]:\n"
        "    return []\n"
    )
    with tempfile.TemporaryDirectory() as tmp:
        for name in ("alpha.py", "beta.py"):
            (Path(tmp) / name).write_text(module, encoding="utf-8")
        by_key: dict[tuple[str, str], set[str]] = defaultdict(set)
        for route in backend_routes(Path(tmp)):
            by_key[(route.method, normalise_path(route.path))].add(route.module)

    assert {k: sorted(v) for k, v in by_key.items() if len(v) > 1} == {
        ("GET", "/twins"): ["alpha.py", "beta.py"]}


# ───────────────────────── acceptance③：fmt=pack 仍然通，且过三与门


def test_pack_export_passes_the_three_way_gate_and_returns_a_zip() -> None:
    """放行用例：门过了 → 200 zip，且 zip 里有 CLAUDE.md 与 tasks.json。"""
    async def scenario() -> None:
        async with _client(CLEAN) as client:
            got = await client.get("/deliverables/route01-d1/render?fmt=pack")

            assert got.status_code == 200, got.text
            assert got.headers["content-type"] == "application/zip"
            with zipfile.ZipFile(io.BytesIO(got.content)) as archive:
                assert "CLAUDE.md" in archive.namelist()
                assert "tasks.json" in archive.namelist()

    run(scenario())


def test_a_refused_gate_blocks_the_export_with_its_violations() -> None:
    """拒绝用例：门拒 → 409 EXPORT_BLOCKED，**并说出是哪两类违规**。

    只回一个 409 而不带 violations 的话，用户知道被拦了却不知道拦在哪——
    而 review 类与 registry 类要人做的事完全不同。
    """
    async def scenario() -> None:
        async with _client(BLOCKED) as client:
            got = await client.get("/deliverables/route01-d1/render?fmt=pack")

            assert got.status_code == 409, got.text
            body = got.json()
            assert body["code"] == "EXPORT_BLOCKED"
            violations = body["detail"]["violations"]
            assert {v.split(":")[0] for v in violations} == {"review", "registry"}

    run(scenario())


def test_a_missing_gate_refuses_instead_of_exporting() -> None:
    """**门禁没注入 → 503 明说，NEVER 当成放行**。

    「没配门禁」与「门禁放行了」是两件相反的事。
    退回「没注入就直接出件」的话，一份本该被拦的 pack 会照常发出去。
    """
    async def scenario() -> None:
        async with _client(None) as client:
            got = await client.get("/deliverables/route01-d1/render?fmt=pack")

            assert got.status_code == 503, got.text
            assert got.json()["code"] == "SERVICE_UNAVAILABLE"
            assert "gate" in got.json()["message"]

    run(scenario())


def test_a_missing_builder_still_says_unavailable() -> None:
    """builder 没注入那条**原样保留**（E6 姿态，`WIRE-01` 挑赢家的理由之一）。"""
    async def scenario() -> None:
        async with _client(CLEAN, builder=False) as client:
            got = await client.get("/deliverables/route01-d1/render?fmt=pack")

            assert got.status_code == 503, got.text

    run(scenario())


def test_the_other_four_formats_are_untouched() -> None:
    """另外四种 fmt **不进门禁那条路**——它们走的是 `guarded_render`。

    把三与门套到 markdown/html 上会让报告导出被 pack 的门拦住，
    那是两件事：pack 的门管的是 vibe_pack 出件（DAG、registry、审查），
    报告的门管的是 blocking 审查。
    """
    async def scenario() -> None:
        async with _client(BLOCKED) as client:   # 门是拒的，但这几种不看它
            got = await client.get("/deliverables/route01-d1/render?fmt=markdown")

            assert got.status_code == 200, got.text

    run(scenario())


# ───────────────────────── acceptance①：输家的独有端点照常挂


def test_the_pack_content_path_survives() -> None:
    """`GET /deliverables/{id}/pack` 还在——模块没有被连坐丢掉。"""
    mounted = {r.path for r in mounted_route_table(
        create_app("postgresql://x@127.0.0.1:1/y"))}

    assert "/deliverables/{deliverable_id}/pack" in mounted


def test_pack_module_no_longer_registers_the_render_path() -> None:
    """`pack.py` 里不再有那条 route 声明。

    留着不挂只是把静默遮蔽换成了死代码：下一个人把它挂上去，
    今天这处冲突原样回来。
    """
    modules = {route.module for route in backend_routes(API_DIR)
               if normalise_path(route.path) == normalise_path(RENDER)}

    assert modules == {"deliverables.py"}, f"还有谁在注册 render：{modules}"


# ───────────────────────── acceptance④：单子关掉


def test_the_ticket_is_closed() -> None:
    head = "\n".join(TICKET.read_text(encoding="utf-8").splitlines()[:16])

    assert "**状态** closed" in head
    assert "ROUTE-01" in head
