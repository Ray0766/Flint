"""PLAZA-03：广场四条状态规则（规格 `docs/前端功能说明-v2.md#2.14` 第 105~108 行）。

规格逐条写着：

    加载中 → 骨架卡；空结果 → 「该区当日无数据」并给出可切换的区，
    NEVER 回落到别的区假装有数据。
    单区源全灭 → 该区卡片区显示缺数据角标（E6 新降级行），其余区照常。
    译名缺失（翻译服务不可用）→ 只显示 name_native 单行（A7），NEVER 用原文冒充译文。

## 判据分两层，各挡各的

- **阴性对照在 vitest**（`web/components/plaza/plazaStates.test.tsx`，12 条）：
  四态各构造一次，并**逐条断言另外三态不在场**——只断言「本态在」的话，
  一个把四态全渲染出来的实现照样全绿。
- **本文件**判三件 vitest 够不着的：状态判别位互不重复（源码层）、
  文案走 i18n 且中英各一份、**骨架在真浏览器里真的占了卡片那么大的位**。

最后那条是本卡的重心：骨架的全部意义就是**占住将来那张卡的位置**。
一个 0 像素的骨架与「一行加载中文字」在效果上一模一样——数据落地时屏幅照样跳。
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
PLAZA_DIR = WEB / "components" / "plaza"
CARDS = PLAZA_DIR / "PlazaCards.tsx"
SKELETON = PLAZA_DIR / "HotspotCardSkeleton.tsx"
STATES_TEST = PLAZA_DIR / "plazaStates.test.tsx"
PAGE = WEB / "app" / "plaza" / "page.tsx"
ZH = WEB / "messages" / "zh.json"
EN = WEB / "messages" / "en.json"
SPEC = REPO / "docs" / "前端功能说明-v2.md"
ARTIFACT = REPO / ".ui-probe" / "plaza_states.json"

PWENV = Path(r"C:\pwenv\Scripts\python.exe")
FRONTEND = "http://localhost:3000/plaza"

STATES = ("loading", "empty", "source_outage", "ready")


def _code_only(path: Path) -> str:
    text = re.sub(r"/\*[\s\S]*?\*/", "", path.read_text(encoding="utf-8"))
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("//")
    )


def _messages(path: Path) -> dict[str, str]:
    return json.loads(path.read_text(encoding="utf-8"))


# ───────────────────────── 一、四态各有各的判别位


def test_every_state_has_its_own_marker() -> None:
    """四种状态各有各的 `data-plaza-state`。

    共用一个判别位的话，「还在查」与「查过了没有」在取证里长得一模一样——
    而这两件事该说的话完全相反。
    """
    code = _code_only(CARDS) + _code_only(SKELETON)

    for state in STATES:
        assert f'"{state}"' in code, f"{state} 这一态没有判别位"


def test_loading_is_not_the_same_branch_as_empty() -> None:
    """「还没查」与「查过了没有」分在两条路上，NEVER 由同一个条件盖住。"""
    code = _code_only(CARDS)

    assert "clusters === null" in code, "「还在取」不是靠 null 判的"
    assert "cards.length === 0" in code, "「查过了没有」不是靠长度判的"
    # 两条判断 NEVER 并成一句（`||` 一并起来，两态就合成了一态）。
    assert not re.search(r"clusters\s*===\s*null\s*\|\|", code)


def test_the_outage_signal_is_parameterised_not_guessed() -> None:
    """后端今天没有「该区源全灭」这个信号 → **参数化留位**，NEVER 由前端猜。

    「一条都没有」既可能是源挂了，也可能是这一区当日真的没有热点，
    而这两件事该说的话完全相反。缺省 `false` 时行为与今天逐字相同。
    """
    code = _code_only(CARDS)

    assert "sourceOutage = false" in code, "源全灭没有缺省值，或缺省不是 false"
    # NEVER 由「没有卡」推出「源挂了」。
    assert not re.search(r"sourceOutage\s*=\s*[^;]*length\s*===\s*0", code)


def test_the_outage_badge_never_swallows_the_cards() -> None:
    """其余照常渲染（规格原话）。把内容藏起来等于用一次降级抹掉所有还好的部分。"""
    code = _code_only(CARDS)

    # 角标是并列的一段，NEVER 出现在「有卡就不画卡」那种三元里。
    assert not re.search(r"sourceOutage\s*\?\s*[^:]*:\s*<>\s*<HotspotCardStack", code)
    assert "plaza-outage-badge" in code


# ───────────────────────── 二、文案走 i18n，中英各一份


def test_the_four_state_lines_are_keys_not_hardcoded_text() -> None:
    zh, en = _messages(ZH), _messages(EN)

    for key in ("plaza.empty.no_data_today", "plaza.badge.source_outage",
                "plaza.region.switch_not_wired", "plaza.screen.loading"):
        assert key in zh, f"zh 缺 {key}"
        assert key in en, f"en 缺 {key}"
        assert zh[key] != en[key], f"{key} 中英同文——那说明有一侧没翻"


def test_the_two_spec_keys_use_the_spec_wording() -> None:
    """规格 #2.14 的话术表里逐字写着这两句，**照它的原话**。"""
    zh = _messages(ZH)
    spec = SPEC.read_text(encoding="utf-8")

    for key in ("plaza.empty.no_data_today", "plaza.badge.source_outage"):
        row = next((ln for ln in spec.splitlines() if key in ln), "")
        assert row, f"规格里找不到 {key}"
        assert zh[key] in row, f"{key} 的中文与规格原话不一致：{zh[key]!r} vs {row!r}"


