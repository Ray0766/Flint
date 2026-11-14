"""NAV-04：顶栏只有两项——四个无参屏建好之后没人回来加过入口。

## 改前的实况（本卡复核过）

`AppShell` 的 `NAV_ITEMS` 只有 `/plaza` 与 `/demo`。而盘上无参可达的屏有六个：
`/account`（UI-04）· `/favorites`（FAV-06）· `/design`（DESIGN-02）
· `/settings/locale`（I18N-08）也都建好了，**只能手敲 URL**。

`AppShell` 文件头一直守着一条纪律：「NEVER 编造一排链接来把顶栏填满」。
那条守的是**入口点不开**，而实际发生的是另一种毛病：**屏没有入口**。
两者的修法相反，而在报告上都显示为「顶栏很干净」。

## 账户位：那句「接口未提供」是**写死的**，而它已经过期

`WIRE-01` 把 `GET /account` 挂上之后，账户屏真的在取数（四态各自显示）。
顶栏没有任何办法知道那四态里是哪一态——**写死其中一态就是说谎**。
所以本卡把它改成一个真入口：`入口照常给，状态归屏说`。

## `/demo` 留下，理由在 `AppShell.tsx` 文件头写着

它是演示串屏、不是产品屏（屏对照表 §四 已登记）。留着是因为
**它今天是唯一能看到整条链路怎么走的地方**；撤它的条件也一并写了，
免得下一个人再判一次。
"""
from __future__ import annotations

import json
import re
import subprocess
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
WEB = REPO / "web"
SHELL = WEB / "components" / "shell" / "AppShell.tsx"
CSS = WEB / "app" / "globals.css"
GRAPH = REPO / "assets" / "screen_graph.json"
ZH = WEB / "messages" / "zh.json"
EN = WEB / "messages" / "en.json"
ARTIFACT = REPO / ".ui-probe" / "nav04_shell.json"

PWENV = Path(r"C:\pwenv\Scripts\python.exe")
PLAZA_URL = "http://localhost:3000/plaza"

# 顶栏该有的常驻入口。**判等值**：多一项、少一项都要有人回到这里确认。
#
# `WB-01` / `DEC-059` 加了第 7 项 `/workbench`（计划书主工作台）。
# 它**新增**而不是替换——`/design` 那一项还在这份名单里，一个字没动，
# 而这条判等值的判据正是「没被替换掉」的签字。
WANTED = {"/plaza", "/favorites", "/design", "/settings/locale", "/account", "/demo",
          "/workbench"}

# 无参屏里**不进顶栏**的那些，每一条写明从哪进来。
# `NEVER 让一个无参屏既不在顶栏、也没有别的入口，而判据一声不吭`——
# 那正是改前四屏的处境。
NOT_IN_BAR = {
    # NAV-04 的决定（卡上原话「账户屏或顶栏（NAV-04 决定）」）：**账户屏**。
    # 它是账户的一部分，放进顶栏会让一个二级页面与「热点广场」平级。
    "/billing": "/account",
    # 它仍然**不该从顶栏进**：没带 cluster id 进去是一屏「你怎么走到这儿的」。
    # 它要从广场带着选中的卡进来——`ENTRY-04` 把「多选卡片建组合」这个**功能**
    # 建出来了，于是它今天从 `/plaza` 进得来，`ENTRY-05` 把那条边声明进了图。
    #
    # 这一格从 `None` 变成 `/plaza`，靠的是那个功能真的被做出来了，
    # **NEVER 是靠给它硬塞一个顶栏入口**——那正是这条判据一直在拦的事。
    "/combo": "/plaza",
}


def _code_only(path: Path) -> str:
    text = re.sub(r"/\*[\s\S]*?\*/", "", path.read_text(encoding="utf-8"))
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("//")
    )


def _static_routes() -> set[str]:
    """无参可达的屏——顶栏能链过去的全部候选。"""
    from tools.check_reachability import app_routes

    return {r for r in app_routes() if "[" not in r}


# ───────────────────────── 一、四条入口补上了


