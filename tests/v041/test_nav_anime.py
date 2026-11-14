"""NAV-ANIME-01：顶部居中的药丸浮动条 + 跟随发光块。

## 风格来源只有一个

`前端设计/Anime navbar live demo/Anime Navbar.dc.html`（owner 2026-08-11 指定）。
**照它做，NEVER 自创一版。**

蓝本的核心机制是 `measure()`：逐个量 `a[data-tab]` 的 `offsetLeft` / `offsetWidth`，
发光块按当前项那一对数定位——**不是靠 CSS 猜，是量出来的**。
所以本文件最要紧的一条是 §二：**发光块的 left/width 与当前项逐字相等**。

## 判据一律正向（本批 `positive_criteria`）

每条都是「这个元素 MUST 长成什么样」+ 实测数值（computed style /
`getBoundingClientRect()`），打真浏览器真栈（`:3000`）。

由来：`UI-01~11` 挂的四条禁止性判据全绿，而那一屏是个 4072px 的裸 `<ul><li>`——
**禁止性判据挡得住做错，挡不住没做**。

## 三处蓝本没写、而本仓必须有

| 补的 | 判在哪 |
|---|---|
| 中文字体加载后**重测** | §三（慢字体模拟） |
| 亮/暗**两套**配色 | §四（两主题量到同一组颜色就判红） |
| `prefers-reduced-motion` 全停 | `test_nav_mascot.py`（与吉祥物同一条口径） |

**NEVER 引蓝本那条外链 Google Fonts（Manrope）**：CI 不联网，且那是第三方请求。
字号与字重照蓝本，字形走本仓既有档——差异写在 `docs/trace/NAV-ANIME-01.md`。
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
PW_PYTHON = Path(r"C:\pwenv\Scripts\python.exe")
BLUEPRINT = REPO / "前端设计" / "Anime navbar live demo" / "Anime Navbar.dc.html"

_PROBE = r"""
import json, sys
from playwright.sync_api import sync_playwright

READ = '''() => {
  const nav = document.querySelector('.anime-nav');
  if (!nav) return {missing: true};
  const cs = getComputedStyle(nav);
  const r = nav.getBoundingClientRect();
  const glow = document.querySelector('.anime-nav__glow');
  const gs = getComputedStyle(glow);
  const active = nav.querySelector('a[data-active="true"]');
  const tabs = [...nav.querySelectorAll('a[data-tab]')];
  const ctrl = nav.querySelector('.anime-nav__controls');
  const brand = nav.querySelector('.anime-nav__brand');
  const tops = [
    ...(brand ? [brand.offsetTop] : []),
    ...tabs.map(a => a.offsetTop),
    ...(ctrl ? [...ctrl.children].map(c => c.offsetTop) : []),
  ];
  // 取一个**不是当前项**的 tab 当「其余项」的样本。
  // 直接用 tabs[0] 的话，它恰好就是当前页（/plaza 排第一），
  // 于是「当前项与其余项不同色」那条判据会拿当前项和自己比——**永远绿**。
  const firstTab = tabs.find(a => a.dataset.active !== 'true') || tabs[0];
  const label = firstTab.querySelector('.anime-nav__label');
  const icon = firstTab.querySelector('.anime-nav__icon');
  return {
    position: cs.position,
    borderRadius: cs.borderRadius,
    backdropFilter: cs.backdropFilter,
    borderTopWidth: cs.borderTopWidth,
    boxShadow: cs.boxShadow,
    background: cs.backgroundColor,
    tabColor: getComputedStyle(firstTab).color,
    activeColor: active ? getComputedStyle(active).color : null,
    tabFontSize: getComputedStyle(firstTab).fontSize,
    tabFontWeight: getComputedStyle(firstTab).fontWeight,
    gap: cs.gap,
    padding: cs.padding,
    leftGap: r.left,
    rightGap: innerWidth - r.right,
    glowLeft: parseFloat(gs.left),
    glowWidth: parseFloat(gs.width),
    glowOpacity: parseFloat(gs.opacity),
    activeLeft: active ? active.offsetLeft : null,
    activeWidth: active ? active.offsetWidth : null,
    activeTab: active ? active.dataset.tab : null,
    tops: [...new Set(tops)],
    tabCount: tabs.length,
    hrefs: tabs.map(a => new URL(a.href).pathname),
    labelDisplay: getComputedStyle(label).display,
    iconDisplay: getComputedStyle(icon).display,
    glowLayers: document.querySelectorAll('.anime-nav__glow-layer').length,
    navScrollW: nav.scrollWidth, navClientW: nav.clientWidth,
    docScrollW: document.documentElement.scrollWidth,
  };
}'''

