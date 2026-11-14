"""ENTRY-03：工作台写族——建工作台（`POST /workbenches`）+ 入台（`POST /workbenches/{id}/nodes`）。

## 治的病

工单 §2 说对账器那唯一一条是 `POST /workbenches`。**实测不是**——
那一条是 **`POST /workbenches/{id}/nodes`**（`ShareMenu.tsx` 在调它）。
两条都缺，只是只有后者被对账器数到：前者的调用写在 `cardActions.ts` 里，
而那份表把**跳转与调用**分开数（`_NAV`，第 8 批 `FIX-16` 建的）。

所以本模块建的是**两条**，缺一条这一族都算没接通：

| 端点 | 谁在调 | 实测 |
|---|---|---|
| `POST /workbenches` | `cardActions.ts#addToWorkbench`（广场三动作里的「入台」） | 框架 404 |
| `POST /workbenches/{id}/nodes` | `ShareMenu.tsx#addToWorkbench`（分享菜单里的「一键入台」） | 框架 404 |

前端两处**都已经接完**（`NAV-03`：入台成功就把人带去图谱工作台），而实测回的是
**框架的 404**（没有 `code`）→ 前端照口径落 `not_provided` → **入台永远拿不到 `ok`**。
`NAV-01` 的可达性尺子为此专门长出了第三格：「路接上了，而那条路今天走不通」。

## 两条路 NEVER 分叉出两套幂等键

`ShareMenu` 的文件头写过这件事：另开一条的坏处不是多写代码，而是
**幂等键会分叉**——同一个热点从广场入台一次、从菜单入台一次，
画布上会出现两张一模一样的卡片，而用户以为那是两个热点。
所以两条端点**共用 `add_node`**（它按 `(graph_id, source_kind, source_id)` 幂等）。

## 回什么名字：`graph_id`，只此一个

`NAV-03` 的前端只认 `graph_id`（`workbenchTarget()` 逐字读它），
而那个名字来自既有路由 `POST /workbenches/{graph_id}/edges`。
**NEVER 改前端去迁就一个别的字段名**：改名字省不了事，只是把同一件事的两个说法
留在两个地方，服务端哪天改口，前端会安静地跳到另一处。

## 幂等按 (owner, seed_cluster_id) 判

「同一个热点重复入台」应当回到**同一张图**，而不是每点一次多出一张空工作台。
按请求体里的 id 判是不够的：用户第二次点「入台」时不会带着上次的 graph_id。

作用域是**这个人**：同一个热点当然可以出现在两个人各自的图里。
这与 `flint/graph/store.py#add_node` 的入台幂等（按 `(graph_id, source_kind, source_id)`）
是**同一条纪律的两层**——那一层管「一张图里同一个热点只有一个节点」，
这一层管「一个人对同一个热点只有一张图」。

## 三种拒绝各说各的（AUTH-03）

缺头 401 `IDENTITY_MISSING` · 身份不存在 401 `IDENTITY_UNKNOWN` ·
热点不存在 404 `NOT_FOUND`。**NEVER 混成一个**：前两种是「你是谁」的问题，
第三种是「你要的东西在不在」的问题，调用方要做的事完全不同。

`403` 这一档本端点**没有**：建自己的工作台不需要任何人给权限。
硬凑一档出来会让读代码的人以为这里有一套角色，而它并不存在。

## 存储面：PERSIST-02 已落库

改前 `GraphStore` 是内存件，**工作台活不过一次进程重启**——而用户点过「入台」，
他以为存下了。`PERSIST-02` 建了三张表（迁移 0027）并把 `create_app` 注进来的那个
对象换成 `PgGraphStore`。本模块**依赖的仍然是那个面**（`GraphStoreLike`），
换实现时存储写法一行没改；单据 `GRAPH-HAS-NO-STORAGE-FACE.md` 由那张卡关掉。

`create_app` 里注的那一个实例**与 edges 端点共用**——换成 SQL 之后两个实例连的
是同一个库，但仍然只造一个：每个实例各开各的连接，两个就是两倍连接数。

## 为什么每次碰 store 都过一次 `run_in_threadpool`

`GraphStoreLike` 的方法是**同步**的（域函数同步调它们），而本模块的处理函数是
`async def`（`check_user` / `cluster_exists` 是异步的，改不掉）。
`PgGraphStore` 底下走 `flint/db/sync_bridge.run_sync`，那个函数**在已经跑在事件
循环上时会当场抛** `BlockingCallOnEventLoop`——这是 `PERSIST-01` 刻意立的护栏，
它拦的是「在事件循环上阻塞住整个进程」。

本卡实测撞上了它（六条端点判据一起 500）。**NEVER 把那道护栏拆掉**：
它拦的是真问题。正确的做法是把同步调用挪出循环——`run_in_threadpool` 干的就是这件事，
与 `flint/api/favorites.py` 那一族用 `def` 处理函数（FastAPI 自动丢进线程池）
是同一条路的两种写法。
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from functools import partial
from typing import Any

from fastapi import FastAPI, Header
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from flint.api.identity import install_identity_handlers
from flint.api.schemas import ErrorBody, ErrorCode
from flint.graph.store import GraphStoreLike, add_node

#: 入台节点的来源类型。热点 = `cluster`（与 `add_node` 的 `source_kind` 同一套词）。
SOURCE_KIND = "cluster"


@dataclass
class WorkbenchDeps:
    store: GraphStoreLike
    now: Callable[[], datetime]
    #: `X-User-Id 的值 -> user_id`；缺头 / 查不到各抛各的（`flint/api/identity.py`）。
    check_user: Callable[[str | None], Awaitable[str]]
    #: 这个热点在不在。**NEVER 省掉**：拿一个不存在的簇建出来的工作台
    #: 打开就是空的，而用户会以为是自己的数据丢了。
    cluster_exists: Callable[[str], Awaitable[bool]]
    #: `(user_id, cluster_id) -> graph_id`。注入是为了让 SQL 实现接进来时
    #: 不必改本模块——今天的内存实现见 `create_app`。
    graph_id_for: Callable[[str, str], str]
    node_id_for: Callable[[str, str], str]
    node_model: Any


class WorkbenchIn(BaseModel):
    seed_cluster_id: str


class NodeIn(BaseModel):
    """入台一个既有实体。`source_kind` 与 `add_node` 的那一套词同源。"""

    source_kind: str
    source_id: str
    label: str = ""


def _error(status: int, code: ErrorCode, message: str) -> JSONResponse:
    body = ErrorBody(code=code, message=message, detail=None)
    return JSONResponse(status_code=status, content=body.model_dump(exclude_none=True))


def create_workbench_app(deps: WorkbenchDeps) -> FastAPI:
    app = FastAPI(title="flint-workbenches-api")
    install_identity_handlers(app)

    @app.post("/workbenches")
    async def create_workbench(
        payload: WorkbenchIn, x_user_id: str | None = Header(default=None),
    ) -> Response:
        user_id = await deps.check_user(x_user_id)

        cluster_id = payload.seed_cluster_id.strip()
        if not cluster_id:
            return _error(422, "VALIDATION_FAILED",
                          "seed_cluster_id 是空的——入台总得说清带哪个热点进去。")
        if not await deps.cluster_exists(cluster_id):
            # 404 而不是 422：这不是请求写错了，是那个热点不在。
            return _error(404, "NOT_FOUND", f"没有这个热点：{cluster_id}")

        graph_id = deps.graph_id_for(user_id, cluster_id)
        # **幂等的那一半在这里**：graph_id 由 (user_id, cluster_id) 决定，
        # 所以第二次入台落回同一张图；`add_node` 再保证那张图里节点也不重复。
        #
        # PERSIST-02 改前这一句是 `not deps.store.nodes(graph_id)`——
        # 拿「有没有节点」当「这张图在不在」。三张表建齐之后图有了自己的一行，
        # 问的就是那一行：**「图不存在」与「图存在但空了」NEVER 再合成一件**。
        created = await run_in_threadpool(deps.store.workbench, graph_id) is None
        # 建图这一步幂等（`put_workbench` 同 graph_id 什么都不做），
        # 所以第二次点击 NEVER 改写这张图的来历（谁建的、由哪个热点起的）。
        await run_in_threadpool(partial(
            deps.store.put_workbench, graph_id=graph_id, owner_id=user_id,
            seed_cluster_id=cluster_id, now=deps.now()))
        await run_in_threadpool(partial(
            add_node, deps.store, graph_id=graph_id,
            node_id=deps.node_id_for(graph_id, cluster_id),
            source_kind=SOURCE_KIND, source_id=cluster_id,
            label=cluster_id, position=(0.0, 0.0),
            now=deps.now(), model=deps.node_model,
        ))
        return JSONResponse(
            status_code=201 if created else 200,
            # `created` 让调用方**读得出**这次是新建还是落回既有的那张图。
            # 前端今天不用它（两种都是 ok，都该把人带过去），
            # 而没有它的话，「点了两次只出来一张图」这件事在响应里看不出来。
            content={"graph_id": graph_id, "seed_cluster_id": cluster_id,
                     "created": created},
        )

    @app.get("/workbenches/{graph_id}")
    async def read_workbench(
        graph_id: str, x_user_id: str | None = Header(default=None),
    ) -> Response:
        """PERSIST-02-b：把那张图取回来。

        改前 `web/app/workbenches/[id]/page.tsx` 里写死 `const graph = null`，
        文件头自述「端点建好之后，这里只要把 graph 从 null 换成取回来的那张图」——
        **这就是那个端点**。没有它的话，入台成功之后跳过去看到的是一张空画布，
        而用户刚刚才点过「入台」。

        ## 别人的图回 404 而不是 403

        `graph_id` 由 `(user_id, cluster_id)` **算出来**，谁都能算——
        知道对方的 user_id 就能算出他那张图的 id。所以读路径必须比一次归属，
        否则那个 id 就是一把公开的钥匙。

        而回 403 等于**用状态码告诉对方「这张图存在」**：
        403 与 404 一对照，谁有哪张图就被数出来了。两种都回 404，问不出东西。
        """
        user_id = await deps.check_user(x_user_id)

        bench = await run_in_threadpool(deps.store.workbench, graph_id)
        if bench is None or bench.owner_id != user_id:
            return _error(404, "NOT_FOUND", f"没有这张工作台：{graph_id}")

        nodes = await run_in_threadpool(deps.store.nodes, graph_id)
        edges = await run_in_threadpool(deps.store.edges, graph_id)
        return JSONResponse(status_code=200, content={
            "graph_id": bench.graph_id,
            "seed_cluster_id": bench.seed_cluster_id,
            "created_at": bench.created_at.isoformat(),
            # `project_id` 照原样交出去，NEVER 在这里把 None 变成空串或者编一个：
            # `null` 有确定的意思——「这张图还没有归属任何项目」（`DEC-051`）。
            "project_id": bench.project_id,
            "nodes": [{
                "node_id": n.node_id, "source_kind": n.source_kind,
                "source_id": n.source_id, "label": n.label,
                "position": list(n.position), "primary": n.primary,
            } for n in nodes],
            "edges": [{
                "edge_id": e.edge_id, "from_node_id": e.from_node_id,
                "to_node_id": e.to_node_id, "hypothesis": e.hypothesis,
            } for e in edges],
        })

    @app.post("/workbenches/{graph_id}/nodes")
    async def add_workbench_node(
        graph_id: str, payload: NodeIn, x_user_id: str | None = Header(default=None),
    ) -> Response:
        await deps.check_user(x_user_id)

        source_id = payload.source_id.strip()
        if not source_id or not payload.source_kind.strip():
            return _error(422, "VALIDATION_FAILED",
                          "source_kind 与 source_id 都要给——入台总得说清带哪个东西进去。")
        # 这张图在不在。**NEVER 见图就建**：往一个不存在的 graph_id 里塞节点，
        # 等于用一次 POST 凭空造出一张图，而调用方那边的 id 多半是打错的。
        #
        # PERSIST-02 改前问的是「有没有节点」。那个判法会在一张**建过但空了**的图上
        # 回 404「没有这张工作台」——而那张工作台明明在。现在问的是它自己那一行。
        if await run_in_threadpool(deps.store.workbench, graph_id) is None:
            return _error(404, "NOT_FOUND", f"没有这张工作台：{graph_id}")

        known = {n.node_id
                 for n in await run_in_threadpool(deps.store.nodes, graph_id)}
        node = await run_in_threadpool(partial(
            add_node, deps.store, graph_id=graph_id,
            node_id=deps.node_id_for(graph_id, source_id),
            source_kind=payload.source_kind.strip(), source_id=source_id,
            label=payload.label.strip() or source_id, position=(0.0, 0.0),
            now=deps.now(), model=deps.node_model,
        ))
        # `node_id` **由后端给**（`ShareMenu` 文件头的原话：前端 NEVER 自己编一个——
        # 编出来的 id 与库里那条对不上，后续对这个节点的任何操作都会落空）。
        return JSONResponse(
            status_code=201 if node.node_id not in known else 200,
            content={"node_id": node.node_id, "graph_id": graph_id,
                     "created": node.node_id not in known},
        )

    return app
