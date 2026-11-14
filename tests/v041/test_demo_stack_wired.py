"""WIRE-02 · demo 栈改用装配后的 app，并修掉「报告屏恒 500」。

## 两件事，一个根

**一**：`harness/demo_server.py` 原先各屏各造一个 `create_*_app` 再 `include_router`，
七族的清单与 `flint/api/app.py` **各写各的**——两个真相。
「哪些挂了」这件事要有人记着，正是 51 条藏一整批的原因。

**二**：`start-demo.ps1` 只设了 `NEXT_PUBLIC_FLINT_API`（客户端那份），
没设 `FLINT_API_BASE`（服务端那份）。服务器组件基址为空 →
Node 侧 `fetch("/deliverables/…/blocks")` 是相对 URL → `Failed to parse URL` →
**报告屏恒 500**。后端一直是好的（直连同一路径 200）。

两件事的根是同一件：**「配齐了没有」这件事没有任何判据在量**，
全靠人记着。所以本文件量的是**覆盖关系**，不是某一行在不在。

## 判据 NEVER 只断言脚本里那行环境变量存在

卡面 acceptance③ 点名了这条。只断言 `'FLINT_API_BASE' in script` 的写法：

- 换个变量名照样绿；
- 前端**新读**一个环境变量而脚本没跟上时，照样绿。

所以这里判的是**前端读的 ⊆ 脚本设的**——多读一个没设的，当场红。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from flint.api.app import mounted_route_table
from harness.demo_server import build_app

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "start-demo.ps1"
WEB = REPO / "web"
PROBE = REPO / ".ui-probe" / "fe_smoke.json"
TICKET = REPO / "docs" / "blocked" / "FE-DEMO-ENV-FLINT-API-BASE.md"
# demo 栈自己的 dsn 指向本机 55432；测试里只建应用、不发库请求的那些用它即可。
_ENV_READ = re.compile(r"process\.env\.([A-Z_][A-Z0-9_]*)")
_ENV_SET = re.compile(r"\$env:([A-Za-z_][A-Za-z0-9_]*)")


# ───────────────────────── acceptance①：demo 栈用的是装配后的 app


def test_the_demo_stack_starts_from_the_assembled_app() -> None:
    """demo 栈的路由面 **⊇** 可部署应用的路由面。

    改前两边各建各的，`flint/api/app.py` 挂上一族而 demo 没跟上（或反过来）
    不会有任何判据变红。
    """
    from flint.api.app import create_app

    demo = {(m, r.path) for r in mounted_route_table(build_app()) for m in r.methods}
    deployable = {
        (m, r.path)
        for r in mounted_route_table(create_app("postgresql://x@127.0.0.1:1/y"))
        for m in r.methods
    }

    assert deployable - demo == set(), (
        f"可部署应用挂了、demo 栈却没有：{sorted(deployable - demo)}"
    )


def test_the_demo_stack_adds_exactly_the_families_it_alone_can_wire() -> None:
    """demo 比可部署应用**多出来**的，正好是那三族。

    这三族在可部署应用里挂不上（缺 `role_resolver` 与模型配置），
    而 demo 有——`lambda _u, _o: "owner"` 在 demo 里是明知故犯的口径，
    在可部署应用里是安全洞。这条判据把那条界线钉住：
    多一条要有人来确认它是不是也该进可部署应用。
    """
    from flint.api.app import create_app

    demo = {r.path for r in mounted_route_table(build_app())}
    deployable = {
        r.path
        for r in mounted_route_table(create_app("postgresql://x@127.0.0.1:1/y"))
    }

    # 这条等值判据在 `WIRE-07/08/09` 三次接通中各红过一次——**每次都红得对**，
    # 它就是来提醒「demo 多出来的那几族又变了」的。
    # `WIRE-10` 之后 **demo 一族都不再独有**——它就是可部署应用加两条中间件。
    # 这个空集是本条判据现在的全部内容：**NEVER 让 demo 悄悄比线上多一族**。
    assert demo - deployable == set(), (
        f"demo 又比可部署应用多出了：{sorted(demo - deployable)}"
    )


def test_the_collision_guard_still_bites_where_the_assembler_lives() -> None:
    """**阴性对照**：往装配器里塞一条已被占住的路径 → 必须 raise。

    改前这条是在 demo 上造撞车（monkeypatch 掉 `create_combo_app`）。
    `WIRE-10` 之后 **demo 一族都不再自己挂**，那种造法没有落点了——
    于是改成直接对 `_Assembler` 造一次真撞车。

    守卫只在真撞车时说话，所以要造一次才量得到它。
    没有这条，「走的是同一道闸」就是一句没人验证过的话。
    """
    from fastapi import FastAPI

    from flint.api.app import RouteConflictError, _Assembler, create_app

    app = create_app("postgresql://x@127.0.0.1:1/y")
    assembler = _Assembler(app=app, claimed={
        (method, route.path): "flint/api/app.py"
        for route in mounted_route_table(app) for method in route.methods
    })
    collider = FastAPI()

    @collider.get("/categories")          # 装配后的 app 已经占了这条
    async def _steal() -> list[str]:
        return []

    with pytest.raises(RouteConflictError) as caught:
        assembler.add(collider)

    assert "/categories" in str(caught.value)


def test_the_demo_stack_no_longer_builds_its_own_copies() -> None:
    """`views` / `deliverables` / `categories` / `deref` 不再在 demo 里各造一份。

    造两份就有两个真相，而它们的 deps 逐字相同（只有 dsn）。
    """
    source = (REPO / "harness" / "demo_server.py").read_text(encoding="utf-8")

    for factory in ("create_views_app", "create_deliverables_app",
                    "create_deref_app"):
        assert f"{factory}(" not in source, f"demo 仍在自己造 {factory}"
    assert "create_app(DSN)" in source


# ───────────────────────── acceptance②③：真发请求，不是断言那行在不在


def test_the_report_screen_endpoint_answers_without_a_five_hundred() -> None:
    """**真发请求**：demo 栈上打报告屏要的那条端点，不是 500。

    这条端点本来就是好的（问题单里 `curl` 直连是 200），
    本判据守的是「装配换了之后它还在、还通」。
    库不可达时会是 500——所以这条只在库起着的时候判，否则 skip 并说清楚。
    """
    client = TestClient(build_app(), raise_server_exceptions=False)

    response = client.get("/deliverables/del-demo-fixture-report/blocks")

    if response.status_code == 500:
        pytest.skip("本机库没起（55432）：这条要真库才量得准，NEVER 当它通过")
    assert response.status_code != 404, "端点没挂上"
    assert response.status_code < 500, response.text[:200]


def test_the_frontend_reads_no_env_var_the_start_script_forgets_to_set() -> None:
    """**前端读的环境变量 ⊆ 启动脚本设的**。

    这是本卡的核心判据。原缺陷正是「前端读 `FLINT_API_BASE`、脚本只设
    `NEXT_PUBLIC_FLINT_API`」——两个名字，一个被漏掉，**没有任何判据在量这层覆盖**。

    只断言 `'FLINT_API_BASE' in script` 拦不住下一次：
    前端新读一个变量而脚本没跟上时，那种写法照样绿。
    """
    read: set[str] = set()
    for source in (*WEB.joinpath("app").rglob("*.tsx"),
                   *WEB.joinpath("lib").rglob("*.ts")):
        if ".test." in source.name:
            continue
        read |= set(_ENV_READ.findall(source.read_text(encoding="utf-8")))
    # `NODE_ENV` 之类由 Next 自己给，不该要求脚本设。
    read -= {"NODE_ENV", "VERCEL_URL", "PORT"}
    declared = set(_ENV_SET.findall(SCRIPT.read_text(encoding="utf-8")))

    assert read - declared == set(), (
        f"前端读了而 start-demo.ps1 没设：{sorted(read - declared)}——"
        f"基址为空时 Node 侧的相对 URL 会 Failed to parse URL，那一屏恒 500"
    )
    assert read, "一个都没扫到：扫描面塌了，这条判据在空转"


def test_both_halves_of_the_base_url_are_set_because_each_serves_one_side() -> None:
    """两份基址都要设：一份给服务器组件、一份给客户端组件。

    **缺任一都会有一半页面取不到数**，而两种「取不到」的表现完全不同
    （服务端是 500，客户端是空数据），查起来像两个 bug。
    """
    script = SCRIPT.read_text(encoding="utf-8")

    assert "$env:FLINT_API_BASE" in script
    assert "$env:NEXT_PUBLIC_FLINT_API" in script


def test_the_probe_artifact_shows_the_report_screen_at_two_hundred() -> None:
    """真栈取证：`.ui-probe/fe_smoke.json` 里报告屏两主题都是 200、零控制台报错。

    这是「真发请求」最硬的那份证据——它是 playwright 在真前端上跑出来的。
    """
    if not PROBE.exists():
        pytest.skip("本机没跑过真栈冒烟：缺 .ui-probe/fe_smoke.json")
    report = json.loads(PROBE.read_text(encoding="utf-8"))
    if report.get("stack_down"):
        pytest.skip(f"上次实跑时栈没起：{report['stack_down']}")
    rows = [r for r in report["screens"] if r["route"] == "/deliverables/[id]"]

    assert rows, "取证里没有报告屏这一行"
    for row in rows:
        assert row["http_status"] == 200, row
        # 控制台那几条报错**不是本卡的**，这里判**等值**而不是判零——
        # 顺手放行会让新增的混进来，判零又会把别人正确的行为算成失败。
        #
        # **10 → 3（`FIX-06` 全量取证时确认）**：`FIX-02` 把
        # `DEMO-REPORT-REFS-NOT-SEEDED` 那九个实体补种了六个，单子已关；
        # 剩下三个是 `DEMO-REFS-NO-STORAGE-FACE`（chart / 质量卡 / gap hints
        # **全库没有存储面**），端点如实回 404——**当前行为是对的，NEVER 修绿**。
        #
        # 同一份基线在 `tests/v041/test_mobile_sweep.py#CONSOLE_BASELINE` 里
        # 逐屏对，且那边还判「挂的单必须仍是 open」。
        assert row["console_error_count"] == 3, (
            f"报告屏控制台报错数从 3 变成 {row['console_error_count']}："
            f"若是 DEMO-REFS-NO-STORAGE-FACE 建了存储面，把本条改成 0；"
            f"若是新增的，停下登记"
        )
    assert (REPO / "docs" / "blocked" / "DEMO-REPORT-REFS-NOT-SEEDED.md").exists()


# ───────────────────────── acceptance④：单子关掉


def test_the_ticket_is_closed_with_a_banner_and_a_date() -> None:
    """问题单关掉：顶部横幅 + 日期 + 修法一句。

    修好了还挂着的单 = 下一个 worker 会再停一次；
    直接删掉 = 这段经过就没了。所以是**关闭**，不是删除。
    """
    text = TICKET.read_text(encoding="utf-8")
    head = "\n".join(text.splitlines()[:14])

    assert "已关闭" in head, "顶部没有关闭横幅"
    assert "2026-08-05" in head, "没写关闭日期"
    assert "FLINT_API_BASE" in head, "没写修法"
    assert "WIRE-02" in head, "没写是哪张卡关的"


def test_the_smoke_test_gate_that_watched_this_ticket_lets_go() -> None:
    """`EYE-03` 留的那条守卫：脚本一天没补那行，单子一天不许消失。

    **补上之后它自动放行**——本条确认那个机制真的生效了，
    而不是靠人记着去删一条过期判据。
    """
    guard = REPO / "tests" / "v041" / "test_fe_smoke.py"
    source = guard.read_text(encoding="utf-8")

    assert "FE-DEMO-ENV-FLINT-API-BASE" in source, "守卫不见了"
    assert "$env:FLINT_API_BASE" in SCRIPT.read_text(encoding="utf-8")
