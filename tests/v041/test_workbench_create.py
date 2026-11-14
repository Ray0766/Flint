"""ENTRY-03：`POST /workbenches` 建工作台——入台那条边今天走不通。

## 改前的实况

对账器实测 `frontend_wants_missing_backend = 1`，**那一条就是这个端点**：

```
POST /workbenches → 框架的 404（没有 code）= 路由未挂
                  → 前端照口径落 not_provided
                  → 入台永远拿不到 ok
```

前端**已经接完**（第 8 批 `NAV-03`：入台成功就把人带去图谱工作台），
所以 `NAV-01` 的可达性尺子把 `/workbenches/[id]` 放进了第三格：
**「路接上了，而那条路今天走不通」**。本卡把那条路打通。

## 幂等按 (user_id, cluster_id) 判，不是按请求体里的 id

用户第二次点「入台」时**不会带着上次的 graph_id**。按请求体判等于不判——
每点一次多出一张空工作台，而他以为自己只建了一张。

这与 `flint/graph/store.py#add_node` 的入台幂等是**同一条纪律的两层**：
那一层管「一张图里同一个热点只有一个节点」，这一层管「一个人对同一个热点只有一张图」。

## `graph_id`，只此一个名字

`NAV-03` 的前端逐字读 `graph_id`（`workbenchTarget()`），而那个名字来自既有路由
`POST /workbenches/{graph_id}/edges`。**NEVER 改前端去迁就另一个字段名**。
"""
from __future__ import annotations

import re
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from contracts_v04.models_v04 import GraphNode
from flint.api.identity import IdentityMissing, IdentityUnknown
from flint.api.workbenches import WorkbenchDeps, create_workbench_app
from flint.graph.store import GraphStore, add_edge

REPO = Path(__file__).resolve().parents[2]
APP_PY = REPO / "flint" / "api" / "app.py"
CARD_ACTIONS = REPO / "web" / "components" / "plaza" / "cardActions.ts"

NOW = datetime(2026, 8, 9, 12, 0, tzinfo=UTC)
OWNER = "wb-owner"
OTHER = "wb-other"
CLUSTER = "c-20260629-088"
MISSING_CLUSTER = "c-nope"


def _stable(seed: str) -> str:
    import hashlib

    return hashlib.blake2b(seed.encode("utf-8"), digest_size=6).hexdigest()


def _client(store: GraphStore | None = None) -> tuple[TestClient, GraphStore]:
    """离线装配：身份与「热点在不在」都注 fixture，**判据面 NEVER 连库**。"""
    kept = store if store is not None else GraphStore()

    async def check_user(header: str | None) -> str:
        if header is None or not header.strip():
            raise IdentityMissing("X-User-Id")
        who = header.strip()
        if who not in (OWNER, OTHER):
            raise IdentityUnknown(who)
        return who

    async def cluster_exists(cluster_id: str) -> bool:
        return cluster_id == CLUSTER

    app = create_workbench_app(WorkbenchDeps(
        store=kept, now=lambda: NOW, check_user=check_user,
        cluster_exists=cluster_exists,
        graph_id_for=lambda u, c: "wb-" + _stable(f"{u}|{c}"),
        node_id_for=lambda g, c: "gn-" + _stable(f"{g}|{c}"),
        node_model=GraphNode))
    return TestClient(app), kept


def _post(client: TestClient, cluster_id: str, who: str | None = OWNER) -> Any:
    headers = {} if who is None else {"x-user-id": who}
    return client.post("/workbenches", json={"seed_cluster_id": cluster_id},
                       headers=headers)


# ───────────────────────── 一、建得出来，且回的是那个名字


def test_creating_a_workbench_returns_a_graph_id() -> None:
    """`NAV-03` 的前端只认 `graph_id`。回别的名字 = 前端拿不到目标，留在原地。"""
    client, _ = _client()

    r = _post(client, CLUSTER)

    assert r.status_code == 201, r.text
    body = r.json()
    assert body["graph_id"], "没回 graph_id"
    assert body["seed_cluster_id"] == CLUSTER
    assert body["created"] is True


