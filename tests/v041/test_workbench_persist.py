"""PERSIST-02-a：工作台三表建齐，图从内存件换成 SQL 实现。

## 卡面那句「`POST /workbenches` 也没挂」与实况不符——先把这件事钉住

`ENTRY-03` **早就把两条端点建好并装配了**（`flint/api/app.py` 里
`create_workbench_app(...)`）。对账器实跑：

```
frontend_wants_missing_backend   0        ← 卡面写的是 1
frontend_untyped_response        2        ← /workbenches 与 /workbenches/{}/nodes
```

所以**缺的不是挂载，是表**：`workbenches` / `graph_nodes` / `graph_edges`
三张一张都不存在（`DEC-048`），`GraphStore` 是内存件，它自己的文件头写着
「SQL 实现随 E2 的 `graph_nodes` / `graph_edges` 两表接入」。

**入台今天拿得到 `ok`，只是那张工作台活不过一次进程重启。**
这与「拿不到 ok」是两种完全不同的坏——前者用户以为存下了，
下次打开发现没了；后者当场就知道没成。下面第一组判据把这个区别钉住。

## 为什么 `workbenches` 是**第三张**表，而不是「有节点就算有图」

今天「这张图在不在」判的是 `store.nodes(graph_id)` 非空
（`flint/api/workbenches.py:167` 原话「NEVER 见图就建」）。
那个判法在只有两张表时是唯一能用的，但它把两件事合成了一件：

- **图不存在**（没人建过）
- **图存在但空了**（建过，节点被删光）

第二种今天不会发生（没有删节点的路），而它一旦发生，
`POST /workbenches/{id}/nodes` 会回 404「没有这张工作台」——
**而那张工作台明明在**。所以图的存在性落到自己的表上，
`graph_id` 是主键，谁建的、由哪个热点起的、什么时候建的各占一列。

## 幂等的两层各自有判据

`graph_id` 由 `(user_id, cluster_id)` **决定**（`create_app` 注的 `graph_id_for`），
所以同一个人对同一个热点第二次入台落回同一张图；
`add_node` 再保证那张图里同一个热点只有一个节点。
**两层都换成 SQL 之后要重新量一次**——upsert 写错就是第二张图或者第二个节点。
"""
from __future__ import annotations

import asyncio
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import asyncpg
import pytest

pytestmark = pytest.mark.compose

REPO = Path(__file__).resolve().parents[2]
DSN = os.environ.get(
    "FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")
NOW = datetime(2026, 8, 9, 12, 0, 0, tzinfo=UTC)
TABLES = ("workbenches", "graph_nodes", "graph_edges")
GRAPH = "wb-persist02"
OWNER = "persist02-me"
CLUSTER = "persist02-cluster"


def run(coro: Any) -> Any:
    return asyncio.run(coro)


async def _conn() -> asyncpg.Connection:
    return await asyncpg.connect(DSN)


async def _wipe() -> None:
    conn = await _conn()
    try:
        # 先边后节点再工作台：外键方向决定删除顺序。
        for table in ("graph_edges", "graph_nodes", "workbenches"):
            await conn.execute(f"DELETE FROM {table}")
    finally:
        await conn.close()


#: 端点判据用到的两个身份。**`check_user` 会去 `users` 表里查**，
#: 编一个 id 会被它拦成 401——那与本卡要量的东西无关，只会让判据红得没有意义。
PEOPLE = ("demo-user", "self")


async def _seed_people() -> None:
    """种两个身份。幂等，且**不在收尾时删**。

    不删的理由：`demo-user` 是这套栈自己用的那个演示身份（`harness/demo_server.py`
    注的就是它），别的判据也在用。收尾时删掉的话，谁先跑谁把后面的人的前提拆了——
    而那种红看起来像是被删的那张卡出的问题。
    """
    conn = await _conn()
    try:
        for who in PEOPLE:
            await conn.execute(
                "INSERT INTO users (user_id, email, display_name, created_at) "
                "VALUES ($1, $2, $1, now()) ON CONFLICT (user_id) DO NOTHING",
                who, f"{who}@persist02.invalid")
    finally:
        await conn.close()