def test_the_top_bar_lists_every_static_screen() -> None:
    """**双向判**：顶栏里的每一项都是真屏，且每一个无参屏都在顶栏里。

    只判前一半的话（既有那条纪律），把顶栏清空也能拿到一个「零个坏链接」的绿——
    而那正是改前的实况。
    """
    from tools.check_reachability import nav_items

    items = set(nav_items())

    assert items == WANTED, f"多出 {sorted(items - WANTED)}，少了 {sorted(WANTED - items)}"

    # 不在顶栏的无参屏**必须逐条有交代**：要么从别处进来，要么明说它还没有入口。
    unaccounted = _static_routes() - items - set(NOT_IN_BAR)
    assert unaccounted == set(), (
        f"这些无参屏既不在顶栏、也没写从哪进来：{sorted(unaccounted)}")


def test_the_screens_kept_off_the_bar_are_accounted_for_one_by_one() -> None:
    """不进顶栏的那两屏，一条真接上了，一条**照实留在孤岛名单里**。

    `/billing` → 从账户屏进（NAV-04 的决定）。
    `/combo` → 没有入口，**而这不是遗漏**：它要从广场带着选中的卡进来，
    「多选卡片建组合」是广场上还没有的能力——那是一个功能，不是一条链接。
    硬塞一个顶栏入口的话，用户点进去会落在一屏「你怎么走到这儿的」。

    **NEVER 用一个点得到但没用的入口把孤岛名单做小。**
    """
    from tools.check_reachability import check

    report = check()

    for route, comes_from in NOT_IN_BAR.items():
        if comes_from is None:
            assert route in report.islands, (
                f"{route} 说没有入口，尺子却说它可达——两句话有一句是假的")
            continue
        assert route in report.reachable, f"{route} 说从 {comes_from} 进，而走不到"
        screen = next(
            s for s in json.loads(GRAPH.read_text(encoding="utf-8"))["screens"]
            if s["route"] == route)
        assert any(e["from"] == comes_from for e in screen["reached_by"])


def test_every_nav_item_points_at_a_screen_that_exists() -> None:
    """点不开的入口比没有入口更坏——它把「还没做」伪装成「做完了」。"""
    from tools.check_reachability import app_routes, nav_items

    routes = set(app_routes())
    for href in nav_items():
        assert href in routes, f"顶栏里 {href} 在 web/app 下没有对应的屏"


def test_the_visible_and_the_reachable_agree() -> None:
    """出现在顶栏的每一项 MUST 在 `NAV-01` 的图里连得上。

    图里凭空多一个入口，遍历会从一个屏上根本没有的地方出发；
    顶栏上真有的入口没进图，图会低报可达面。**两个方向都报。**
    """
    from tools.check_reachability import check, nav_items

    report = check()

    assert report.entry_mismatches == [], report.entry_mismatches
    assert sorted(nav_items()) == sorted(report.entries)
    for href in nav_items():
        assert href in report.reachable, f"顶栏里有 {href}，而图上走不到它"


# ───────────────────────── 二、账户：入口照常给，状态归屏说


def test_the_account_entry_is_given_even_though_the_data_may_be_missing() -> None:
    """`NEVER 因为后端没数据就把入口藏起来`——藏起来的话用户不知道有这个能力。"""
    from tools.check_reachability import nav_items

    assert "/account" in nav_items()


def test_the_top_bar_no_longer_hardcodes_one_of_the_four_states() -> None:
    """顶栏那句写死的「接口未提供」删掉了。

    `WIRE-01` 挂上 `GET /account` 之后它就成了假的：端点在，屏真的在取数，
    而顶栏没有办法知道四态里是哪一态。**写死其中一态就是说谎。**

    注意这不是「删掉一个诚实态」——诚实态一条都不许删（`FB-10` 的分界）。
    删的是**说这句话的地方站错了**：账户屏自己四态齐全，那里说才说得准。
    """
    code = _code_only(SHELL)

    assert "NotProvided" not in code, "顶栏还在替账户屏说状态"
    assert "app-shell__account" not in code
    # 那一格的样式一起退役——留着会让下一个人以为它还在。
    assert ".app-shell__account {" not in CSS.read_text(encoding="utf-8")


