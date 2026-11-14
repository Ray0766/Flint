"""SHELL-01 / `DEC-046`：地区与语言下拉挪到右上角。

owner 2026-08-09 原话：「**地区和语言做到页面右上角，直接下拉选择**」。

## 卡面那句「当前两者只在 `/settings/locale` 那一屏里」不确

实查：`LocaleSettings` 确实只在那一屏，而 **`RegionSwitch` 在广场页上另有一个实例**
（`web/app/plaza/page.tsx`，按 `?region=` 驱动热点集合）。
真相是**外壳右上角两者都没有**——那才是 owner 说的那件事。

所以本卡是**新增第三处**，不是搬家。**三处共用同一个值**：
都读 `GET /settings/locale`，写都走 `PUT /settings/locale`。
各存一份的话，用户在右上角切了区、进详情屏看到的还是旧的，
而**两个真相长得一模一样**，谁也说不出哪个是对的。

## 判据分两层，缺一层都判不出这张卡

- **源码层**判得出「谁复用了谁」「一次发几根轴」——那是屏上看不见的；
- **真浏览器**判得出「右上角真有两个下拉」「390px 不溢出」「切了之后真的存住了」——
  那是源码层看不见的。

第 8 批 `FIX-17` 抓到过一次只有看屏才发现的缺陷（署名与词面挤成一句），
所以这张卡两层都留着。
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SHELL = REPO / "web" / "components" / "shell"
APP_SHELL = SHELL / "AppShell.tsx"
CONTROLS = SHELL / "LocaleControls.tsx"
CLIENT = SHELL / "localeClient.ts"
LOCALE_SCREEN = REPO / "web" / "app" / "settings" / "locale" / "page.tsx"
PLAZA_SCREEN = REPO / "web" / "app" / "plaza" / "page.tsx"

PWENV = Path(r"C:\pwenv\Scripts\python.exe")
ARTIFACT = REPO / ".ui-probe" / "shell01-locale.json"
WEB_BASE = os.environ.get("FLINT_WEB_BASE", "http://localhost:3000")


# ───────────────────────── 一、右上角真的挂上了（源码层）


def test_the_shell_mounts_the_locale_controls_after_the_spacer() -> None:
    """顶栏渲染 `LocaleControls`，且**排在 `.app-shell__spacer` 后面**。

    第一版这条判据写反了：它断言那个空占位「必须没了」，理由是
    「留着会把两个下拉挤开」。**那个理由是猜的，而且猜错了**——
    `.app-shell__spacer` 是 `flex: 1`（`web/app/globals.css:178`），
    它不挤开任何东西，**它就是把后面的东西推到右边的那个机制**。

    删掉之后实测控件停在 x=146 而顶栏右边缘在 390：
    「右上角」只做到了「在顶栏里」。**是真浏览器那条判据把它抓出来的**，
    源码层怎么判都判不出这一层。
    """
    code = APP_SHELL.read_text(encoding="utf-8")

    assert "<LocaleControls />" in code, "顶栏没有挂上地区/语言控件"
    assert 'className="app-shell__spacer"' in code, (
        "推到右边的那个 flex:1 占位没了——控件会停在导航右边而不是顶栏右边")
    assert code.index('className="app-shell__spacer"') < code.index(
        "<LocaleControls />"), "占位排在控件后面了——那样推的是别的东西"


def test_the_controls_reuse_the_existing_pieces_instead_of_writing_a_second_copy() -> None:
    """复用既有件（acceptance②）：地区用 `RegionSwitch`，语言可选值用 `LANGS`。

    另写一份的后果不是多几行代码，是**两份清单迟早各说各的**——
    加第十个地区那天只有一处会跟上，而读的人分不出哪份是真的（`LOC-01` 原话）。
    """
    code = CONTROLS.read_text(encoding="utf-8")

    assert "from \"../region-switch/RegionSwitch\"" in code, "地区那一格没复用 RegionSwitch"
    assert "LANGS" in code, "语言可选值没复用 LocaleSettings 的 LANGS"


def test_the_region_list_still_comes_from_the_endpoint() -> None:
    """九区清单仍从 `GET /settings/locale` 的 `options.region` 取（`LOC-01`：一处真相）。

    在这里自带一份的话，`RegionSwitch` 文件头那句「清单不在这里」当场作废。
    """
    code = CONTROLS.read_text(encoding="utf-8")

    assert "state.data.options.region" in code, "地区清单不是从端点响应里来的"
    for hardcoded in ('"CN"', '"US"', '"JP"'):
        assert hardcoded not in code, f"控件里自带了一份地区清单：{hardcoded}"


# ───────────────────────── 二、两条轴各自独立（`PRINCIPLES#A3`）


def test_a_write_carries_exactly_one_axis() -> None:
    """**切地区 NEVER 改语言**的落地形态：一次只发改动的那一根轴。

    两根一起发的话，用户切地区时会把语言也原样写一次，
    而那次写入会把**另一个设备上刚改的语言**覆盖掉——
    而屏上什么异常都看不出来。
    """
    code = CLIENT.read_text(encoding="utf-8")

    assert "JSON.stringify({ [axis]: value })" in code, (
        "请求体不是「只放改动的那一根轴」")
    assert '"lang":' not in code.split("export async function")[1], (
        "写函数里出现了写死的第二根轴")


def test_switching_region_never_touches_lang_and_the_other_way_round() -> None:
    """两个方向**各断言一次**：`onChange` 各自只调自己那一根。

    只判一个方向的话，「切语言顺手把地区也写了」这一半没人看着。
    """
    code = CONTROLS.read_text(encoding="utf-8")

    assert 'write("region", next.region)' in code, "切地区没有只写 region"
    assert 'write("lang", e.target.value)' in code, "切语言没有只写 lang"


def test_the_region_switch_still_carries_lang_through_untouched() -> None:
    """`RegionSwitch` 的既有口径：切区时把 `lang` **原样带回**，NEVER 由 region 推导。

    本卡把它挂到顶栏，那条口径不该因为换了个位置就变。
    """
    code = CONTROLS.read_text(encoding="utf-8")

    assert "lang={state.data.lang}" in code, "没有把当前语言原样传给 RegionSwitch"


# ───────────────────────── 三、存得住 + 两处同一个值


def test_the_choice_is_written_to_the_server_not_kept_in_memory() -> None:
    """acceptance④：**存得住**靠 `PUT /settings/locale`（`PERSIST-01` 的 `prefs` 表）。

    只改本地状态的话，刷新一次就回去了——而 owner 那句「选择要存得住」
    说的正是刷新之后还在。
    """
    code = CLIENT.read_text(encoding="utf-8")

    assert 'method: "PUT"' in code
    assert "/settings/locale" in code
    assert "localStorage" not in code and "sessionStorage" not in code, (
        "偏好被存进了浏览器——那样换台设备就变了，"
        "而『服务端为真相』正是 flint/profile/prefs.py 文件头那条")


def test_the_screen_after_a_write_shows_what_the_server_took() -> None:
    """写完**回读**，屏上显示的恒是库里认下的那个值。

    本地乐观改的话，服务端把值规范化过之后两边就不一样了，
    而用户不会知道自己看到的不是存进去的那个。
    """
    code = CONTROLS.read_text(encoding="utf-8")

    assert "refetch()" in code, "写完没有回读服务端"


def test_the_detail_screen_is_kept_and_reads_the_same_endpoint() -> None:
    """acceptance⑤：`/settings/locale` **保留为详情屏**，且两处同一个值。

    「同一个值」在源码层的可判形态是**同一个端点**：
    两处都读 `/settings/locale`，就不存在第二份真相。
    """
    assert LOCALE_SCREEN.exists(), "详情屏被删了——卡面写的是保留"
    screen = LOCALE_SCREEN.read_text(encoding="utf-8")
    controls = CONTROLS.read_text(encoding="utf-8")

    assert '"/settings/locale"' in screen
    assert '"/settings/locale"' in controls


def test_the_plaza_instance_was_not_removed() -> None:
    """广场页那个 `RegionSwitch` 实例**留着**。

    卡面说「当前两者只在 `/settings/locale`」——不确（见模块 docstring）。
    照那句话去做会顺手把广场那个删掉，而它驱动的是热点集合的筛选，
    删了之后广场就没法切区了。
    """
    plaza = PLAZA_SCREEN.read_text(encoding="utf-8")

    assert "RegionSwitch" in plaza, "广场页那个地区切换被删掉了"


def test_no_hardcoded_chinese_in_the_new_shell_pieces() -> None:
    """文案走词条表，两种语言各一份（既有纪律）。

    顶栏是每一屏都看得到的地方，硬编一句中文等于让英文用户永远看见它。
    """
    import re

    # **注释有三种，JSX 的 `{/* … */}` 是第三种**——本卡第一次跑就栽在这里：
    # 只剥 `//` 与 `*` 开头的行，一段 JSX 注释里的中文会让下面那个字符串正则
    # 跨行匹配到两个毫不相干的引号之间，于是尺子报出一段谁都读不懂的「硬编中文」。
    # **红的是尺子自己，不是代码。**
    jsx_comment = re.compile(r"\{/\*.*?\*/\}", re.DOTALL)
    # 字符串**不跨行**（`[^"\n]` 而不是 `[^"]`）：跨行的话，
    # 一行末尾的引号会与下一行开头的引号配成一对，而它们之间什么都不是。
    literal = re.compile(r'"[^"\n]*[\u4e00-\u9fff][^"\n]*"')

    for path in (CONTROLS, CLIENT):
        text = jsx_comment.sub("", path.read_text(encoding="utf-8"))
        body = "\n".join(
            line for line in text.splitlines()
            if not line.lstrip().startswith(("//", "*", "/*"))
        )
        found = literal.findall(body)
        assert found == [], f"{path.name} 里有硬编中文：{found}"


# ───────────────────────── 四、真浏览器：右上角、不溢出、切了真的存住


# 探针打的是**顶栏那个** `shell-region-select`。
# `CN-02` 之前两处共用 `region-select`，`eval_on_selector` 取第一个匹配——
# 那是「碰巧对了」，不是「判对了」：广场屏上另有一个同名记号的 select。
_RUNNER = r"""
import json, sys
from playwright.sync_api import sync_playwright