OUT = {}
with sync_playwright() as pw:
    b = pw.chromium.launch()
    for theme in ("light", "dark"):
        for w, h in ((1920, 1080), (390, 844)):
            page = b.new_page(viewport={"width": w, "height": h},
                              color_scheme=theme)
            page.goto("http://localhost:3000/plaza", wait_until="networkidle")
            page.wait_for_timeout(700)
            OUT[f"{theme}-{w}"] = page.evaluate(READ)
            page.close()

    # 切一次当前页，发光块 MUST 跟过去（蓝本的核心机制）
    page = b.new_page(viewport={"width": 1920, "height": 1080})
    page.goto("http://localhost:3000/plaza", wait_until="networkidle")
    page.wait_for_timeout(700)
    before = page.evaluate(READ)
    page.goto("http://localhost:3000/favorites", wait_until="networkidle")
    page.wait_for_timeout(700)
    OUT["switched"] = page.evaluate(READ)
    OUT["before_switch"] = before
    page.close()

    # **慢字体**：拖住 document.fonts.ready，量重测之后还对不对得上
    page = b.new_page(viewport={"width": 1920, "height": 1080})
    page.add_init_script('''
      const real = Object.getOwnPropertyDescriptor(Document.prototype, 'fonts');
      const slow = new Promise(r => setTimeout(r, 1200));
      Object.defineProperty(document, 'fonts', {
        configurable: true,
        get() {
          const f = real ? real.get.call(document) : null;
          return { ready: slow.then(() => f), check: () => false };
        },
      });
    ''')
    page.goto("http://localhost:3000/plaza", wait_until="networkidle")
    page.wait_for_timeout(2200)
    OUT["slow_font"] = page.evaluate(READ)
    page.close()
    b.close()