def test_the_account_screen_still_tells_the_truth_about_its_four_states() -> None:
    """状态归屏说，所以屏那边**必须还在说**。

    这条与上一条是一对：只删顶栏那句而屏上也不说，就成了把诚实态删掉。
    """
    panel = _code_only(WEB / "components" / "account-billing" / "AccountPanel.tsx")

    for state in ("not_checked", "no_record"):
        assert state in panel, f"账户屏不再分 {state} 这一态"


# ───────────────────────── 三、/demo 的去留，理由写下来了


def test_the_fate_of_demo_is_decided_with_a_reason() -> None:
    """卡上要求：**本卡决定 `/demo` 留不留在顶栏，决定写进 trace 并给理由**。

    这里判的是理由**在代码里也写着**——只写在 trace 的话，
    下一个改顶栏的人不会去翻 trace，于是要么误删要么再判一次。
    撤它的条件也要写：没有条件的「暂时留着」等于永远留着。
    """
    from tools.check_reachability import nav_items

    assert "/demo" in nav_items(), "本卡的决定是留下（理由见 AppShell.tsx 文件头）"

    head = SHELL.read_text(encoding="utf-8")
    assert "演示串屏" in head and "NAV-05" in head, "没写清留它的理由与撤它的条件"

    graph = json.loads(GRAPH.read_text(encoding="utf-8"))
    demo = next(e for e in graph["entries"] if e["route"] == "/demo")
    assert "撤" in demo["why"], "图上没记撤它的条件"


# ───────────────────────── 四、文案


def test_the_new_nav_copy_is_keyed_in_both_languages() -> None:
    zh = json.loads(ZH.read_text(encoding="utf-8"))
    en = json.loads(EN.read_text(encoding="utf-8"))

    for key in ("shell.nav.favorites", "shell.nav.design",
                "shell.nav.locale", "shell.nav.account"):
        assert key in zh, f"zh 缺 {key}"
        assert key in en, f"en 缺 {key}"
        assert zh[key] != en[key], f"{key} 中英同文——有一侧没翻"


def test_no_hardcoded_chinese_in_the_shell() -> None:
    for literal in re.findall(r'"([^"]*)"', _code_only(SHELL)):
        assert not re.search(r"[一-鿿]", literal), f"顶栏里有裸中文：{literal!r}"


# ───────────────────────── 五、390px：顶栏不溢出（FIX-05/06 的既有判据不倒）


_RUNNER = r"""
import json, sys
from playwright.sync_api import sync_playwright

out, url = sys.argv[1], sys.argv[2]
got = {}
with sync_playwright() as p:
    b = p.chromium.launch()
    page = b.new_page(viewport={"width": 390, "height": 844})
    errs = []
    page.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_selector(".app-shell__nav-link", timeout=30000)

    got["links"] = page.eval_on_selector_all(
        ".app-shell__nav-link",
        "els => els.map(e => ({href: e.getAttribute('href'),"
        " w: e.getBoundingClientRect().width,"
        " h: e.getBoundingClientRect().height,"
        " right: e.getBoundingClientRect().right}))")
    got["doc_scroll_width"] = page.evaluate("document.documentElement.scrollWidth")
    got["viewport"] = 390
    got["bar_scroll_width"] = page.eval_on_selector(
        ".app-shell__bar", "e => e.scrollWidth")
    got["bar_client_width"] = page.eval_on_selector(
        ".app-shell__bar", "e => e.clientWidth")
    got["console_errors"] = errs
    page.screenshot(path=".ui-probe/nav04-shell-390.png")
    b.close()
open(out, "w", encoding="utf-8").write(
    json.dumps({"schema": "nav04/1", **got}, ensure_ascii=False, indent=1))
"""


#: 这份取证一旦落盘就不再重跑——所以它 MUST 记下**自己量的是哪一版屏**。
#: 顶栏的样子由这两个文件决定；它们变了，缓存就是上一版屏的照片。
_INPUTS = (SHELL, CSS)