@pytest.fixture(autouse=True)
def _clean() -> Any:
    run(_seed_people())
    run(_wipe())
    yield
    run(_wipe())


def _store() -> Any:
    from flint.graph.pgstore import PgGraphStore

    return PgGraphStore(dsn=DSN)


def _node_model() -> Any:
    from flint.api.app import _graph_node_model

    return _graph_node_model()


def _edge_model() -> Any:
    """边的类型从 `pgstore` 取——它与 `flint/api/app.py#_graph_node_model`
    是**同一条取法**（延迟 import additive 层）。NEVER 在判据里新定义一个。"""
    from flint.graph.pgstore import _edge_model

    return _edge_model()


# ───────────────────────── 一、三张表真的建出来了


def test_the_three_tables_exist_now() -> None:
    """实查 `pg_tables`，不是查迁移文件（写了 `create_table` 没跑过也能骗过后者）。"""
    async def _probe() -> list[str]:
        conn = await _conn()
        try:
            rows = await conn.fetch(
                "SELECT tablename FROM pg_tables WHERE schemaname='public' "
                "AND tablename = ANY($1::text[])", list(TABLES))
        finally:
            await conn.close()
        return sorted(r["tablename"] for r in rows)

    assert run(_probe()) == sorted(TABLES)


def test_the_migration_number_is_0027_and_chains_onto_0026() -> None:
    """本批的迁移号从 0023 起顺序编，**NEVER 跳号也 NEVER 撞号**。

    这条判据本身被改过一次号，值得记下来：它原来写的是「0024 接 0023」——
    那是**本卡先占号、后面的卡绕着它走**的写法。`PERSIST-03` 那一轮为此留了个
    0024 的空号，三把尺子当场变红且**它们是对的**（`docs/trace/PERSIST-03.md` §2）。
    改法是「**接盘上当时最高的那一号**」：`templates` 补进 0024、
    `cluster_verdicts` 0025、`prefs.theme` 0026，本卡因此是 **0027**。

    留号的坏处不是名字不好看：alembic 按 `down_revision` 串成一条链，
    盘上缺一环时 `upgrade head` 会停在缺口前，而**它不报错**——
    库停在半路，下一个人看到的是「迁移跑过了但表没有」。
    """
    import re

    versions = sorted(
        (REPO / "migrations" / "versions").glob("[0-9][0-9][0-9][0-9]_*.py"))
    numbers = [int(p.name[:4]) for p in versions]
    mine = [p for p in versions if p.name.startswith("0027_")]

    assert numbers == list(range(1, len(numbers) + 1)), f"号不连续：{numbers}"
    assert len(mine) == 1, "0027 不在盘上，或者有两个"
    text = mine[0].read_text(encoding="utf-8")
    assert re.search(r'down_revision\s*[:=]\s*"0026"', text), "没接在 0026 后面"
    assert re.search(r'revision\s*[:=]\s*"0027"', text)


def test_project_id_is_nullable_and_says_what_null_means() -> None:
    """`DEC-051`：`workbenches.project_id` 可空，且**语义逐字写在迁移注释里**。

    为什么非要一句注释：这一列今天**没有一个写入方**（甲这一族不带项目）。
    一列全是 `NULL` 而没人说得清 `NULL` 是什么意思的话，
    下一个人会做两件事里的一件——把它当「没做完」去补一个编出来的项目 id，
    或者把它当「不需要」直接删掉。两件都是错的：
    到 K6 交互稿落地时它要被一次 `UPDATE` 填上，**而不是被一次迁移回填**。
    """
    text = (REPO / "migrations" / "versions" / "0027_workbench_graph.py").read_text(
        encoding="utf-8")

    assert "NULL =「这张图还没有归属任何项目」" in text
    assert "NEVER 往这一列写一个编出来的项目 id" in text

    async def _nullable() -> str:
        conn = await _conn()
        try:
            return str(await conn.fetchval(
                "SELECT is_nullable FROM information_schema.columns "
                "WHERE table_name='workbenches' AND column_name='project_id'"))
        finally:
            await conn.close()

    assert run(_nullable()) == "YES", "project_id 建成非空了——今天没有写入方，非空建不出行"


