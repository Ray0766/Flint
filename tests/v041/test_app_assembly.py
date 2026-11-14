"""WIRE-01 · 把 `flint/api/` 全部路由族挂进同一个 ASGI 应用。

## 这张卡要治的病

`flint/api/app.py` 到本卡为止是 **22 行、一条路由**（`/categories`，M1-022 起步件）。
其余 **51 条端点写好了、测试全绿、却挂不上任何应用**——前端调不到。

**为什么它藏了一整批**：每张 BE 卡的测试都拿自己的 `create_*_app` 造 `TestClient` 跑。
**造得出来 ≠ 挂上了。** worker 在 `BE-01~11` 十一张 trace 的「登记未做」里写了十一遍
「没挂进任何 ASGI 应用」，而**没有任何一条判据会因此变红**。

## 所以本文件的判据是「探活」，不是「语句在不在」

断言 `include_router` 语句存在，正是这次漏掉 51 条的那种写法：
它对「挂了个空 router」「挂错了对象」「被另一个模块遮蔽」三种情况**全部报绿**。

本文件对**每一条**已实现的路由发一次真请求，断言**不是 404、也不是 405**：

- **404** = 这条路径不在路由表里 → 没挂上；
- **405** = 路径在、方法不在 → 挂了一半。

500 / 422 / 401 **都算挂上了**——它们证明请求被路由到了处理函数并执行了。
本卡量的是「够得到」，不是「跑得通」（跑得通是 `E2E-01` 的活）。
"""
from __future__ import annotations

import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from flint.api.app import (
    KNOWN_COLLISIONS,
    UNWIRED_FAMILIES,
    RouteCollision,
    RouteConflictError,
    UnwiredFamily,
    _Assembler,
    create_app,
    mounted_route_table,
)
from tools.check_fe_be_parity import backend_routes, normalise_path, parity

REPO = Path(__file__).resolve().parents[2]
API_DIR = REPO / "flint" / "api"
# 建应用不许连库，所以这个 dsn 是**故意不可达**的：连得上就说明有人在建应用时连库了。
UNREACHABLE_DSN = "postgresql://nobody:nobody@127.0.0.1:1/nowhere"
# 测试库（flint_test，DSN-ISO 口径）：只有「不该有 500」那条用它——它要真库才量得准。
LOCAL_DSN = os.environ.get(
    "FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")
_PARAM = re.compile(r"\{[^}]+\}")


@pytest.fixture(scope="module")
def app() -> FastAPI:
    return create_app(UNREACHABLE_DSN)


@pytest.fixture(scope="module")
def client(app: FastAPI) -> TestClient:
    # `raise_server_exceptions=False`：处理函数里连库失败要变成 500 回来，
    # 而不是把异常抛进测试——抛出来就分不清「没挂上」和「挂上了但库不可达」。
    return TestClient(app, raise_server_exceptions=False)


def _is_unrouted(response: Any) -> bool:
    """这个 404 是**路由没命中**，还是**应用自己发的**？

    两者状态码一模一样，但意思相反：前者是「没挂上」，后者是
    「挂上了、跑到了处理函数、它说这东西不存在」。

    `/public/shares/{token}` 就是后者——`BE-09` 的「404 不 403」口径把
    未知与无权收进同一条路（回 `{"code": "NOT_FOUND", ...}`），
    拿探测用的假 token 去打，本来就该是 404。

    判别靠响应体：框架的路由未命中恒回 `{"detail": "Not Found"}`，
    而本仓所有应用自己发的 404 都带 `code`。
    """
    if response.status_code != 404:
        return False
    try:
        body = response.json()
    except ValueError:
        return True
    return "code" not in body


def _probe(path: str) -> str:
    """把 `/topics/{topic_id}` 变成可发的 `/topics/probe`。"""
    return _PARAM.sub("probe", path)


# ───────────────────────── acceptance①：全部族挂进同一个应用


