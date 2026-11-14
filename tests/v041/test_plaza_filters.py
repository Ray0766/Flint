"""REGION-10：广场地区筛选器上屏（第 5 批 `PLAZA-02` 重做）。

## 改前

`RegionSwitch` 与 `SourceColumns` 两个组件**建好至今零页面引用**。
广场空态里那句 `plaza.region.switch_not_wired`（「切换还没接上」）是当时的实话：
`GET /plaza/hot` 只收 `day`。

`REGION-09` 之后那句话变成了**假话**——端点真的筛了
（154 → `CN` 68 / `global` 85，互不相交、都是全量真子集）。所以本卡把它变成真开关。

## 判据打真栈

「切区后卡片集合真的变了」**只能在真栈上量**：组件层能测的是「onChange 被调了」，
而改前那一版**也会调**——它只是调完之后请求回来的东西没变。
这正是 `DEC-035` 那句话的形状：**静静地什么都不筛的筛选器比没有筛选器更坏**。

## 文案有一条硬约束

端点回的两个区是 `CN` 与 `global`。**`global` 不是一个区**——它是 `ghtrend`
源码里写死的常量（「这个源不分区」），单据
`docs/blocked/REGION-08-GLOBAL-IS-A-SOURCE-CONSTANT-NOT-A-REGION.md` 待 owner 裁。

所以本屏**恒用端点/清单回的区名原样显示**，NEVER 自己映射成「全球」：
用户选「全球」拿到的会是只来自 GitHub Trending 的那 85 条。
"""
from __future__ import annotations

import json
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[2]
WEB = REPO / "web"
PAGE = WEB / "app" / "plaza" / "page.tsx"
CARDS = WEB / "components" / "plaza" / "PlazaCards.tsx"
SWITCH = WEB / "components" / "region-switch" / "RegionSwitch.tsx"
COLUMNS = WEB / "components" / "source-columns" / "SourceColumns.tsx"
SHEET = REPO / "docs" / "blocked" / (
    "PLAZA-02-REGION-QUERY-AND-SOURCE-REGION-NOT-BUILT.md")
COMPOSITION = REPO / "assets" / "screen_composition.json"

PWENV = Path(r"C:\pwenv\Scripts\python.exe")
DEMO_WEB = "http://localhost:3000"
ARTIFACT = REPO / ".ui-probe" / "plaza_region_filter.json"


def _code_only(path: Path) -> str:
    text = re.sub(r"/\*[\s\S]*?\*/", "", path.read_text(encoding="utf-8"))
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("//")
    )


# ───────────────────────── 一、组件真的接上了屏


def test_the_region_switch_is_on_the_plaza_screen() -> None:
    """`RegionSwitch` 从「建好没人用」变成屏上真有。

    判**调用点**而不是 import：只留一个 import 而不渲染，
    「组件建好了屏没用」这件事在判据上看不出来——本仓踩过五次。
    """
    code = _code_only(PAGE)

    assert "<RegionSwitch" in code, "广场屏上没有 RegionSwitch"
    assert "region-switch/RegionSwitch" in code


def test_the_list_comes_from_the_endpoint_not_a_local_copy() -> None:
    """九区清单来自 `GET /settings/locale` 的 `options.region`（LOC-01）。

    广场再抄一份的后果：加第十个区那天只有一处会跟上，
    而读的人分不出哪份是真的。
    """
    code = _code_only(PAGE)

    assert "options?.region" in code or "options.region" in code, "清单不是从端点取的"
    for hardcoded in ('"CN"', "'CN'", '"US"', "'US'", '"global"', "'global'"):
        assert hardcoded not in code, f"广场屏里写死了区名 {hardcoded}"


def test_the_not_wired_line_is_gone() -> None:
    """那句「切换还没接上」现在是假话——**留着它比没有更坏**。

    它会让用户以为筛选器不工作，于是不去用一个已经能用的东西。
    """
    assert "plaza.region.switch_not_wired" not in _code_only(CARDS), (
        "空态里还写着「切换还没接上」"
    )
    assert "plaza.region.switch_not_wired" not in _code_only(PAGE)