def test_the_field_name_matches_what_the_front_end_reads() -> None:
    """**两处对齐**：端点回的名字与前端读的名字逐字相同。

    只判端点回了什么的话，前端改读别的名字这条判据也不会红——
    而那时入台会「成功」却带不走人。
    """
    client, _ = _client()
    body = _post(client, CLUSTER).json()
    front = CARD_ACTIONS.read_text(encoding="utf-8")

    assert "graph_id" in body
    assert 'detail["graph_id"]' in front, "前端读的不是 graph_id 了"


def test_the_seed_cluster_becomes_a_node_in_that_graph() -> None:
    """建出来的图**不是空的**：那个热点已经在里面。

    空图的话，用户被带过去只看到一张白板——他刚点的那个热点去哪儿了？
    """
    client, store = _client()
    graph_id = _post(client, CLUSTER).json()["graph_id"]

    nodes = store.nodes(graph_id)
    assert len(nodes) == 1
    assert nodes[0].source_kind == "cluster"
    assert nodes[0].source_id == CLUSTER


def test_edges_can_be_added_to_the_graph_that_was_just_created() -> None:
    """**建工作台与建边共用一个 store**。

    两个 store 实例的话，建出来的工作台**加不上边**——`add_edge` 的第一件事
    就是查两端节点在不在，而它看的是另一个字典。
    `create_app` 里那一处改动（`graph_store` 变量）正为此。
    """
    client, store = _client()
    graph_id = _post(client, CLUSTER).json()["graph_id"]
    node_id = store.nodes(graph_id)[0].node_id

    from contracts_v04.models_v04 import GraphEdge
    from flint.graph.store import add_node

    other = add_node(store, graph_id=graph_id, node_id="gn-2",
                     source_kind="cluster", source_id="c-other", label="x",
                     position=(1.0, 1.0), now=NOW, model=GraphNode)
    edge = add_edge(store, graph_id=graph_id, edge_id="ge-1",
                    from_node_id=node_id, to_node_id=other.node_id,
                    hypothesis="两个热点指向同一个需求", now=NOW, model=GraphEdge)

    assert edge.from_node_id == node_id


# ───────────────────────── 二、幂等：同一热点重复入台 NEVER 建出第二张


def test_entering_the_same_cluster_twice_lands_on_the_same_graph() -> None:
    """**卡上点名的那条**。第二次点「入台」时用户不会带着上次的 graph_id，
    所以幂等只能按 `(user_id, cluster_id)` 判。
    """
    client, store = _client()

    first = _post(client, CLUSTER).json()
    second = _post(client, CLUSTER).json()

    assert first["graph_id"] == second["graph_id"]
    assert first["created"] is True
    assert second["created"] is False, "第二次也报 created=True——调用方分不出新建与落回"
    assert len(store.nodes(first["graph_id"])) == 1, "同一个热点在图里出现了两次"


def test_the_second_call_answers_200_not_201() -> None:
    """新建 201 / 落回既有 200。

    两次都回 201 的话，「点了两次只出来一张图」这件事在响应里**看不出来**。
    """
    client, _ = _client()

    assert _post(client, CLUSTER).status_code == 201
    assert _post(client, CLUSTER).status_code == 200


def test_two_people_entering_the_same_cluster_get_their_own_graphs() -> None:
    """作用域是**这个人**：同一个热点当然可以出现在两个人各自的图里。

    共用一张的话，另一个人一进来就看到你连的线——那是别人的思考。
    """
    client, _ = _client()

    mine = _post(client, CLUSTER, OWNER).json()["graph_id"]
    theirs = _post(client, CLUSTER, OTHER).json()["graph_id"]

    assert mine != theirs


def test_the_graph_id_is_reproducible_not_random() -> None:
    """id 由内容决定。**随机 id 的幂等只在同一个进程里成立**——
    重启一次，同一个人对同一个热点又会建出一张新的。
    """
    client_a, _ = _client()
    client_b, _ = _client()          # 另一个「进程」：全新的 store

    assert (_post(client_a, CLUSTER).json()["graph_id"]
            == _post(client_b, CLUSTER).json()["graph_id"])