print(json.dumps(OUT, ensure_ascii=False))
"""


def _probe() -> dict[str, dict[str, object]]:
    if not PW_PYTHON.exists():
        pytest.skip("playwright 环境不在（它恒在项目外 C:\\pwenv）")
    done = subprocess.run(
        [str(PW_PYTHON), "-c", _PROBE], capture_output=True, text=True,
        check=False,  # 跑不起来要 skip 而不是抛——真栈没起是环境问题，不是判据失败
        encoding="utf-8", errors="replace", timeout=420)
    if done.returncode != 0:
        pytest.skip(f"真栈没起来（:3000）：{(done.stderr or '')[-400:]}")
    return dict(json.loads(done.stdout.strip().splitlines()[-1]))


@pytest.fixture(scope="module")
def screens() -> dict[str, dict[str, object]]:
    return _probe()


# ───────────────────────── 一、形态（全部正向，全部带实测值）


@pytest.mark.compose
def test_the_bar_is_a_fixed_floating_pill(
    screens: dict[str, dict[str, object]],
) -> None:
    """药丸条 MUST 是 `position: fixed` 的浮动条。

    实测（1920，亮底）：`fixed` · `border-radius: 9999px` ·
    `backdrop-filter: blur(16px)` · 1px 描边 · 有投影。
    """
    m = screens["light-1920"]
    assert not m.get("missing"), "屏上没有 `.anime-nav`——药丸条根本没渲染"

    assert m["position"] == "fixed", f"不是浮动条：position={m['position']}"
    radius = float(str(m["borderRadius"]).split("px")[0])
    assert radius >= 999, f"不是药丸：border-radius={m['borderRadius']}"
    assert "blur" in str(m["backdropFilter"]), (
        f"没有毛玻璃：backdrop-filter={m['backdropFilter']}")
    assert float(str(m["borderTopWidth"]).rstrip("px")) >= 1, "没有描边"
    assert m["boxShadow"] and m["boxShadow"] != "none", "没有投影"


@pytest.mark.compose
def test_the_bar_is_centred_at_the_top(
    screens: dict[str, dict[str, object]],
) -> None:
    """顶部**居中**：左右外边距差 ≤2px（实测 348 / 348）。"""
    m = screens["light-1920"]
    left, right = float(m["leftGap"]), float(m["rightGap"])

    assert abs(left - right) <= 2, f"没居中：左 {left:.0f}px 右 {right:.0f}px"
    assert left > 0, "条把整行占满了——那不是浮动药丸条"


@pytest.mark.compose
def test_the_tabs_match_the_blueprint_type(
    screens: dict[str, dict[str, object]],
) -> None:
    """tab 的字号与字重照蓝本：`14px` / `700`。

    字**形**不照抄（蓝本引外链 Manrope，CI 不联网），字号字重照抄。
    """
    m = screens["light-1920"]

    assert m["tabFontSize"] == "14px", f"字号不是蓝本那档：{m['tabFontSize']}"
    assert str(m["tabFontWeight"]) == "700", f"字重不是蓝本那档：{m['tabFontWeight']}"
    assert m["gap"].startswith("12px"), f"间距不是蓝本那档：{m['gap']}"


@pytest.mark.compose
def test_all_nine_controls_render_on_one_row(
    screens: dict[str, dict[str, object]],
) -> None:
    """**owner「做成一个横栏」的可量形式**：条内每一项 `offsetTop` 相等。

    6 个导航项 + 品牌字 + 地区/语言 + 主题——**全部 `offsetTop = 8`**（实测）。
    改前它们在 476px 的容器里折成三四行。

    `WB-01` 之后导航项是 **7** 个（新增「工作台」）。
    这条判据看的是**排不排得成一行**，而不是「有几项」——
    多一项正是它该继续咬得动的场景：条更长了，若因此折行，
    `tops` 会当场出现第二个值。项数本身由
    `test_the_seven_entries_are_unchanged` 判等值。
    """
    m = screens["light-1920"]

    assert m["tops"] == [8] or len(m["tops"]) == 1, (
        f"顶栏没排成一行：offsetTop 有 {m['tops']} 这些值")
    assert int(m["tabCount"]) == 7, f"导航项不是 7 个：{m['tabCount']}"


@pytest.mark.compose
def test_the_bar_does_not_overflow_the_viewport(
    screens: dict[str, dict[str, object]],
) -> None:
    """1920 下条内**不横向滚动**，整页也不溢出。"""
    m = screens["light-1920"]

    assert int(m["navScrollW"]) <= int(m["navClientW"]) + 1, (
        f"条内溢出了：scrollWidth {m['navScrollW']} > clientWidth {m['navClientW']}")
    assert int(m["docScrollW"]) <= 1920 + 1, f"整页横向溢出：{m['docScrollW']}"


# ───────────────────────── 二、跟随发光块（蓝本的核心机制）


@pytest.mark.compose
def test_the_glow_sits_exactly_on_the_active_tab(
    screens: dict[str, dict[str, object]],
) -> None:
    """发光块的 `left` / `width` 与当前项的 `offsetLeft` / `offsetWidth`
    **相等（±1px）**。

    这是蓝本 `measure()` 那一路的落点：位置**量出来**而不是猜。
    实测 1920 亮底：glow(127, 104) == active(127, 104)。
    """
    m = screens["light-1920"]

    assert m["activeTab"], "没有当前项——发光块无处可去"
    assert abs(float(m["glowLeft"]) - float(m["activeLeft"])) <= 1, (
        f"发光块 left={m['glowLeft']:.0f} 与当前项 offsetLeft={m['activeLeft']} 对不上")
    assert abs(float(m["glowWidth"]) - float(m["activeWidth"])) <= 1, (
        f"发光块 width={m['glowWidth']:.0f} 与当前项 offsetWidth={m['activeWidth']} 对不上")
    assert float(m["glowOpacity"]) > 0.5, "发光块没显示出来"


@pytest.mark.compose
def test_the_glow_follows_when_the_page_changes(
    screens: dict[str, dict[str, object]],
) -> None:
    """**真切换再量**：换一屏之后发光块跟到新的当前项上。

    只在一屏上量的话，一个把 `left` 写死的实现也会绿。
    """
    before, after = screens["before_switch"], screens["switched"]

    assert before["activeTab"] != after["activeTab"], (
        f"两次量到的当前项是同一个（{before['activeTab']}）——这条判据没切成")
    assert abs(float(after["glowLeft"]) - float(after["activeLeft"])) <= 1, (
        f"切换后发光块没跟过去：glow={after['glowLeft']:.0f} "
        f"active={after['activeLeft']}")
    assert float(before["glowLeft"]) != float(after["glowLeft"]), (
        "切换前后发光块停在同一个位置——它没有跟随")


@pytest.mark.compose
def test_the_glow_has_the_blueprint_layers(
    screens: dict[str, dict[str, object]],
) -> None:
    """发光块 MUST 是**多层模糊**（蓝本四层 + 一层扫光）。

    只用一层的话屏上是一块硬边色斑，不是光。
    """
    assert int(screens["light-1920"]["glowLayers"]) >= 4, (
        f"发光层只有 {screens['light-1920']['glowLayers']} 层，蓝本是四层")


# ───────────────────────── 三、中文字体加载后重测（本仓补的，NEVER 省）


@pytest.mark.compose
def test_the_glow_is_still_aligned_after_slow_fonts(
    screens: dict[str, dict[str, object]],
) -> None:
    """**慢字体之后仍对齐**（acceptance④ 逐字，owner 点名不许省）。

    造法：把 `document.fonts.ready` 拖到 1.2 秒后才 resolve，
    也就是「首帧用后备字体、随后换成中文字体」那一幕。

    不在 `fonts.ready` 之后重测的话，发光块停在**后备字体量出来的**位置上——
    这在英文蓝本上看不出来，在中文界面上是必现。
    """
    m = screens["slow_font"]

    assert not m.get("missing"), "慢字体那一轮条没渲染出来"
    assert abs(float(m["glowLeft"]) - float(m["activeLeft"])) <= 1, (
        f"慢字体之后发光块错位：glow={m['glowLeft']:.0f} "
        f"active={m['activeLeft']}——`document.fonts.ready` 之后没重测")
    assert abs(float(m["glowWidth"]) - float(m["activeWidth"])) <= 1


def test_the_component_re_measures_on_fonts_ready() -> None:
    """源码里 MUST 有那一次重测，且写清为什么。

    实测判据能证明「今天对齐了」，这一条证明「它是被有意保住的」——
    换一台字体加载快的机器，上面那条可能碰巧绿。
    """
    code = (REPO / "web" / "components" / "shell" / "AnimeNav.tsx").read_text(
        encoding="utf-8")

    assert "document.fonts" in code and "ready" in code
    assert "measure" in code
    assert "中文字体" in code, "没写清为什么要重测——下一个人会把它当多余的"


# ───────────────────────── 四、两主题各一套（沿用 DARK-02 的判据形状）


@pytest.mark.compose
def test_the_two_themes_are_two_palettes(
    screens: dict[str, dict[str, object]],
) -> None:
    """**两主题量到同一组颜色就判红**（`DARK-02` 的判据形状）。

    实测：暗底 `rgba(0,0,0,0.5)` + 白字 + `0 8px 32px rgba(0,0,0,0.4)`；
    亮底 `rgba(255,255,255,0.72)` + 深色字 + `0 6px 20px rgba(27,42,46,0.12)`。
    """
    light, dark = screens["light-1920"], screens["dark-1920"]

    assert light["background"] != dark["background"], (
        f"两主题的条底色一样：{light['background']}")
    assert light["tabColor"] != dark["tabColor"], (
        f"两主题的字色一样：{light['tabColor']}")
    assert light["boxShadow"] != dark["boxShadow"], (
        "两主题的投影一样——亮底照抄暗底会得到一块糊在浅色纸上的黑影")


@pytest.mark.compose
def test_the_active_tab_is_brighter_than_the_rest(
    screens: dict[str, dict[str, object]],
) -> None:
    """当前项与其余项**颜色不同**（蓝本 `col()` 那一路）。

    一样的话，发光块之外再没有第二个信号说「你在这一屏」。
    """
    for name in ("light-1920", "dark-1920"):
        m = screens[name]
        assert m["activeColor"] != m["tabColor"], (
            f"{name}：当前项与其余项同色（{m['tabColor']}）")


# ───────────────────────── 五、响应式（蓝本 isMobile 那一路）


@pytest.mark.compose
def test_labels_become_icons_on_a_phone(
    screens: dict[str, dict[str, object]],
) -> None:
    """<768：文字 `display:none`、图标 `display:inline-flex`；≥768 反过来。

    **两个方向各断言一次**——只判窄屏的话，一个恒显示图标的实现也会绿。
    """
    wide, narrow = screens["light-1920"], screens["light-390"]

    assert wide["labelDisplay"] != "none", "宽屏下文字标签不见了"
    assert wide["iconDisplay"] == "none", "宽屏下图标还占着位"
    assert narrow["labelDisplay"] == "none", "窄屏下文字标签还在"
    # 浏览器把 flex 容器里的 `inline-flex` 算成 `flex`（blockification）——
    # 判「不是 none 且是某种 flex」，而不是逐字比那个写法。
    assert narrow["iconDisplay"] in {"inline-flex", "flex"}, (
        f"窄屏下图标没显示：{narrow['iconDisplay']}")


@pytest.mark.compose
def test_the_phone_viewport_has_no_horizontal_overflow(
    screens: dict[str, dict[str, object]],
) -> None:
    """390 下整页 MUST 不横向溢出。"""
    m = screens["light-390"]
    assert int(m["docScrollW"]) <= 390 + 1, f"390 下横向溢出：{m['docScrollW']}"


# ───────────────────────── 六、既有导航语义一条不改


@pytest.mark.compose
def test_the_seven_entries_are_unchanged(
    screens: dict[str, dict[str, object]],
) -> None:
    """入口的 `href` **逐字照旧**（`ENTRY-05` 的判据一条都不许倒）。

    `NAV-ANIME-01` 换的只有长相。少一个入口或改一个 `href`，
    可达性那三个空表就不再成立了。

    改名自 `test_the_six_entries_are_unchanged`：`WB-01` / `DEC-059`
    在**末尾**加了第 7 项 `/workbench`。名字里的「六」过期了，
    而**前六项一个字没动**——这条判等值的判据正是
    「新增一屏而不是替换掉 `/design`」的签字。
    """
    # `WB-07` 调过次序（`/workbench` 排到 `/design` 之前）；七项本身一条没少。
    expected = ["/plaza", "/workbench", "/favorites", "/design",
                "/settings/locale", "/account", "/demo"]
    assert list(screens["light-1920"]["hrefs"]) == expected, (
        f"导航入口变了：{screens['light-1920']['hrefs']}")


def test_the_blueprint_is_the_only_style_source() -> None:
    """蓝本在盘上，且组件里点名了它——**风格来源唯一锚点**。"""
    assert BLUEPRINT.exists(), "蓝本不在盘上了"
    code = (REPO / "web" / "components" / "shell" / "AnimeNav.tsx").read_text(
        encoding="utf-8")

    assert "Anime Navbar.dc.html" in code, "组件没点名风格来源"
    assert "NEVER 自创一版" in code


def test_no_external_font_request_was_added() -> None:
    """**NEVER 引蓝本那条外链 Google Fonts**（CI 不联网，且那是第三方请求）。

    判的是全仓 `web/`：一条 `fonts.googleapis.com` 都不许有。
    """
    offenders: list[str] = []
    for path in sorted((REPO / "web").rglob("*.*")):
        if any(p in path.parts for p in ("node_modules", ".next")):
            continue
        if path.suffix not in {".css", ".ts", ".tsx", ".js", ".html"}:
            continue
        if "fonts.googleapis.com" in path.read_text(encoding="utf-8",
                                                    errors="replace"):
            offenders.append(path.relative_to(REPO).as_posix())

    assert offenders == [], f"这些文件引了外链字体：{offenders}"