def _inputs_stamp() -> str:
    """顶栏那两个输入文件的内容指纹。"""
    import hashlib

    h = hashlib.sha256()
    for path in _INPUTS:
        h.update(path.read_bytes())
    return h.hexdigest()[:16]


def _artifact() -> dict[str, object]:
    """取这份真浏览器取证；**输入变了就重拍**。

    ## 这一段为什么改（`WB-01` 现场逮到的）

    改前只判 `ARTIFACT.exists()`：缓存在就直接用。
    于是 `NAV-ANIME-01` 把顶栏换成固定的药丸条之后，
    这条判据一直在量**药丸条之前那一版**的照片——
    而真实的 390 屏上，6 项里最右两项早已排到了 x=471，屏外。

    看不见的原因是双重的：条是 `position: fixed`，fixed 元素的溢出
    **不会**把文档 `scrollWidth` 撑大，所以「零横向溢出」也是绿的。
    **两条判据同时说没事，而屏上有两项点不到。**

    `WB-01` 加第 7 项时它才现形。修法不是「记得手动删缓存」——
    那是把纪律寄托在记性上；改成**指纹对不上就自动重拍**。
    """
    if ARTIFACT.exists():
        cached = json.loads(ARTIFACT.read_text(encoding="utf-8"))
        if cached.get("inputs_stamp") == _inputs_stamp():
            return dict(cached)
        # 指纹对不上 = 顶栏改过了，这份照片作废。
        ARTIFACT.unlink()
    if not PWENV.exists():
        pytest.skip(f"本机没有 {PWENV}（playwright 恒在项目外，NEVER 进项目依赖）")
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        runner = Path(tmp) / "nav04_runner.py"
        runner.write_text(_RUNNER, encoding="utf-8")
        done = subprocess.run(
            [str(PWENV), str(runner), str(ARTIFACT), PLAZA_URL],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=REPO, check=False)
    if done.returncode != 0:
        pytest.skip(f"前端没起或探针跑不动：{done.stderr[-600:]}")
    got = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    # 指纹在**拍完之后**盖：拍之前盖的话，探针失败时会留下一份
    # 「指纹对得上而内容是旧的」缓存——比没有缓存更坏。
    got["inputs_stamp"] = _inputs_stamp()
    ARTIFACT.write_text(json.dumps(got, ensure_ascii=False, indent=1), encoding="utf-8")
    return dict(got)


def test_all_seven_entries_are_on_the_bar_in_a_real_browser() -> None:
    """源码层判得出「清单里有几项」，判不出「屏上看得见几项」。

    改名自 `test_all_six_entries_are_on_the_bar_in_a_real_browser`：
    `WB-01` 加了第 7 项。**这条判据靠一份落盘的取证缓存**
    （`.ui-probe/nav04_shell.json`），缓存在就不重跑——
    所以改了导航之后要把那份缓存删掉，否则它量的是上一版的屏。
    """
    links = _artifact()["links"]

    assert {row["href"] for row in links} == WANTED
    for row in links:
        assert row["w"] > 20 and row["h"] > 10, f"{row['href']} 几乎没有面积：{row}"


def test_the_bar_does_not_overflow_at_390() -> None:
    """`FIX-05/06` 的既有判据不倒：**390px 下横向不溢出**。

    六项排一行放不下——`.app-shell__nav` 的 `flex-wrap: wrap` 让它折行。
    折行是对的，横向滚出去不是：顶栏滚出去的那几项，用户根本不知道它们在。
    """
    got = _artifact()

    assert got["doc_scroll_width"] <= got["viewport"], (
        f"整页横向溢出：scrollWidth {got['doc_scroll_width']} > 390")
    assert got["bar_scroll_width"] <= got["bar_client_width"] + 1, (
        f"顶栏自己横向溢出：{got['bar_scroll_width']} > {got['bar_client_width']}")
    for row in got["links"]:
        assert row["right"] <= 390.5, f"{row['href']} 右边缘跑到了 {row['right']}"


def test_the_bar_is_clean() -> None:
    assert _artifact()["console_errors"] == [], _artifact()["console_errors"]