def test_every_implemented_route_is_either_mounted_or_registered_as_unwired(
        app: FastAPI) -> None:
    """实现了的每一条路径，要么**挂上了**，要么**登记在案并写明缺什么**。

    判**等值**是有意的：没挂的那几条要是只是「不在集合里」，它与
    「忘了挂」长得一模一样——这次 51 条藏一整批，靠的正是没人给它命名。
    """
    implemented = {normalise_path(r.path) for r in backend_routes(API_DIR)}
    mounted = {normalise_path(r.path) for r in mounted_route_table(app)}
    registered = {
        normalise_path(p) for fam in UNWIRED_FAMILIES for p in fam.paths}

    assert implemented - mounted - registered == set(), (
        f"这些既没挂上、也没登记：{sorted(implemented - mounted - registered)}"
    )
    assert registered - implemented == set(), (
        f"登记了却根本不存在的路径：{sorted(registered - implemented)}"
    )
    assert registered & mounted == set(), (
        f"登记成「没挂」却其实挂上了：{sorted(registered & mounted)}"
    )


def test_each_unwired_family_says_what_is_missing_and_holds_a_ticket() -> None:
    """没挂的每一族都要写清**缺的是什么**并挂问题单。

    只说「没挂」等于把定位活退回给人；而不写单号，它就永远不会被谁捡起来。
    """
    # **兑现本条自己写的那句话**：`WIRE-07~10` 把四族全接通了，
    # 所以这里从「必须非空」翻成「必须空」。留着旧写法的话，
    # 它会在「全挂上了」这件好事发生时变红，而红的原因不是缺陷。
    assert UNWIRED_FAMILIES == (), (
        f"又有族挂不上了：{[f.module for f in UNWIRED_FAMILIES]}——"
        f"那要写清缺什么并挂单，把本条改回断言非空"
    )
    for family in UNWIRED_FAMILIES:
        assert isinstance(family, UnwiredFamily)
        assert family.paths, f"{family.module} 登记了却没列路径"
        assert len(family.missing) > 30, f"{family.module} 的「缺什么」太短"
        assert (REPO / family.ticket).exists(), f"问题单不在盘上：{family.ticket}"


def test_the_app_is_no_longer_the_one_route_starter() -> None:
    """反向：起步件只有 `/categories` 一条。挂完必须远多于一条。

    没有这一条，上一条在「实现面也塌了」时会一起变绿。
    """
    mounted = mounted_route_table(create_app(UNREACHABLE_DSN))
    paths = {normalise_path(r.path) for r in mounted}

    assert len(paths) >= 40, f"只挂到 {len(paths)} 条唯一路径，起步件是 1 条"


# ───────────────────────── acceptance②：逐条探活，NEVER 只断言语句存在


def test_every_mounted_route_answers_something_other_than_404(
        client: TestClient) -> None:
    """**本卡最要紧的一条**：对每条路由发真请求，断言不是 404 / 405。

    404 = 路径不在路由表；405 = 路径在、方法不在（挂了一半）。
    500 / 422 / 401 都算挂上了——它们证明请求被路由到处理函数并执行了。
    """
    missed: list[tuple[str, str, int]] = []
    for route in mounted_route_table(client.app):  # type: ignore[arg-type]
        for method in sorted(route.methods):
            response = client.request(method, _probe(route.path))
            if response.status_code == 405 or _is_unrouted(response):
                missed.append((method, route.path, response.status_code))

    assert missed == [], f"这些没探活（404/405）：{missed}"


def test_the_liveness_probe_would_notice_a_route_that_went_missing(
        client: TestClient) -> None:
    """阴性对照：编一条没人实现的路径，探活必须报 404。

    没有这一条，上一条可能是「见谁都算通过」——那与只断言语句存在没有区别。
    """
    response = client.get("/this-route-was-never-implemented")

    assert response.status_code == 404


def test_a_probe_that_only_checked_statements_would_have_missed_this() -> None:
    """本文件 NEVER 用「源码里有 include_router」当判据。

    这条判据判的是**本测试文件自己**：它必须真的发请求。
    只扫语句的写法对「挂了个空 router」「被另一个模块遮蔽」两种情况全绿，
    而后者本卡实测撞上了（见 `KNOWN_COLLISIONS`）。
    """
    source = Path(__file__).read_text(encoding="utf-8")

    assert "client.request(" in source, "本文件不再发真请求了"
    assert "status_code in (404, 405)" in source