out, base = sys.argv[1], sys.argv[2]
got = {}
with sync_playwright() as p:
    b = p.chromium.launch()
    page = b.new_page(viewport={"width": 390, "height": 844})
    errs = []
    page.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
    page.goto(base + "/plaza", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_selector("[data-testid='shell-locale']", timeout=30000)
    page.wait_for_selector("[data-testid='shell-region-select']", timeout=30000)

    box = page.eval_on_selector(
        "[data-testid='shell-locale']",
        "e => { const r = e.getBoundingClientRect();"
        " return {left: r.left, right: r.right, w: r.width, h: r.height}; }")
    bar = page.eval_on_selector(
        ".app-shell__bar",
        "e => { const r = e.getBoundingClientRect();"
        " return {left: r.left, right: r.right, w: r.width}; }")
    inner = page.eval_on_selector(
        ".app-shell__inner",
        "e => { const r = e.getBoundingClientRect();"
        " const cs = getComputedStyle(e);"
        " return {left: r.left, right: r.right, w: r.width,"
        "  pad_right: parseFloat(cs.paddingRight)}; }")
    got["locale_box"] = box
    got["bar_box"] = bar
    got["inner_box"] = inner
    got["doc_scroll_width"] = page.evaluate("document.documentElement.scrollWidth")
    got["viewport"] = 390
    got["selects"] = page.eval_on_selector_all(
        "[data-testid='shell-locale'] select",
        "els => els.map(e => ({axis: e.getAttribute('data-locale-axis'),"
        " testid: e.getAttribute('data-testid'), value: e.value}))")

    before_lang = page.eval_on_selector(
        "[data-testid='shell-lang-select']", "e => e.value")
    before_region = page.eval_on_selector(
        "[data-testid='shell-region-select']", "e => e.value")
    options = page.eval_on_selector_all(
        "[data-testid='shell-region-select'] option", "els => els.map(e => e.value)")
    target = next((o for o in options if o and o != before_region), before_region)
    page.select_option("[data-testid='shell-region-select']", target)
    page.wait_for_timeout(1500)
    got["before"] = {"lang": before_lang, "region": before_region}
    got["chosen_region"] = target
    got["after_switch"] = {
        "lang": page.eval_on_selector("[data-testid='shell-lang-select']", "e => e.value"),
        "region": page.eval_on_selector("[data-testid='shell-region-select']", "e => e.value"),
    }

    # 刷新：存得住的可观测形式
    page.reload(wait_until="domcontentloaded", timeout=60000)
    page.wait_for_selector("[data-testid='shell-region-select']", timeout=30000)
    page.wait_for_timeout(800)
    got["after_reload"] = {
        "lang": page.eval_on_selector("[data-testid='shell-lang-select']", "e => e.value"),
        "region": page.eval_on_selector("[data-testid='shell-region-select']", "e => e.value"),
    }

    # 详情屏：两处同一个值
    page.goto(base + "/settings/locale", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_selector("[data-locale-axis='region']", timeout=30000)
    page.wait_for_timeout(800)
    got["detail_screen"] = page.eval_on_selector_all(
        "[data-locale-axis]",
        "els => els.map(e => ({axis: e.getAttribute('data-locale-axis'),"
        " value: e.value === undefined ? null : e.value}))")

    got["console_errors"] = errs
    page.screenshot(path=".ui-probe/shell01-locale-390.png")
    b.close()
open(out, "w", encoding="utf-8").write(
    json.dumps({"schema": "shell01/1", **got}, ensure_ascii=False, indent=1))
"""


def _artifact() -> dict[str, object]:
    if ARTIFACT.exists():
        return json.loads(ARTIFACT.read_text(encoding="utf-8"))
    if not PWENV.exists():
        pytest.skip(f"本机没有 {PWENV}（playwright 恒在项目外，NEVER 进项目依赖）")
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        runner = Path(tmp) / "shell01_runner.py"
        runner.write_text(_RUNNER, encoding="utf-8")
        done = subprocess.run(
            [str(PWENV), str(runner), str(ARTIFACT), WEB_BASE],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=REPO, check=False)
    if done.returncode != 0:
        pytest.skip(f"前端没起或探针跑不动：{done.stderr[-800:]}")
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


def test_both_dropdowns_are_really_on_the_top_right() -> None:
    """源码层判得出「挂上了」，判不出「在右上角」。

    「右上角」的可判形态：控件的右边缘贴着顶栏的右边缘（容差 24px），
    且**两个下拉都真的有面积**——0 高的空壳在 DOM 里有、屏幕上没有
    （`F-09` / `GAUGE-15` 都栽在这一处）。
    """
    got = _artifact()
    box = got["locale_box"]
    inner = got["inner_box"]
    selects = got["selects"]

    # **按 testid 认，不按 `data-locale-axis` 认**：地区那一格是复用的
    # `RegionSwitch`，它身上没有 `data-locale-axis`（那是 `LocaleSettings`
    # 与本卡语言格的记号）。第一版照 axis 判，红的是**判据要求被复用的组件
    # 长出一个它没有的属性**——而为了让判据变绿去改一个既有组件，
    # 正是「复用既有件」这条 acceptance 要防的事。
    # 记号从 `region-select` 换成 `shell-region-select`（`CN-02` 取证时发现
    # 广场上那个 `RegionSwitch` 用的是同一个记号，两者意思不同却分不开）。
    assert {s["testid"] for s in selects} == {
        "shell-region-select", "shell-lang-select"}, f"右上角不是两个下拉：{selects}"
    assert box["w"] > 40 and box["h"] > 10, f"控件几乎没有面积：{box}"
    # **参照物是内容列的右内边缘，不是顶栏的右边缘**：顶栏是通栏的，
    # `.app-shell__inner` 才是内容住的那一列，它自己有 `var(--sp-5)` 的内边距。
    # 第一版拿顶栏右边缘比、容差写 24，实测差正好 24（就是那个内边距）——
    # 那个容差是**照着内边距的数值猜的**，猜对了也说不清它为什么是 24。
    # 改成量内容列：控件的右边缘 MUST 贴着内容列的右内边缘（容差 4px 留给亚像素）。
    content_right = inner["right"] - inner["pad_right"]
    assert content_right - box["right"] < 4, (
        f"控件没有贴住内容列右边缘：content_right={content_right} "
        f"locale.right={box['right']}")


def test_the_bar_does_not_overflow_at_390() -> None:
    """`FIX-05/06` 的既有判据不倒：390px 下**横向不溢出**。

    加两个下拉最容易撞的就是这一条——溢出去的部分用户根本不知道它在。
    """
    got = _artifact()

    assert got["doc_scroll_width"] <= got["viewport"] + 1, (
        f"390px 下横向溢出了：scrollWidth={got['doc_scroll_width']}")


def test_switching_the_region_in_a_real_browser_leaves_the_language_alone() -> None:
    """`PRINCIPLES#A3` 在真浏览器上再量一次：切地区之后**语言一个字都没动**。

    源码层那条判的是「只发一根轴」，这条判的是「屏上确实没跟着变」——
    中间还隔着一次回读，回读把两根都写回屏上时最容易把另一根也换掉。
    """
    got = _artifact()

    assert got["after_switch"]["region"] == got["chosen_region"], (
        f"地区没切过去：{got['after_switch']}")
    assert got["after_switch"]["lang"] == got["before"]["lang"], (
        f"切地区把语言也改了：{got['before']} -> {got['after_switch']}")


def test_the_choice_survives_a_reload() -> None:
    """acceptance④ 的可观测形式：**刷新之后仍是上次选的**。

    这一条是 `PERSIST-01` 那张卡的产品面回声——`prefs` 表建出来之前，
    刷新一次就回默认值了。
    """
    got = _artifact()

    assert got["after_reload"]["region"] == got["chosen_region"], (
        f"刷新之后地区回去了：{got['after_reload']}")


def test_the_detail_screen_shows_the_same_value() -> None:
    """acceptance⑤：两处显示**同一个值**。

    各存一份的话，用户在右上角切了区、进详情屏看到的还是旧的，
    而两个真相长得一模一样。
    """
    got = _artifact()
    detail = {row["axis"]: row["value"] for row in got["detail_screen"]}

    assert detail.get("region") == got["chosen_region"], (
        f"详情屏与右上角不是同一个值：详情={detail} 右上角={got['chosen_region']}")


def test_no_console_errors_while_switching() -> None:
    """切换过程中控制台干净。

    一条 React 报错在屏上常常什么都看不出来，而它意味着那次渲染
    有一半没跑完——下一次交互的行为就不可预期了。
    """
    got = _artifact()

    assert got["console_errors"] == [], f"控制台有错：{got['console_errors']}"
