"""EDGES-UI：画布连线——端点在、表在，前端一处都没在调。

## 卡面说的是一件事，实况是两件

卡面：「端点已装配、`graph_edges` 表已建，**缺的是画布上那个交互**」。
实测**那条路自己也没通**：`create_app` 给它注的 `edge_model=None`，
于是 `add_edge` 拿 `None` 当构造器调——`POST /workbenches/{id}/edges`
**每一次都 500**。接了画布也照样存不下。

第二处同类：那个处理函数是 `async def`，而 `PERSIST-02` 把图换成
`PgGraphStore` 之后它每次都抛 `BlockingCallOnEventLoop`。
`PERSIST-02` 给 `workbenches.py` 包了 `run_in_threadpool`，**漏了这一个**——
那时这条路上的 store 还是内存件，包不包都跑得动。
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

import asyncpg
import pytest

REPO = Path(__file__).resolve().parents[2]
CLIENT = REPO / "web" / "lib" / "edgesClient.ts"
CANVAS = REPO / "web" / "components" / "graph-workbench" / "GraphWorkbench.tsx"
PAGE = REPO / "web" / "app" / "workbenches" / "[id]" / "page.tsx"
APP_PY = REPO / "flint" / "api" / "app.py"
EDGES_PY = REPO / "flint" / "api" / "graph_edges.py"
DSN = os.environ.get(
    "FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")

_SEEDED: list[str] = []


def _code(path: Path) -> str:
    text = re.sub(r"/\*.*?\*/", "", path.read_text(encoding="utf-8"), flags=re.DOTALL)
    return "\n".join(
        ln for ln in text.splitlines()
        if not ln.strip().startswith(("//", "#")))


@pytest.fixture(autouse=True)
def _cleanup() -> object:
    """种了就收。

    `graph_edges` / `graph_nodes` 都有外键指向 `workbenches`，
    不收的话别的判据清表时撞外键——**红会出现在别人的文件里，而根因在这里**
    （`WIRE-VERDICT` 那轮实测栽过一次：全量从 0 failed 变成 6 failed / 18 errors）。
    """
    yield
    if not _SEEDED:
        return
    import asyncio

    async def go() -> None:
        conn = await asyncpg.connect(DSN)
        try:
            for graph_id in _SEEDED:
                # 先边后节点再图：外键方向决定删除顺序。
                await conn.execute(
                    "DELETE FROM graph_edges WHERE graph_id = $1", graph_id)
                await conn.execute(
                    "DELETE FROM graph_nodes WHERE graph_id = $1", graph_id)
                await conn.execute(
                    "DELETE FROM workbenches WHERE graph_id = $1", graph_id)
        finally:
            await conn.close()

    asyncio.run(go())
    _SEEDED.clear()


# ───────────────────────── 一、那条路本身通了


def test_the_edge_model_is_wired_not_none() -> None:
    """`create_app` 注的 `edge_model` **不再是 `None`**。

    注 `None` 时 `add_edge` 拿它当构造器调——每一次都 500，
    而屏上会说「没存下」，排查的人会去查画布。
    """
    code = _code(APP_PY)

    assert "edge_model=None" not in code
    assert "edge_model=_graph_edge_model()" in code


def test_the_sync_store_is_moved_off_the_event_loop() -> None:
    """同步 store 挪出事件循环——`PERSIST-01` 立的那道护栏。

    不包的话 `PgGraphStore` 每次抛 `BlockingCallOnEventLoop`，
    **而那道护栏是对的**：它拦的是「在事件循环上阻塞住整个进程」。
    """
    code = _code(EDGES_PY)

    assert "await run_in_threadpool" in code


@pytest.mark.compose
def test_the_endpoint_answers_with_a_code_instead_of_five_hundred() -> None:
    """改前**每一次都 500**；现在拒绝带 code。"""
    from fastapi.testclient import TestClient

    from flint.api.app import create_app

    client = TestClient(create_app(dsn=DSN), raise_server_exceptions=False)
    got = client.post("/workbenches/wb-nope/edges", json={
        "edge_id": "e1", "from_node_id": "n1", "to_node_id": "n2",
        "hypothesis": "两者相关"})

    assert got.status_code == 422, got.text
    assert got.json()["code"] == "VALIDATION_FAILED"
    assert "悬空边" in got.json()["message"]


# ───────────────────────── 二、连完刷新那条线还在（打真库）


def _seed_graph() -> tuple[str, str, str]:
    """种一张真图与两个节点，返回 `(graph_id, node_a, node_b)`。"""
    import asyncio

    graph_id = f"wb-edges-{uuid.uuid4().hex[:8]}"
    a, b = f"gn-a-{uuid.uuid4().hex[:6]}", f"gn-b-{uuid.uuid4().hex[:6]}"
    _SEEDED.append(graph_id)

    async def go() -> None:
        conn = await asyncpg.connect(DSN)
        try:
            # 读那张图要比一次归属，而 `check_user` 会去 `users` 表查——
            # 不种这一行的话报的是 401 IDENTITY_UNKNOWN，
            # **而那与本卡要量的东西无关**（`PERSIST-02` 那轮踩过同一处）。
            await conn.execute(
                "INSERT INTO users (user_id, email, display_name, created_at) "
                "VALUES ('edges-owner','edges@edges-ui.invalid','edges',now()) "
                "ON CONFLICT (user_id) DO NOTHING")
            await conn.execute(
                "INSERT INTO workbenches (graph_id, owner_id, seed_cluster_id, "
                "created_at) VALUES ($1,'edges-owner','c-seed',now())", graph_id)
            for node_id, label in ((a, "热点一"), (b, "热点二")):
                await conn.execute(
                    "INSERT INTO graph_nodes (node_id, graph_id, source_kind, "
                    "source_id, label, position_x, position_y, created_at) "
                    "VALUES ($1,$2,'cluster',$3,$4,0,0,$5)",
                    node_id, graph_id, node_id, label, datetime.now(UTC))
        finally:
            await conn.close()

    asyncio.run(go())
    return graph_id, a, b


@pytest.mark.compose
def test_an_edge_survives_a_brand_new_app() -> None:
    """acceptance③：连完**换一个 app 实例**（= 进程重启的等价物），那条线还在。

    只断言前端 state 的话，一个把边塞进内存的实现也能全绿。
    """
    from fastapi.testclient import TestClient

    from flint.api.app import create_app

    graph_id, a, b = _seed_graph()
    made = TestClient(create_app(dsn=DSN), raise_server_exceptions=False).post(
        f"/workbenches/{graph_id}/edges", json={
            "edge_id": f"ge-{uuid.uuid4().hex[:6]}", "from_node_id": a,
            "to_node_id": b, "hypothesis": "两个热点撑同一个假设"})
    assert made.status_code == 201, made.text

    got = TestClient(create_app(dsn=DSN), raise_server_exceptions=False).get(
        f"/workbenches/{graph_id}", headers={"x-user-id": "edges-owner"})
    assert got.status_code == 200, got.text
    edges = got.json()["edges"]

    assert len(edges) == 1, edges
    assert edges[0]["hypothesis"] == "两个热点撑同一个假设"


@pytest.mark.compose
def test_an_empty_hypothesis_keeps_its_own_code() -> None:
    """空假设走**既有的那一个** code，NEVER 分叉出第二个。

    `docs/blocked/EMPTY-HYPOTHESIS-TWO-CODES.md` 已经定过一次——
    分叉之后调用方要按两套规矩判同一件事。
    """
    from fastapi.testclient import TestClient

    from flint.api.app import create_app

    graph_id, a, b = _seed_graph()
    got = TestClient(create_app(dsn=DSN), raise_server_exceptions=False).post(
        f"/workbenches/{graph_id}/edges", json={
            "edge_id": "ge-empty", "from_node_id": a, "to_node_id": b,
            "hypothesis": ""})

    assert got.status_code == 422, got.text
    assert got.json()["code"] == "EMPTY_HYPOTHESIS", got.json()


# ───────────────────────── 三、屏上那一半


def test_the_canvas_has_a_connect_form_only_when_it_can_connect() -> None:
    """连线表单在画布上，且**不传回调就不渲染**。

    渲染一个按不动的表单，与「这个能力没有」在屏上长得一样。
    """
    canvas = _code(CANVAS)
    page = _code(PAGE)

    assert 'data-workbench-connect="true"' in canvas
    assert "onConnect ?" in canvas, "没有「不传就不渲染」这一步"
    assert "onConnect=" in page


def test_the_three_failures_each_say_their_own_thing() -> None:
    """空假设 / 悬空边 / 没存下——**三条各说各的**。

    合成一句的话，用户不知道自己该去补一句假设，还是去看两端选对没有。
    """
    client = _code(CLIENT)
    messages = json.loads(
        (REPO / "web" / "messages" / "zh.json").read_text(encoding="utf-8"))

    assert '"empty_hypothesis"' in client and '"rejected"' in client
    texts = [messages[f"workbench.connect.error.{k}"]
             for k in ("empty", "rejected", "failed")]
    assert len(set(texts)) == 3, texts


def test_a_failed_connect_never_leaves_the_line_on_the_canvas() -> None:
    """acceptance④：存不下时 **NEVER 把线留在画布上假装成功**。

    与 `LocaleSettings` 那条「NEVER 回滚成旧值假装成功」是同一条纪律的两个方向：
    那边禁「失败了把屏改回去」，这边禁「失败了把屏留在新样子」——
    共同点是**屏上显示的东西没有依据**。

    判法：成功那一支才重取整张图；全程 NEVER 出现 `setGraph`
    （屏自己把线画上去 = 一句没有依据的话）。
    """
    page = _code(PAGE)
    body = page[page.index("async function connectNodes"):]
    body = body[: body.index("useEffect")]
    ok_branch = body[body.index('result.state === "ok"'):]

    assert "setRound" in ok_branch, "成功之后没有重取"
    assert "setGraph" not in body, "屏自己把线画上去了——那是一句没有依据的话"


# ───────────────────────── 四、对账器少一条


def test_the_endpoint_left_the_unused_list() -> None:
    """acceptance⑤。"""
    done = subprocess.run(
        [sys.executable, str(REPO / "tools" / "check_fe_be_parity.py"), "--json"],
        capture_output=True, text=True, encoding="utf-8", cwd=REPO, check=False)
    unused = [f["subject"] for f in json.loads(done.stdout)["findings"]
              if f["kind"] == "backend_unused_by_frontend"]

    assert "/workbenches/{}/edges" not in unused, unused[:5]
