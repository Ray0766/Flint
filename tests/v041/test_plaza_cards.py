"""PLAZA-01：广场换成热点卡片——列表版 `PlazaView` 退役。

## 改前的实况（owner 2026-08-07 亲自起栈看到的那一屏）

`web/app/plaza/page.tsx` 接的是 `PlazaView`：一个 `<ul><li>`，**全文件 0 个 `className`**，
所以拿不到设计系统任何样式。那就是那张 4077px 项目符号列表的机械根因——
不是「样式没调好」，是**那一屏从来没有接过样式系统**。

## 判据分两层

- **源码层**：零计算（不排序/不筛选/不合成）、卡面只写一份、`PlazaView` 真的没了；
- **运行时层**：真屏上量堆叠的几何（420px 高 / perspective 1100 / 扇形与重叠）、
  量卡片真的占了像素、量网格真的是 grid。

运行时那一层是本卡的重心：`EYE-03` 那四条判据（HTTP 200 · 零控制台报错 · 无横向溢出 ·
两主题截图）在改前**全绿**，而那一屏是个 `ul/li`——**禁止性判据挡得住做错，挡不住没做**。
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

# FIX-13：小节切法只有一处（`tools/css_sections.py`）。
from tools.css_sections import (
    bare_sizes,
    colour_literals,
    section_after,
)

WEB = REPO / "web"
PLAZA_DIR = WEB / "components" / "plaza"
PAGE = WEB / "app" / "plaza" / "page.tsx"
GLOBALS = WEB / "app" / "globals.css"
ASSET = REPO / "前端设计" / "Flint 热点线索卡堆叠" / "CardStack.dc.html"
ARTIFACT = REPO / ".ui-probe" / "plaza_cards.json"

PWENV = Path(r"C:\pwenv\Scripts\python.exe")
FRONTEND = "http://localhost:3000/plaza"


def _code_only(path: Path) -> str:
    text = re.sub(r"/\*[\s\S]*?\*/", "", path.read_text(encoding="utf-8"))
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("//")
    )


def _plaza_sources() -> dict[str, str]:
    return {
        p.name: _code_only(p)
        for p in PLAZA_DIR.rglob("*.ts*")
        if not p.name.endswith(".test.tsx")
    }


def _asset_number(name: str) -> float:
    """从素材的 props 声明里取一个几何参数。**期望值的真相是素材**，判据里零手抄。"""
    text = ASSET.read_text(encoding="utf-8")
    m = re.search(rf"&quot;{name}&quot;:.*?&quot;default&quot;: ([0-9.]+)", text)
    assert m, f"素材里找不到 {name} 的默认值"
    return float(m.group(1))


# ───────────────────────── 一、列表版真的退役了


def test_the_ul_li_plaza_is_gone() -> None:
    """全仓零引用后删除，NEVER 留着两个广场。"""
    assert not (WEB / "components" / "views" / "PlazaView.tsx").exists(), (
        "PlazaView.tsx 还在——留着它，下一个人会接回去"
    )
    survivors = [
        str(p.relative_to(WEB)) for p in WEB.rglob("*.ts*")
        if "node_modules" not in p.parts
        and re.search(r"\bPlazaView\b", _code_only(p))
    ]
    assert survivors == [], f"这些文件还在引用 PlazaView：{survivors}"


def test_the_plaza_screen_is_wired_to_the_cards() -> None:
    code = _code_only(PAGE)

    assert "PlazaCards" in code, "广场屏没接卡片版"


def test_its_assertions_were_moved_not_deleted() -> None:
    """退役 NEVER 等于把判据一起删掉。

    否则「换了个更好看的广场」与「换了个不干活的广场」在测试上长得一模一样。
    """
    moved = (PLAZA_DIR / "plazaCards.test.tsx").read_text(encoding="utf-8")

    assert "顺序原样照后端" in moved, "「列簇按后端序」这条没接住"
    assert "空结果说空态" in moved, "「空结果说空态」这条没接住"


# ───────────────────────── 二、零计算


def test_the_plaza_layer_computes_nothing() -> None:
    """后端已按 total_heat 排好。本屏不排序、不筛选、不合成任何数值。

    `slice` 不在禁列里：**取前 N 段不是排序**，顺序仍是后端给的。
    """
    banned = (r"\.sort\(", r"\.filter\(", r"\.reduce\(", r"Math\.max", r"Math\.min",
              r"toFixed", r"\bparseFloat\b")

    for name, code in _plaza_sources().items():
        # 几何计算（堆叠的位移与角度）不算「合成数值」——它算的是像素，不是数据。
        data_lines = [
            line for line in code.splitlines()
            if "heat" in line or "cluster" in line or "cards" in line
        ]
        for pattern in banned:
            hits = [line.strip() for line in data_lines if re.search(pattern, line)]
            assert hits == [], f"{name} 对数据做了计算（{pattern}）：{hits}"


def test_the_heat_is_carried_through_untouched() -> None:
    code = _plaza_sources()["clusterToCard.ts"]

    assert "heat: cluster.total_heat" in code, "热度不是原样搬运的"


# ───────────────────────── 三、卡面只写一份


# 骨架卡是**唯一**准借卡壳的：它的全部意义就是占住将来那张卡的位置，
# 借的是同一套盒子类（`hotspot-card` / `__top` / `__foot`），所以尺寸逐像素相同。
# 另写一个「长得像卡片」的盒子才是坏事——那就有两份卡形在漂了。
# 借的代价由下一条判据兜住：**它一个数据槽都不许渲染**。
SHELL_BORROWER = "HotspotCardSkeleton.tsx"


def test_the_layout_layers_never_draw_the_card_face() -> None:
    """堆叠与网格只负责排布。两份卡面会各自漂移，而它们渲染的是同一份数据。"""
    for name, code in _plaza_sources().items():
        if name == SHELL_BORROWER:
            continue
        assert "hotspot-card__" not in code, f"{name} 在画卡面内部结构"
        assert "native-name" not in code, f"{name} 在画名称槽"


def test_the_shell_borrower_renders_no_data_at_all() -> None:
    """骨架卡借了卡壳，**但一个数据槽都不许渲染**。

    渲染了数据的「骨架」就是第二份卡面，而它会与真卡各自漂移；
    更坏的是：加载态里出现真内容，用户会把半份数据读成全部。
    """
    code = _plaza_sources()[SHELL_BORROWER]

    for slot in ("NativeName", "hotspot-region", "hotspot-verdict",
                 "hotspot-first-seen", "hotspot-stale", "hotspot-heat",
                 "clusterToCard", "PlazaCardProps"):
        assert slot not in code, f"骨架卡渲染了数据槽 {slot}"
    # 它连一个数据入参都不该有：只收「画几张」。
    assert "clusters" not in code and "cards" not in code


def test_both_layouts_render_the_same_component() -> None:
    stack = _plaza_sources()["HotspotCardStack.tsx"]
    cards = _plaza_sources()["PlazaCards.tsx"]

    assert "HotspotCard" in stack and "HotspotCard" in cards
    for code in (stack, cards):
        assert 'from "../hotspot-card/HotspotCard"' in code


def test_no_new_dependency_came_with_the_animation() -> None:
    """堆叠有动效，而素材那份是零依赖实现的——照它做即可（S2-6）。"""
    pkg = json.loads((WEB / "package.json").read_text(encoding="utf-8"))
    deps = {**pkg["dependencies"], **pkg["devDependencies"]}

    for banned in ("framer-motion", "lucide-react", "tailwindcss", "react-spring",
                   "embla-carousel-react", "swiper"):
        assert banned not in deps, f"{banned} 被加进了依赖"


# ───────────────────────── 四、几何照素材


def test_the_stack_geometry_matches_the_asset() -> None:
    """扇形角度与重叠率**从素材的 props 声明解析**，NEVER 手抄一个数。"""
    code = _plaza_sources()["HotspotCardStack.tsx"]

    assert f"SPREAD_DEG = {int(_asset_number('spreadDeg'))}" in code
    assert f"OVERLAP = {_asset_number('overlap')}" in code


def test_the_keyboard_path_exists_in_source() -> None:
    """NEVER 只能拖拽：只留拖拽的话，用键盘与用读屏的人到不了第二张卡。"""
    code = _plaza_sources()["HotspotCardStack.tsx"]

    assert "ArrowLeft" in code and "ArrowRight" in code
    assert "tabIndex={0}" in code
    assert "focus-visible" in GLOBALS.read_text(encoding="utf-8"), (
        "焦点环没写——能用键盘但看不出焦点在哪，和不能用差不多"
    )


def test_the_plaza_styles_use_tokens_except_the_named_geometry() -> None:
    """本段样式的字号、间距、颜色**一律走 `_ds` token**；几何值**显式列名**。

    `UI-01` 那把尺子（`test_ui_restyle.py`）判的是它自己那一段——本段由这里判，
    口径相同：颜色零字面量、字号与间距零裸值。

    几何是例外，而例外**逐个写在这里**：`_ds` 的刻度里没有「420px 的台面高」
    「1100px 的透视距」「300px 的网格列底」——它们是舞台尺寸，不是字号也不是间距。
    把它们硬塞成 `--sp-*` 的组合只会多一层间接，不会多一分一致性
    （那正是 `UI-01` 那条判据自己的原话）。
    NEVER 靠「判据没查到」蒙混：名单少一条即红，多一条要来这里解释。
    """
    # 收敛到**本段**：`globals.css` 是追加式的，取到文件尾会把后来每一段
    # （DESIGN-02 的工作台样式就是）都当成本卡的判。
    # 这与 `UI01-RULER-JUDGES-EVERY-LATER-SECTION.md` 记的是同一个毛病——
    # 本卡写这条尺子时照抄了那个形状，**照抄错的也是错的**。
    #
    # `FIX-13` 把切法收成一处（`tools/css_sections.py`）：
    # 这里原先自己写了一遍，还带着那个魔数 `8`。
    css = GLOBALS.read_text(encoding="utf-8")
    section = section_after(css, "* PLAZA-01 · 广场")

    colours = colour_literals(section)
    assert colours == [], f"本段写死了颜色：{colours}"

    # 逐个列名的几何值。新增一个就要来这里加一行并说清它是什么——
    # 420/1100 是台面高与透视距（素材原值）、300 是网格列底、180 是卡片高底、
    # 1160 是卡片屏的最大内容宽；520×320 是素材里卡片本身的尺寸，
    # PLAZA-03 的骨架用它占住堆叠当前卡的位（占不对位的骨架等于没占）。
    allowed = ("420px", "1100px", "300px", "180px", "1160px", "520px", "320px")
    offenders = bare_sizes(section, allowed)
    assert offenders == [], f"本段写死了字号/间距：{offenders}"


# ───────────────────────── 五、运行时：真屏上量


_RUNNER = r"""
import json, sys
from playwright.sync_api import sync_playwright