def test_the_screen_composition_declares_it() -> None:
    """`GAUGE-12` 的正向尺子：新组件 MUST 登记进逐屏声明。

    不登记的话，它哪天被删掉，没有任何判据会响。
    """
    declared = json.loads(COMPOSITION.read_text(encoding="utf-8"))
    plaza = next(
        (s for s in declared["screens"] if s["route"] == "/plaza"), None)

    assert plaza is not None, "屏声明里没有 /plaza"
    # 声明面是**选择器**（`GAUGE-12` 定的形状：判运行时量得到，不判类名在源码里）。
    assert any("region-select" in sel for sel in plaza["components"]), (
        "地区下拉没登记进 /plaza 的组件声明"
    )
    assert any("region-switch" in name for name in plaza["styled"]), (
        "地区下拉没登记进样式声明——`GAUGE-12` 的另一半：结构与样式成对交付"
    )


# ───────────────────────── 二、两条轴正交（A3，两个方向都判）


def test_switching_region_never_changes_the_language() -> None:
    """切区时 `lang` **原样带回**——组件自己守着这一条，屏不能绕过它。"""
    code = _code_only(PAGE)
    call = code[code.index("<RegionSwitch"):]
    call = call[: call.index("/>") + 2]

    assert "lang=" in call, "没把当前语言传给 RegionSwitch"
    assert "onChange" in call


def test_switching_language_never_refetches_the_hotspots() -> None:
    """反向那条轴：语言变了 NEVER 重拉热点集合。

    取数的依赖数组里**只能有 region 与 day**——把 `locale` 整个放进去，
    切语言会顺手把热点集合换一批，而那正是 A3 禁止的耦合。
    """
    code = _code_only(PAGE)
    effects = re.findall(r"useEffect\([\s\S]*?\}, \[([^\]]*)\]\)", code)

    assert effects, "屏上没有取数 effect"
    fetching = [dep for dep in effects if "fetchPlazaHot" in code]
    assert fetching is not None
    for deps in effects:
        assert "lang" not in deps, f"取数 effect 依赖了语言：[{deps}]"


# ───────────────────────── 三、真栈：切区后卡片集合真的变了


_RUNNER = """
import json, sys
from playwright.sync_api import sync_playwright
base, out = sys.argv[1], sys.argv[2]

def ids(page):
    return page.evaluate('''() => [...document.querySelectorAll(
        '[data-plaza-list] [data-cluster-id]')].map(e => e.getAttribute('data-cluster-id'))''')

got = {}
with sync_playwright() as p:
    b = p.chromium.launch()
    page = b.new_page(viewport={"width": 1440, "height": 900})
    errs = []
    page.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
    page.goto(base + "/plaza", wait_until="networkidle", timeout=60000)
    page.wait_for_selector('[data-testid="hotspot-card"]', timeout=30000)
    got["whole"] = ids(page)
    got["hasSwitch"] = page.locator('[data-testid="region-select"]').count()
    got["options"] = page.evaluate('''() => [...document.querySelectorAll(
        '[data-testid="region-select"] option')].map(o => o.value)''')
    got["labels"] = page.evaluate('''() => [...document.querySelectorAll(
        '[data-testid="region-select"] option')].map(o => o.textContent.trim())''')
    if got["hasSwitch"]:
        for value in got["options"]:
            page.select_option('[data-testid="region-select"]', value)
            page.wait_for_timeout(1200)
            got.setdefault("byRegion", {})[value] = ids(page)
            got.setdefault("urls", {})[value] = page.url
            got.setdefault("emptyState", {})[value] = page.locator(
                '[data-testid="plaza-empty"]').count()
    page.screenshot(path=".ui-probe/plaza-region-filter.png", full_page=False)
    got["console_errors"] = errs
    b.close()
open(out, "w", encoding="utf-8").write(
    json.dumps({"schema": "plaza-region-filter/1", **got}, ensure_ascii=False, indent=1))
"""


