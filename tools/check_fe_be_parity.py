"""AUDIT-01：前后端契约全表对账器（路由 ↔ 端点 ↔ 字段，机器可验）。

## 三个面，两次比对

| 面 | 从哪来 |
|---|---|
| **期望** | 交付包 README 的「路由 ↔ 界面 ↔ 主端点」全表 |
| **后端实况** | `flint/api/` 里的路由装饰器（AST，不是 grep） |
| **前端实况** | `web/app/` 的页面树 + 全仓源码里的端点字面量 |

卡面要三类，本器出**六种**——三类里有两类各自分成了两种，
因为**混在一起的那两种，修法完全不同**：

| 卡面类 | 本器 kind | 分开的理由 |
|---|---|---|
| ① 前端要而后端没有 | `frontend_wants_missing_backend` | |
| ② 后端有而前端没接 | `backend_not_assembled` | **写好了没挂进应用**：每张卡的验收都是拿 `create_*_app` 直接造 TestClient 跑的，于是「没挂上」在任何单卡里都看不见，只有全表对账看得见 |
| ② 同上 | `backend_unused_by_frontend` | 挂上了、但前端一次都没调 |
| ③ 字段对不上 | `field_mismatch` | 前端**建了**类型却少了字段 → 要**对齐** |
| ③ 同上 | `frontend_untyped_response` | 前端**根本没建**这条端点的类型 → 要**新建** |
| （外） | `dynamic_path_not_checked` | 静态扫不动的动态派发路径：**本表没核对**，说出来而不是悄悄丢掉 |

## 路径三种方言先归一

后端 `{deliverable_id}`、前端路由 `[id]`、模板串 `${id}` 是同一条路的三种写法。
不归一的话三边永远对不上，尺子会把**全部**端点报成缺失——
而一把全红的尺子和一把全绿的尺子一样没人看。

## 字段比对的边界（说清楚它量不了什么）

后端字段取自各模块 `*_json()` 里**字面量 dict 的键**；前端字段取自
**`web/lib/**` 全部非测试文件**的接口成员，**按接口分组**
（`TYPE-04` 改：只读 `types.ts` 会把「类型在 client 里」报成「根本没建」；
平集比对会让一个同名字段就把「没建类型」误判成「漂移」）。
两边都是**静态可见**的那部分：
动态拼出来的键（`{**base, ...}`）与运行期才知道的字段量不到。
量不到的不报——**报一个量不准的差异比不报更糟**，它会让人去改本来对的代码。
"""
from __future__ import annotations

import ast
import importlib.util
import json
import re
import sys
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_ROUTE_METHODS = ("get", "post", "put", "patch", "delete", "head")
_PARAM = re.compile(r"\{[^}]*\}|\[[^\]]*\]|\$\{[^}]*\}")
_STRING_LITERAL = re.compile(r"`[^`]*`|\"[^\"\n]*\"|'[^'\n]*'")
# 端点路径**在字符串里的任何位置**：客户端拼的是 `${base}/jobs/${id}`，
# 路径并不紧跟引号。只在字符串里找，是为了把**注释**排除在外——
# 注释里写着的路径会随代码改动而过时，把它当成「前端在调这条」是假实况。
#
# ## GAUGE-14：首段白名单退役
#
# 这里原先列着 `plaza|clusters|projects|topics|jobs|…`——**不在清单里的路径
# 永远扫不到**。七条真被调用的路（`/facts/{}`、`/citations/{}`…）因此被报成
# 「后端有、前端没人用」，而真相是尺子没量到。**两者的修法完全相反**：
# 一个是去接线，一个是去修尺子；读到误报的人会去接一条已经接好的线。
#
# 现在宽着扫（任何 `/小写段` 开头的路径样字面量），再**与后端真实路由取交集**
# ——新增一族端点时尺子自动认得，而人维护的那串前缀永远慢一批。
_ENDPOINT_LITERAL = re.compile(
    # 括号要留在里面：`${encodeURIComponent(jobId)}` 少了右括号就归一不掉，
    # 于是这条调用会被当成一条后端没有的路。
    r"/[a-z][a-z0-9-]*[^`\"'\s]*"
)

# `href={...}` / `href="..."`：**导航，不是 API 调用**。
# 后端恰好也有 `GET /topics/{id}`——不排掉的话，一条只被链接、
# 从没被调用的端点会被算成「前端在调」，**那是往反方向错**。
# 静态资源：路径以文件扩展名结尾。本仓的 API 路径**一条都不带扩展名**。
_STATIC_ASSET = re.compile(r"\.[a-z0-9]{2,5}$")
_HREF = re.compile(r"href\s*=\s*(\{[^}]*\}|\"[^\"]*\"|'[^']*')")
# 同一条规则的另外两种写法：**程序化跳转也是导航，不是 API 调用**。
#
# 这条判据的前提在 `NAV-02/03` 那天过期了：在那之前，站内跳转只有 `href` 一种写法，
# 所以只排 `href` 就够。`NAV-02` 用 `window.location.assign(\`/clusters/${id}\`)`
# 把广场接到分析屏、`NAV-03` 用同样的写法接到工作台，
# 于是这两条**跳转**被读成「前端在调两条后端没有的端点」——两条假发现。
#
# 排的是导航那一处的**参数**，不是路径本身：别处真有一次 `fetch` 打同一条路，
# 它照样会被数到。`NAV-01` 的可达性尺子认的也正是这三种写法。
_NAV = re.compile(
    r"(?:router\.push|router\.replace|location\.assign|location\.replace"
    r"|location\.href\s*=)\s*\(?\s*(`[^`]*`|\"[^\"]*\"|'[^']*')")