# ───────────────────────── 三、三种拒绝各说各的（AUTH-03）


def test_a_missing_header_is_401_identity_missing() -> None:
    """缺头是**调用方漏了身份**，不是权限问题。"""
    client, _ = _client()

    r = _post(client, CLUSTER, None)

    assert r.status_code == 401
    assert r.json()["code"] == "IDENTITY_MISSING"


def test_an_unknown_identity_is_401_identity_unknown() -> None:
    """两个 401 分开：一个是调用方的 bug，一个是数据。

    同一个状态码下，`code` 是唯一能区分它们的位。
    """
    client, _ = _client()

    r = _post(client, CLUSTER, "nobody")

    assert r.status_code == 401
    assert r.json()["code"] == "IDENTITY_UNKNOWN"


def test_a_missing_cluster_is_404_not_422() -> None:
    """热点不存在**不是请求写错了**，是那个东西不在。

    判成 422 的话，调用方会去检查自己的 JSON——而该改的是那个 id。
    """
    client, _ = _client()

    r = _post(client, MISSING_CLUSTER)

    assert r.status_code == 404
    assert r.json()["code"] == "NOT_FOUND"
    assert MISSING_CLUSTER in r.json()["message"]


def test_an_empty_cluster_id_is_422_not_404() -> None:
    """空的 `seed_cluster_id` 是请求本身不完整——与「那个热点不在」是两件事。"""
    client, _ = _client()

    r = _post(client, "   ")

    assert r.status_code == 422
    assert r.json()["code"] == "VALIDATION_FAILED"


def test_the_three_refusals_never_share_a_code() -> None:
    """**阴性对照**：三种拒绝的 code 两两不同。

    混成一个的话，调用方读到一句通用的「不行」，分不出该加头、该换身份、
    还是该换一个热点 id。
    """
    client, _ = _client()
    codes = {
        _post(client, CLUSTER, None).json()["code"],
        _post(client, CLUSTER, "nobody").json()["code"],
        _post(client, MISSING_CLUSTER).json()["code"],
    }

    assert len(codes) == 3, codes


def test_no_default_identity_is_invented() -> None:
    """`NEVER 返回一个默认身份`——兜一个，所有匿名请求都会以同一个人的名义写数据。"""
    client, store = _client()

    _post(client, CLUSTER, None)

    assert store.nodes("") == []
    for who in (OWNER, OTHER):
        graph_id = "wb-" + _stable(f"{who}|{CLUSTER}")
        assert store.nodes(graph_id) == [], "匿名那一次仍然落了盘"


# ───────────────────────── 四、装配：挂上了才算接线


def test_the_route_is_assembled_into_the_real_app() -> None:
    """**挂上才算接线**。本仓这一批反复撞见的形状是「能力建好了路由没挂」，
    而没挂时前端拿到的是框架那种没有 `code` 的 404——与「这一条不存在」长得一样。
    """
    from flint.api.app import create_app

    app = create_app("postgresql://unused/flint_test")
    routes = {getattr(r, "path", "") for r in app.router.routes}

    assert "/workbenches" in routes, "端点建好了，路由没挂"


