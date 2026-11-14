"""AUDIT-01 · 前后端契约全表对账器。

期望面 = 交付包 README 的「路由 ↔ 界面 ↔ 主端点」全表；
实况面 = `flint/api/` 的路由装饰器 + `web/app/` 的页面树 + 前端源码里的端点字面量。
两边**双向比对**，报三类：

1. **前端要而后端没有**（缺端点）
2. **后端有而前端没接**（能力闲置）——**未装配**是它最锋利的一种形态：
   端点写好了、测试全绿，却没挂进任何 ASGI 应用，前端根本调不到。
3. **两边都有但字段对不上**

## 阴性对照是这把尺子的一半

「两边齐了」与「尺子瞎了」在退出码上长得一模一样（都是 0）。
所以每一条「这样算对齐」的旁边，都有一条「这样必须报出来」。
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

from flint.api.app import UNWIRED_FAMILIES
from tools.check_fe_be_parity import (
    AppUnbuildable,
    Finding,
    backend_routes,
    frontend_calls,
    frontend_routes,
    mounted_paths,
    normalise_path,
    parity,
    readme_expectations,
    render_table,
)

REPO = Path(__file__).resolve().parents[2]
README = (REPO / "Claude design Flint 前端设计" / "Flint 应用 · 20 屏"
          / "design_handoff_flint_web" / "README.md")


# ───────────────────────── 一、路径归一（三种写法说的是同一条路）


def test_the_three_path_dialects_normalise_to_one() -> None:
    """后端 `{id}`、前端路由 `[id]`、模板串 `${id}` 是同一条路的三种写法。

    不归一的话，三边永远对不上，尺子会把**全部**端点报成缺失——
    一把全红的尺子和一把全绿的尺子一样没人看。
    """
    assert normalise_path("/deliverables/{deliverable_id}/blocks") == \
        normalise_path("/deliverables/[id]/blocks") == \
        normalise_path("/deliverables/${id}/blocks") == \
        "/deliverables/{}/blocks"


def test_a_query_string_is_dropped_but_the_path_is_not() -> None:
    assert normalise_path("/plaza/hot?day=2026-08-05") == "/plaza/hot"


def test_two_different_paths_never_collapse() -> None:
    """阴性对照：归一不能归到把不同的路揉成一条。"""
    assert normalise_path("/jobs/{id}") != normalise_path("/jobs/{id}/events")


# ───────────────────────── 二、后端实况：路由从 AST 取


def test_backend_routes_are_read_from_the_decorators() -> None:
    routes = backend_routes(REPO / "flint" / "api")
    paths = {(r.method, r.path) for r in routes}

    assert ("GET", "/account") in paths
    assert ("GET", "/billing") in paths
    assert ("PUT", "/settings/locale") in paths
    assert ("POST", "/design/render") in paths


def test_every_backend_route_knows_which_module_it_came_from() -> None:
    """报出来的东西要能被定位，否则读表的人不知道去哪儿改。"""
    routes = backend_routes(REPO / "flint" / "api")

    assert all(r.module for r in routes)
    assert {r.module for r in routes if r.path == "/account"} == {"account.py"}


def test_a_multi_method_route_is_expanded_one_row_per_method() -> None:
    """`api_route(methods=[...])` 要展开：一行一个方法。

    合成一行的话，「GET 有而 POST 没有」这种缺口会被藏起来。
    """
    routes = backend_routes(REPO / "flint" / "api")
    share = {r.method for r in routes if r.path == "/public/shares/{}"}

    assert "GET" in share
    assert "POST" in share


# ───────────────────────── 三、装配：写好了 ≠ 挂上了


def test_mounted_paths_come_from_the_app_factory() -> None:
    mounted = mounted_paths(REPO / "flint" / "api" / "app.py")

    assert "/categories" in mounted


def test_an_unmounted_route_is_reported_as_idle_capacity() -> None:
    """**本卡最要紧的一条**：端点写好了、测试全绿，却没挂进任何应用。

    这种「闲置」在任何单卡的验收里都看不见——每张卡都只跑自己的 TestClient，
    而 TestClient 是拿 `create_*_app` 直接造的。

    **`WIRE-01` 之后本条换了样本**：`/account` 已经挂上了（原样本），
    原先用的是 `/projects/{}/analysis`——`WIRE-07` 把它挂上之后本条当场红了，
    **那正是这条判据自己写着的那个机制**（「等四族接上，本条会因为找不到闲置样本而红，
    那正是提醒来这里改判据」）。换成仍未挂的 `/projects/{}/report`（compose 族）；
    等 `WIRE-08` 把它也挂上，本条会再红一次，那时再换或改成断言空集。
    """
    findings = parity(REPO)
    idle = {f.subject for f in findings if f.kind == "backend_not_assembled"}

    # 闲置样本换成 `interventions` 那族——`WIRE-08` 把 report 也挂上了。
    # **这一行被换过两次**，每次都是因为「又接通了一族」，那正是这条判据的用途。
    # **本条自己写着的那个机制兑现了**：四族接完，闲置样本一个都没有了。
    # 从「拿某条当样本」翻成「断言空集」——这正是它 docstring 里预告的那一步。
    assert idle == set(), f"又有端点没挂上：{sorted(idle)}"


def test_a_module_that_is_not_mounted_still_turns_the_zero_red(
    tmp_path: Path,
) -> None:
    """**归零的阴性对照（`WIRE-11` acceptance③）**：真造一个不挂的模块，
    未装配那一类 MUST 报出来。

    这一条是「0」这个数**唯一的意义来源**。没有它，归零有两种读法：
    「量到了、确实全挂上了」与「尺子塌了，什么都量不到」——
    而两者在报告上长得一模一样。

    造法是真的：一个临时 api 目录，里面一个模块声明了 `/never-mounted`，
    另有一份 `app.py` **不挂它**。
    """
    api = tmp_path / "flint" / "api"
    api.mkdir(parents=True)
    (api / "orphan.py").write_text(_ORPHAN_MODULE, encoding="utf-8")
    (api / "app.py").write_text(_APP_WITHOUT_ORPHAN, encoding="utf-8")

    declared = {normalise_path(r.path) for r in backend_routes(api)}
    mounted = mounted_paths(api / "app.py")

    assert "/never-mounted" in declared, "扫描面没看见那个模块——对照本身塌了"
    assert "/never-mounted" not in mounted
    assert declared - mounted == {"/never-mounted"}, (
        f"未挂载的差集不是那一条：{sorted(declared - mounted)}"
    )


_APP_WITH_ROUTER = '''
from fastapi import APIRouter, FastAPI

router = APIRouter()


@router.get("/alpha")
def alpha() -> dict[str, str]:
    return {}


@router.get("/beta/{item_id}")
def beta(item_id: str) -> dict[str, str]:
    return {}


def create_app(dsn: str) -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    return app
'''

# `WIRE-11` 的归零阴性对照用的两份源码：一个模块声明了路由，一份 app.py 不挂它。
_ORPHAN_MODULE = '''
from fastapi import APIRouter, FastAPI

router = APIRouter()


def create_orphan_app() -> FastAPI:
    app = FastAPI()

    @app.get("/never-mounted")
    async def read() -> dict[str, str]:
        return {}

    return app
'''

_APP_WITHOUT_ORPHAN = '''
from fastapi import FastAPI


def create_app(dsn: str) -> FastAPI:
    app = FastAPI()

    @app.get("/categories")
    async def cats() -> list[str]:
        return []

    return app
'''


def test_a_router_mounted_without_a_path_literal_is_seen(tmp_path: Path) -> None:
    """`app.include_router(account.router)` 这一行里**没有任何路径字面量**。

    按源码字面量扫的读法会把它读成「一条都没挂」——于是装配卡把事情做对了、
    路由真的通了，`backend_not_assembled` 仍然停在 51。
    **DEC-031 的出口判据（该计数归零）在那种读法下永远不可能达成**，
    而它红着的样子和「真没装配」一模一样，没人分得出来。
    """
    app_file = tmp_path / "app.py"
    app_file.write_text(_APP_WITH_ROUTER, encoding="utf-8")

    assert mounted_paths(app_file) == {"/alpha", "/beta/{}"}


def test_naming_include_router_is_not_the_same_as_mounting_a_route(tmp_path: Path) -> None:
    """DEC-031 的空转条款，可执行化：**认出 `include_router` 这个词不算数**。

    挂一个空 router——源码里 `include_router` 明明白白写着，
    而用户能打到的路由**一条都没有**。量到的挂载数必须是 0。
    """
    app_file = tmp_path / "app.py"
    app_file.write_text(
        "from fastapi import APIRouter, FastAPI\n"
        "\n"
        "empty = APIRouter()\n"
        "\n"
        "\n"
        "def create_app(dsn: str) -> FastAPI:\n"
        "    app = FastAPI()\n"
        "    app.include_router(empty)\n"
        "    return app\n",
        encoding="utf-8")

    assert mounted_paths(app_file) == set()


def test_a_prefixed_and_hidden_route_still_counts_as_mounted(tmp_path: Path) -> None:
    """两处实测出来的坑，各一条：

    1. `include_router(r, prefix="/v2")` 的前缀要拼上；
    2. `include_in_schema=False` 的路由**照样是挂上了的**——
       走 `app.openapi()` 读路由表会把它漏掉，于是一条隐藏路由
       就能让出口判据永远归不了零，而报告上写的是「这条没装配」。
    """
    app_file = tmp_path / "app.py"
    app_file.write_text(
        "from fastapi import APIRouter, FastAPI\n"
        "\n"
        "r = APIRouter()\n"
        "\n"
        "\n"
        '@r.get("/alpha")\n'
        "def alpha() -> dict[str, str]:\n"
        "    return {}\n"
        "\n"
        "\n"
        '@r.get("/hidden", include_in_schema=False)\n'
        "def hidden() -> dict[str, str]:\n"
        "    return {}\n"
        "\n"
        "\n"
        "def create_app(dsn: str) -> FastAPI:\n"
        "    app = FastAPI()\n"
        '    app.include_router(r, prefix="/v2")\n'
        "    return app\n",
        encoding="utf-8")

    assert mounted_paths(app_file) == {"/v2/alpha", "/v2/hidden"}


def test_an_app_that_cannot_be_built_is_never_reported_as_empty(tmp_path: Path) -> None:
    """建不起来 ≠ 一条都没挂。

    退化成空集合的话，报告会照着「后端有 62 条、挂了 0 条」的样子印出 62 行
    `backend_not_assembled`——**和真的没装配一模一样**。
    这正是本批那条纪律的老地方：「没查过」与「查过了、是空的」NEVER 同一个表示。
    """
    app_file = tmp_path / "app.py"
    app_file.write_text("raise RuntimeError('起不来')\n", encoding="utf-8")

    with pytest.raises(AppUnbuildable) as caught:
        mounted_paths(app_file)

    assert "起不来" in str(caught.value)


def test_a_missing_app_file_is_also_loud(tmp_path: Path) -> None:
    """文件根本不在，同理——静悄悄返回空集合等于替它作答。"""
    with pytest.raises(AppUnbuildable):
        mounted_paths(tmp_path / "nope.py")


def test_an_unbuildable_app_reports_one_gap_not_sixty_two_false_ones(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """建不起来时，报告里 `backend_not_assembled` 必须是 **0 条**，另有一条说明。

    这是整个分支存在的理由：拿空集合往下算，会印出一份与
    「62 条端点一条都没挂」**逐字相同**的报告——而两者该让人做的事正好相反。
    """
    import tools.check_fe_be_parity as tool

    def boom(_: Path) -> set[str]:
        raise AppUnbuildable("import 失败：装不进来")

    monkeypatch.setattr(tool, "mounted_paths", boom)
    findings = tool.parity(REPO)

    assert [f.kind for f in findings].count("app_unbuildable") == 1
    assert [f for f in findings if f.kind == "backend_not_assembled"] == []
    assert [f for f in findings if f.kind == "backend_unused_by_frontend"] == []
    note = next(f.note for f in findings if f.kind == "app_unbuildable")
    assert "没有核对" in note and "装不进来" in note


def test_the_command_line_run_measures_the_assembly_too() -> None:
    """命令行跑法**也要量得到装配面**。

    `app.py` 里 `from flint.repo... import ...` 要求仓库根在 `sys.path` 上；
    pytest 会替你放，`python tools/check_fe_be_parity.py` 不会。
    少了这一句，CLI 出的那份表会**整块塌成「没量到」**——
    诚实是诚实，但 owner 拿去当出口判据读的正是这份表。
    """
    done = subprocess.run(
        [sys.executable, "tools/check_fe_be_parity.py"],
        cwd=REPO, capture_output=True, text=True, encoding="utf-8", check=False)

    # ⑤ 那一节是**恒印的**（「空报告要写扫描面为空」），所以判的是它的条数，
    # 不是那几个字在不在——判在不在会被自己的空节骗过去。
    unbuildable = re.search(r"应用建不起来[^\n]*?（(\d+) 条）", done.stdout)
    assert unbuildable, done.stdout[-800:]
    assert unbuildable.group(1) == "0", "CLI 跑法下装配面没量到"

    # `WIRE-07~10` 之后闲置项归零。判的是**那一节印出来了且数得出**——
    # 判 `> 0` 会在「全挂上了」这件好事发生时变红；
    # 判「那几个字在不在」又会被自己的空节骗过去。
    idle = re.search(r"未装配（能力闲置）（(\d+) 条）", done.stdout)
    assert idle, done.stdout[-800:]
    assert int(idle.group(1)) == 0, (
        f"又有 {idle.group(1)} 条没挂上——四族此刻应当全接通"
    )


def test_the_real_app_is_measured_by_its_route_table() -> None:
    """本仓实况：`/categories` 挂着，且 FastAPI 自带的文档路由不算我们的端点。"""
    mounted = mounted_paths(REPO / "flint" / "api" / "app.py")

    assert "/categories" in mounted
    assert "/openapi.json" not in mounted and "/docs" not in mounted


# ─────────────── 三·补二、WIRE-05：装配面接进全局门，防止再裂开


def test_no_route_is_unassembled_without_being_registered_first() -> None:
    """**本卡的门**：一条路由要么挂上了，要么**登记在案**。两者都不是 → 红。

    ## 为什么不是「大于 0 即红」

    卡面 acceptance① 的字面写法是判零。**盘上判不了零**：`analysis` /
    `compose` / `interventions` / `combo` 四族挂不上，缺的是 `role_resolver`
    （判 owner/viewer 的那只手）与模型配置——凑一个 `lambda: "owner"` 上去
    就是人人是 owner 的安全洞。owner 尚未答复
    （`docs/blocked/WIRE-01-FOUR-FAMILIES-NEED-AUTH-AND-PROVIDER.md`）。

    判零的话，**全局门从今天起恒红**，而恒红的门与没有门等价——
    人会开始习惯性忽略它，那正是 F-11 那条教训的另一面。

    所以判的是**等值**：未装配面 == 登记面。

    - **新增模块忘了挂 → 它不在登记面里 → 红**（本卡要的效果，阴性对照见下一条）；
    - 四族接上了 → 登记面该缩 → 红，提醒来这里改判据并关单；
    - 谁把登记面注水 → `test_app_assembly.py` 那条判**路径存在性**的会红。
    """
    idle = {f.subject for f in parity(REPO) if f.kind == "backend_not_assembled"}
    registered = {
        normalise_path(path)
        for family in UNWIRED_FAMILIES for path in family.paths
    }

    assert idle == registered, (
        "装配面裂开了。\n"
        f"  没挂上也没登记（**这就是本条要抓的**）：{sorted(idle - registered)}\n"
        f"  登记了却已经挂上（登记面该缩）：{sorted(registered - idle)}\n"
        "登记面在 flint/api/app.py 的 UNWIRED_FAMILIES，"
        "每一族都要写明缺什么并挂问题单。"
    )


def test_a_new_module_that_forgets_to_mount_turns_this_gate_red(
        tmp_path: Path) -> None:
    """**阴性对照**：往 `flint/api/` 放一个没挂进 `app.py` 的模块 → 上一条必须红。

    这是本卡的要害。上一条判等值，等值判据有一种典型的空转方式：
    **两边都是空集也叫相等**。所以要真造一次「忘了挂」，看它是否被抓住。

    临时模块用完即删（`finally`），**NEVER 留在产品树里**——
    卡面点名了这一条。
    """
    intruder = REPO / "flint" / "api" / "_wire05_negative_control.py"
    assert not intruder.exists(), "上一次跑没删干净，先手动清掉再跑"
    intruder.write_text(
        '"""WIRE-05 阴性对照用的临时模块。测试结束即删。"""\n'
        "from __future__ import annotations\n"
        "\n"
        "from fastapi import FastAPI\n"
        "\n"
        "\n"
        "def create_wire05_probe_app() -> FastAPI:\n"
        "    app = FastAPI()\n"
        "\n"
        '    @app.get("/plaza/wire05-never-mounted")\n'
        "    async def probe() -> dict[str, str]:\n"
        '        return {"ok": "1"}\n'
        "\n"
        "    return app\n",
        encoding="utf-8")
    try:
        idle = {f.subject for f in parity(REPO) if f.kind == "backend_not_assembled"}
        registered = {
            normalise_path(path)
            for family in UNWIRED_FAMILIES for path in family.paths
        }

        assert "/plaza/wire05-never-mounted" in idle, (
            "新模块的路由没被报成未装配——这把尺子看不见新增的东西"
        )
        assert idle != registered, "门没红：忘了挂一整个模块，它却说一切正常"
    finally:
        intruder.unlink()

    assert not intruder.exists(), "临时模块没删掉——NEVER 留在产品树里"
    # 删掉之后门要恢复绿，否则下一条判据会被这次对照污染。
    after = {f.subject for f in parity(REPO) if f.kind == "backend_not_assembled"}
    assert "/plaza/wire05-never-mounted" not in after


def test_this_gate_runs_inside_pytest_q() -> None:
    """F-11 的教训：**不在门里的尺子等于没有**。

    本文件在 `tests/v041/` 下、文件名 `test_*.py`、函数名 `test_*`——
    `pytest -q` 会收它。这条判的是「收得到」这件事本身，
    防止有人把它挪进一个不被收集的位置（比如改名成 `check_*.py`）。
    """
    done = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q",
         "-k", "no_route_is_unassembled_without_being_registered"],
        cwd=REPO, capture_output=True, text=True, encoding="utf-8", check=False)

    # 判的是**默认收集面**（不指定文件，就像 `pytest -q` 那样跑）。
    # 断言源码里没有 `pytestmark`/`skipif` 那种写法会判到本条自己的断言串上——
    # 第一版就是这么假红的。这里改成**问 pytest 它到底收没收到**。
    assert done.returncode == 0, done.stdout[-500:] + done.stderr[-500:]
    assert "test_no_route_is_unassembled_without_being_registered_first" in done.stdout
    # `1/3714 tests collected`——分母是全仓收集面，证明它是**在默认那一跑里**被收到的，
    # 而不是只有指名道姓才跑得到。
    assert re.search(r"1/\d+ tests collected", done.stdout), done.stdout[-300:]


# ───────────────────────── 四、前端实况：页面树与调用字面量


def test_frontend_routes_are_read_from_the_page_tree() -> None:
    routes = frontend_routes(REPO / "web" / "app")

    assert "/plaza" in routes
    assert "/deliverables/{}/export" in routes


def test_frontend_calls_are_read_from_the_source() -> None:
    # GAUGE-14：第二个参数是后端真实路由表（宽扫 + 取交集）。
    calls = frontend_calls(REPO / "web", {"/plaza/hot"})

    assert "/plaza/hot" in calls


def test_a_page_that_does_not_exist_is_not_invented(tmp_path: Path) -> None:
    """阴性对照：没建的屏 NEVER 被当成建了。

    用**合成目录**验，不拿真仓库的某一条路由当例子：
    第一版写的是 `assert "/account" not in routes`——那是把**当下的事实**
    钉成了永久要求，UI-08 把 `/account` 建出来的那天它就红了，
    而红的原因是「有人把屏建好了」。
    """
    app = tmp_path / "app" / "only-this"
    app.mkdir(parents=True)
    (app / "page.tsx").write_text("export default function P() { return null; }\n",
                                  encoding="utf-8")

    routes = frontend_routes(tmp_path / "app")

    assert routes == {"/only-this"}


# ───────────────────────── 五、期望面：README 全表


def test_the_readme_table_is_parsed_into_expectations() -> None:
    rows = readme_expectations(README)
    by_route = {r.route: r for r in rows}

    assert "/plaza/hot" in by_route
    assert by_route["/plaza/hot"].screen.startswith("P1")
    assert "/plaza/hot" in by_route["/plaza/hot"].endpoints


def test_a_row_that_says_the_endpoint_is_not_built_is_kept_not_dropped() -> None:
    """「端点未建」那几行**不能丢**：它们正是本卡要核对的东西。"""
    rows = readme_expectations(README)
    placeholder = [r for r in rows if "占位" in r.screen or "未建" in r.note]

    assert placeholder, "README 里那几行占位屏没被解析出来"


def test_the_parser_never_invents_an_endpoint() -> None:
    """阴性对照：没写端点的行（P14 项目总览「无专属端点」）不许凭空造一个。"""
    rows = readme_expectations(README)
    overview = next(r for r in rows if r.route == "/projects/{}")

    assert overview.endpoints == []


# ───────────────────────── 六、三类差异（各带阴性对照）


def test_a_wanted_but_missing_endpoint_is_reported(tmp_path: Path) -> None:
    """用**合成仓库**验这一类，不拿真仓库验。

    真仓库此刻这一类是 0 条——那是真结果（BE-01~11 把 README 点名的端点补齐了）。
    拿真仓库断言「必须有一条」，就是把一个**当下的事实**钉成了永久要求：
    哪天它真的被补齐，判据反而红。
    """
    (tmp_path / "flint" / "api").mkdir(parents=True)
    (tmp_path / "flint" / "api" / "app.py").write_text(
        "def create_app():\n    pass\n", encoding="utf-8")
    (tmp_path / "web" / "lib").mkdir(parents=True)
    (tmp_path / "web" / "lib" / "c.ts").write_text(
        "const u = `${b}/topics/${id}`;\n", encoding="utf-8")

    findings = parity(tmp_path)

    assert [f.subject for f in findings
            if f.kind == "frontend_wants_missing_backend"] == ["/topics/{}"]


def test_an_aligned_pair_is_not_reported() -> None:
    """阴性对照：两边都有且字段对得上的，不许出现在报告里。"""
    findings = parity(REPO)

    assert not [f for f in findings
                if f.subject == "/categories"
                and f.kind == "frontend_wants_missing_backend"]


def test_a_field_mismatch_is_reported_with_both_sides() -> None:
    """字段对不上时，两边的字段名都要列出来——只说「对不上」没法改。"""
    findings = parity(REPO)
    mismatches = [f for f in findings if f.kind == "field_mismatch"]

    # `TYPE-04` 之后真仓库**没有漂移了**（尺子改准 + 四条真缺口补齐）。
    # 所以这里判的是「报的时候两边都列」这条**性质**，
    # 用合成输入验证——而不是要求真仓库此刻恰好有一条漂移。
    for finding in mismatches:
        assert finding.expected, finding.subject
        assert finding.actual, finding.subject
    assert "前端在 {best} 里为这条端点建了类型" in (
        REPO / "tools" / "check_fe_be_parity.py").read_text(encoding="utf-8"), (
        "报漂移时不再指名接口了——那等于把定位活退回给人"
    )


def test_a_drift_and_an_untyped_response_are_two_different_findings() -> None:
    """「建了类型但少字段」要**对齐**，「根本没建类型」要**新建**——
    混成一类的话，读表的人不知道该做哪件事。

    ## `TYPE-02` 之后本条换了判法

    原判据要求**真仓库此刻两种都有**。`TYPE-02` 往 `types.ts` 补了几组
    正当的类型之后，`frontend_untyped_response` **归零了**——
    不是因为类型建齐了，而是因为**每条端点都碰上了至少一个同名字段**，
    于是全被归进 `field_mismatch`。

    尺子把前端字段名当**一个平集**比，`types.ts` 越大越容易误判：
    补得越多，「没建类型」这一类越报不出来。
    登记在 `docs/blocked/PARITY-FIELD-NAMES-COMPARED-AS-ONE-FLAT-SET.md`
    与 `docs/blocked/PARITY-ONLY-SCANS-TYPES-TS.md`（同一段代码的两处病，归 `TYPE-04`）。

    所以本条改判**分类能力还在不在**：拿一个合成仓库跑一次，
    确认这把尺子**分得出**两类——而不是要求真仓库此刻恰好两类都有。
    """
    from tools.check_fe_be_parity import _best_interface

    kinds = {f.kind for f in parity(REPO)}

    # ## 这条判据的**真仓库那一半，第三次换值了**
    #
    # `TYPE-04` 修好尺子后两类都是零 → `GAUGE-14` 看清调用面后两类都非零
    # → `TYPE-05` 把 `field_mismatch` 那七条补完类型之后，它**又回到零**。
    #
    # 三次都不是尺子瞎了，而**每一次钉住当时那个值，都会让下一次正常的修复被判成错**。
    # 所以这里彻底不再钉真仓库的取值，改判**分类能力本身**——
    # 那才是这条判据从第一天起就想守的东西。
    #
    # 分类能力另有 `tests/v041/test_parity_dynamic_path.py` 的四条合成对照
    # （一个同名字段不算证据 / 分层按层算 / 杂字段不算一层 / 编出来的字段匹配不到接口）。
    assert kinds <= {
        "backend_unused_by_frontend", "frontend_wants_missing_backend",
        "field_mismatch", "frontend_untyped_response",
        "unscannable", "app_unbuildable",
    }, f"冒出了一个没登记的类别：{kinds}"

    # **两类分得开**：同一份响应键，声明齐了就该判成「有类型」，
    # 只声明一半就该判成「漂移」，一个都不像才是「没建类型」。
    keys = {"fact_id", "statement", "value", "unit", "citation_ids"}
    assert _best_interface(keys, {"x#Full": set(keys)})[0] == "x#Full"
    partial_best, partial_covered = _best_interface(
        keys, {"x#Half": {"fact_id", "statement"}})
    assert partial_best is not None and keys - partial_covered, "漂移那一类判不出来了"
    assert _best_interface(keys, {"x#Unrelated": {"a", "b"}})[0] is None, (
        "毫不相干的接口被当成了这条端点的类型")
    for ticket in ("PARITY-FIELD-NAMES-COMPARED-AS-ONE-FLAT-SET.md",
                   "PARITY-ONLY-SCANS-TYPES-TS.md"):
        lines = (REPO / "docs" / "blocked" / ticket).read_text(
            encoding="utf-8").splitlines()[:14]
        assert any("已关闭" in line for line in lines), f"{ticket} 还挂着"


def test_a_path_that_cannot_be_checked_statically_is_declared_not_dropped() -> None:
    """动态派发路径**扫不动**。扫不动就说扫不动——

    悄悄丢掉的话，这张表会被读成「全都核对过了」，而它没有。

    **`TYPE-04` 之后真仓库没有扫不动的了**：唯一那条
    `/projects/${id}/${kind}` 的 `kind` 是有限枚举（`JobKind` 三个成员），
    展开之后就是三条具体路径——**它从来不是判不动，是没人去展开它**。

    所以本条改判**机制还在**：那句「没有核对」的话术必须还在源码里，
    下一条真判不动的路径出现时才报得出来。
    行为层面的对照在 `tests/v041/test_parity_dynamic_path.py`
    （展不开的原样返回、联合里混进非字面量就整条放弃）。
    """
    findings = [f for f in parity(REPO) if f.kind == "dynamic_path_not_checked"]
    source = (REPO / "tools" / "check_fe_be_parity.py").read_text(encoding="utf-8")

    assert findings == [], (
        f"又有扫不动的了：{[f.subject for f in findings]}——"
        f"若能展开就去展开，展不开就确认它确实判不动"
    )
    assert "没有核对" in source, "那句话术没了，下一条判不动的路径就报不出来"
    assert "dynamic_path_not_checked" in source


def test_every_finding_says_where_to_look() -> None:
    for finding in parity(REPO):
        assert finding.where, finding.subject
        assert finding.kind in {
            "frontend_wants_missing_backend",
            "backend_not_assembled",
            "backend_unused_by_frontend",
            "field_mismatch",
            "frontend_untyped_response",
            "dynamic_path_not_checked",
            "app_unbuildable",
        }


# ───────────────────────── 七、对账表就是本卡的产品


def test_the_table_is_generated_from_a_real_run_not_hand_written() -> None:
    """表里的每一行都要能在扫描结果里找到对应——手写的行会立刻过时。"""
    table = Path("docs/前后端对账表-v041.md").read_text(encoding="utf-8")
    findings = parity(REPO)

    assert f"共 {len(findings)} 条" in table


def test_the_table_lists_every_finding() -> None:
    table = Path("docs/前后端对账表-v041.md").read_text(encoding="utf-8")

    for finding in parity(REPO):
        assert finding.subject in table, finding.subject


def test_the_renderer_marks_an_empty_report_as_empty_not_as_passing() -> None:
    """阴性对照：一条都没有时，表里要写「没扫到」而不是留白。

    留白与「扫过了、干净」在纸面上长得一模一样。

    判据钉的是**那句警告本身**（「不能被当成已对齐的证据」），不是「扫描面为空」
    这五个字——空报告那段解释文字里也写着这五个字，判它等于被邻居喂饱
    （变异⑭ 就是这么活下来的）。
    """
    rendered = render_table([], scanned={"backend": 0, "frontend": 0, "expected": 0})

    assert "共 0 条" in rendered
    assert "不能被当成" in rendered


def test_a_report_with_a_real_scan_surface_carries_no_such_warning() -> None:
    """反向对照：扫描面不空时，那句警告 NEVER 出现——出现就成了狼来了。"""
    rendered = render_table([], scanned={"backend": 9, "frontend": 3, "expected": 5})

    assert "不能被当成" not in rendered


def test_test_files_are_not_mistaken_for_frontend_calls(tmp_path: Path) -> None:
    """阴性对照：测试与 mock 里的样例 id 不是契约。

    扫进来的话，`/jobs/job-9` 这种样例会被报成「后端没有这条」——
    而它本来就不该有。变异⑨ 证明当时没有任何判据拦着这件事。
    """
    lib = tmp_path / "lib"
    lib.mkdir(parents=True)
    (lib / "real.ts").write_text("const a = `${b}/topics/${id}`;\n", encoding="utf-8")
    (lib / "real.test.ts").write_text('fetch("/jobs/job-9/events");\n',
                                      encoding="utf-8")
    (lib / "mock").mkdir()
    (lib / "mock" / "sample.ts").write_text('fetch("/plaza/hot?day=x");\n',
                                            encoding="utf-8")

    # 三条候选全给进去：真调用那条必须留下，测试与 mock 那两条必须被排掉。
    # **交集不是过滤器的全部**——把它们也放进路由表，才验得出「排掉」是真的。
    calls = frontend_calls(
        tmp_path, {"/topics/{}", "/jobs/{}/events", "/plaza/hot"})

    assert calls == {"/topics/{}"}


def test_the_renderer_never_swallows_a_finding() -> None:
    rendered = render_table(
        [Finding(kind="field_mismatch", subject="/x", where="a.py",
                 expected=["a"], actual=["b"], note="")],
        scanned={"backend": 1, "frontend": 1, "expected": 1})

    assert "/x" in rendered
    assert "共 1 条" in rendered


# ───────────────────────── 八、更正一处错误登记（acceptance④）


def _gap_doc_data_lines() -> list[str]:
    """登记文档里**陈述事实**的那些行。

    引文与更正说明（`>` 引用块、`- ` 条目）不算：更正一句错话时要把那句错话
    **引出来**，否则读的人不知道改的是什么。判据要判的是「还有没有人在陈述那句错话」，
    不是「这几个字还出不出现」——判后者会逼着更正说明写得含糊。
    """
    text = Path("docs/handoff_gap_v04.md").read_text(encoding="utf-8")
    return [
        line for line in text.splitlines()
        # 缩进行是上一条的续行（`- ` 条目常换行写），与它同属说明，不是数据行。
        if line.strip() and not line.startswith((">", "- ", " ", "\t"))
    ]


def test_the_handoff_gap_note_no_longer_claims_the_package_is_absent() -> None:
    """`docs/handoff_gap_v04.md` 原判「包不在本仓库」是错的——它只查了仓库根目录。"""
    text = Path("docs/handoff_gap_v04.md").read_text(encoding="utf-8")

    assert README.exists(), "包就在这儿"
    assert not [ln for ln in _gap_doc_data_lines() if "不在本仓库" in ln]
    assert "更正（AUDIT-01" in text, "改了就要说是谁改的、什么时候改的"
    assert "Claude design Flint 前端设计" in text, "更正后要写清它到底在哪"


def test_the_placeholder_numbers_were_replaced_with_measured_ones() -> None:
    """`[待核实]` 是「还没量」的标记。量过之后就不该再留在数据行上。"""
    assert not [ln for ln in _gap_doc_data_lines() if "[待核实]" in ln]


def test_the_measured_numbers_are_reproducible() -> None:
    """写进登记的数字要能被同一把尺子再量一次量出来。"""
    from tools.check_fe_be_parity import measure_handoff_package

    measured = measure_handoff_package(README.parent)
    text = Path("docs/handoff_gap_v04.md").read_text(encoding="utf-8")

    assert str(measured["screens"]) in text
    assert str(measured["tabular_nums"]) in text
    assert str(measured["warning_glyphs"]) in text


def test_the_measurement_counts_nothing_when_the_package_is_missing() -> None:
    """阴性对照：包不在时报 0 并说清，NEVER 报一个看起来像实测的数。"""
    from tools.check_fe_be_parity import measure_handoff_package

    measured = measure_handoff_package(Path("does/not/exist"))

    assert measured["present"] is False
    assert measured["screens"] == 0


def test_the_tool_is_runnable_from_the_command_line() -> None:
    import subprocess
    import sys

    done = subprocess.run(
        [sys.executable, "tools/check_fe_be_parity.py", "--json"],
        cwd=REPO, capture_output=True, text=True, encoding="utf-8", check=False)

    assert done.returncode in (0, 1)
    assert done.stdout.lstrip().startswith(("{", "[")), done.stdout[:200]
    assert not re.search(r"[^\s]", done.stdout.split("\n")[0].replace(
        done.stdout.split("\n")[0].strip(), ""))
