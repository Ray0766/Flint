"""FastAPI 边界层：把 `flint/api/` 的全部路由族装配进**一个**应用（WIRE-01）。

## 本文件到 WIRE-01 之前是什么样

22 行、一条路由（`/categories`，M1-022 起步件）。其余 **51 条端点写好了、
测试全绿、却挂不上任何应用**——前端调不到。

**为什么它藏了一整批**：每张 BE 卡的测试都拿自己的 `create_*_app` 造
`TestClient` 跑。**造得出来 ≠ 挂上了。**

## 装配的三条纪律

1. **重复注册要 raise，NEVER 静默遮蔽。** FastAPI 对同一 method+path 注册两次
   不报错——先注册的先匹配，后一个永远收不到请求。已知的那一处登记在
   `KNOWN_COLLISIONS` 里，写明谁赢、谁被遮、为什么、挂哪张单；
   **未登记的冲突直接 raise**。
2. **建应用不连库。** 这里只组装可调用对象，一次连接都不发；库不可达时应用
   照样建得出来，否则冒烟脚本根本起不来。
3. **没有后端的族，走模块自己的「没查过」缝，NEVER 编一个空结果。** 见下节。

## 「没配后端」与「查过了、是空的」NEVER 挤进同一个表示

`BE-01~11` 建的十一族里，有几族的 store 是**内存件**（`dict` / `set`，无 dsn），
而迁移里 34 张表**没有** users / memberships / favorites / prefs / share_links /
templates 任何一张——它们**没有持久层**。

给这些族塞一个空的内存 store，端点会回「你没有收藏」「没有账户记录」——
那是一句**系统没有依据说出口的话**：它查的是一个刚建出来、进程重启就没了的字典。
用户会把它读成「查过了，确实没有」。

所以这里走模块**自己设计好的那条缝**：

| 模块 | 缝 | 效果 |
|---|---|---|
| `account` | `load_user=None` → `profile_checked=False` | 回 `status: "not_checked"`，**连那个键都不给** |
| `billing` | `count_used` / `load_events` / `load_usage` = None | 同上 |
| `design` | `TemplateRegistry(available=False)` | 回「注册表不可用」，不是「没有模板」 |
| `quality` / `pack` | `ref_resolver` / `pack_owner` / `pack_ready` = None | 同上 |

这几处的类型注解本来就写着 `X | None`——**「没配」是一等公民**，不是临时想出来的。
前端那一侧同构：`NotProvided` 与空态各带自己的 `data-*-state`。

## 没有 `X | None` 缝的那几族：503，NEVER 500

`quality` / `staleness` / `pricebook` / `profile` / `pack` / `share` / `favorites`
的部分依赖**不可为空**，处理函数拿到占位就直接调。
第一版占位抛的是裸 `NotImplementedError` → 每次请求 **500 Internal Server Error**
（`WIRE-03` 开工探端点时实测到）。

**500 说的是「坏了」，真相是「没配后端」**——两者该让人做的事完全不同：
前者去翻栈查日志，后者去配一个后端。所以占位改抛 `FamilyNotConfigured`，
经异常处理器变成 **503 + `{"code": "FAMILY_NOT_CONFIGURED", "family": …}`**，
与 `deliverables.py` 对 `fmt=pack` 的处置同款（E6 姿态：明说不可用）。
"""
from __future__ import annotations

import hashlib
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from starlette.routing import BaseRoute