url, out = sys.argv[1], sys.argv[2]
with sync_playwright() as p:
    b = p.chromium.launch()
    page = b.new_page(viewport={"width": 1440, "height": 900})
    errs = []
    page.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
    page.goto(url, wait_until="networkidle", timeout=60000)
    page.wait_for_selector("[data-plaza-stack]", timeout=30000)
    page.wait_for_timeout(1200)
    got = page.evaluate(
        '''() => {
            const deck = document.querySelector('.plaza-stack__deck');
            const grid = document.querySelector('.plaza-grid__list');
            const cards = [...document.querySelectorAll('.hotspot-card')];
            const first = cards[0] ? cards[0].getBoundingClientRect() : null;
            const slots = [...document.querySelectorAll('.plaza-stack__slot')];
            const dcs = getComputedStyle(deck);
            const gcs = getComputedStyle(grid);
            return {
              deck: {height: dcs.height, perspective: dcs.perspective},
              grid: {display: gcs.display, listStyleType: gcs.listStyleType,
                     columns: gcs.gridTemplateColumns.split(' ').length},
              cardCount: cards.length,
              firstCard: first ? {width: first.width, height: first.height} : null,
              stackSlots: slots.length,
              activeSlots: document.querySelectorAll(
                  '[data-stack-active="true"]').length,
              dots: document.querySelectorAll('.plaza-stack__dot').length,
              counter: (document.querySelector('.plaza-stack__counter')
                        || {}).textContent || '',
              transforms: slots.slice(0, 3).map(
                  s => getComputedStyle(s).transform),
              bodyScrollWidth: document.body.scrollWidth,
              innerWidth: window.innerWidth,
            };
        }''')
    got["console_errors"] = errs
    page.screenshot(path=".ui-probe/plaza-cards.png", full_page=False)
    b.close()