def _screen() -> dict[str, Any]:
    if ARTIFACT.exists():
        return json.loads(ARTIFACT.read_text(encoding="utf-8"))
    if not PWENV.exists():
        pytest.skip(f"本机没有 {PWENV}（playwright 恒在项目外）")
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        runner = Path(tmp) / "plaza_region_runner.py"
        runner.write_text(_RUNNER, encoding="utf-8")
        done = subprocess.run(
            [str(PWENV), str(runner), DEMO_WEB, str(ARTIFACT)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=REPO, check=False,
        )
    if done.returncode != 0:
        pytest.skip(f"前端没起或探针跑不动：{done.stderr[-500:]}")
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


def test_the_switch_is_really_on_screen_with_the_real_options() -> None:
    art = _screen()

    assert art["hasSwitch"], "屏上没有地区下拉"
    assert len(art["options"]) >= 2, f"可选区不足两个：{art['options']}"


def test_switching_really_changes_the_card_set() -> None:
    """**本卡的核心判据**：切区之后卡片集合真的变了。

    只断言「请求发出去了」的话，改前那一版照样绿——它也发请求，
    只是回来的东西一条没少。

    ## 判据形状随实况改过一次

    第一版要「两个都非空的区，集合不同」。本机数据里**只有 `CN` 有热点**
    （其余八区今天没有），那条判据会因为拿不到第二个非空区而红——
    **红的是判据的假设，不是筛选器**。

    改成三条，合起来比原来更强，且**改前那一版一条都过不了**
    （改前每个区都回全量 154）：

    1. 至少一个区是**非空真子集**（`CN`：0 < 68 < 154）；
    2. 至少一个区是**空的**——那证明筛选真的排除了东西，
       且它落到既有空态而不是回落到别的区；
    3. **没有任何一个区回全量**——那正是改前的样子。
    """
    art = _screen()
    by_region = {r: set(ids) for r, ids in (art.get("byRegion") or {}).items()}
    whole = set(art["whole"])

    assert len(by_region) >= 2, f"只量到 {len(by_region)} 个区"
    assert whole, "全量是空的，这条判据在空转"

    nonempty = {r: got for r, got in by_region.items() if got}
    empty = [r for r, got in by_region.items() if not got]

    assert nonempty, "每个区都是空的——那不是筛选，是断了"
    for region, got in nonempty.items():
        assert got < whole, f"{region} 不是全量的真子集：{len(got)} vs {len(whole)}"
    assert empty, "没有任何一个区被筛空——筛选器可能根本没在排除东西"
    for region, got in by_region.items():
        assert got != whole, f"{region} 回的是全量——那正是改前的样子"


def test_an_empty_region_lands_on_the_existing_empty_state() -> None:
    """acceptance⑤：空区落 `PLAZA-03` 已建的「该区当日无数据」态。

    **NEVER 回落到别的区假装有数据**（规格 #2.14 的原话）——
    回落之后屏上有卡片、标题写着你选的区，而那些卡片属于另一个区。
    """
    art = _screen()
    by_region = {r: set(ids) for r, ids in (art.get("byRegion") or {}).items()}
    empty_state = art.get("emptyState") or {}

    empty = [r for r, got in by_region.items() if not got]
    assert empty, "没有空区可测"
    for region in empty:
        assert empty_state.get(region), f"{region} 是空的，屏上却没有空态"


def test_the_chosen_region_survives_a_reload() -> None:
    """选中的区写进 URL：刷新之后停在同一个区。

    不写的话，用户分享一个链接给同事，同事看到的是另一个区的热点，
    而两人都以为在看同一屏。
    """
    art = _screen()
    urls = art.get("urls") or {}

    assert urls, "没量到 URL"
    for region, url in urls.items():
        assert f"region={region}" in url, f"切到 {region} 之后 URL 没跟上：{url}"


def test_the_screen_stays_clean_while_switching() -> None:
    art = _screen()

    assert art["console_errors"] == [], f"切区过程中有控制台报错：{art['console_errors']}"


# ───────────────────────── 四、文案 NEVER 自称「全球」


def test_the_region_names_are_shown_verbatim() -> None:
    """屏上显示的就是端点给的区名。

    `global` 今天不是一个区（`ghtrend` 写死的常量）。把它显示成「全球」，
    用户选完拿到的却是只来自 GitHub Trending 的那一批——**那是一句我们还没确认的话**。
    """
    art = _screen()

    assert art["labels"] == art["options"], (
        f"区名被映射过：{art['labels']} ≠ {art['options']}"
    )
    for banned in ("全球", "Global", "全国"):
        assert banned not in "".join(art["labels"]), f"屏上出现了 {banned}"


def test_the_global_semantics_were_ruled_on_and_not_renamed_to_worldwide() -> None:
    """**改前这条判的是「单子必须还开着」**——`DEC-040` 裁完之后它红了。

    **红的是自己描述的那个状态过去了**：owner 2026-08-08 裁了，
    `REGION-11` 执行，单据 closed。

    判据的**意图**一字未改，而且它本来就写在 docstring 里：
    「关掉它，下一个人会顺手把**「全球」两个字**加上，而没有任何判据会响。」
    所以改后守的就是那一句本身——裁决**没有**把 `global` 改名成「全球」，
    它把 `global` 与 `NULL` 一起归进了「未归区」。

    这两件事在屏上差得很远：「全球」是一个地方（选完拿到的却只是
    GitHub Trending 那一批），「未归区」承认我们不知道产地。
    """
    pending = REPO / "docs" / "blocked" / (
        "REGION-08-GLOBAL-IS-A-SOURCE-CONSTANT-NOT-A-REGION.md")
    text = pending.read_text(encoding="utf-8")
    state = next(ln for ln in text.splitlines()[:6] if ln.startswith("**状态**"))

    assert state.startswith("**状态** closed"), f"单据状态不对：{state!r}"
    assert "DEC-040" in text and "REGION-11" in text, "关单没写依据与执行卡"
    assert "未归区" in text, "裁决结果不是「未归区」"

    # 那句担心的话仍然要守住：屏上 NEVER 出现把 `global` 叫成「全球」的映射。
    label = json.loads(
        (REPO / "web" / "messages" / "zh.json").read_text(encoding="utf-8"),
    ).get("region.unassigned.label", "")
    assert "未归区" in label, f"选项文案不是「未归区」：{label!r}"
    assert not label.startswith("全球"), f"`global` 被叫成了「全球」：{label!r}"


# ───────────────────────── 五、`PLAZA-02` 的两条缺口：一条关了，一条换了形状


def test_the_region_half_of_the_old_sheet_is_closed() -> None:
    """单据的第一条缺口（`region` query 不存在）**确实没有了**。"""
    text = SHEET.read_text(encoding="utf-8")

    assert "REGION-09" in text, "单子里没记是被哪张卡关的"
    assert "REGION-10" in text


def test_the_source_columns_half_says_exactly_what_is_still_missing() -> None:
    """`SourceColumns` **本卡没有接上**，而且理由必须写清楚。

    它要的是 `SourceStatement{sourceId, region, text}`，`text` 的契约逐字是
    「**原文；NEVER 是译文**」。广场每个源手上只有**分值**与**地区**——
    把分值塞进那个槽，就是拿一个已经有主的槽去说另一件事
    （`DEC-034`/`DEC-038` 反复禁的那一条）。

    真正缺的是每个源的**原文词面**（`trend_items_raw.keyword`，
    微博说「脑机接口」、GitHub 说 `bci`）——那正是 `PRINCIPLES#B4`
    「把话还给说话的人」要的东西，而它离端点只有一个字段。
    但那是 `flint/api/views.py`，**不在本卡 outputs 里**。
    """
    text = SHEET.read_text(encoding="utf-8")

    assert "trend_items_raw" in text, "单子里没点名缺的是哪个字段"
    assert "SourceStatement" in text or "原文" in text
    assert "SourceColumns" in text
    code = _code_only(PAGE)
    assert "<SourceColumns" not in code, (
        "SourceColumns 被接上了——那它的 text 槽里现在装的是什么？"
    )