def normalise_path(path: str) -> str:
    """三种方言归一：`{id}` / `[id]` / `${id}` → `{}`；查询串丢掉，路径不动。"""
    return _PARAM.sub("{}", path.split("?", 1)[0]).rstrip("/") or "/"


@dataclass(frozen=True)
class BackendRoute:
    method: str
    path: str
    module: str
    handler: str
    response_keys: tuple[str, ...]


@dataclass(frozen=True)
class Expectation:
    route: str
    screen: str
    endpoints: list[str]
    note: str


@dataclass(frozen=True)
class Finding:
    kind: str
    subject: str
    where: str
    expected: list[str] = field(default_factory=list)
    actual: list[str] = field(default_factory=list)
    note: str = ""


#: 这些关键字参数收的 dict 是**发出去的东西**，不是回给调用方的响应。
#: 目前只有一个：`runner.submit(payload={...})` 排进队列的作业载荷。
#: 单据 `docs/blocked/PARITY-READS-A-REQUEST-PAYLOAD-AS-A-RESPONSE.md`。
_NOT_A_RESPONSE_KWARG = frozenset({"payload"})


def _literal_dict_keys(node: ast.AST) -> list[str]:
    """一个函数体里所有字面量 dict 的键。动态拼出来的键取不到——那是有意的。

    ## 有一类 dict **不是响应**，NEVER 数进来

    本文件开头写着「后端字段取自各模块 `*_json()` 里字面量 dict 的键」。
    可这个函数是对**整个函数体**做 `ast.walk`，于是同一个函数里
    「排进队列的作业载荷」也被当成了响应的一部分。

    `PERSIST-04` 往 `POST /projects/{}/analysis` 的 `runner.submit(payload={...})`
    里加了一个 `topic_id`（判定收尾要沿它反查热点），尺子当场把这条端点报成
    `field_mismatch`——而那条端点的响应**只有 `job_id` 一个字段**，
    前端的类型一点没漂。照那份报告去改代码的人，会去给一个正确的类型加一个
    它不该有的字段。

    所以按**关键字参数名**排除：`payload=` 收的是发出去的东西。
    位置参数与别的名字照旧数——这一刀切得越窄越好，
    切宽了会把真的响应字段一起丢掉，而那种漏报比误报更难发现。
    ## 只数**真的被交出去**的那些

    排除单个关键字还不够。`POST /projects/combo` 实测：它的三个「后端字段」
    `card_ids` / `hypothesis` / `n` **一个都不在响应里**——前两个来自
    `runner.submit(payload=…)`，第三个来自一个局部计数器 `counter = {"n": 0}`。
    而前端的 `ComboSubmitEcho` 恰好照着这三个字段建了类型，于是两边**对着一份
    虚构的形状达成了一致**，尺子报绿。这比报错更坏：它把「没人核对过」
    伪装成了「核对过、没问题」。

    所以数的范围收到 `return` 语句能到达的 dict：`return {...}` 与
    `return JSONResponse({...})` / `JSONResponse(content={...})` 都算。
    交不出去的 dict 一律不算——**响应就是交出去的那个东西**。
    """
    returned: list[ast.AST] = []
    for sub in ast.walk(node):
        if isinstance(sub, ast.Return) and sub.value is not None:
            returned.append(sub.value)

    skip: set[int] = set()
    for sub in ast.walk(node):
        if not isinstance(sub, ast.Call):
            continue
        for kw in sub.keywords:
            if kw.arg in _NOT_A_RESPONSE_KWARG and isinstance(kw.value, ast.Dict):
                skip.add(id(kw.value))

    keys: list[str] = []
    seen: set[int] = set()
    for root in returned:
        for sub in ast.walk(root):
            if not isinstance(sub, ast.Dict) or id(sub) in skip or id(sub) in seen:
                continue
            seen.add(id(sub))
            for key in sub.keys:
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    keys.append(key.value)
    return keys


def backend_routes(api_dir: Path) -> list[BackendRoute]:
    """`flint/api/` 里的全部路由。判在 AST 上——注释里写的路径不算数。"""
    routes: list[BackendRoute] = []
    for source_file in sorted(api_dir.glob("*.py")):
        tree = ast.parse(source_file.read_text(encoding="utf-8"))
        # `*_json` 辅助函数**逐个**留着，NEVER 合成整模块一份：
        # 合成之后 `views.py` 的五条路由会共用同一套键，
        # 于是「字段对不上」报的是哪条路都对不上——那种报告没法拿来改代码。
        helpers = {
            node.name: tuple(_literal_dict_keys(node))
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name.endswith("_json")
        }
        for node in ast.walk(tree):
            if not isinstance(node, ast.AsyncFunctionDef | ast.FunctionDef):
                continue
            if not node.decorator_list:
                continue
            keys = _handler_keys(node, helpers)
            for decorator in node.decorator_list:
                routes.extend(_routes_from(decorator, node, source_file, keys))
    return routes