from flint.align.stage1 import LLMCitationAligner
from flint.api.account import AccountApiDeps, create_account_app
from flint.api.analysis import AnalysisApiDeps, create_analysis_app
from flint.api.billing import BillingApiDeps, create_billing_app
from flint.api.combo import ComboApiDeps, create_combo_app, make_topic_keywords_resolver
from flint.api.compose import ComposeApiDeps, create_compose_app
from flint.api.deliverables import DeliverableApiDeps, create_deliverables_app
from flint.api.deref import DerefApiDeps, create_deref_app
from flint.api.design import DesignApiDeps, create_design_app
from flint.api.favorites import FavoritesApiDeps, create_favorites_app
from flint.api.graph_edges import GraphEdgeDeps, create_graph_edge_app
from flint.api.identity import build_user_check, install_identity_handlers
from flint.api.interventions import InterventionApiDeps, create_interventions_app
from flint.api.pack import PackApiDeps, create_pack_app
from flint.api.pricebook import PriceProfileApiDeps, create_pricebook_app
from flint.api.project_overview import ProjectOverviewDeps, create_project_overview_app
from flint.api.quality import QualityApiDeps, create_quality_app
from flint.api.settings import LocaleApiDeps, create_settings_app
from flint.api.share import ShareApiDeps, create_share_app
from flint.api.staleness import StalenessApiDeps, create_staleness_app
from flint.api.topics import TopicsApiDeps, create_topics_app
from flint.api.views import ViewsApiDeps, create_views_app
from flint.api.workbenches import WorkbenchDeps, create_workbench_app
from flint.authz import (
    ProjectNotFound,
    build_owner_scope_for_project,
    build_role_resolver,
)
from flint.billing.quota import BillingConfig
from flint.design.templates.pgregistry import PgTemplateRegistry
from flint.domain.models import JSON, JobKind
from flint.embed import DeterministicHashBackend, EmbeddingService
from flint.fav.pgstore import PgFavoriteStore
from flint.fav.pin import SnapshotPins
from flint.fav.snapshot_source import build_snapshot_source
from flint.fav.stale import SnapshotHistoryStore
from flint.graph.pgstore import PgGraphStore
from flint.jobs.events import PgJobEventStream
from flint.jobs.runner import PgJobRunner
from flint.ledger.store import PgLedgerStore
from flint.profile.pgprefs import PgPrefsStore
from flint.repo.categories import fetch_categories
from flint.scoring.scorer import DualScaleScorer, ScorerContext
from flint.share.pgstore import PgShareLinkStore


@dataclass(frozen=True)
class RouteCollision:
    """同一 method+path 被两个模块注册。

    **登记它不是为了容忍它**，是为了让「谁被遮蔽」这件事有名字、有理由、有单号。
    未登记的冲突走 `RouteConflictError`，NEVER 静默挑一个。
    """

    method: str
    path: str
    winner: str
    shadowed: str
    reason: str
    ticket: str


class RouteConflictError(RuntimeError):
    """出现了没登记过的路由冲突。

    NEVER 降级成「先挂的赢」——那正是这条路径被两个模块各注册一次却没人发现的原因。
    """


# **空的**。`WIRE-01` 装配时实测撞出一处（`GET …/render` 被 deliverables.py 与
# pack.py 各注册一次），当时按临时处置登记在这里、挂单等 owner 裁决。
# `ROUTE-01` 按裁决把冲突**真正解掉**（pack.py 不再注册那条路径，
# 它身上那道三与门搬进赢家），登记面因此空了。
#
# 空登记 NEVER 意味着「不再检查」：装配器对**未登记**的冲突直接 raise，
# 现在等于任何一处新冲突都会当场炸——这比登记着一条更严。
KNOWN_COLLISIONS: tuple[RouteCollision, ...] = ()


@dataclass(frozen=True)
class UnwiredFamily:
    """挂不上的一族，及**缺的到底是什么**。

    登记它是为了让「没挂」这件事有名字与单号。空着不写，它就与
    「忘了挂」长得一模一样——而这次 51 条藏一整批，靠的正是没人给它命名。
    """

    module: str
    paths: tuple[str, ...]
    missing: str
    ticket: str


# 缺的是**授权事实**与**模型配置**，不是接线。详见单子。
# 判等值：`tests/v041/test_app_assembly.py` 里多一条少一条都会红。
_AUTH_TICKET = "docs/blocked/WIRE-01-FOUR-FAMILIES-NEED-AUTH-AND-PROVIDER.md"
UNWIRED_FAMILIES: tuple[UnwiredFamily, ...] = (
)


@dataclass(frozen=True)
class MountedRoute:
    """装配后的应用真正会去派发的一条路径。"""

    path: str
    methods: frozenset[str]


# FastAPI 自带的文档路由不是我们的端点。
_FRAMEWORK_PATHS = frozenset(
    {"/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc"})