def test_a_dangling_node_cannot_be_stored_without_its_workbench() -> None:
    """外键：节点 NEVER 挂在一张不存在的工作台上。

    没有这条约束的话，`graph_nodes` 里会攒下一批**孤儿节点**——
    它们在任何一张图里都读不到，却占着 `node_id`，
    而下一次同名节点入台时会撞主键，报的错与「重复入台」一模一样。
    """
    async def _go() -> Any:
        conn = await _conn()
        try:
            with pytest.raises(asyncpg.ForeignKeyViolationError):
                await conn.execute(
                    "INSERT INTO graph_nodes (node_id, graph_id, source_kind, "
                    "source_id, label, position_x, position_y, created_at) "
                    "VALUES ('n-orphan', 'wb-nonexistent', 'cluster', 'c', 'c', "
                    "0, 0, $1)", NOW)
        finally:
            await conn.close()

    run(_go())


# ───────────────────────── 二、图存得住


def test_a_workbench_survives_a_new_store_object() -> None:
    """建一张图、换一个 store 对象——**它还在**。内存件在这一条上必红。"""
    _store().put_workbench(
        graph_id=GRAPH, owner_id=OWNER, seed_cluster_id=CLUSTER, now=NOW)

    row = _store().workbench(GRAPH)

    assert row is not None
    assert row.graph_id == GRAPH
    assert row.owner_id == OWNER
    assert row.seed_cluster_id == CLUSTER


def test_an_empty_workbench_is_still_a_workbench() -> None:
    """**「图不存在」与「图存在但空了」NEVER 合并**（见模块 docstring）。

    改前这两件事都表现成 `nodes(graph_id) == []`。
    有了 `workbenches` 表之后，前者 `workbench()` 回 `None`，后者回一行。
    """
    _store().put_workbench(
        graph_id=GRAPH, owner_id=OWNER, seed_cluster_id=CLUSTER, now=NOW)

    assert _store().nodes(GRAPH) == []
    assert _store().workbench(GRAPH) is not None
    assert _store().workbench("wb-never-built") is None


def test_nodes_and_edges_survive_a_new_store_object() -> None:
    """节点与边都跨对象还在，且**边只属于自己那张图**。"""
    from flint.graph.store import add_edge, add_node

    store = _store()
    store.put_workbench(
        graph_id=GRAPH, owner_id=OWNER, seed_cluster_id=CLUSTER, now=NOW)
    add_node(store, graph_id=GRAPH, node_id="n1", source_kind="cluster",
             source_id=CLUSTER, label="热点一", position=(1.0, 2.0),
             now=NOW, model=_node_model())
    add_node(store, graph_id=GRAPH, node_id="n2", source_kind="cluster",
             source_id="other-cluster", label="热点二", position=(3.0, 4.0),
             now=NOW, model=_node_model())
    add_edge(store, graph_id=GRAPH, edge_id="e1", from_node_id="n1",
             to_node_id="n2", hypothesis="两个热点撑同一个假设",
             now=NOW, model=_edge_model())

    fresh = _store()
    nodes = fresh.nodes(GRAPH)
    edges = fresh.edges(GRAPH)

    assert [n.node_id for n in nodes] == ["n1", "n2"]
    assert nodes[0].position == (1.0, 2.0), "坐标没存住——画布会把节点全堆在原点"
    assert nodes[0].label == "热点一"
    assert [e.edge_id for e in edges] == ["e1"]
    assert edges[0].hypothesis == "两个热点撑同一个假设"
    assert fresh.edges("wb-someone-else") == []