def test_the_app_shares_one_graph_store_between_workbench_and_edges() -> None:
    """两处共用一个 store——源码层钉住它。

    运行时那一半在 `test_edges_can_be_added_to_the_graph_that_was_just_created`。
    只判运行时的话，`create_app` 里退回两个实例时这条判据看不见
    （那条用例自己构造 store，不经过 `create_app`）。

    `PERSIST-02` 把装配处的内存件换成了 `PgGraphStore`（迁移 0027 建的三张表），
    所以钉的名字跟着换。**这条纪律换实现之后仍然成立**，只是理由变了：
    改前两个实例是两个互相看不见的进程内字典（建出来的工作台加不上边），
    改后两个实例连的是同一个库、但**各开各的连接**——两个就是两倍连接数。
    """
    raw = APP_PY.read_text(encoding="utf-8")
    # **先把注释剥掉再数**：装配处那两段注释里逐字写着「改前它是 `GraphStore()`」
    # ——那是**记录改动理由**的文字，不是一个实例。不剥的话这条判据量的是
    # 「有没有人解释过这件事」，而解释得越清楚它越红。
    # 本轮第六次撞上「尺子读了注释」，前五次记在 SHELL-01/02、ENTRY-04、FIX-19 的 trace 里。
    code = "\n".join(
        line for line in raw.splitlines() if not line.strip().startswith("#"))

    assert "graph_store = PgGraphStore(dsn=dsn)" in code
    assert code.count("PgGraphStore(") == 1, "又有人 new 了第二个图 store"
    # 内存件 NEVER 再出现在装配处：留一个在这里，等于留着一条
    # 「重启就丢图」的老路，而它与新路长得一模一样。
    assert "GraphStore()" not in code
    assert re.search(r"create_graph_edge_app\(GraphEdgeDeps\(\s*\n\s*store=graph_store",
                     code), "edges 那一族没用同一个 store"
    assert re.search(r"create_workbench_app\(WorkbenchDeps\(\s*\n\s*store=graph_store",
                     code), "建工作台没用同一个 store"


def test_the_missing_endpoint_finding_is_gone_from_the_parity_table() -> None:
    """出口判据之一：对账器的 `frontend_wants_missing_backend` 归零。

    改前那张表里唯一的一条就是 `POST /workbenches`。
    """
    from tools.check_fe_be_parity import parity

    wanted = [f for f in parity(REPO) if f.kind == "frontend_wants_missing_backend"]

    assert wanted == [], [f.subject for f in wanted]


# ───────────────────────── 五、存储面还没有，而这件事要留痕


# ───────────────────────── 单据留痕的判法：**收在一处**（GAUGE-16）
#
# 这三样原来在本文件与另一个判据文件里**各有一份、逐字相同**（各 1499 字符）。
# 两份各自漂移的那天，两张单会按两套规矩判——而它们守的是同一条纪律；
# 更坏的是，修好其中一份的人会以为自己修好了这条纪律。
# 收进 `tests/v041/_sheet_trace.py`（下划线开头、不叫 test_*，pytest 不收集它）。
# 本文件只判单据留痕那一半；孤岛那道闸在 test_main_chain_walk.py（图在那边）。
from tests.v041._sheet_trace import assert_sheet_keeps_its_trace, status_of

SHEET_UNDER_TEST = REPO / "docs" / "blocked" / "GRAPH-HAS-NO-STORAGE-FACE.md"


def test_the_storage_face_story_keeps_its_trace() -> None:
    """存储面那件事**从头到尾留着痕**。

    这张单开的时候，`GraphStore` 是内存件、工作台活不过一次重启——
    那不是端点的实现选择，是两张表还没建。缝留在 `WorkbenchDeps.store`：
    换成 SQL 实现时端点一行都不用改，而 `PERSIST-02` 正是那样换的。

    判据原来钉着「这张单必须 open」。表建好、单被关掉之后它当场变红，
    **而红的原因是活干完了**。改成判留痕：单还在、状态说得出是谁在哪一天关的、
    关闭那一节写得出为什么。缺什么、缝在哪儿那两处点名照旧钉着——
    它们记的是当时的实况，NEVER 因为事情做完了就抹掉。
    """
    state, _day, card = assert_sheet_keeps_its_trace(SHEET_UNDER_TEST)
    text = SHEET_UNDER_TEST.read_text(encoding="utf-8")

    assert state == "closed", f"这张单还开着，而三张表已经建好了：{state}"
    assert card == "PERSIST-02", f"关它的应该是 PERSIST-02，状态行写的是 {card}"
    assert "graph_nodes" in text and "graph_edges" in text, "没点名缺的是哪两张表"
    assert "WorkbenchDeps.store" in text, "没写清缝留在哪儿"