def _walk(routes: list[BaseRoute], prefix: str = "") -> list[MountedRoute]:
    """递归展开路由表。

    FastAPI 0.140 的 `include_router` **不把子路由摊进 `app.routes`**，
    而是留一个惰性节点（`path` 是 `None`，真路径在 `original_router` 里）。
    """
    found: list[MountedRoute] = []
    for route in routes:
        context = getattr(route, "include_context", None)
        included = getattr(route, "original_router", None)
        if context is not None and included is not None:
            found.extend(_walk(
                included.routes, prefix + str(getattr(context, "prefix", "") or "")))
            continue
        path = getattr(route, "path", None)
        if not path:
            continue
        children = getattr(route, "routes", None)
        if children:
            found.extend(_walk(children, prefix + str(path)))
            continue
        methods = getattr(route, "methods", None) or {"GET"}
        found.append(MountedRoute(
            path=prefix + str(path),
            methods=frozenset(str(m) for m in methods if m != "HEAD")))
    return found


def mounted_route_table(app: FastAPI) -> tuple[MountedRoute, ...]:
    """应用**真的会去派发**的那张表。

    NEVER 靠读源码里的 `include_router` 语句代替它：那种读法对
    「挂了个空 router」「挂错了对象」「被另一个模块遮蔽」三种情况全部报绿。
    """
    return tuple(
        route for route in _walk(list(app.routes))
        if route.path not in _FRAMEWORK_PATHS
    )


def _module_of(sub: FastAPI) -> str:
    """子应用来自哪个模块——冲突报错时要指名道姓。

    NEVER 回一个「未知模块」占位：撞车信息里没有模块名，等于把定位活退回给人，
    而这条错误信息出现的时机恰恰是有人正在装配、手上没有上下文的时候。
    """
    for route in sub.routes:
        if isinstance(route, APIRoute):
            return route.endpoint.__module__.rsplit(".", 1)[-1] + ".py"
    return "<空应用：一条路由都没有>"


def _known_collision(method: str, path: str) -> RouteCollision | None:
    for collision in KNOWN_COLLISIONS:
        if collision.method == method and collision.path == path:
            return collision
    return None


@dataclass
class _Assembler:
    """按 method+path 记账地装配，撞车就 raise。"""

    app: FastAPI
    claimed: dict[tuple[str, str], str] = field(default_factory=dict)

    def add(self, sub: FastAPI) -> None:
        module = _module_of(sub)
        keep: list[BaseRoute] = []
        for route in sub.router.routes:
            if not isinstance(route, APIRoute):
                continue
            if not self._claim(route, module):
                continue
            keep.append(route)
        self.app.router.routes.extend(keep)

    def _claim(self, route: APIRoute, module: str) -> bool:
        """占位成功返回 True；这条被登记过的冲突遮蔽则返回 False。"""
        shadowed = False
        for method in sorted(route.methods or ()):
            if method == "HEAD":
                continue
            key = (method, route.path)
            owner = self.claimed.get(key)
            if owner is None:
                self.claimed[key] = module
                continue
            known = _known_collision(method, route.path)
            if known is None:
                raise RouteConflictError(
                    f"{method} {route.path} 被 {owner} 与 {module} 同时注册，且未登记。"
                    f"NEVER 静默挑一个：并进一个应用后必有一个永远收不到请求。"
                    f"登记进 KNOWN_COLLISIONS 并写明谁赢、为什么、挂哪张单。")
            if known.winner != owner:
                raise RouteConflictError(
                    f"{method} {route.path} 登记的赢家是 {known.winner}，"
                    f"但先占住的是 {owner}——装配顺序与登记不一致。")
            shadowed = True
        return not shadowed


class _UnconfiguredProvider:
    """没配模型时占住 `LLMProvider` 那个位的东西。

    **一被调用就 `FamilyNotConfigured`**——与既有的 `_unconfigured()` 同一姿态：
    路由照样挂着，用到模型的那条打过去回 **503 + 点名是哪一族**。

    NEVER 让它返回一个空补全：那样对齐会「成功」地把每条 claim 判成没有引用，
    而**「没配模型」与「模型说这条没有出处」是两件相反的事**。

    这一族缺的东西是**确定**的（就是没注 provider），所以它把真原因写进
    `reason`——`COMBO-WIRE-01` 之前它与「那张表不存在」共用同一句话。
    """

    #: 这一族缺的到底是什么。**这句是知道的，不是猜的**：走到这里就说明
    #: `create_app(…_provider=…)` 那条缝没人传。
    REASON = "没有注入模型 provider：本端点要调模型"

    def __init__(self, family: str) -> None:
        self._family = family

    def generate(self, prompt: str, tools: Any = None) -> Any:
        raise FamilyNotConfigured(self._family, self.REASON)

    def generate_structured(
        self, prompt: str, schema: Any, max_retries: int = 2,
    ) -> Any:
        raise FamilyNotConfigured(self._family, self.REASON)