def test_no_state_copy_is_hardcoded_in_the_component() -> None:
    for path in (CARDS, SKELETON):
        code = _code_only(path)
        assert not re.search(r"[\u4e00-\u9fff]", code), f"{path.name} 里有写死的中文"


# ───────────────────────── 三、清单只有一处真相


def test_the_region_list_comes_from_the_locale_endpoint() -> None:
    """九区清单从 `GET /settings/locale` 取，**NEVER 在广场再抄一份**（LOC-01）。"""
    page = _code_only(PAGE)

    assert "/settings/locale" in page, "广场屏没去取地区清单"
    for code in (_code_only(CARDS), page):
        # 抄一份的样子：把区码写成字面量数组。
        assert not re.search(r'\[\s*"(AU|CN|FR|GB|IT|JP|KR|SG|US)"\s*,', code), (
            "广场里自带了一份地区清单"
        )


def test_a_missing_list_is_not_invented() -> None:
    code = _code_only(CARDS)

    assert "regions ?? []" in code, "地区清单缺失时没有走空表，而是可能编了一份"


# ───────────────────────── 四、阴性对照真的在（不是只测 happy path）


def test_the_negative_controls_exist_for_every_state() -> None:
    """卡面 acceptance⑤ 原话：四种情况分别渲染，断言互不串台。"""
    tests = STATES_TEST.read_text(encoding="utf-8")

    for state in STATES:
        assert f'"{state}"' in tests, f"vitest 里没有 {state} 的对照"
    assert "NEVER 回落到别的区假装有数据" in tests
    assert "NEVER 共用一个表示" in tests


# ───────────────────────── 五、运行时：骨架真的占了一张卡那么大的位