@pytest.mark.parametrize("field", ["store", "cluster_exists", "graph_id_for"])
def test_every_moving_part_is_injectable(field: str) -> None:
    """存储、查簇、算 id 三样都是注进来的——判据面因此**一次库都不连**。

    写死任何一样，这组判据就得起一个 PG 才能跑，而 CI 恒不联网（`S2-7`）。
    """
    assert field in WorkbenchDeps.__dataclass_fields__


def test_a_status_line_that_says_neither_open_nor_closed_goes_red() -> None:
    """**阴性对照**：状态行改成一个既不是 open 也不是 closed 的值 → 判据 MUST 红。

    没有这一条的话，上面那条判据在「状态行烂掉」时的行为无人知晓——
    而一把在坏数据上照样绿的尺子，与一把被注释掉的尺子长得一模一样。

    连**真文件都不动**：把文本改在内存里、写进临时文件。
    改真文件去量一次红，是在盘上留一个随时可能被人当成实况的坏状态。
    """
    text = SHEET_UNDER_TEST.read_text(encoding="utf-8")
    line = next(ln for ln in text.splitlines() if ln.startswith("**状态**"))

    for bogus in ("**状态** 差不多吧 · 2026-08-09 · `X-01`",   # 状态不是三个词之一
                  "**状态** closed · 最近 · `X-01`",           # 日期不是日期
                  "**状态** closed · 2026-08-09"):             # 没说是哪张卡
        with tempfile.TemporaryDirectory() as tmp:
            fake = Path(tmp) / SHEET_UNDER_TEST.name
            fake.write_text(text.replace(line, bogus, 1), encoding="utf-8")
            with pytest.raises(ValueError, match="状态行"):
                assert_sheet_keeps_its_trace(fake)


def test_a_closed_sheet_without_a_closing_section_goes_red() -> None:
    """**阴性对照第四例**：状态行合法、写着 closed，**而没有「## 关闭」那一节**。

    前三例的坏样本全部落在 `status_of` 的 `ValueError` 上——
    「必须有 `## 关闭` 节」与「关闭那一节要点名同一张卡」是两条 `assert`，
    **一次都没被碰到**：把那两条删掉，阴性对照照样绿。这一例与下一例补上它们。

    期望的是 `AssertionError` 而**不是** `ValueError`：两者说的是两件事——
    前者是「这张单没交代清楚」，后者是「这张单的状态行读不出来」。
    合成一个的话，读到红的人不知道该去补一节还是去修一行。
    """
    text = SHEET_UNDER_TEST.read_text(encoding="utf-8")
    assert "## 关闭" in text, "这条对照的前提没了：这张单本来就没有关闭节"
    stripped = text.split("## 关闭", 1)[0]

    with tempfile.TemporaryDirectory() as tmp:
        fake = Path(tmp) / SHEET_UNDER_TEST.name
        fake.write_text(stripped, encoding="utf-8")
        with pytest.raises(AssertionError, match="没写关闭那一节"):
            assert_sheet_keeps_its_trace(fake)


def test_a_closing_section_that_names_another_card_goes_red() -> None:
    """**阴性对照第五例**：有「## 关闭」那一节，**而里面点的是另一张卡**。

    这是三种关法里最像真的那一种：单据看上去交代得齐全，
    只是状态行说 A 关的、正文说 B 关的。不判的话，
    「谁关的」这件事在盘上有两个互相矛盾的答案，而下一个人只会读到其中一个。
    """
    text = SHEET_UNDER_TEST.read_text(encoding="utf-8")
    line = next(ln for ln in text.splitlines() if ln.startswith("**状态**"))
    _state, day, _card = status_of(text)
    bogus = line.split(" · ")[0] + f" · {day} · `NOBODY-99`"

    with tempfile.TemporaryDirectory() as tmp:
        fake = Path(tmp) / SHEET_UNDER_TEST.name
        fake.write_text(text.replace(line, bogus, 1), encoding="utf-8")
        with pytest.raises(AssertionError, match="没点名 NOBODY-99"):
            assert_sheet_keeps_its_trace(fake)