def _queue_hook(redis_url: str | None, queue_name: str | None = None) -> Any:
    """作业入队。`redis_url` 为 None → 走 `_unconfigured`（503，点名 analysis）。"""
    if redis_url is None:
        # 这一族缺的是**队列**，不是表也不是模型——知道，所以说。
        return _unconfigured("analysis", "没有配作业队列：create_app 没给 redis_url")

    async def enqueue(job_id: str, kind: JobKind, payload: JSON) -> None:
        from arq import create_pool
        from arq.connections import RedisSettings

        from flint.jobs.worker_main import DEFAULT_QUEUE_NAME, build_enqueue_hook

        pool = await create_pool(RedisSettings.from_dsn(redis_url))
        try:
            hook = build_enqueue_hook(
                pool, queue_name=queue_name or DEFAULT_QUEUE_NAME)
            await hook(job_id, kind, payload)
        finally:
            await pool.aclose()

    return enqueue


def _stable_id(seed: str) -> str:
    """由内容决定的短 id。**同样的输入恒得同样的输出**——`ENTRY-03` 的幂等靠它。

    NEVER 换成随机 id：那样同一个人对同一个热点每点一次「入台」，
    就多出一张空工作台，而他以为自己只建了一张。

    用 `blake2b` 而不是 `uuid4`：这里要的正是「可复算」，
    而 `S2-2` 的第三条铁律（产物可复现）在 id 这一层同样成立。
    """
    return hashlib.blake2b(seed.encode("utf-8"), digest_size=6).hexdigest()


def _template_record_model() -> Any:
    """固化产物的类型。与 `_graph_node_model` 同一条取法（延迟 import additive 层）。"""
    from contracts_v04.models_v04 import TemplateRecord

    return TemplateRecord


def _solidify_result_model() -> Any:
    """固化事件的类型。`SolidifyResult` 同样住在 additive 那一层。"""
    from contracts_v04.models_v04 import SolidifyResult

    return SolidifyResult


def _graph_edge_model() -> Any:
    """连线的类型。与 `_graph_node_model` 同一条取法（延迟 import additive 层）。

    **`EDGES-UI` 之前这里注的是 `None`**——于是 `add_edge` 拿 `None` 当构造器调，
    `POST /workbenches/{id}/edges` **每一次都 500**。
    卡面写的是「端点在、表在，缺的是画布上那个交互」；
    实测那条路自己也没通，接了画布也照样存不下。
    """
    from contracts_v04.models_v04 import GraphEdge

    return GraphEdge


def _graph_node_model() -> Any:
    """入台节点的类型。**从 `contracts_v04` 取**，NEVER 在这里新定义一个。

    图谱那一族的模型住在 additive 那一层（`contracts/models.py` 里没有 `GraphNode`），
    与 `flint/design/graph_stale.py` 同一条取法：延迟 import，
    这样应用装配不因为 additive 层的加载顺序而变脆。
    """
    from contracts_v04.models_v04 import GraphNode

    return GraphNode


def _cluster_exists(dsn: str) -> Callable[[str], Awaitable[bool]]:
    """这个热点在不在。

    `ENTRY-03` 拿它把「热点不存在」判成 404——**NEVER 省掉这一问**：
    拿一个不存在的簇建出来的工作台打开就是空的，而用户会以为是自己的数据丢了。
    """
    async def exists(cluster_id: str) -> bool:
        import asyncpg

        conn = await asyncpg.connect(dsn)
        try:
            found: bool = await conn.fetchval(
                "SELECT EXISTS (SELECT 1 FROM clusters WHERE cluster_id = $1)",
                cluster_id)
        finally:
            await conn.close()
        return found

    return exists