def test_a_dangling_edge_is_still_refused_through_sql() -> None:
    """悬空边 NEVER 入库（`add_edge` 的既有口径）——换成 SQL 之后再量一次。

    这一条既有判据在内存件上量过。SQL 实现里它靠的是**同一个**
    `add_edge`（本卡没有重写任何域函数），所以这条判据同时也是
    「域逻辑真的被复用了」的证据。
    """
    from flint.graph.store import add_edge

    store = _store()
    store.put_workbench(
        graph_id=GRAPH, owner_id=OWNER, seed_cluster_id=CLUSTER, now=NOW)

    with pytest.raises(ValueError, match="悬空边"):
        add_edge(store, graph_id=GRAPH, edge_id="e1", from_node_id="nope",
                 to_node_id="nope2", hypothesis="h", now=NOW,
                 model=_edge_model())


# ───────────────────────── 三、幂等的两层


def test_putting_the_same_workbench_twice_never_makes_a_second_one() -> None:
    """同一个人对同一个热点第二次入台 → **同一张图**，NEVER 多出一张。"""
    for _ in range(2):
        _store().put_workbench(
            graph_id=GRAPH, owner_id=OWNER, seed_cluster_id=CLUSTER, now=NOW)

    async def _count() -> int:
        conn = await _conn()
        try:
            return int(await conn.fetchval("SELECT count(*) FROM workbenches"))
        finally:
            await conn.close()

    assert run(_count()) == 1


def test_adding_the_same_cluster_twice_never_makes_a_second_node() -> None:
    """`add_node` 按 `(graph_id, source_kind, source_id)` 幂等——SQL 上再量一次。"""
    from flint.graph.store import add_node

    store = _store()
    store.put_workbench(
        graph_id=GRAPH, owner_id=OWNER, seed_cluster_id=CLUSTER, now=NOW)
    for node_id in ("n1", "n2-different-id"):
        add_node(store, graph_id=GRAPH, node_id=node_id, source_kind="cluster",
                 source_id=CLUSTER, label="同一个热点", position=(0.0, 0.0),
                 now=NOW, model=_node_model())

    assert [n.node_id for n in _store().nodes(GRAPH)] == ["n1"]


# ───────────────────────── 四、端到端：入台走真代码，落真表


def _client() -> Any:
    from fastapi.testclient import TestClient

    from flint.api.app import create_app

    return TestClient(create_app(dsn=DSN), raise_server_exceptions=False)


def _seed_cluster() -> str:
    """种一个真簇——`cluster_exists` 会去库里查，编一个 id 会被它 404 挡住。"""
    async def _go() -> str:
        conn = await _conn()
        try:
            cat = await conn.fetchval("SELECT category_id FROM categories LIMIT 1")
            await conn.execute(
                "INSERT INTO clusters (cluster_id, canonical_name, category_id, "
                "centroid, status, first_seen, last_active) "
                "VALUES ($1, $2, $3, $4, 'active', $5, $5) "
                "ON CONFLICT (cluster_id) DO NOTHING",
                CLUSTER, "入台用的热点", cat, "[" + ",".join(["0"] * 1024) + "]",
                NOW.date())
        finally:
            await conn.close()
        return CLUSTER

    return run(_go())


def test_adding_to_the_workbench_through_the_endpoint_lands_in_the_tables() -> None:
    """**入台今天拿得到 `ok`，本卡治的是那张图活不过重启**（见模块 docstring）。

    只断言端点回 201 的话，一个把图塞进进程内字典的实现也能全绿——
    所以这里查的是**库里那三张表**。
    """
    _seed_cluster()
    client = _client()

    posted = client.post("/workbenches", json={"seed_cluster_id": CLUSTER},
                         headers={"x-user-id": "demo-user"})

    assert posted.status_code == 201, posted.text
    graph_id = posted.json()["graph_id"]
    assert graph_id, "没回 graph_id——NAV-03 的前端只认这一个名字"

    async def _rows() -> tuple[int, int]:
        conn = await _conn()
        try:
            return (
                int(await conn.fetchval(
                    "SELECT count(*) FROM workbenches WHERE graph_id = $1", graph_id)),
                int(await conn.fetchval(
                    "SELECT count(*) FROM graph_nodes WHERE graph_id = $1", graph_id)),
            )
        finally:
            await conn.close()

    benches, nodes = run(_rows())
    assert benches == 1, "workbenches 表里没有这张图"
    assert nodes == 1, "入台的那个热点没有落成节点"