def _handler_keys(
    handler: ast.AST, helpers: dict[str, tuple[str, ...]]
) -> tuple[str, ...]:
    """这条路由**自己**返回的键：本体里的字面量 dict + 它调到的 `*_json` 辅助。"""
    keys = list(_literal_dict_keys(handler))
    for node in ast.walk(handler):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            keys.extend(helpers.get(node.func.id, ()))
    return tuple(dict.fromkeys(keys))


def _routes_from(
    decorator: ast.expr, node: ast.AST, source_file: Path,
    response_keys: tuple[str, ...],
) -> list[BackendRoute]:
    if not isinstance(decorator, ast.Call) or not decorator.args:
        return []
    first = decorator.args[0]
    if not (isinstance(first, ast.Constant) and isinstance(first.value, str)):
        return []
    if not isinstance(decorator.func, ast.Attribute):
        return []
    handler = getattr(node, "name", "")
    verb = decorator.func.attr
    methods: list[str] = []
    if verb in _ROUTE_METHODS:
        methods = [verb.upper()]
    elif verb == "api_route":
        # 一行一个方法：合成一行会把「GET 有而 POST 没有」这种缺口藏起来。
        for keyword in decorator.keywords:
            if keyword.arg == "methods" and isinstance(keyword.value, ast.List):
                methods = [
                    element.value.upper() for element in keyword.value.elts
                    if isinstance(element, ast.Constant)
                    and isinstance(element.value, str)
                ]
    return [
        BackendRoute(method=m, path=normalise_path(first.value),
                     module=source_file.name, handler=handler,
                     response_keys=response_keys)
        for m in methods
    ]


class AppUnbuildable(RuntimeError):
    """`app.py` 建不起来，因此**这一项没量到**。

    NEVER 退化成空集合返回：空集合会让报告印出「后端 62 条、挂了 0 条」，
    与「真的一条都没装配」逐字一样。读表的人分不出自己看的是缺陷还是瞎眼。
    """


# 建应用只为读路由表，不发请求、不连库；给个不可达 dsn 就够。
_PROBE_DSN = "postgresql://unused@127.0.0.1:1/unused"
# FastAPI 自带的文档路由不是我们的端点，不进挂载面。
_FRAMEWORK_ROUTES = frozenset(
    {"/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc"})


def _build_app(app_file: Path) -> Any:
    """把 `app.py` 装进来并建出应用。任何一步失败都 raise，NEVER 吞掉。"""
    if not app_file.exists():
        raise AppUnbuildable(f"没有这个文件：{app_file}")
    spec = importlib.util.spec_from_file_location(
        f"_parity_probe_{abs(hash(str(app_file)))}", app_file)
    if spec is None or spec.loader is None:
        raise AppUnbuildable(f"装不进来：{app_file}")
    module = importlib.util.module_from_spec(spec)
    # 先登记进 sys.modules 再 exec：`@dataclass` 解析注解时要
    # `sys.modules[cls.__module__]` 取模块全局；没登记就拿到 None，
    # 报成 `'NoneType' object has no attribute '__dict__'`——
    # 那读起来像「应用坏了」，其实是装载方式不对。
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        # 建不起来的原因原样带出去：只说「建不起来」等于把定位活退回给人。
        raise AppUnbuildable(f"import 失败：{exc}") from exc

    factory = getattr(module, "create_app", None)
    if callable(factory):
        try:
            return factory(_PROBE_DSN)
        except Exception as exc:
            raise AppUnbuildable(f"create_app 失败：{exc}") from exc
    app = getattr(module, "app", None)
    if app is None:
        raise AppUnbuildable(f"{app_file} 里既没有 create_app 也没有模块级 app")
    return app


def _walk_routes(routes: Iterable[Any], prefix: str = "") -> Iterator[str]:
    """递归展开路由表。

    FastAPI 0.140 的 `include_router` **不把子路由摊进 `app.routes`**，
    而是留一个惰性节点（`path` 是 `None`，真路径在 `original_router` 里）。
    照直读 `app.routes` 会把整整一个 router 读成零条。
    """
    for route in routes:
        context = getattr(route, "include_context", None)
        included = getattr(route, "original_router", None)
        if context is not None and included is not None:
            yield from _walk_routes(
                included.routes, prefix + str(getattr(context, "prefix", "") or ""))
            continue
        path = getattr(route, "path", None)
        if not path:
            continue
        children = getattr(route, "routes", None)
        if children:  # Mount：自己是前缀，端点在孩子上
            yield from _walk_routes(children, prefix + str(path))
            continue
        yield prefix + str(path)


def mounted_paths(app_file: Path) -> set[str]:
    """真正挂进应用的那些路径——**问建起来的应用要它的路由表**。

    只看 `app.py`：那是唯一被部署起来的入口。别处的 `create_*_app`
    是各卡自己的工厂，测试拿它造 TestClient——**造得出来不等于挂上了**。

    ## 为什么不扫源码字面量

    装配的惯用写法是 `app.include_router(account.router)`——**这一行里没有
    任何路径字面量**。按字面量扫，这样挂上去的 51 条会一条都数不到，
    于是「装配卡做对了」与「根本没装配」在计数上完全同形。

    反过来，只要在源码里看见 `include_router` 这个词就算数也不行：
    挂一个空 router 同样一条路由都不通。两种读法各错一半，
    **路由表是唯一同时避开这两头的读法**——它是应用真的会去派发的那张表。

    也 NEVER 走 `app.openapi()`：那份 schema 会漏掉 `include_in_schema=False`
    的路由——挂着、能打通、却数不到，于是出口判据被一条隐藏路由永远卡住。

    量的仍然是「挂上了」这一层；「能通」要一条条探活，那是装配卡的验收。
    """
    app = _build_app(app_file)
    return {
        normalise_path(path)
        for path in _walk_routes(app.routes)
        if path not in _FRAMEWORK_ROUTES
    }