def _now() -> datetime:
    return datetime.now(UTC)


def _today() -> date:
    return _now().date()


class FamilyNotConfigured(RuntimeError):
    """这一族的后端还没有——**不是坏了**。

    `WIRE-03` 实测逼出来的：`_unconfigured` 原本写的是「永不被调用」，
    但 `quality` / `staleness` / `pricebook` / `profile` 四族**没有 `X | None` 缝**，
    处理函数拿到占位就直接调，于是每次请求都是 **500 Internal Server Error**。

    500 说的是「坏了」。真相是「没配后端」。两者该让人做的事完全不同：
    前者要去查日志翻栈，后者要去配一个后端。**NEVER 让它们共用一个表示。**

    落到响应上是 **503 + 明说哪一族没配**（E6 姿态：明说不可用，
    与 `deliverables.py` 对 `fmt=pack` 的处置同款）。

    ## `reason`：**知道才说，NEVER 猜**（`COMBO-WIRE-01`）

    这句话原本硬写着「迁移里没有对应的表」——那是四族里某几族的实况，
    被当成通用文案套给了所有族。**对 combo 它是假的**：表全在
    （`origins` / `topic_seeds` / `topics` / `projects` 实查在库），缺的是模型。
    而 owner 在工作台屏上按下「按你选的卡建项」看到的就是这一句，
    照着它去查迁移的人会白查一趟。

    「没配」与「表不存在」该让人做的事完全不同：前者去注一个东西进来，
    后者去建一张表。**NEVER 把两件事写成同一句话。**
    所以默认不猜原因；构造方**确实知道**时把它写进 `reason`。
    """

    def __init__(self, family: str, reason: str | None = None) -> None:
        super().__init__(
            f"{family} 这一族的后端没有配上"
            + (f"（{reason}）" if reason else "")
            + "，本端点未配置。这不是故障：没配 ≠ 坏了。")
        self.family = family
        self.reason = reason


def _design_session_loader(dsn: str) -> Callable[[str], Any]:
    """DESIGN-01：把设计会话的取数件接上（改前恒 `None` → 那条 replay 端点一律 404）。

    连接延迟到请求期——与本文件其它「有库后端的族」同一条口径：
    **建应用期间一次连接都不发**。
    """
    from flint.jobs.design_generate import load_design_session
    from flint.jobs.events import PgJobEventStream

    async def loader(job_id: str) -> Any:
        return await load_design_session(job_id, PgJobEventStream(dsn=dsn))

    return loader


def _unconfigured(family: str, reason: str | None = None) -> Callable[..., Any]:
    """给没有 `X | None` 缝的族做占位：一被调用就说清「没配」。

    **NEVER 让它抛裸的 `NotImplementedError`**——那会变成 500，
    与真故障挤进同一个表示。

    `reason` **知道才传**（`COMBO-WIRE-01`）：这个函数服务十来族，
    它们缺的东西并不是同一样，硬套一个具体原因就会有几族被说错。
    """

    def _raise(*_args: Any, **_kwargs: Any) -> Any:
        raise FamilyNotConfigured(family, reason)

    return _raise