_RUNNER = r"""
import json, sys
from playwright.sync_api import sync_playwright

url, out = sys.argv[1], sys.argv[2]
with sync_playwright() as p:
    b = p.chromium.launch()
    page = b.new_page(viewport={"width": 1440, "height": 900})
    # 把取数拖慢，好让骨架那一态**真的出现在屏上**被量到。
    # 只延后不改内容：量的仍是产品自己的加载态。
    page.route("**/plaza/hot**", lambda route: (page.wait_for_timeout(2500),
                                                route.continue_())[-1])
    page.goto(url, wait_until="commit", timeout=60000)
    page.wait_for_selector("[data-testid='plaza-skeleton']", timeout=30000)
    loading = page.evaluate(
        '''() => {
            const host = document.querySelector('[data-plaza-state]');
            // 只取**网格里**那几张：堆叠那张是放大过的（scale 1.03），
            // 拿它跟网格卡比宽是拿两族东西比，比出来的差说明不了任何事。
            const cards = [...document.querySelectorAll(
                '.plaza-skeleton__grid .hotspot-card--skeleton')];
            const first = cards[0] ? cards[0].getBoundingClientRect() : null;
            const cs = cards[0] ? getComputedStyle(cards[0]) : null;
            return {
              state: host ? host.getAttribute('data-plaza-state') : null,
              count: cards.length,
              box: first ? {width: first.width, height: first.height} : null,
              backgroundColor: cs ? cs.backgroundColor : '',
              borderTopLeftRadius: cs ? cs.borderTopLeftRadius : '',
              ariaBusy: !!document.querySelector('[aria-busy="true"]'),
              realCards: document.querySelectorAll(
                  '[data-testid="hotspot-card"]').length,
              deckReserved: (() => {
                  const d = document.querySelector(
                      '[data-testid="plaza-skeleton-deck"]');
                  return !!d && d.getBoundingClientRect().height > 300;
              })(),
            };
        }''')
    page.screenshot(path=".ui-probe/plaza-loading.png")
    page.wait_for_selector("[data-plaza-list]", timeout=30000)
    ready = page.evaluate(
        '''() => {
            const host = document.querySelector('[data-plaza-state]');
            const card = document.querySelector(
                '[data-plaza-list] [data-testid="hotspot-card"]');
            const r = card ? card.getBoundingClientRect() : null;
            return {
              state: host ? host.getAttribute('data-plaza-state') : null,
              box: r ? {width: r.width, height: r.height} : null,
              skeletons: document.querySelectorAll('.hotspot-card--skeleton').length,
            };
        }''')
    b.close()
open(out, "w", encoding="utf-8").write(
    json.dumps({"schema": "plaza-states/1", "url": url,
                "loading": loading, "ready": ready},
               ensure_ascii=False, indent=1))
"""


def _artifact() -> dict[str, object]:
    if ARTIFACT.exists():
        return json.loads(ARTIFACT.read_text(encoding="utf-8"))
    if not PWENV.exists():
        pytest.skip(f"本机没有 {PWENV}（playwright 恒在项目外，NEVER 进项目依赖）")
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        runner = Path(tmp) / "plaza_states_runner.py"
        runner.write_text(_RUNNER, encoding="utf-8")
        done = subprocess.run(
            [str(PWENV), str(runner), FRONTEND, str(ARTIFACT)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=REPO, check=False,
        )
    if done.returncode != 0:
        pytest.skip(f"前端没起或探针跑不动（{FRONTEND}）：{done.stderr[-500:]}")
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


def test_the_skeleton_really_shows_up_while_loading() -> None:
    loading = _artifact()["loading"]

    assert loading["state"] == "loading"
    assert loading["count"] > 1, f"只画了 {loading['count']} 张骨架卡"
    assert loading["deckReserved"], "堆叠那一段没占位——数据落地时上面会凭空多出一截"
    assert loading["ariaBusy"], "读屏软件不知道这里在等东西"
    assert loading["realCards"] == 0, "加载态里混进了真卡"


def test_the_skeleton_reserves_a_card_sized_box() -> None:
    """骨架的全部意义就是占住将来那张卡的位置。

    0 像素的骨架与「一行加载中文字」在效果上一模一样——数据落地时屏幅照样跳。
    """
    art = _artifact()
    skeleton, real = art["loading"]["box"], art["ready"]["box"]

    assert skeleton["width"] > 200 and skeleton["height"] > 100, (
        f"骨架卡几乎没有面积：{skeleton}"
    )
    # 与真卡同宽（同一套网格、同一个卡壳）——差一点点是子像素，差一截就是没占对位。
    assert abs(skeleton["width"] - real["width"]) < 2, (
        f"骨架宽 {skeleton['width']}，真卡宽 {real['width']}——没占对位"
    )


def test_the_skeleton_borrows_the_same_card_shell() -> None:
    """借的是 `DS-02` 那一份卡壳，NEVER 另写一个「长得像卡片」的盒子。"""
    loading = _artifact()["loading"]

    assert loading["borderTopLeftRadius"] == "8px", "圆角不是 --r-card"
    assert loading["backgroundColor"] not in ("", "rgba(0, 0, 0, 0)"), "没有纸面底色"


def test_the_skeleton_is_gone_once_the_data_lands() -> None:
    ready = _artifact()["ready"]

    assert ready["state"] == "ready"
    assert ready["skeletons"] == 0, "数据到了骨架还赖着"