def frontend_routes(app_dir: Path) -> set[str]:
    """`web/app/` 的页面树 → 路由集合。"""
    routes: set[str] = set()
    for page in app_dir.rglob("page.tsx"):
        rel = page.parent.relative_to(app_dir).as_posix()
        routes.add(normalise_path("/" + rel) if rel != "." else "/")
    return routes



def _looks_like_an_api_path(path: str) -> bool:
    """这条路径**长得像不像一条 API**（用于滤宽扫带进来的噪声）。

    口径：至少两段，或带参数（`/topics/{}`）。单段的 `/plaza`、`/demo`
    多半是页面路由——而它们里面真是 API 的那几条（`/account`、`/billing`）
    由**真实路由表**认领，不靠这条形状判据。

    **NEVER 反过来**（先形状后路由表）：那样一条真实的单段 API
    会被形状判据先毙掉，而它明明在路由表里写着。
    """
    # 静态资源不是 API：`_ds_bundle.js`、`messages/zh.json` 都是从 `web/public/`
    # 取的文件。宽扫会把它们带进来，而它们**按定义**不在后端路由表里——
    # 不排掉的话，`frontend_wants_missing_backend` 会说「前端要一条后端没有的路」，
    # 而真相是那根本不是一条路。
    if _STATIC_ASSET.search(path):
        return False
    return path.count("/") >= 2 or "{}" in path


def _is_fragment_of(path: str, backend_paths: set[str]) -> bool:
    """这条路径是不是某条真实路由的**尾巴**。

    客户端会跨字面量拼 URL：

        `/deliverables/${did}` +
        `/sections/${sid}/regenerate` + `?project_id=…`

    扫描器一次只看一个字面量，于是拿到 `/sections/{}/regenerate` 这个**片段**。
    整条 `/deliverables/{}/sections/{}/regenerate` 同时也在调用面里
    （它由另一处完整写出），所以片段是纯噪声。

    不排掉的话，`frontend_wants_missing_backend` 会说
    「前端要 `/sections/{}/regenerate` 而后端没有」——
    而后端有，只是路径前面还有一截。**那种误报会让人去建一条已经存在的端点。**
    """
    return any(route.endswith(path) and route != path for route in backend_paths)

def frontend_calls(web_dir: Path, backend_paths: set[str]) -> set[str]:
    """前端**真正发出去的**端点字面量（归一后）。

    ## GAUGE-14 之前：两个盲区

    - **首段白名单写死**：不在那串前缀里的路径永远扫不到（七条真调用被误报）；
    - **只扫 `web/lib/`**：页面与组件里的直接调用一条都看不见
      （`useScreenData("/account")` 就在 `web/app/**/page.tsx` 里）。

    两者的共同后果是那份报告说「后端有、前端没人用」，
    而真相是「尺子没量到」——**修法完全相反**。

    ## 现在：宽着扫，再与真实路由取交集

    `backend_paths` 是后端真实路由表（归一后）。宽扫会带进一批噪声，
    交集把它们滤掉；**新增一族端点时尺子自动认得**，
    而人维护的那串前缀永远慢一批。

    ## 交集**只滤噪声，NEVER 滤掉「前端要而后端没有」的那些**

    第一版直接 `if path in backend_paths` 就收——当场把
    `frontend_wants_missing_backend` 整类判空了：前端想要一条后端还没有的路，
    那条路按定义就不在路由表里，于是被自己的过滤器吃掉。
    **那是把尺子的另一半弄瞎了**，而它看起来是绿的（一条都不报）。

    所以噪声判据换成**形状**：路径要长得像一条 API（至少两段，或带参数），
    而 `href="/plaza"` 这种单段导航先前已被 `_HREF` 排掉。
    `backend_paths` 仍然收下——真实路由**恒不算噪声**，
    哪怕它只有一段（`/account`、`/billing` 就是）。

    仍然排掉的三种：

    - **注释**（`_without_comments`）：注释里的路径会过时，
      当成调用是假实况——而假实况会让一条真没人用的端点被当成用着的；
    - **测试与 mock**：`/jobs/job-9` 是样例数据，不是契约；
    - **`href` 与程序化跳转**：导航不是调用（见 `_HREF` / `_NAV`）。
      `NAV-02/03` 之前站内跳转只有 `href` 一种写法，所以只排 `href` 就够了；
      现在还有 `location.assign` 与 `router.push` 两种，**同一条规则的另外两种写法**。
    """
    calls: set[str] = set()
    # `web/lib` 是取数层；`web/app` 是页面（`useScreenData("/account")` 在那儿）；
    # `web/components` 是组件（`designSession.ts` 的提交在那儿）。
    for sub in ("lib", "app", "components"):
        root = web_dir / sub
        if not root.exists():
            continue
        for source_file in sorted(root.rglob("*.ts*")):
            if "node_modules" in source_file.parts or ".test." in source_file.name:
                continue
            if "mock" in source_file.parts or "__tests__" in source_file.parts:
                continue
            text = _without_comments(
                _without_imports(source_file.read_text(encoding="utf-8")))
            text = _HREF.sub("href={}", text)
            text = _NAV.sub("navigate()", text)
            unions = _union_members(text)
            for literal in _STRING_LITERAL.findall(text):
                for hit in _ENDPOINT_LITERAL.findall(literal):
                    for expanded in _expand_enum_segments(hit.split("#", 1)[0], unions):
                        path = normalise_path(expanded)
                        if path in backend_paths or _looks_like_an_api_path(path) and not _is_fragment_of(
                                path, backend_paths):
                            calls.add(path)
    return calls