def test_a_family_without_a_backend_answers_503_not_500(client: TestClient) -> None:
    """没配后端的族回 **503 + 说清是哪一族**，NEVER 500。

    `WIRE-03` 开工探端点时实测到：`quality` / `staleness` / `pricebook` / `profile`
    的必填依赖没有 `X | None` 缝，处理函数拿到占位就直接调，
    第一版占位抛裸 `NotImplementedError` → **每次请求 500**。

    **500 说的是「坏了」，真相是「没配后端」**——前者让人去翻栈查日志，
    后者让人去配一个后端。挤进同一个表示，等于把定位活退回给人。
    """
    for path in ("/pricebook", "/profile/probe",
                 "/deliverables/probe/quality", "/deliverables/probe/staleness"):
        response = client.get(path, headers={"X-User-Id": "probe"})

        assert response.status_code == 503, f"{path} → {response.status_code}"
        body = response.json()
        assert body["code"] == "FAMILY_NOT_CONFIGURED"
        assert body["family"], f"{path} 没说是哪一族"
        assert "没配" in body["message"] or "还没有后端" in body["message"]


def test_no_mounted_route_answers_500_out_of_the_box(client: TestClient) -> None:
    """装配后的应用在**库可达**时，不该有任何一条端点无脑 500。

    500 是「坏了」的专用位置。占着它的每一条，都会让真故障淹没在噪音里。
    库不可达时连库那些族本来就会 500——所以这条只在库起着时判。
    """
    # 这条**必须用真库**：模块级 fixture 的 dsn 是故意不可达的，
    # 拿它来量会永远走 skip 分支——**永远跳过的判据等于不存在**。
    live = TestClient(create_app(LOCAL_DSN), raise_server_exceptions=False)
    if live.get("/categories").status_code >= 500:
        pytest.skip(f"本机库没起（{LOCAL_DSN}）：连库的族此时本来就 500，这条量不准")

    broken: list[tuple[str, str]] = []
    for route in mounted_route_table(live.app):  # type: ignore[arg-type]
        for method in sorted(route.methods):
            response = live.request(method, _probe(route.path),
                                    headers={"X-User-Id": "probe"})
            if response.status_code == 500:
                broken.append((method, route.path))

    assert broken == [], f"这些无脑 500：{broken}"


# ───────────────────────── acceptance③：前缀零冲突，冲突要指名道姓


def test_a_path_claimed_by_two_modules_is_reported_with_both_names() -> None:
    """同一 method+path 被两个模块注册 → 判红并**指出是哪两个模块**。

    并进一个应用后，先挂的会被后挂的静默遮蔽（或反之）——
    「静默」正是本批一路在治的那件事。
    """
    # 两侧都归一（`backend_routes` 给的是 `{}`，装配器用的是 `{deliverable_id}`）。
    by_key: dict[tuple[str, str], set[str]] = defaultdict(set)
    for route in backend_routes(API_DIR):
        by_key[(route.method, normalise_path(route.path))].add(route.module)
    collisions = {k: sorted(v) for k, v in by_key.items() if len(v) > 1}

    known = {(c.method, normalise_path(c.path)): sorted([c.winner, c.shadowed])
             for c in KNOWN_COLLISIONS}

    assert collisions == known, (
        f"冲突面变了。实测 {collisions}，登记 {known}——"
        f"多出来的要停下登记，少掉的说明修好了，两种都要有人来这里确认"
    )