open(out, "w", encoding="utf-8").write(
    json.dumps({"schema": "plaza-cards/1", "url": url, **got},
               ensure_ascii=False, indent=1))
"""


def _artifact() -> dict[str, object]:
    if ARTIFACT.exists():
        return json.loads(ARTIFACT.read_text(encoding="utf-8"))
    if not PWENV.exists():
        pytest.skip(f"本机没有 {PWENV}（playwright 恒在项目外，NEVER 进项目依赖）")
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        runner = Path(tmp) / "plaza_cards_runner.py"
        runner.write_text(_RUNNER, encoding="utf-8")
        done = subprocess.run(
            [str(PWENV), str(runner), FRONTEND, str(ARTIFACT)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=REPO, check=False,
        )
    if done.returncode != 0:
        pytest.skip(f"前端没起或探针跑不动（{FRONTEND}）：{done.stderr[-500:]}")
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


def test_the_deck_is_a_420px_stage_with_perspective() -> None:
    deck = _artifact()["deck"]

    assert deck["height"] == "420px", f"堆叠台面不是 420px：{deck}"
    assert deck["perspective"] == "1100px", (
        f"没有透视——没有透视的「堆叠」只是几张重叠的卡：{deck}"
    )


def test_the_cards_really_occupy_pixels() -> None:
    """`F-09` 量的正是这一件事的反面：DOM 里有、宽高是 0。"""
    art = _artifact()

    assert art["cardCount"] > 0, "屏上一张卡都没有"
    first = art["firstCard"]
    assert first["width"] > 200 and first["height"] > 100, f"卡片几乎没有面积：{first}"


def test_the_stack_fans_out_instead_of_piling_up() -> None:
    """三张相邻卡的 transform 互不相同——一样就说明它们叠在一处，扇形没生效。"""
    transforms = _artifact()["transforms"]

    assert len(transforms) >= 3, "堆叠里的卡不足三张"
    assert len(set(transforms)) == len(transforms), f"卡片叠在一处：{transforms}"
    assert all(t != "none" for t in transforms)


def test_exactly_one_card_is_in_front() -> None:
    art = _artifact()

    assert art["activeSlots"] == 1, f"当前卡不是恰好一张：{art['activeSlots']}"
    assert art["dots"] == art["stackSlots"], "圆点数与卡数对不上"
    assert "/" in art["counter"], f"计数器没写 N / M：{art['counter']!r}"


def test_the_full_list_is_a_grid_not_a_bullet_list() -> None:
    """改前那一屏是 `ul/li` 带项目符号。这条盯着它 NEVER 回去。"""
    grid = _artifact()["grid"]

    assert grid["display"] == "grid", f"全量区不是网格：{grid}"
    assert grid["listStyleType"] == "none", "项目符号还在"
    assert grid["columns"] >= 2, f"1440px 下只有 {grid['columns']} 列"


def test_the_screen_is_clean() -> None:
    art = _artifact()

    assert art["console_errors"] == [], f"控制台有报错：{art['console_errors']}"
    assert art["bodyScrollWidth"] <= art["innerWidth"] + 1, "横向溢出"