def _union_members(text: str) -> dict[str, tuple[str, ...]]:
    """本文件里 `变量名 → 它可能取的那几个字面量`。

    两步：先收 `export type JobKind = "analysis" | "report" | "proposal";`，
    再收形参注解 `kind: JobKind`，把变量名接到那组成员上。

    只认**全部成员都是字符串字面量**的联合——有一个是 `string` 就整条放弃，
    那种确实判不动，该留在 `dynamic_path_not_checked` 里。
    """
    types: dict[str, tuple[str, ...]] = {}
    for name, body in re.findall(
            r"(?:export\s+)?type\s+(\w+)\s*=\s*([^;]+);", text):
        parts = [p.strip() for p in body.split("|")]
        if parts and all(re.fullmatch(r'"[^"]+"', p) for p in parts):
            types[name] = tuple(p.strip('"') for p in parts)
    variables: dict[str, tuple[str, ...]] = {}
    for var, type_name in re.findall(r"(\w+)\s*:\s*(\w+)\s*[,)]", text):
        if type_name in types:
            variables[var] = types[type_name]
    return variables


def _expand_enum_segments(
    path: str, unions: dict[str, tuple[str, ...]]
) -> list[str]:
    """把 `/projects/${id}/${kind}` 展成三条具体路径——**只在展得开时**。

    `kind` 的类型是 `JobKind = "analysis" | "report" | "proposal"`，
    后端也正好有这三条 POST 路由。**这条路不是判不动，是没人去展开它。**

    展不开（变量没有字面量联合类型）就原样返回一条——
    它会照旧落进 `dynamic_path_not_checked`。
    **NEVER 展不开还硬猜**：猜错了就是把「没核对」写成「核对过了」。
    """
    match = re.search(r"\$\{(\w+)\}$", path)
    if match is None:
        return [path]
    members = unions.get(match.group(1))
    if not members:
        return [path]
    head = path[: match.start()]
    return [head + member for member in members]


def _without_comments(text: str) -> str:
    """剥掉 `//` 行注释与 `/* */` 块注释。

    ## 模块 docstring 那句话此前是**假的**

    它写着「只在字符串里找，是为了把**注释**排除在外」。
    可注释里写 `` `/projects/{}/{}` `` 时，那对反引号**本身就长得像模板串**——
    于是一句解释性的注释被当成了一次真调用。

    `TYPE-04` 实测撞上：给 `types.ts` 写了一句说明「这条路径此前藏在
    `/projects/{}/{}` 里」，尺子当场把它报成一条扫不动的动态路径。

    注释里写着的路径会随代码改动而过时，把它当成「前端在调这条」是假实况。
    按行剥（`splitlines` 认所有换行形态），块注释按配对剥。
    """
    text = re.sub(r"/\*[\s\S]*?\*/", "", text)
    return "\n".join(
        line.split("//", 1)[0] if line.lstrip().startswith("//") else line
        for line in text.splitlines()
    )


def _without_imports(text: str) -> str:
    """把 `import ... from "…"` 里的模块路径剥掉。

    `WIRE-03` 实测撞出来的：`web/lib/screenAdapters.ts` 里
    `from "../components/account-billing/AccountPanel"` 被当成了一条端点，
    报出「前端要 `/account-billing/AccountPanel` 而后端没有」——
    **一条纯误报**。模块路径与端点路径长得一样，但一个是磁盘上的文件、
    一个是 HTTP 上的资源。

    误伤会让人去改本来对的代码，这把尺子的 docstring 自己写着
    「报一个量不准的差异比不报更糟」。
    """
    kept: list[str] = []
    inside_import = False
    for line in text.splitlines():
        stripped = line.lstrip()
        if inside_import:
            # 多行 import 的续行：直到出现 `from "…"` 那一行为止。
            inside_import = not stripped.startswith("} from ") and " from \"" not in stripped
            kept.append("")
            continue
        # `export type { Locale } from "./i18n/config"` 也是模块路径——
        # `GAUGE-14` 宽扫之后它被报成「前端要 /i18n/config 而后端没有」，
        # **一条纯误报**（与上面那句 docstring 记的是同一种）。
        if stripped.startswith(("import ", "export * from", "export {",
                                "export type {", "export type *")):
            inside_import = " from \"" not in stripped and not stripped.endswith(";")
            kept.append("")
            continue
        kept.append(line)
    return "\n".join(kept)


