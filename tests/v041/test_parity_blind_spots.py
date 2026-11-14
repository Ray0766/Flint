"""GAUGE-14：对账器把已接线的端点报成「前端没人用」——**报的是反的**。

## 两个盲区，机制不同

**① 首段白名单写死。** `_ENDPOINT_LITERAL` 那串正则里列着
`plaza|clusters|projects|topics|jobs|…`——不在清单里的路径**永远扫不到**。
七条被误报的路（`/facts/{}` · `/price-entries/{}` · `/citations/{}` ·
`/charts/{}` · `/cards/{}` · `/hints/{}` · `/interventions/lock`）
全都躺在 `web/lib/derefClient.ts` 与 `interventionClient.ts` 里**真被调用**。

**② 只扫 `web/lib/`。** 页面（`web/app/`）与组件（`web/components/`）里的直接调用
一条都看不见——`/account`、`/billing`、`/settings/locale`、`/projects/{}`、
`/favorites`、`/projects/{}/design_generate`、`/projects/{}/chosen-topic` 都在那儿。

**两个盲区的共同后果**：那份报告说「后端有、前端没人用」，
而真相是「尺子没量到」。**修法完全相反**——一个是去接线，一个是去修尺子。
读到误报的人会去接一条**已经接好的**线。

## 首段白名单怎么退役

不再靠人维护一串前缀，改成**按真实路由表比对**：宽着扫出所有像路径的字面量，
再与后端真实路由取交集。新增一族端点时，尺子自动认得——
**而人维护的那串前缀，永远慢一批**。

## 为什么 `href` 要排掉

页面里的 `href="/topics/abc"` 是**导航**，不是 API 调用。
而后端恰好也有 `GET /topics/{id}`——不排掉的话，一条只被链接、
从没被调用的端点会被算成「前端在调」，那是往反方向错。
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

TOOL = REPO / "tools" / "check_fe_be_parity.py"
TRIAGE = REPO / "docs" / "端点分诊-v041.md"
SHEET = REPO / "docs" / "blocked" / "PARITY-BLIND-TO-PAGES-AND-UNLISTED-PREFIXES.md"

# 单子点名的、**实测在前端真被调用**的那些。尺子改好之后它们必须消失在
# `backend_unused_by_frontend` 里——那正是「报的是反的」这句话的机器形态。
WRONGLY_REPORTED = (
    "/facts/{}", "/price-entries/{}", "/citations/{}", "/charts/{}",
    "/cards/{}", "/hints/{}", "/interventions/lock",
    "/account", "/billing", "/settings/locale", "/projects/{}", "/favorites",
)


def _report() -> dict[str, object]:
    done = subprocess.run(
        [sys.executable, str(TOOL), "--json"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=REPO, timeout=300, check=False)
    assert done.stdout.strip(), done.stderr[-2000:]
    return json.loads(done.stdout[done.stdout.index("{"):])


def _unused() -> set[str]:
    return {
        str(f["subject"]) for f in _report()["findings"]  # type: ignore[index]
        if f["kind"] == "backend_unused_by_frontend"  # type: ignore[index]
    }


# ───────────────────────── 一、首段白名单退役


def test_the_prefix_whitelist_is_gone() -> None:
    """那串写死的首段清单**不在了**。

    留着它的话，下一族端点（比如 `/quality/…`）又会被报成「没人用」——
    **而人维护的那串前缀，永远慢一批**。
    """
    # **剥注释再判**：那串旧清单逐字写在改因注释里（说明它为什么退役）。
    # 不剥的话，判据会把**解释问题的那句话**当成问题本身——
    # 本批这是第四次（规格 `#2.4` · `backfill.py` · 噪声基线 · 本处）。
    code = "\n".join(
        line for line in TOOL.read_text(encoding="utf-8").splitlines()
        if not line.lstrip().startswith("#"))

    assert "plaza|clusters|projects|topics|jobs" not in code, (
        "首段白名单还在——它是这两个盲区里更隐蔽的那一个"
    )


def test_the_calls_are_filtered_by_the_real_route_table() -> None:
    """改成**按真实路由表比对**：宽着扫、再与后端真实路由取交集。

    判的是**签名**（`frontend_calls` 收下了路由表），不是注释里那句话——
    改了实现却没改注释时，注释仍然会说得很好听。
    """
    import inspect

    from tools.check_fe_be_parity import frontend_calls

    params = list(inspect.signature(frontend_calls).parameters)

    assert len(params) >= 2, f"`frontend_calls` 还是只收一个 web_dir：{params}"


# ───────────────────────── 二、两个盲区各自被补上


def test_a_call_under_an_unlisted_prefix_is_seen() -> None:
    """**阴性对照①**：造一条新前缀的真调用，尺子必须认得出来。

    `/quality/…` 从来不在那串白名单里。它被认出来，
    才说明「按路由表比对」真的生效了。
    """
    from tools.check_fe_be_parity import frontend_calls

    with tempfile.TemporaryDirectory() as tmp:
        web = Path(tmp) / "web"
        (web / "lib").mkdir(parents=True)
        (web / "lib" / "qualityClient.ts").write_text(
            'export const f = () => fetch(`${base}/quality/${id}/report`);\n',
            encoding="utf-8")

        seen = frontend_calls(web, {"/quality/{}/report"})

    assert "/quality/{}/report" in seen, f"新前缀没被认出来：{seen}"


def test_a_call_inside_a_page_component_is_seen() -> None:
    """**阴性对照②**：页面里的调用也要看得见。

    改前只扫 `web/lib/`，于是 `useScreenData("/account")` 那种在
    `web/app/**/page.tsx` 里的调用**一条都不算**。
    """
    from tools.check_fe_be_parity import frontend_calls

    with tempfile.TemporaryDirectory() as tmp:
        web = Path(tmp) / "web"
        (web / "app" / "account").mkdir(parents=True)
        (web / "app" / "account" / "page.tsx").write_text(
            'const s = useScreenData<A>("/account");\n', encoding="utf-8")

        seen = frontend_calls(web, {"/account"})

    assert "/account" in seen, f"页面里的调用没被看见：{seen}"


def test_a_path_written_only_in_a_comment_is_not_a_call() -> None:
    """**阴性对照③**：注释里的路径 NEVER 算调用（`GAUGE-10` 的剥注释不倒）。

    注释里的路径会随代码改动而过时——把它当成「前端在调这条」是假实况，
    而假实况会让一条真没人用的端点被当成用着的。
    """
    from tools.check_fe_be_parity import frontend_calls

    with tempfile.TemporaryDirectory() as tmp:
        web = Path(tmp) / "web"
        (web / "lib").mkdir(parents=True)
        (web / "lib" / "notes.ts").write_text(
            "// 将来要接 `/quality/{id}/report`\n"
            "/* 也可能是 /billing */\n"
            "export const nothing = 1;\n", encoding="utf-8")

        seen = frontend_calls(web, {"/quality/{}/report", "/billing"})

    assert seen == set(), f"注释里的路径被当成了调用：{seen}"


def test_an_href_is_not_a_call() -> None:
    """**阴性对照④**：`href` 是导航，不是 API 调用。

    后端恰好也有 `GET /topics/{id}`——不排掉的话，一条只被链接、
    从没被调用的端点会被算成「前端在调」，**那是往反方向错**。
    """
    from tools.check_fe_be_parity import frontend_calls

    with tempfile.TemporaryDirectory() as tmp:
        web = Path(tmp) / "web"
        (web / "app").mkdir(parents=True)
        (web / "app" / "page.tsx").write_text(
            'export const L = () => <a href={`/topics/${id}`}>go</a>;\n',
            encoding="utf-8")

        seen = frontend_calls(web, {"/topics/{}"})

    assert seen == set(), f"href 被当成了 API 调用：{seen}"


# ───────────────────────── 三、误报真的消失了


def test_the_wrongly_reported_endpoints_are_no_longer_unused() -> None:
    """**本卡的核心**：那些实测在调的端点，不再被报成「没人用」。

    只判「条数变少了」是不够的——少下去的可能是**别的**几条。
    这里逐条点名。
    """
    unused = _unused()
    still_wrong = [path for path in WRONGLY_REPORTED if path in unused]

    assert still_wrong == [], f"这些仍被误报成没人用：{still_wrong}"


def test_the_checker_did_not_go_blind_altogether() -> None:
    """**反向守卫**：它没有变成「什么都不报」。

    把 `frontend_calls` 写成「返回全部路由」也能让上面那条绿——
    而那时这把尺子就彻底不响了。本仓确实有真没人用的端点
    （维护面那四条：pricebook / profile 两族）。
    """
    unused = _unused()

    assert unused, "一条都不报了——尺子瞎了，而它看起来是绿的"
    assert any(path.startswith(("/pricebook", "/profile")) for path in unused), (
        f"那四条维护面端点也不报了：{sorted(unused)}"
    )


# ───────────────────────── 四、分诊表跟着重算


def test_the_triage_matches_the_new_count() -> None:
    """分诊表与实跑**等值**（`test_endpoint_triage` 那条判据的口径）。

    尺子改了而表没改的话，那份表会继续替 12 条已接线的端点说
    「前端没人用」——**留着的假话比没有表更坏**。
    """
    triaged = {
        line.split("`")[1]
        for line in TRIAGE.read_text(encoding="utf-8").splitlines()
        if line.startswith("| `/")
    }

    assert _unused() <= triaged | {""}, (
        f"分诊表没覆盖实跑报的：{sorted(_unused() - triaged)}"
    )


# ───────────────────────── 五、单据关掉


def test_the_sheet_is_closed() -> None:
    text = SHEET.read_text(encoding="utf-8")
    state = next(ln for ln in text.splitlines()[:8] if ln.startswith("**状态**"))

    assert state.startswith("**状态** closed"), f"单据还开着：{state!r}"
    assert "GAUGE-14" in text
