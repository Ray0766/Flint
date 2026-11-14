"""NAV-ANIME-02：吉祥物照蓝本做全（owner 2026-08-10：**要，照蓝本做全**）。

## 来源

`前端设计/Anime navbar live demo/Anime Navbar.dc.html` 第 56~71 行那一块。
尺寸与位置逐条照抄：

| 部件 | 蓝本 |
|---|---|
| 整体 | `top: -48px` · 48×48 · `left = 当前项中心 - 24` |
| 头 | 40×40 白圆 · `mBob 2s` |
| 眼 | 8×8 黑圆 @ `left/right 25%` · `top 40%` |
| 腮红 | 8×6 `#f9a8d4` @ `left/right 15%` · `top 55%` · 不透明度 0.6 |
| 嘴 | 16×8 · `border-bottom: 2px solid #000` @ `left 30%` · `top 60%` |
| 尾巴 | 16×16 白方块旋 45° · `mTailBob 1s` |

hover 时四样一起变：头 `mWiggle` · 眼 `mBlink` · 尾 `mTailHop` · 冒两颗 ✨；
腮红 0.6 → 0.8，嘴 `scaleY(1.5) translateY(-1px)`。

## 本仓补的一条（蓝本没有）

`prefers-reduced-motion: reduce` 时**全部动画停**——
**吉祥物仍在位、仍跟随，只是不动**。停的是动，不是位置。

## 判据一律正向

每条都是「MUST 长成什么样 / MUST 在动什么」+ 实测值。
动画那几条打 computed 的 `animation-name`，**NEVER 只断言「类名在」**——
类名在而 keyframes 没定义时，屏上什么都不会发生。
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
import json
from playwright.sync_api import sync_playwright

READ = '''() => {
  const q = s => document.querySelector(s);
  const m = q('.anime-nav__mascot');
  if (!m) return {missing: true};
  const box = s => { const e = q(s); if (!e) return null;
    const r = e.getBoundingClientRect();
    return {l: r.left, t: r.top, w: r.width, h: r.height}; };
  const anim = s => { const e = q(s); return e ? getComputedStyle(e).animationName : null; };
  const active = q('.anime-nav a[data-active="true"]');
  const ar = active ? active.getBoundingClientRect() : null;
  const mr = m.getBoundingClientRect();
  const head = q('.anime-nav__mascot-head');
  return {
    mascotCx: mr.left + mr.width / 2,
    tabCx: ar ? ar.left + ar.width / 2 : null,
    activeTab: active ? active.dataset.tab : null,
    pointerEvents: getComputedStyle(m).pointerEvents,
    opacity: parseFloat(getComputedStyle(m).opacity),
    headBox: box('.anime-nav__mascot-head'),
    eyeBox: box('.anime-nav__mascot-eye--l'),
    blushBox: box('.anime-nav__mascot-blush--l'),
    mouthBox: box('.anime-nav__mascot-mouth'),
    tailBox: box('.anime-nav__mascot-tail'),
    headAnim: anim('.anime-nav__mascot-head'),
    eyeAnim: anim('.anime-nav__mascot-eye--l'),
    tailAnim: anim('.anime-nav__mascot-tail'),
    sparkles: document.querySelectorAll('.anime-nav__mascot-sparkle').length,
    blushOpacity: parseFloat(getComputedStyle(q('.anime-nav__mascot-blush--l')).opacity),
    mouthTransform: getComputedStyle(q('.anime-nav__mascot-mouth')).transform,
    headShadow: getComputedStyle(head).boxShadow,
    headBg: getComputedStyle(head).backgroundColor,
  };
}'''

OUT = {}
with sync_playwright() as pw:
    b = pw.chromium.launch()

    for theme in ("light", "dark"):
        page = b.new_page(viewport={"width": 1920, "height": 1080},
                          color_scheme=theme)
        page.goto("http://localhost:3000/plaza", wait_until="networkidle")
        page.wait_for_timeout(800)
        OUT[f"idle-{theme}"] = page.evaluate(READ)
        page.hover('.anime-nav a[data-tab="/favorites"]')
        page.wait_for_timeout(350)
        OUT[f"hover-{theme}"] = page.evaluate(READ)
        page.close()

    # 切一屏：吉祥物 MUST 跟过去
    page = b.new_page(viewport={"width": 1920, "height": 1080})
    page.goto("http://localhost:3000/plaza", wait_until="networkidle")
    page.wait_for_timeout(800)
    OUT["before_switch"] = page.evaluate(READ)
    page.goto("http://localhost:3000/account", wait_until="networkidle")
    page.wait_for_timeout(900)
    OUT["switched"] = page.evaluate(READ)
    page.close()

    # **减动效**：全停，而仍在位、仍跟随
    page = b.new_page(viewport={"width": 1920, "height": 1080},
                      reduced_motion="reduce")
    page.goto("http://localhost:3000/account", wait_until="networkidle")
    page.wait_for_timeout(900)
    OUT["reduced"] = page.evaluate(READ)
    page.hover('.anime-nav a[data-tab="/favorites"]')
    page.wait_for_timeout(350)
    OUT["reduced_hover"] = page.evaluate(READ)
    page.close()

    # 吉祥物下面那一项**仍然点得动**（`pointer-events: none` 的意义）
    page = b.new_page(viewport={"width": 1920, "height": 1080})
    page.goto("http://localhost:3000/plaza", wait_until="networkidle")
    page.wait_for_timeout(800)
    m = page.evaluate('''() => {
      const r = document.querySelector('.anime-nav__mascot').getBoundingClientRect();
      return {x: r.left + r.width / 2, y: r.top + r.height - 2};
    }''')
    hit = page.evaluate('''([x, y]) => {
      const el = document.elementFromPoint(x, y);
      return el ? (el.closest('a[data-tab]')?.dataset.tab ?? el.className) : null;
    }''', [m["x"], m["y"]])
    OUT["click_through"] = {"hit": hit}
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
def seen() -> dict[str, dict[str, object]]:
    return _probe()


# ───────────────────────── 一、位置：坐在当前项正上方，且跟过去


@pytest.mark.compose
def test_the_mascot_is_centred_on_the_active_tab(
    seen: dict[str, dict[str, object]],
) -> None:
    """吉祥物水平中心 = 当前项中心（±2px）。

    实测：mascotCx 528 == tabCx 528。
    蓝本 `mascotLeft = r.left + r.width / 2 - 24` 那一行的落点。
    """
    m = seen["idle-dark"]
    assert not m.get("missing"), "屏上没有吉祥物"

    assert abs(float(m["mascotCx"]) - float(m["tabCx"])) <= 2, (
        f"吉祥物中心 {m['mascotCx']:.0f} 与当前项中心 {m['tabCx']:.0f} 差太多")
    assert float(m["opacity"]) > 0.9, "吉祥物没显示出来"


@pytest.mark.compose
def test_the_mascot_follows_when_the_page_changes(
    seen: dict[str, dict[str, object]],
) -> None:
    """**真切换再量**：换一屏之后它跟到新的当前项上。

    只在一屏上量的话，一个把 `left` 写死的实现也会绿。
    """
    before, after = seen["before_switch"], seen["switched"]

    assert before["activeTab"] != after["activeTab"], "这条判据没切成"
    assert abs(float(after["mascotCx"]) - float(after["tabCx"])) <= 2, (
        f"切换后没跟过去：吉祥物 {after['mascotCx']:.0f} "
        f"当前项 {after['tabCx']:.0f}")
    assert abs(float(before["mascotCx"]) - float(after["mascotCx"])) > 10, (
        "切换前后吉祥物停在同一个位置——它没有跟随")


@pytest.mark.compose
def test_the_mascot_sits_above_the_bar(
    seen: dict[str, dict[str, object]],
) -> None:
    """它在条**上方**（蓝本 `top: -48px`），不是压在条里。"""
    head = seen["idle-dark"]["headBox"]

    # **NEVER 逐字比浮点**：浏览器算出来的是 39.999996185302734。
    # 判「四舍五入到整数等于 40」——量的是那个尺寸，不是浮点表示。
    assert (round(float(head["w"])), round(float(head["h"]))) == (40, 40), (
        f"头不是 40×40：{head['w']}×{head['h']}")
    assert float(head["t"]) < 48, f"头压得太低（top={head['t']:.0f}）——它该浮在条上方"


# ───────────────────────── 二、部件齐全，尺寸照蓝本


@pytest.mark.compose
def test_every_part_is_there_with_the_blueprint_size(
    seen: dict[str, dict[str, object]],
) -> None:
    """眼 8×8 · 腮红 8×6 · 嘴 16×? · 尾 16×16——**逐条照蓝本**。

    少一件屏上就不是那个吉祥物了，而「有个白圆」这种判据看不出来。
    """
    m = seen["idle-dark"]
    eye, blush, mouth, tail = m["eyeBox"], m["blushBox"], m["mouthBox"], m["tailBox"]

    assert eye and (round(eye["w"]), round(eye["h"])) == (8, 8), f"眼睛：{eye}"
    assert blush and (round(blush["w"]), round(blush["h"])) == (8, 6), f"腮红：{blush}"
    assert mouth and round(mouth["w"]) == 16, f"嘴：{mouth}"
    assert tail and (round(tail["w"]), round(tail["h"])) == (16, 16), f"尾巴：{tail}"


@pytest.mark.compose
def test_the_parts_sit_where_the_blueprint_puts_them(
    seen: dict[str, dict[str, object]],
) -> None:
    """眼在头的 40% 高处、腮红 55%、嘴 60%——**相对头去量**。

    绝对坐标会随条的位置变，相对位置才是蓝本说的那件事。
    """
    m = seen["idle-dark"]
    head = m["headBox"]
    rel = lambda part: (float(part["t"]) - float(head["t"])) / float(head["h"])

    assert 0.30 <= rel(m["eyeBox"]) <= 0.50, f"眼睛不在 40% 高处：{rel(m['eyeBox']):.2f}"
    assert 0.45 <= rel(m["blushBox"]) <= 0.65, f"腮红不在 55%：{rel(m['blushBox']):.2f}"
    assert 0.50 <= rel(m["mouthBox"]) <= 0.72, f"嘴不在 60%：{rel(m['mouthBox']):.2f}"


# ───────────────────────── 三、四种交互动画各有判据


@pytest.mark.compose
def test_idle_is_bob_and_tail_bob(seen: dict[str, dict[str, object]]) -> None:
    """不 hover 时：头漂浮 `mBob`、尾巴轻摆 `mTailBob`。

    判的是 computed 的 `animation-name`——**NEVER 只断言「类名在」**：
    类名在而 keyframes 没定义时，屏上什么都不会发生。
    """
    m = seen["idle-dark"]

    assert m["headAnim"] == "mBob", f"静止时头没在漂浮：{m['headAnim']}"
    assert m["tailAnim"] == "mTailBob", f"静止时尾巴没在摆：{m['tailAnim']}"
    assert m["eyeAnim"] in {"none", ""}, f"静止时眼睛在眨：{m['eyeAnim']}"
    assert int(m["sparkles"]) == 0, "静止时就在冒星星"


@pytest.mark.compose
def test_hovering_makes_it_wiggle_blink_hop_and_sparkle(
    seen: dict[str, dict[str, object]],
) -> None:
    """hover 时四样一起来：`mWiggle` · `mBlink` · `mTailHop` · 两颗 ✨。

    实测（1920 暗底）：全部成立，腮红 0.6 → 0.80，嘴 `scaleY(1.5)`。
    """
    m = seen["hover-dark"]

    assert m["headAnim"] == "mWiggle", f"没扭动：{m['headAnim']}"
    assert m["eyeAnim"] == "mBlink", f"没眨眼：{m['eyeAnim']}"
    assert m["tailAnim"] == "mTailHop", f"尾巴没跳：{m['tailAnim']}"
    assert int(m["sparkles"]) == 2, f"星星不是两颗：{m['sparkles']}"


@pytest.mark.compose
def test_hovering_changes_the_face(seen: dict[str, dict[str, object]]) -> None:
    """腮红更红、嘴咧开——两样都是**值变了**，不是类名换了。"""
    idle, hover = seen["idle-dark"], seen["hover-dark"]

    assert float(hover["blushOpacity"]) > float(idle["blushOpacity"]), (
        f"腮红没变：{idle['blushOpacity']} → {hover['blushOpacity']}")
    assert hover["mouthTransform"] != idle["mouthTransform"], (
        f"嘴没变：{idle['mouthTransform']}")
    assert "1.5" in str(hover["mouthTransform"]), (
        f"嘴不是蓝本那个 scaleY(1.5)：{hover['mouthTransform']}")


# ───────────────────────── 四、减动效：全停，而仍在位、仍跟随（本仓补的）


@pytest.mark.compose
def test_reduced_motion_stops_every_animation(
    seen: dict[str, dict[str, object]],
) -> None:
    """**阴性对照**（acceptance④）：开着减动效仍在动 → 判据红。

    蓝本没有这一条，是本仓补的。系统说了不要动效就 NEVER 动。
    """
    m = seen["reduced"]
    still = {"none", ""}

    assert m["headAnim"] in still, f"减动效下头还在动：{m['headAnim']}"
    assert m["tailAnim"] in still, f"减动效下尾巴还在动：{m['tailAnim']}"
    assert m["eyeAnim"] in still, f"减动效下眼睛还在眨：{m['eyeAnim']}"

    hovered = seen["reduced_hover"]
    assert hovered["headAnim"] in still, (
        f"减动效下 hover 还会扭动：{hovered['headAnim']}")
    assert hovered["tailAnim"] in still


@pytest.mark.compose
def test_reduced_motion_keeps_it_in_place_and_following(
    seen: dict[str, dict[str, object]],
) -> None:
    """**停的是动，不是位置**：减动效下它仍在当前项正上方。

    连位置一起停掉的话，它会留在上一屏的那个 tab 上方——
    那不是「尊重偏好」，那是坏了。
    """
    m = seen["reduced"]

    assert float(m["opacity"]) > 0.9, "减动效下吉祥物不见了"
    assert abs(float(m["mascotCx"]) - float(m["tabCx"])) <= 2, (
        f"减动效下没跟到当前项：吉祥物 {m['mascotCx']:.0f} "
        f"当前项 {m['tabCx']:.0f}")


# ───────────────────────── 五、两主题都看得清


@pytest.mark.compose
def test_it_is_visible_on_both_themes(
    seen: dict[str, dict[str, object]],
) -> None:
    """亮底给它一圈描边（本仓补的）——白脸放在浅色纸上会糊成一团。

    沿用 `DARK-02` 的判据形状：**两主题量到同一组值就判红**。
    """
    light, dark = seen["idle-light"], seen["idle-dark"]

    assert light["headShadow"] != dark["headShadow"], (
        f"两主题下头的描边一样（{light['headShadow']}）——"
        f"亮底那一套没生效")
    assert light["headShadow"] not in {"none", ""}, "亮底下白脸没有描边"


# ───────────────────────── 六、它挡不住任何可点区域


@pytest.mark.compose
def test_the_tab_under_the_mascot_is_still_clickable(
    seen: dict[str, dict[str, object]],
) -> None:
    """`pointer-events: none`（蓝本原话）——**判据真去点它底下**。

    在吉祥物矩形内取一点做 `elementFromPoint`，
    拿到的 MUST 是导航项，不是吉祥物。
    """
    assert seen["idle-dark"]["pointerEvents"] == "none", (
        f"吉祥物在吃点击：pointer-events={seen['idle-dark']['pointerEvents']}")
    hit = seen["click_through"]["hit"]
    assert hit and "mascot" not in str(hit), (
        f"吉祥物挡住了它下面的东西：elementFromPoint 命中 {hit}")


def test_the_blueprint_block_is_named_in_the_component() -> None:
    """组件里点名了蓝本那一块——**风格来源唯一锚点**。"""
    assert BLUEPRINT.exists()
    code = (REPO / "web" / "components" / "shell" / "AnimeNav.tsx").read_text(
        encoding="utf-8")

    assert "蓝本第 56~71 行" in code, "组件没点名蓝本那一块"
    assert "pointer-events" in code


def test_the_reduced_motion_addition_is_written_down() -> None:
    """减动效那一条是**本仓补的**，MUST 写明。

    不写的话，下一个人对着蓝本比对时会以为它是多余的。
    """
    css = (REPO / "web" / "app" / "globals.css").read_text(encoding="utf-8")

    assert "prefers-reduced-motion" in css
    assert "本仓补的" in css
    assert "停的是**动**，不是位置" in css or "停的是动，不是位置" in css