def readme_expectations(readme: Path) -> list[Expectation]:
    """README 的「路由 ↔ 界面 ↔ 主端点」表 → 期望行。

    「端点未建」那几行**保留**——它们正是要核对的东西，丢了就等于自证清白。
    """
    if not readme.exists():
        return []
    rows: list[Expectation] = []
    for line in readme.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| /") and not line.startswith("| R"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 3 or cells[0].startswith("---"):
            continue
        route_cell, screen, endpoint_cell = cells[0], cells[1], cells[2]
        route = normalise_path(route_cell.split("·")[0].strip())
        # **只取跟在 HTTP 动词（或 SSE）后面的路径**。表里的写法恒是
        # 「GET /x · POST /y」；括号里那句「仓库路由习惯亦可用 /gate/[jobId]」
        # 说的是**页面路由**，不是端点——不按动词取的话它会被当成一条缺失的端点，
        # 而那条端点本来就不存在也不该存在。
        endpoints = [
            normalise_path(m) for m in re.findall(
                r"(?:GET|POST|PUT|PATCH|DELETE|SSE)\s+(/[A-Za-z0-9_\[\]{}/$-]+)",
                endpoint_cell)
        ]
        rows.append(Expectation(route=route, screen=screen,
                                endpoints=endpoints, note=endpoint_cell))
    return rows


def parity(repo: Path) -> list[Finding]:
    """双向比对，出四种发现。"""
    api_dir = repo / "flint" / "api"
    readme = (repo / "Claude design Flint 前端设计" / "Flint 应用 · 20 屏"
              / "design_handoff_flint_web" / "README.md")
    # `app.py` 里 `from flint...` 要求仓库根在 `sys.path` 上。pytest 会替你放，
    # `python tools/check_fe_be_parity.py` 不会——少了这句，CLI 出的那份表会
    # 整块塌成「装配面没量到」，而那正是被当出口判据读的一份表。
    if str(repo) not in sys.path:
        sys.path.insert(0, str(repo))

    routes = backend_routes(api_dir)
    try:
        mounted: set[str] | None = mounted_paths(api_dir / "app.py")
        app_error = ""
    except AppUnbuildable as exc:
        # 量不到就说量不到。**NEVER** 拿空集合往下算——那会印出一份
        # 与「全都没装配」逐字相同的报告，而两者该让人做的事完全相反。
        mounted, app_error = None, str(exc)
    expectations = readme_expectations(readme)

    backend_paths = {r.path for r in routes}
    # GAUGE-14：交集要在**知道真实路由之后**才算得出来，所以挪到这里。
    calls = frontend_calls(repo / "web", backend_paths)
    by_path: dict[str, list[BackendRoute]] = {}
    for route in routes:
        by_path.setdefault(route.path, []).append(route)

    findings: list[Finding] = []
    skipped: list[str] = []

    # ① 前端要而后端没有（期望面 ∪ 实际调用面 − 后端实况）
    wanted: dict[str, str] = {}
    for row in expectations:
        for endpoint in row.endpoints:
            wanted.setdefault(endpoint, f"README 表 · {row.screen}")
    for call in calls:
        wanted.setdefault(call, "web/ 源码里的调用")
    for path, where in sorted(wanted.items()):
        if path in backend_paths:
            continue
        if path.endswith("/{}") and path.count("{}") > 1:
            # 末段是参数的多参路径 = **动态派发**（`/projects/${id}/${kind}`）：
            # 静态扫描看不出它最终打到哪条路。报成「后端没有」是误伤，
            # 但也 NEVER 悄悄丢掉——它进 `dynamic` 名单，在表里单列一节。
            skipped.append(path)
            continue
        findings.append(Finding(
            kind="frontend_wants_missing_backend", subject=path, where=where,
            note="前端要这条，后端没有"))

    if mounted is None:
        # ②③ 这一整面**没量到**。只报这一条，不报任何一条未装配：
        # 报了就等于替它作答，而答案正好是最刺眼的那个。
        findings.append(Finding(
            kind="app_unbuildable", subject="flint/api/app.py",
            where="flint/api/app.py",
            note=f"应用建不起来，装配面本次没有核对（不是「已核对且全部未装配」）：{app_error}"))
    else:
        # ② 写好了但没挂进应用（能力闲置最锋利的一种）
        for path in sorted(backend_paths - mounted):
            modules = sorted({r.module for r in by_path[path]})
            findings.append(Finding(
                kind="backend_not_assembled", subject=path,
                where="flint/api/" + "、".join(modules),
                note="端点已实现且测试全绿，但没挂进 flint/api/app.py——前端调不到"))

        # ③ 挂上了但前端一次都没调
        for path in sorted(backend_paths & mounted):
            if path not in calls and path not in wanted:
                findings.append(Finding(
                    kind="backend_unused_by_frontend", subject=path,
                    where="flint/api/" + min(r.module for r in by_path[path]),
                    note="已装配但前端源码里没有任何调用"))

    # ④ 两边都有但字段对不上
    findings.extend(_field_findings(by_path, calls, repo))
    if skipped:
        # 静态扫不动的那些**要说出来**：不说的话，读表的人会以为它们已被核对。
        findings.append(Finding(
            kind="dynamic_path_not_checked",
            subject="、".join(sorted(skipped)),
            where="web/lib/",
            note="末段是参数的动态派发路径：静态扫描判不出它最终打到哪条路，"
                 "本表**没有核对**它——NEVER 当成已核对"))
    return findings