def create_app(
    dsn: str, redis_url: str | None = None, queue_name: str | None = None,
    aligner_provider: Any = None, combo_provider: Any = None,
    combo_model: str | None = None,
) -> FastAPI:
    """装配全部路由族。

    `dsn` 只被存进各族 deps，**建应用期间一次连接都不发**——
    库不可达时这个函数照样返回一个应用。

    `combo_provider` / `combo_model` 是 `combo` 那一族的模型缝（`WIRE-10`）：
    来源是 `flint/config.py#ModelAccess`（`FLINT_MODEL_BASE_URL` / `FLINT_MODEL_NAME`），
    **NEVER 在这里编一个默认地址**——猜出来的地址要么连不上（好），
    要么连上了某个不该连的东西（更坏）。

    `aligner_provider` 是**模型的缝**（`WIRE-09`）：`interventions` 的证据注入要跑
    两段式对齐，那一步吃 LLM。不给就注一个**一调用就 503** 的占位——
    NEVER 注一个「返回空补全」的假 provider：那样对齐会「成功」地把每条 claim
    判成没有引用，而「没配模型」与「模型说这条没有出处」是两件相反的事。

    `redis_url` / `queue_name` 是**作业队列的缝**（`WIRE-07`）：给了就把提交推进真 arq
    （`queue_name` 不给走 arq 默认队列；端到端夹具每轮用自己的队列，
    NEVER 让两条跑在同一条队列上互相吃对方的作业）；
    不给就用 `_unconfigured("analysis")` 那条既有的缝——
    路由照样挂着，打过去回 **503 + 点名是哪一族**。
    **NEVER 让它默默地不入队**：那样作业会永远停在 `queued`，
    而「队列没配」与「worker 没起来」在表上长得一模一样。
    """
    app = FastAPI(title="flint-api")
    assembler = _Assembler(app=app)

    # 身份三拒（缺头 401 IDENTITY_MISSING / 身份不存在 401 IDENTITY_UNKNOWN /
    # 无角色 403）**要装在整机上**。
    #
    # `_Assembler.add` 只搬 `APIRoute`——**子应用的异常处理器一个都不跟过来**。
    # 于是每个模块里那句 `install_identity_handlers(app)` 只在它自己那个
    # `create_*_app()` 造出来的 TestClient 上生效；并进整机之后，
    # 任何一条从处理函数里抛出来的身份异常都变成**裸 500**。
    #
    # 这不是本卡引入的：它一直是这样，只是**一直没有一条路把它照出来**——
    # 身份类端点大多要请求体，探针不带体时先被 422 挡住，走不到抛异常那一步。
    # `PERSIST-02` 建的 `GET /workbenches/{id}` 是这一族第一条**不要体**的路，
    # `test_app_assembly.py#test_no_mounted_route_answers_500_out_of_the_box`
    # 当场把它报成「无脑 500」——**那把尺子是对的，而它指的是整机装配这一层**。
    #
    # 500 说的是「坏了」，而真相是「你没带身份」——两者该让人做的事完全相反。
    install_identity_handlers(app)

    @app.exception_handler(FamilyNotConfigured)
    async def _not_configured(
        _request: Request, exc: FamilyNotConfigured,
    ) -> JSONResponse:
        """没配后端 → **503 + 说清是哪一族**，NEVER 500。

        500 会被读成「坏了」，让人去翻栈；而这里要做的事是**配一个后端**。
        """
        return JSONResponse(
            status_code=503,
            content={"code": "FAMILY_NOT_CONFIGURED", "family": exc.family,
                     "message": str(exc)})

    @app.exception_handler(ProjectNotFound)
    async def _no_project(_request: Request, exc: ProjectNotFound) -> JSONResponse:
        """项目不存在 → **404**，NEVER 500。

        真 `owner_scope_for_project` 查不到项目时抛这个（`AUTH-02`）。
        不接住的话，一次「项目 id 打错了」会以 500 收场——
        而 500 读起来是「服务器坏了」，那会让人去翻栈，
        实际上要做的只是改一个 id。
        """
        return JSONResponse(status_code=404, content={
            "code": "NOT_FOUND", "message": f"unknown project: {exc.args[0]}"})

    @app.get("/categories")
    async def list_categories() -> list[dict[str, Any]]:
        return await fetch_categories(dsn)

    assembler.claimed[("GET", "/categories")] = "app.py"

    # ── 有库后端的族：dsn 直给，连接延迟到请求期
    assembler.add(create_views_app(ViewsApiDeps(dsn=dsn)))
    assembler.add(create_project_overview_app(ProjectOverviewDeps(dsn=dsn)))
    assembler.add(create_deliverables_app(DeliverableApiDeps(dsn=dsn)))
    assembler.add(create_deref_app(DerefApiDeps(dsn=dsn)))

    # ── analysis 族（WIRE-07）与 compose 族（WIRE-08）：
    # 鉴权那只真手到位之后才挂得上。两族**共用同一个 runner**——
    # 各造一个就是两条入队路径，而「作业进了哪条队列」会因此说不清。
    roles = build_role_resolver(dsn)
    owner_of = build_owner_scope_for_project(dsn)
    runner = PgJobRunner(
        dsn=dsn, role_resolver=roles, enqueue=_queue_hook(redis_url, queue_name))
    assembler.add(create_analysis_app(AnalysisApiDeps(
        dsn=dsn, runner=runner, events=PgJobEventStream(dsn=dsn),
        owner_scope_for_project=owner_of, role_resolver=roles,
        topic_keywords_for=make_topic_keywords_resolver(dsn))))
    assembler.add(create_compose_app(ComposeApiDeps(
        dsn=dsn, runner=runner, owner_scope_for_project=owner_of,
        role_resolver=roles)))
    # ── topics 写族（ENTRY-02）：`POST /projects/{id}/chosen-topic`。
    # **挂上才算接线**——本仓这一批反复撞见的形状是「能力建好了路由没挂」，
    # 而没挂时前端拿到的是框架那种没有 `code` 的 404（= 这个能力还没挂），
    # 与「这一条不存在」长得一模一样。
    assembler.add(create_topics_app(TopicsApiDeps(
        dsn=dsn, owner_scope_for_project=owner_of, role_resolver=roles)))
    # ── combo 族（WIRE-10）：它要 provider 与 embed_service。
    # 模型没配时 provider 注占位（一调用即 503 并点名 combo）；
    # embed 用**确定性哈希后端**——它不吃模型，也不需要配置，
    # 且 NEVER 假装自己是真嵌入（那份后端自己的 docstring 写着这句）。
    assembler.add(create_combo_app(ComboApiDeps(
        dsn=dsn,
        provider=combo_provider or _UnconfiguredProvider("combo"),
        embed_service=EmbeddingService(DeterministicHashBackend(dim=1024)),
        model=combo_model or "unconfigured",
        id_factory=lambda: f"combo{uuid.uuid4().hex[:10]}",
        now=_now)))

    # ── interventions 族（WIRE-09）：多一样东西要注——对齐用的 provider。
    assembler.add(create_interventions_app(InterventionApiDeps(
        dsn=dsn, runner=runner, role_resolver=roles,
        owner_scope_for_project=owner_of,
        ledger_store=PgLedgerStore(dsn=dsn),
        scorer=DualScaleScorer(ScorerContext(today=_today())),
        aligner=LLMCitationAligner(
            aligner_provider or _UnconfiguredProvider("interventions")),
        now=_now)))

    # ── 没有持久层的族：走模块自己的「没查过」缝（见文件头那张表）
    assembler.add(create_account_app(AccountApiDeps(
        load_user=None, load_memberships=None)))
    assembler.add(create_billing_app(BillingApiDeps(
        config=BillingConfig(), count_used=None, load_events=None,
        load_usage=None)))
    # ── 收藏 / 分享 / 偏好三族（`PERSIST-01` · `DEC-048`）：**有库了**。
    #
    # 改前这三族分别注的是 `store=None`（favorites，`WIRE-12` 的 not_provided 缝）
    # 与两个**内存件**（share / prefs）。那不是实现偷懒——
    # `favorites` / `share_links` / `prefs` 三张表**从来没有建过**（`DEC-048`），
    # 内存件是当时唯一诚实的东西。迁移 0023 把三张表建齐之后，它们换成 SQL 实现。
    #
    # `not_provided` 那一态**留着**：`store=None` 时它仍然是唯一诚实的答复，
    # 删掉的话下一次库没配好时端点会回一个空列表——
    # 而那正是 `WIRE-12` 花了一整张卡去消灭的那句话。
    assembler.add(create_settings_app(LocaleApiDeps(store=PgPrefsStore(dsn=dsn))))
    assembler.add(create_favorites_app(FavoritesApiDeps(
        store=PgFavoriteStore(dsn=dsn), pins=SnapshotPins(),
        history=SnapshotHistoryStore(), diff_channel=_unconfigured("favorites"),
        now=_now, project_id_for=lambda _row: "", current_version=lambda: 0,
        # `FAV-SNAPSHOT` / `DEC-055`：快照由后端自取。这一缝**不注 `_unconfigured`**——
        # 它不是「用到才 503」的 provider，而是每次收藏都要走的一步；
        # 注真件之后，取不着由端点自己回 502 并点名，NEVER 存一份空的。
        snapshot_for=build_snapshot_source(dsn))))
    assembler.add(create_share_app(ShareApiDeps(
        store=PgShareLinkStore(dsn=dsn), load_content=_unconfigured("share"),
        now=_now)))
    # `PERSIST-03`（`DEC-048`）：`templates` 表建出来了，注册表换成 SQL 实现。
    # 改前注的是 `TemplateRegistry(available=False)`——**那不是实现偷懒**，
    # 是表根本不存在，`available=False` 是当时唯一诚实的值。
    #
    # `model` / `event_model` 改前是 `None`：没有存储面时它们用不上，
    # 而现在 `POST /design/templates` 会真的走到 `solidify_mock`，
    # 那两个 `None` 会让固化在构造记录那一行炸成 500。
    # 两者都从 additive 那一层取（`contracts_v04`），NEVER 在这里新定义。
    assembler.add(create_design_app(DesignApiDeps(
        registry=PgTemplateRegistry(dsn=dsn), now=_now,
        load_export_inputs=_unconfigured("design"),
        model=_template_record_model(), event_model=_solidify_result_model(),
        deliverables_by_graph={}, load_changes=None,
        # DESIGN-01：设计会话的取数件。改前恒 None —— 那条 replay 端点
        # 一律回 404「unknown session」，断线重连拿不回任何东西。
        load_session=_design_session_loader(dsn))))
    # ── 图谱一族（ENTRY-03）：建工作台与建边**共用同一个 store**。
    #
    # 改前 edges 那一族自己 new 了一个 `GraphStore()`。再给建工作台 new 第二个的话，
    # 建出来的工作台**加不上边**——两个进程内字典互相看不见对方的节点，
    # 而 `add_edge` 的第一件事就是查两端节点在不在。
    #
    # PERSIST-02 把它从**内存件换成了 SQL 件**（迁移 0027 建的三张表）。
    #
    # 改前它是 `GraphStore()`：工作台活在这一个实例的进程内字典里，
    # 重启即消失——而用户点过「入台」，他以为存下了。
    # 那时留的缝就是 `WorkbenchDeps.store`，今天兑现：**端点一行都没改存储写法**，
    # 换的只是这里注进去的那个对象（单据 `GRAPH-HAS-NO-STORAGE-FACE.md` 由本卡关掉）。
    #
    # 仍然只造**一个**：每个实例各开各的连接，两个实例就是两倍连接数。
    graph_store = PgGraphStore(dsn=dsn)
    assembler.add(create_graph_edge_app(GraphEdgeDeps(
        store=graph_store, now=_now, edge_model=_graph_edge_model())))
    assembler.add(create_workbench_app(WorkbenchDeps(
        store=graph_store, now=_now,
        check_user=build_user_check(dsn),
        cluster_exists=_cluster_exists(dsn),
        # graph_id 由 (user_id, cluster_id) **决定**——幂等的那一半就在这里：
        # 同一个人对同一个热点第二次入台，算出来的是同一个 id，落回同一张图。
        # NEVER 用随机 id：那样每点一次多出一张空工作台。
        graph_id_for=lambda user_id, cluster_id: (
            "wb-" + _stable_id(f"{user_id}|{cluster_id}")),
        node_id_for=lambda graph_id, cluster_id: (
            "gn-" + _stable_id(f"{graph_id}|{cluster_id}")),
        node_model=_graph_node_model())))
    assembler.add(create_pricebook_app(PriceProfileApiDeps(
        load_entries=_unconfigured("pricebook"),
        load_profile=_unconfigured("profile"),
        viewer_role_for=_unconfigured("pricebook"), today=_today)))
    assembler.add(create_quality_app(QualityApiDeps(
        load_blocks=_unconfigured("quality"),
        deliverable_owner=_unconfigured("quality"), ref_resolver=None)))
    assembler.add(create_staleness_app(StalenessApiDeps(
        load_staleness=_unconfigured("staleness"),
        diff_channel=_unconfigured("staleness"), today=_today)))
    assembler.add(create_pack_app(PackApiDeps(
        dsn=dsn, bundle_builder=_unconfigured("pack"),
        gate_inputs=_unconfigured("pack"), pack_owner=None, pack_ready=None)))
    return app
