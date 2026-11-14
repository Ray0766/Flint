"""WB-01：计划书主工作台的三栏骨架（左卡片 / 中对话 / 右预览）。

## 风格来源

`前端设计/ai工作台/Flint 设计台 v3.dc.html`（owner 2026-08-12 指定）。
**照它做**，NEVER 自创一版。蓝本里的实数逐个搬过来：

| 蓝本 | 值 | 落到哪 |
|---|---|---|
| `sideW: 600` | 左侧组（卡片 + 对话）600px | `.workbench__side` |
| `cardsW: 250` | 卡片栏 250px | `.workbench__cards` |
| 两条 `width:7px;cursor:col-resize` | 两根拖条 | `.workbench__grip` |
| `previewWidth: '860px'` | `flex:0 1 860px` 的**文档**列 | `.workbench__doc` |
| `flex:1;min-height:0` / `overflow-y:auto` | 整屏不滚、栏内滚 | 见下 |

## 一处要说清的对应关系

工单 acceptance 写的是「右栏预览初始 **860px**」。蓝本里 860 不是右栏的宽度——
右栏是 `flex:1`（吃掉剩下的全部），**860 是右栏画布里那一列文档**的
`flex:0 1 860px`（蓝本第 198 行）。两种读法在 1920 下量出来的数不一样：
右栏实测 1153，文档实测 860。

本卡按**蓝本原形**实现，判据钉的是文档列 860——
把右栏本身钉成 860 会让预览区右边空出一大片，而那不是蓝本的样子。

## `DEC-059` 的那一条在这里的形态

本卡只做骨架，不生成任何东西。但骨架也要**新增而不是替换**：
顶栏从 6 个入口变 7 个，`/design` 那一项与它的路由**一个字没动**
（改名退居次要是 `WB-07` 的活，不是本卡的）。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from tools.probe_evidence import require_probe_evidence

REPO = Path(__file__).resolve().parents[2]
PROBE = REPO / ".ui-probe" / "wb"
REPORT = PROBE / "layout.json"

WEB = REPO / "web"
PAGE = WEB / "app" / "workbench" / "page.tsx"
LAYOUT = WEB / "components" / "workbench" / "WorkbenchShell.tsx"
CSS = WEB / "app" / "globals.css"
SHELL = WEB / "components" / "shell" / "AppShell.tsx"
MESSAGES = WEB / "messages" / "zh.json"
GRAPH = REPO / "assets" / "screen_graph.json"

#: 蓝本第 306 行 `sideW: 600, cardsW: 250` 与第 305 行 `previewWidth: '860px'`。
BLUEPRINT_SIDE = 600
BLUEPRINT_CARDS = 250
BLUEPRINT_DOC = 860
#: 两根拖条各 7px（蓝本第 110 / 155 行 `width:7px;cursor:col-resize`）。
BLUEPRINT_GRIP = 7

THEMES = ("light", "dark")


def _report() -> dict[str, dict[str, object]]:
    if not REPORT.exists():
        pytest.skip("还没取证（跑 tools/ui_probe_wb_layout.py 先）")
    return dict(json.loads(REPORT.read_text(encoding="utf-8")))


@pytest.fixture(scope="module")
def shots() -> dict[str, dict[str, object]]:
    return _report()


def _wb_css() -> str:
    """取 `WB-01` 那一段 CSS 的**规则部分**（注释去掉）。

    两步的顺序不能倒：**先按注释里的锚点切段，再去注释**。
    第一版反过来了——`WB-01` 这个锚点本身就写在段首的注释里，
    去完注释它就没了，于是 `split` 抛 `IndexError`。
    红的是判据自己：它把自己要找的路标先擦掉了。

    去注释这一步仍然要有（**本会话第九次踩它**）：CSS 块注释跨多行，
    续行不以 `*` 开头，按行过滤会漏掉大半——
    然后判据扫到的是自己写的注释，而不是规则。
    """
    raw = CSS.read_text(encoding="utf-8")
    block = raw[raw.index("WB-01 · 计划书主工作台"):]
    return re.sub(r"/\*.*?\*/", "", block, flags=re.DOTALL)


# ───────────────────────── 一、1920 下三栏并排，且三个数逐个对上蓝本


def test_the_three_columns_sit_side_by_side_at_1920() -> None:
    """三栏**并排**：三者的垂直区间重合，而水平区间首尾相接。

    「并排」不能只判 `display:flex`——一个 `flex-wrap:wrap` 的容器
    在窄一点的地方会把第三栏折下去，而 `display` 仍然是 `flex`。
    所以量的是**实际坐标**。
    """
    m = _report()["1920-light"]
    cards, chat, preview = m["cards"], m["chat"], m["preview"]

    for col in (cards, chat, preview):
        assert float(col["height"]) > 200, f"{col['name']} 高度只有 {col['height']}"
    # 水平首尾相接：卡片栏在对话栏左边，对话栏在预览栏左边。
    assert float(cards["right"]) <= float(chat["left"]) + 1, (
        f"卡片栏右缘 {cards['right']} 压过了对话栏左缘 {chat['left']}")
    assert float(chat["right"]) <= float(preview["left"]) + 1, (
        f"对话栏右缘 {chat['right']} 压过了预览栏左缘 {preview['left']}")
    # 垂直重合（没有一栏被折到下一行去）。
    assert abs(float(cards["top"]) - float(preview["top"])) < 2, (
        f"卡片栏与预览栏不在同一行：{cards['top']} vs {preview['top']}")


def test_the_cards_column_starts_at_the_blueprint_width() -> None:
    """左栏初始 **250px**（蓝本 `cardsW = 250`）。"""
    m = _report()["1920-light"]

    assert abs(float(m["cards"]["width"]) - BLUEPRINT_CARDS) < 1.5, (
        f"左栏实测 {m['cards']['width']}，蓝本是 {BLUEPRINT_CARDS}")


def test_the_document_column_starts_at_the_blueprint_width() -> None:
    """预览里那一列文档初始 **860px**（蓝本 `previewWidth = '860px'`）。

    钉的是文档列而不是右栏本身——理由见文件头那一节。
    """
    m = _report()["1920-light"]

    assert abs(float(m["doc"]["width"]) - BLUEPRINT_DOC) < 1.5, (
        f"文档列实测 {m['doc']['width']}，蓝本是 {BLUEPRINT_DOC}")


def test_the_chat_column_takes_what_is_left_and_can_be_squeezed() -> None:
    """中栏 `flex:1` 占满剩余，且 `min-width:0`。

    `min-width:0` 不是可有可无的一行：flex 子项默认 `min-width:auto`，
    一条不换行的长文本会把它**撑破容器**——而撑破之后
    屏上看起来只是「右边被推出去了」，没有人会想到是这一行。
    量到的宽度 MUST 等于 `sideW - cardsW - 拖条`。
    """
    m = _report()["1920-light"]
    expected = BLUEPRINT_SIDE - BLUEPRINT_CARDS - BLUEPRINT_GRIP

    assert m["chat"]["flexGrow"] == "1", f"中栏 flex-grow 是 {m['chat']['flexGrow']}"
    assert m["chat"]["minWidth"] in ("0px", "0"), (
        f"中栏 min-width 是 {m['chat']['minWidth']}——长文本会把它撑破")
    assert abs(float(m["chat"]["width"]) - expected) < 1.5, (
        f"中栏实测 {m['chat']['width']}，算出来该是 {expected}"
        f"（{BLUEPRINT_SIDE} - {BLUEPRINT_CARDS} - {BLUEPRINT_GRIP}）")


# ───────────────────────── 二、整屏不滚，栏内滚


def test_the_page_itself_does_not_scroll_but_the_columns_do() -> None:
    """整屏 `overflow:hidden`，三栏**各自那一层**滚（蓝本原形）。

    滚动放在栏内那一层而不是栏上——这是照蓝本抄的，理由也在蓝本里：
    卡片栏顶上的页签、对话栏底下的输入框**要钉住不跟着滚**
    （蓝本第 54 / 116 / 170 行三处 `overflow-y:auto` 都在栏的内部）。

    连带钉住 `min-height: 0`：flex 子项默认 `min-height:auto`，
    内容多了会把栏**撑高**而不是在栏里滚——撑高之后整页跟着滚，
    而屏上看起来只是「页面变长了」，没有人会想到是这一行。

    **量的是机制不是当下**：骨架里内容还不多，三栏此刻本来就没得滚。
    所以取证脚本往卡片栏的滚动层里塞一个高 4000px 的元素，量完**当场撤掉**——
    量到的是「这一层能不能滚、而整屏会不会跟着滚」，
    NEVER 是「它现在有没有滚」。
    """
    m = _report()["1920-light"]
    probe = m["scrollProbe"]

    assert m["root"]["overflow"] in ("hidden", "hidden hidden"), (
        f"工作台根的 overflow 是 {m['root']['overflow']}")
    for col in ("cards", "chat", "preview"):
        assert m[col]["scrollOverflowY"] == "auto", (
            f"{col} 栏里那一层的 overflow-y 是 {m[col]['scrollOverflowY']}，滚不动")
        assert m[col]["minHeight"] in ("0px", "0"), (
            f"{col} 栏的 min-height 是 {m[col]['minHeight']}——内容多了会把它撑高")
    # 塞进去之后：那一栏滚得动，而页面自己一动不动。
    assert int(probe["colScrollTop"]) > 100, (
        f"塞了 4000px 之后卡片栏只滚到 {probe['colScrollTop']}")
    assert int(probe["pageScrollTop"]) == 0, (
        f"页面自己滚了 {probe['pageScrollTop']}px——整屏该是不动的")
    assert int(probe["restoredScrollHeight"]) == int(probe["baseScrollHeight"]), (
        "取证用的那块 4000px 没撤干净")


def test_nothing_overflows_sideways_at_any_viewport() -> None:
    """零横向溢出，三个视口 × 两主题逐个量。"""
    for key, m in _report().items():
        assert int(m["scrollW"]) <= int(m["vw"]) + 1, (
            f"{key}：横向溢出 {m['scrollW']} > {m['vw']}")


def test_the_console_is_clean() -> None:
    """零控制台报错。"""
    for key, m in _report().items():
        assert m["errors"] == [], f"{key} 有报错：{m['errors'][:2]}"


# ───────────────────────── 三、拖宽：拖得动，且中栏永远留得住


def test_dragging_the_grip_changes_the_cards_width() -> None:
    """拖动分隔条，左栏宽度**真的变了**（实测前后两个数）。"""
    d = _report()["1920-light"]["drag"]

    assert abs(float(d["after"]) - float(d["before"])) > 40, (
        f"拖了 {d['dx']}px 而左栏从 {d['before']} 变到 {d['after']}——没拖动")


def test_the_chat_column_survives_being_dragged_to_the_limit() -> None:
    """拖到极限之后**中栏仍在**（蓝本 `Math.min(sideW - 240, …)` 那一路的意思）。

    没有这个下限的话，一次拖到底会把对话栏压成 0——
    而压成 0 之后**屏上看起来像是那一栏不见了**，用户不会想到往回拖。

    ## 这条判据第一版自己错了：240 是参数，不是屏上量到的宽度

    第一版断言 `chatAtLimit >= 240`，实测 **233**，红。
    红的不是实现——**照蓝本做出来就是 233**：
    蓝本夹的是 `cardsW ≤ sideW - 240`，而那 7px 拖条也住在同一个
    `sideW` 里，于是中栏 = `sideW - (sideW - 240) - 7` = **233**。

    钉**契约的事实**（蓝本夹的是哪个量），NEVER 钉一个看起来一样的数——
    第 12 批 `GATE1-DEDUP` 栽的正是这一处。
    """
    d = _report()["1920-light"]["drag"]
    floor = 240 - BLUEPRINT_GRIP  # 蓝本参数 240 减掉同组里那根 7px 拖条

    assert float(d["chatAtLimit"]) >= floor, (
        f"拖到极限时中栏只剩 {d['chatAtLimit']}px，照蓝本算出来至少有 {floor}")
    assert int(d["scrollWAtLimit"]) <= int(d["vw"]) + 1, (
        f"拖到极限时横向溢出：{d['scrollWAtLimit']} > {d['vw']}")


# ───────────────────────── 四、响应式：390 下不横排


def test_the_columns_stack_instead_of_squeezing_on_a_phone() -> None:
    """390 视口下三栏**不横排**：三者左缘对齐、纵向排开。

    横排硬塞的后果是 250 + 240 + 文档全挤在 390 里——
    每一栏都窄到读不了，而**屏上不会报错**。
    """
    m = _report()["390-light"]
    cards, chat, preview = m["cards"], m["chat"], m["preview"]

    for col in (chat, preview):
        assert abs(float(col["left"]) - float(cards["left"])) < 2, (
            f"{col['name']} 没有与卡片栏左对齐（{col['left']} vs {cards['left']}）")
    assert float(chat["top"]) >= float(cards["bottom"]) - 2, "对话栏没排在卡片栏下面"
    assert float(preview["top"]) >= float(chat["bottom"]) - 2, "预览栏没排在对话栏下面"


# ───────────────────────── 五、两主题各一套（DARK-02 的形状）


@pytest.mark.parametrize("viewport", (1920, 390))
def test_the_two_themes_are_not_the_same_paint(viewport: int) -> None:
    """亮/暗**量到同一组颜色就判红**（`DARK-02` 既有形状）。

    只判「暗色模式下能打开」是判不出东西的：一套写死的颜色在两个主题下
    都渲染得出来，而它在暗底上是白纸一张。
    """
    light = _report()[f"{viewport}-light"]["paint"]
    dark = _report()[f"{viewport}-dark"]["paint"]

    same = [k for k in light if light[k] == dark[k]]
    assert same == [], f"{viewport}：这几处两主题一个色 {same}"


# ───────────────────────── 六、顶栏多一项，既有六项一个字没动


def test_the_top_bar_gains_the_workbench_and_keeps_the_other_six() -> None:
    """顶栏从 6 项变 **7** 项，既有六条 `href` **逐条还在原位**。

    判等值而不是判包含：判包含的话，把 `/design` 换成别的也不会红——
    而本批的裁决第一句就是「新增一屏而不是替换」。
    """
    code = SHELL.read_text(encoding="utf-8")
    hrefs = re.findall(r'\{ href: "([^"]+)", key: "([^"]+)" \}', code)

    # 次序在 `WB-07` 变过一次：`/workbench` 排到 `/design` 之前
    # （「退居次要」的可见形式就是次序）。**清单本身一条没少**——
    # 这条判据判的正是那件事：新增一屏而不是替换。
    assert [h for h, _ in hrefs] == [
        "/plaza", "/workbench", "/favorites", "/design",
        "/settings/locale", "/account", "/demo",
    ], f"顶栏入口清单变了：{[h for h, _ in hrefs]}"
    assert ("/workbench", "shell.nav.workbench") in hrefs


def test_the_new_entry_has_a_label_and_an_icon_like_the_others() -> None:
    """新入口与既有六项**同规格**：有文案、有 18×18 的图标。

    少一样就会在屏上现形：没有文案的话 <768 时读屏软件读到的是空；
    没有图标的话那一格在窄屏上是空白。
    """
    messages = json.loads(MESSAGES.read_text(encoding="utf-8"))
    code = SHELL.read_text(encoding="utf-8")

    assert messages.get("shell.nav.workbench"), "新入口没有中文文案"
    icons = code.split("NAV_ICONS", 1)[1]
    assert '"/workbench":' in icons, "新入口没有图标"


def test_the_design_screen_and_its_route_were_not_touched() -> None:
    """`DEC-059` 第一句：**`/design` 那一屏还在**——新增一屏，不是替换。

    改名退居次要已由 `WB-07` 做过（`shell.nav.design` → 「模板工具」）。
    所以这条判据改判**那一屏与它的组件仍在**，而不是判它还叫不叫旧名字：
    盯着名字的话，`WB-07` 一改它就红，而它本来要守的是「那一屏没被删掉」。
    名字归 `tests/v041/test_wb_nav_rename.py` 管。
    """
    assert (WEB / "app" / "design" / "page.tsx").exists(), "/design 那一屏不见了"
    assert (WEB / "components" / "design-workbench").is_dir(), "设计工作台组件不见了"
    code = SHELL.read_text(encoding="utf-8")
    assert '{ href: "/design", key: "shell.nav.design" }' in code, (
        "/design 从顶栏上被摘掉了——藏起来与删掉在屏上长得一模一样")


def test_the_new_screen_is_declared_in_the_reachability_graph() -> None:
    """新屏进 `screen_graph.json`，且**从顶栏进得去**。

    `ENTRY-05` 的三个空表（孤岛 / 接了线走不通 / 豁免）继续成立：
    新屏有顶栏入口，所以它既不是孤岛，也不需要豁免。
    """
    graph = json.loads(GRAPH.read_text(encoding="utf-8"))
    routes = {s["route"]: s for s in graph["screens"]}

    assert "/workbench" in routes, "新屏没进可达性图"
    assert any(r["from"] == "顶栏" for r in routes["/workbench"]["reached_by"]), (
        "新屏没写「从顶栏进得去」")
    assert "island_since" not in routes["/workbench"], "新屏被记成了孤岛"
    assert "/workbench" not in graph["exempt"], (
        "新屏进了豁免名单——豁免今天只有 /share/[token] 一个住户")


# ───────────────────────── 七、样式取自设计系统，NEVER 裸值


def test_the_workbench_css_uses_tokens_not_raw_colours() -> None:
    """本段 CSS 里**一个裸色值都没有**（`test_ui_restyle` 的既有纪律）。

    蓝本自带一整套 `--bg / --panel / --ink / --accent`——那是它作为独立 demo
    的自备品。搬进本仓要落到 `_ds` 已声明的 token 上，
    NEVER 把蓝本那十几个十六进制色照抄进来：抄进来就是这套系统里
    多了一份没人维护的第二真相。
    """
    block = _wb_css()
    raw = re.findall(r"#[0-9a-fA-F]{3,8}\b", block)

    assert raw == [], f"本段里有裸色值：{raw[:5]}"
    assert block.count("var(--") > 20, (
        f"本段只用到 {block.count('var(--')} 处 token——像是有一半在写裸值")


def test_the_blueprint_font_link_was_not_copied() -> None:
    """蓝本引了 Google Fonts（IBM Plex Sans）——**NEVER 引**。

    两条理由各自成立：CI 恒不联网（`S2-7`），而它是一次第三方请求。
    """
    for path in (PAGE, LAYOUT):
        code = path.read_text(encoding="utf-8")
        assert "fonts.googleapis" not in code and "fonts.gstatic" not in code, (
            f"{path.name} 把蓝本那条外链字体抄进来了")


# ───────────────────────── 八、截图在盘上


@pytest.mark.parametrize("viewport", (1920, 1440, 390))
@pytest.mark.parametrize("theme", THEMES)
def test_the_screenshot_is_on_disk(viewport: int, theme: str) -> None:
    """三视口 × 两主题共六张，逐张在盘上且不是空文件。"""
    require_probe_evidence(REPORT, "起栈后跑 tools/ui_probe_wb_layout.py")
    matches = list(PROBE.glob(f"workbench-{viewport}x*-{theme}.png"))

    assert matches, f"缺这一张：{viewport} × {theme}"
    assert matches[0].stat().st_size > 10_000, (
        f"{matches[0].name} 只有 {matches[0].stat().st_size} 字节")