def _frontend_interfaces(lib_dir: Path) -> dict[str, set[str]]:
    """`web/lib/**` 里**每个接口各自**的字段名：`{"文件#接口": {字段…}}`。

    ## 改前是什么样

    只读 `web/lib/types.ts` 一个文件，且把字段名合成**一个平集**。两处病：

    1. **只读一个文件**：本仓的类型跟着各自的 client 放
       （`viewsClient.ts` 有 `PlazaCluster`，`topicClient.ts` 有 `Topic`…），
       于是「类型在别处」被报成「根本没建类型」——
       `TYPE-02` 差点因此把正在被使用的类型重抄一遍；
    2. **平集比对**：只要任何一个接口碰巧有一个同名字段，这条端点就被判成
       「建了类型」。`TYPE-02` 补完正当类型之后，`frontend_untyped_response`
       **整个消失了**——不是建齐了，是全被误判成「漂移」。
       规律很难看：**`types.ts` 越大，这把尺子越瞎**。

    改后按**接口**分组，两处一起解掉。
    """
    out: dict[str, set[str]] = {}
    if not lib_dir.exists():
        return out
    for source_file in sorted(lib_dir.rglob("*.ts")):
        if ".test." in source_file.name or "node_modules" in source_file.parts:
            continue
        text = source_file.read_text(encoding="utf-8")
        for name, body in re.findall(
                r"export\s+interface\s+(\w+)(?:<[^>]*>)?\s*\{(.*?)\n\}",
                text, re.DOTALL):
            fields = set(re.findall(
                r"^\s{2,}([a-z_][A-Za-z0-9_]*)\??:", body, re.MULTILINE))
            if fields:
                out[f"{source_file.name}#{name}"] = fields
    return out


def _field_findings(
    by_path: dict[str, list[BackendRoute]], calls: set[str], repo: Path
) -> list[Finding]:
    interfaces = _frontend_interfaces(repo / "web" / "lib")
    if not interfaces:
        return []
    out: list[Finding] = []
    for path in sorted(calls & set(by_path)):
        keys = {k for r in by_path[path] for k in r.response_keys}
        if not keys:
            continue          # 量不到就不报（见模块 docstring）
        where = "flint/api/" + by_path[path][0].module
        best, covered = _best_interface(keys, interfaces)
        missing = sorted(keys - covered)
        if not missing:
            continue
        if best is None:
            # **没有任何一个接口像它** = 前端根本没为这条端点建类型。
            # 这与「建了类型但漂移了」是两件事：前者要新建，后者要对齐。
            out.append(Finding(
                kind="frontend_untyped_response", subject=path, where=where,
                expected=sorted(keys),
                note="web/lib 里没有一个接口对得上这条端点——不是漂移，是没建类型"))
            continue
        out.append(Finding(
            kind="field_mismatch", subject=path, where=where,
            expected=missing, actual=sorted(keys & covered),
            note=f"前端在 {best} 里为这条端点建了类型，但后端这几个字段没被声明（真漂移）"))
    return out


def _best_interface(
    keys: set[str], interfaces: dict[str, set[str]]
) -> tuple[str | None, set[str]]:
    """哪个接口**最像**这条端点，以及它加上帮手能覆盖到的字段。

    ## 「像」的门槛，以及为什么要有门槛

    改前的判法是「前端字段名平集里有没有任何一个重合」——
    一个同名字段就算「建了类型」。`ledger_version` 撞上 `disputes`、
    `deliverable_id` 撞上 `Block`，都是这么来的。

    这里要求**至少两个字段重合**：一个字段的巧合不算数。

    ## 覆盖面按「层」算，不按单个接口算

    后端的 `response_keys` 是**摊平**的——`/plaza/hot` 那 21 个键分布在
    信封（3）、簇行（8）、热度分量（6）、弱信号（9）四层上。
    要求单个接口覆盖半数以上，会把**分层建得好好的**响应判成「没建类型」
    （第一版就是这么把 `/plaza/hot` 判错的）。

    所以：**字段集完全落在这条响应里的接口，就是它的一层**。
    覆盖面 = 所有这样的层之并。这条规则不会退回平集比对——
    平集的病是「拿无关接口的一个同名字段当证据」，
    而这里要求**整个接口都落在响应里**，一个不属于的字段就出局。
    """
    overlapping = {
        name: fields for name, fields in interfaces.items()
        if len(keys & fields) >= 2
    }
    if not overlapping and len(keys) == 1:
        # **单键响应**：`>= 2` 那道门在它身上结构上就迈不过去——
        # 一条只回 `{"locked": …}` 的端点，**无论前端怎么写都凑不出两个重合字段**。
        # 于是它恒被报成「根本没建类型」，而建了也不算。
        #
        # 这不是放宽门槛：那道门挡的是「拿一个同名字段当证据」，
        # 而这里要求的是**接口的字段集与响应的字段集完全相等**——
        # 那不是巧合，那是精确匹配。
        # （`TYPE-06` 实测：`/interventions/lock` 的响应键只有 `locked` 一个。）
        exact = {
            name: fields for name, fields in interfaces.items() if fields == keys
        }
        if exact:
            best = min(exact)
            return best, set(keys)
    if not overlapping:
        return None, set()
    best = max(overlapping, key=lambda name: len(keys & overlapping[name]))
    covered: set[str] = set()
    for fields in interfaces.values():
        # 「整个接口都落在响应里」= 它是这条响应的一层。
        #
        # **单字段接口要多一道条件**：光凭一个字段落在响应里，太容易碰巧成立。
        # 但 `TopicResponse { topic: T }` 这种**信封**本来就只有一个字段，
        # 一律排除会把它判成缺口（第一版就把 `/topics/{}` 判错了）。
        # 折中：只有在**这条端点已经确认有类型落点**（`best` 找到了）时，
        # 才认单字段接口——那时它是「这条响应的一层」而不是巧合。
        if fields <= keys and (len(fields) >= 2 or best is not None):
            covered |= fields
    covered |= keys & overlapping[best]
    return best, covered