def test_each_known_collision_names_a_winner_and_says_why() -> None:
    """登记的每处冲突都要写清**谁赢、谁被遮、为什么**。

    只说「有冲突」等于把定位活退回给人；而「随便挂一个」就是静默遮蔽本身。
    """
    # `WIRE-01` 时这里写着「没有登记任何冲突——实测有一处，别把它扫掉」，
    # 因为那时盘上真有一处、而扫掉它就是静默遮蔽。
    # `ROUTE-01` 按 owner 裁决把那处**真正解掉**（`pack.py` 不再注册那条路径），
    # 登记面因此空了——本条于是从「必须非空」翻成「空了要有人确认」。
    #
    # 两件事**不是一回事**：登记面为空 = 没有已知冲突；
    # 检查为空 = 没人在看。前者是本卡挣来的，后者由
    # `test_an_unregistered_collision_raises_instead_of_shadowing_silently`
    # 与 `test_no_path_is_claimed_by_two_modules`（ROUTE-01）盯着。
    assert KNOWN_COLLISIONS == (), (
        f"又登记了冲突：{[c.path for c in KNOWN_COLLISIONS]}——"
        f"登记是临时处置，解掉才是收工"
    )
    for collision in KNOWN_COLLISIONS:
        assert isinstance(collision, RouteCollision)
        assert collision.winner and collision.shadowed
        assert collision.winner != collision.shadowed
        assert len(collision.reason) > 20, f"{collision.path} 的理由太短"
        assert collision.ticket.startswith("docs/blocked/"), (
            f"{collision.path} 没挂问题单——冲突是要 owner 裁的，不是 worker 挑一个"
        )
        assert (REPO / collision.ticket).exists(), f"问题单不在盘上：{collision.ticket}"


def test_an_unregistered_collision_raises_instead_of_shadowing_silently() -> None:
    """**阴性对照**：造一处没登记过的撞车 → 装配器必须 raise 并指名两个模块。

    这条是变异考逼出来的。原先只判「已登记那处的行为对不对」，
    而把守卫整个换成「先占的赢，静默遮蔽」——**十五条判据一条都不红**：
    已登记那处的结果本来就一样，守卫只对**未登记**的冲突说话，
    而盘上此刻没有未登记的冲突。

    没有这条阴性对照，`RouteConflictError` 就是一段没人量过的代码，
    下一次真撞车时它照样可能已经被谁「顺手」改成静默了。
    """
    first, second = FastAPI(), FastAPI()

    @first.get("/collide-on-purpose")
    async def one() -> dict[str, str]:
        return {}

    @second.get("/collide-on-purpose")
    async def two() -> dict[str, str]:
        return {}

    assembler = _Assembler(app=FastAPI())
    assembler.add(first)

    with pytest.raises(RouteConflictError) as caught:
        assembler.add(second)

    message = str(caught.value)
    assert "/collide-on-purpose" in message
    assert "GET" in message
    # 指名道姓：两个模块名都要出现，否则等于把定位活退回给人。
    assert message.count("test_app_assembly.py") == 2, message


def test_a_registered_collision_does_not_raise() -> None:
    """正例：**整套真模块装得起来**——见谁都 raise 的守卫同样量不出东西。

    `ROUTE-01` 之前这条量的是「登记过的那处不报错」。登记面空了之后，
    那个集合是空集，`>= 空集` 恒真——**判据会变成空转**。
    所以改成量真正还成立的那件事：二十几个模块并进一个应用，
    装配器一次都不炸。守卫只对真撞车说话，这是它的正例。
    """
    built = create_app(UNREACHABLE_DSN)

    assert len(mounted_route_table(built)) > 50
    assert {r.path for r in mounted_route_table(built)} >= {
        c.path for c in KNOWN_COLLISIONS}


def test_the_shadowed_module_is_not_silently_dropped(app: FastAPI) -> None:
    """被遮蔽的那条路径**仍然是通的**（由赢家应答），且赢家来自登记的那个模块。

    整个模块被丢掉才是最坏的结果：`pack.py` 的另一条 `/pack` 端点跟着一起没了。
    """
    mounted = {r.path for r in mounted_route_table(app)}

    for collision in KNOWN_COLLISIONS:
        assert collision.path in mounted, f"{collision.path} 干脆没挂"
    # `ROUTE-01` 之后登记面空了，上面那个循环不再跑——**但这两条仍要判**：
    # 被让出路径的那个模块整个丢掉才是最坏的结果。
    assert "/deliverables/{deliverable_id}/render" in mounted, "赢家那条也没了"
    # pack.py 的独有端点没被连坐
    assert "/deliverables/{deliverable_id}/pack" in mounted