def test_a_second_add_returns_the_same_graph_and_says_it_is_not_new() -> None:
    """重复入台：**同一个 graph_id**、`created=False`、库里仍然只有一张图。

    `created` 让调用方读得出这次是新建还是落回既有的那张图——
    没有它的话，「点了两次只出来一张图」这件事在响应里看不出来。
    """
    _seed_cluster()
    client = _client()
    head = {"x-user-id": "demo-user"}

    first = client.post("/workbenches", json={"seed_cluster_id": CLUSTER},
                        headers=head).json()
    second = client.post("/workbenches", json={"seed_cluster_id": CLUSTER},
                         headers=head)

    assert second.status_code == 200, second.text
    assert second.json()["graph_id"] == first["graph_id"]
    assert first["created"] is True
    assert second.json()["created"] is False


def test_two_people_adding_the_same_cluster_get_two_different_graphs() -> None:
    """作用域是**这个人**：同一个热点当然可以出现在两个人各自的图里。

    幂等键少了 `user_id` 的话，第二个人入台会落进第一个人的图——
    而那张图里可能已经有别人的思考。
    """
    _seed_cluster()
    client = _client()

    mine = client.post("/workbenches", json={"seed_cluster_id": CLUSTER},
                       headers={"x-user-id": "demo-user"}).json()
    theirs = client.post("/workbenches", json={"seed_cluster_id": CLUSTER},
                         headers={"x-user-id": "self"})

    assert theirs.status_code in (200, 201), theirs.text
    assert theirs.json()["graph_id"] != mine["graph_id"]


def test_the_workbench_is_still_there_for_a_brand_new_app() -> None:
    """**本卡的产品**：换一个 app 实例（= 进程重启的等价物），那张图还在。

    改前它活在 `create_app` 里那一个 `GraphStore()` 实例的字典里，
    重启即消失——而用户点过「入台」，他以为存下了。
    """
    _seed_cluster()
    created = _client().post("/workbenches", json={"seed_cluster_id": CLUSTER},
                             headers={"x-user-id": "demo-user"}).json()

    again = _client().post("/workbenches", json={"seed_cluster_id": CLUSTER},
                           headers={"x-user-id": "demo-user"})

    assert again.status_code == 200, "换个 app 就变成新建了——图没存住"
    assert again.json()["created"] is False
    assert again.json()["graph_id"] == created["graph_id"]


def test_workbench_and_edges_still_share_one_store() -> None:
    """建工作台与建边**共用同一个 store**（`ENTRY-03` 的既有纪律）。

    改前两处各 new 一个的话，建出来的工作台加不上边。
    换成 SQL 实现之后这条纪律**在类型上不再重要**（两个实例连的是同一个库），
    但判据留着：它量的是「装配处只造一个」，而那仍然是对的做法——
    每个实例都自己开连接，两个实例就是两倍连接数。
    """
    import inspect

    from flint.api import app as app_module

    source = inspect.getsource(app_module.create_app)

    assert source.count("PgGraphStore(") == 1, "又有人 new 了第二个图 store"


# ───────────────────────── 五、PERSIST-02-b：那张图今天打得开

# 卡面 acceptance④：「入台成功后 `/workbenches/[id]` **真能打开并看到刚入台的那个
# 热点**——判据打真栈走一遍，**NEVER 只断言端点回 200**」。
#
# 改前 `web/app/workbenches/[id]/page.tsx` 里写死 `const graph = null`，
# 文件头自述「端点建好之后，这里只要把 graph 从 null 换成取回来的那张图」。
# 所以 -b 是三件事，缺一件那一屏仍然是空的：
# **建 `GET /workbenches/{id}`** → **前端有类型地取它** → **那一屏渲染它**。