def measure_handoff_package(package_dir: Path) -> dict[str, Any]:
    """实测交付包（供 `docs/handoff_gap_v04.md` 把 `[待核实]` 换成实数）。

    包不在时报 `present: False` 且各项为 0——**NEVER 报一个看起来像实测的数**。
    """
    if not package_dir.exists():
        return {"present": False, "screens": 0, "screen_labels": [],
                "batch_files": 0, "inline_mono": 0, "tabular_nums": 0,
                "warning_glyphs": 0, "i18n_keys": 0}
    html = sorted(package_dir.glob("*.dc.html"))
    text = "\n".join(f.read_text(encoding="utf-8", errors="replace") for f in html)
    # 屏数 = **去重后**的 `data-screen-label`。不去重的话数的是「屏出现过几次」
    # （外壳在每个批次文件里都出现一遍），那个数和「有几屏」不是一回事。
    labels = set(re.findall(r'data-screen-label="([^"]*)"', text))
    return {
        "present": True,
        "screens": len(labels),
        "screen_labels": sorted(labels),
        "batch_files": len(html),
        "inline_mono": len(re.findall(r"var\(--font-mono\)", text)),
        "tabular_nums": len(re.findall(r"tabular-nums", text)),
        "warning_glyphs": text.count("⚠"),
        "i18n_keys": len(re.findall(r"data-i18n=", text)),
    }


_KIND_TITLES = {
    "frontend_wants_missing_backend": "① 前端要而后端没有（缺端点）",
    "backend_not_assembled": "② 后端有而前端没接 · 未装配（能力闲置）",
    "backend_unused_by_frontend": "② 后端有而前端没接 · 已装配未调用",
    "field_mismatch": "③ 两边都有但字段对不上 · 真漂移（前端建了类型却少了字段）",
    "frontend_untyped_response": "③ 两边都有但字段对不上 · 前端没建类型",
    "dynamic_path_not_checked": "④ 扫不动 · 本表没核对（不是「已核对且没问题」）",
    "app_unbuildable": "⑤ 应用建不起来 · 装配面本次没量到（不是「全部未装配」）",
}


def render_table(findings: list[Finding], *, scanned: dict[str, int]) -> str:
    """对账表。**空报告要写「扫描面为空」**——留白与「扫过了、干净」长得一样。"""
    lines = [
        "# 前后端对账表 v0.4.1（AUDIT-01）",
        "",
        "> 本表由 `tools/check_fe_be_parity.py` **跑出来**，不是手写的。",
        "> 重跑：`python tools/check_fe_be_parity.py`（`--json` 出机读版）。",
        "",
        (f"扫描面：后端路由 {scanned['backend']} 条 · 前端路由 "
         f"{scanned['frontend']} 条 · README 期望行 {scanned['expected']} 行。"),
        "",
        f"**共 {len(findings)} 条发现。**",
        "",
    ]
    if not findings:
        lines += [("（一条都没有。若这不是因为**扫描面为空**，就是真的对齐了——"
                   "扫描面为空时上面三个数会是 0。）"), ""]
    for kind, title in _KIND_TITLES.items():
        rows = [f for f in findings if f.kind == kind]
        lines += [f"## {title}（{len(rows)} 条）", ""]
        if not rows:
            lines += ["（无）", ""]
            continue
        lines += ["| 对象 | 位置 | 说明 |", "|---|---|---|"]
        for finding in rows:
            note = finding.note
            if finding.expected:
                note += f"；后端字段 `{'`, `'.join(finding.expected)}`"
            if finding.actual:
                note += f"；前端已声明 `{'`, `'.join(finding.actual)}`"
            lines.append(f"| `{finding.subject}` | {finding.where} | {note} |")
        lines.append("")
    if scanned["backend"] == 0 or scanned["expected"] == 0:
        lines += [("> **扫描面为空**：至少有一侧一条都没扫到，"
                   "本表此刻不能被当成「已对齐」的证据。"), ""]
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    repo = Path(__file__).resolve().parents[1]
    findings = parity(repo)
    scanned = {
        "backend": len(backend_routes(repo / "flint" / "api")),
        "frontend": len(frontend_routes(repo / "web" / "app")),
        "expected": len(readme_expectations(
            repo / "Claude design Flint 前端设计" / "Flint 应用 · 20 屏"
            / "design_handoff_flint_web" / "README.md")),
    }
    if "--json" in argv:
        sys.stdout.write(json.dumps(
            {"scanned": scanned,
             "findings": [f.__dict__ for f in findings]},
            ensure_ascii=False, indent=1))
        return 1 if findings else 0
    if "--write" in argv:
        out = repo / "docs" / "前后端对账表-v041.md"
        out.write_text(render_table(findings, scanned=scanned), encoding="utf-8")
        sys.stdout.write(f"wrote {out}\n")
        return 1 if findings else 0
    sys.stdout.write(render_table(findings, scanned=scanned))
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