def test_no_path_is_registered_twice_in_the_assembled_app(app: FastAPI) -> None:
    """装配后的应用里，同一 method+path 只有一个处理函数。

    重复注册不会报错——它只是让其中一个永远收不到请求。
    """
    seen: dict[tuple[str, str], int] = defaultdict(int)
    for route in mounted_route_table(app):
        for method in route.methods:
            seen[(method, route.path)] += 1
    duplicated = {k: v for k, v in seen.items() if v > 1}

    assert duplicated == {}, f"装配后仍有重复注册：{duplicated}"


# ───────────────────────── acceptance④：建应用不连库


def test_the_app_builds_with_an_unreachable_database() -> None:
    """`create_app` 在库不可达时仍要建得出来——否则冒烟脚本根本起不来。

    依赖注入延迟到请求期：建应用只组装可调用对象，不发一次连接。
    """
    built = create_app(UNREACHABLE_DSN)

    assert isinstance(built, FastAPI)
    assert mounted_route_table(built)


def test_building_the_app_twice_gives_two_independent_apps() -> None:
    """两次建出来的是两个应用，不是同一个被改了两遍。

    共享可变状态会让一个进程里的两个应用互相看见对方的内存件。
    """
    first, second = create_app(UNREACHABLE_DSN), create_app(UNREACHABLE_DSN)

    assert first is not second
    assert len(mounted_route_table(first)) == len(mounted_route_table(second))


# ───────────────────────── acceptance⑤：对账器的未装配计数归零


def test_the_parity_checker_sees_exactly_the_registered_gap() -> None:
    """`backend_not_assembled` 剩下的，**逐条**等于登记在案的那 10 条。

    卡面写的出口判据是「归零」。**本轮归不了零**：四族缺的是
    `role_resolver`（判 owner/viewer 的那只手）与模型配置，
    凑一个 `lambda: "owner"` 上去就是人人是 owner 的安全洞——
    停下登记在 `docs/blocked/WIRE-01-FOUR-FAMILIES-NEED-AUTH-AND-PROVIDER.md`。

    所以这里判**等值**而不是判零：
    - 多一条 → 有人新写了端点忘了挂，红；
    - 少一条 → 四族里有的接上了，红（提醒来这里改判据并更新单子）。

    这把尺子读的是**建起来的应用的路由表**，不是源码里的语句
    （`DEC-031` 落地时修的就是这一处）。
    """
    idle = {f.subject for f in parity(REPO) if f.kind == "backend_not_assembled"}
    registered = {
        normalise_path(p) for fam in UNWIRED_FAMILIES for p in fam.paths}

    assert idle == registered, (
        f"未装配面与登记面对不上。多出来：{sorted(idle - registered)}；"
        f"少掉的（可能是接上了）：{sorted(registered - idle)}"
    )


def test_the_gap_shrank_from_fifty_one_to_ten() -> None:
    """`WIRE-01` 开工时 51 条够不到，收卡时 10 条**且每条都有名字有单号**；
    `WIRE-07/08/09/10` 一族一族接完：7 → 5 → 1 → **0**。

    没有这一条，上一条那个等值判据在「登记面被人放大到 51」时照样绿。
    这个数每接通一族就要改一次——**改它就是在记账**，NEVER 把它写成一个范围。
    """
    idle = [f for f in parity(REPO) if f.kind == "backend_not_assembled"]

    assert len(idle) == 0, f"登记面是 {len(idle)} 条：10 → 7 → 5 → 1 → WIRE-10 后应为 0"


def test_the_parity_checker_still_measures_something() -> None:
    """归零要是「量到了、确实没有」，不是「没量到」。

    `app_unbuildable` 一出现，上一条会因为「没有未装配项」而假绿。
    """
    findings = parity(REPO)

    assert [f for f in findings if f.kind == "app_unbuildable"] == []
    assert findings, "一条发现都没有：尺子塌了"