def test_getting_a_workbench_returns_the_cluster_that_was_just_added() -> None:
    """建端点：入台之后取回来的那张图里，**有刚入台的那个热点**。"""
    _seed_cluster()
    client = _client()
    head = {"x-user-id": "demo-user"}

    graph_id = client.post("/workbenches", json={"seed_cluster_id": CLUSTER},
                           headers=head).json()["graph_id"]
    got = client.get(f"/workbenches/{graph_id}", headers=head)

    assert got.status_code == 200, got.text
    body = got.json()
    assert body["graph_id"] == graph_id
    assert body["seed_cluster_id"] == CLUSTER
    # **看到的是那个热点**，不是一张空图回了 200。
    assert [n["source_id"] for n in body["nodes"]] == [CLUSTER]
    assert body["edges"] == []


def test_getting_a_workbench_that_was_never_built_is_a_404_with_a_code() -> None:
    """没有这张图 → 404 **带 `code`**。

    框架那种没有 `code` 的 404 与「这张图不在」是两件事：前者是路由没挂，
    调用方该去问后端；后者是 id 不对，调用方该去问用户。
    前端的四态口径（`cardActions.ts`）**逐字按有没有 `code` 分流**。
    """
    got = _client().get("/workbenches/wb-never-built",
                        headers={"x-user-id": "demo-user"})

    assert got.status_code == 404
    assert got.json()["code"] == "NOT_FOUND"


def test_a_workbench_is_never_readable_by_someone_else() -> None:
    """别人的图 **NEVER** 读得到。

    这一条不是补一档权限，是**幂等键的作用域在读路径上也成立**：
    `graph_id` 由 `(user_id, cluster_id)` 算出来，谁都能算——
    知道对方的 user_id 就能算出他那张图的 id。
    读路径不比一次归属的话，那个 id 就是一把公开的钥匙。
    """
    _seed_cluster()
    client = _client()

    mine = client.post("/workbenches", json={"seed_cluster_id": CLUSTER},
                       headers={"x-user-id": "demo-user"}).json()["graph_id"]
    theirs = client.get(f"/workbenches/{mine}", headers={"x-user-id": "self"})

    # 404 而不是 403：**NEVER 用状态码告诉别人「这张图存在」**。
    assert theirs.status_code == 404, theirs.text


def test_the_screen_stopped_hardcoding_an_empty_graph() -> None:
    """那一屏 NEVER 再写死 `graph = null`——写死的话端点建好了屏上仍然是空的。"""
    page = (REPO / "web" / "app" / "workbenches" / "[id]" / "page.tsx").read_text(
        encoding="utf-8")
    body = page[page.rindex("return ("):]
    code = "\n".join(
        line for line in page.splitlines() if not line.strip().startswith("//"))

    assert "const graph: WorkbenchGraph | null = null" not in code
    assert "fetchWorkbench" in code, "那一屏没有去取这张图"
    assert "<GraphWorkbench" in body


def test_the_two_workbench_responses_are_typed_now() -> None:
    """对账器的 `frontend_untyped_response`：`/workbenches` 那两条**今天有类型了**。

    卡面写的 `frontend_wants_missing_backend = 1` 与实况不符（实测 0，
    `ENTRY-03` 早就挂了）——真正红着的是这两条**没类型**。
    owner 2026-08-09 已按实测改口径，这条判据钉住改后的那个数。
    """
    import json as _json
    import subprocess

    out = subprocess.run(
        [sys.executable,
         str(REPO / "tools" / "check_fe_be_parity.py"), "--json"],
        capture_output=True, text=True, encoding="utf-8", cwd=REPO,
        check=False)  # 尺子红不红由下面那句断言说了算，不由退出码
    report = _json.loads(out.stdout)
    untyped = [p for p in report.get("frontend_untyped_response", [])
               if "/workbenches" in str(p)]

    assert untyped == [], f"还有没类型的工作台响应：{untyped}"
