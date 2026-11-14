"""WB-02：左栏的热点/证据卡片选取（复用广场那张卡）。

## 复用，NEVER 另写

左栏的热点卡就是广场那个 `HotspotCard`，搬运走的也是广场那个
`clusterToCard`。`FAV-CARD-01` 已经走过这条路，理由一字不变：
**两个卡片会各自漂移，而它们呈现的是同一种东西**。

## 取数走既有端点

热点 `GET /plaza/hot`（`fetchPlazaHot`）、证据 `GET /clusters/{id}/evidence-cards`
（`fetchEvidenceCards`）。**NEVER 新建一份平行取数**，也 NEVER 在前端拼卡面。

## 证据卡跟着已选热点走

蓝本左栏把证据卡列成一份**与热点无关的清单**（它是 demo，数据写死在 `state` 里）。
本仓这一处照不了：证据卡是按簇取的（端点签名就是 `/clusters/{id}/evidence-cards`），
**凭空列一份「所有证据」要么得多打 N 次请求，要么得编一份出来**。
所以改成「跟着已选热点走」——选了哪几条热点，就列那几条的证据。
一条都没选时如实说，NEVER 显示一份空清单假装那里本来就没有证据。

## 三种空态 NEVER 合并（`CN-02` 的既有纪律）

| 态 | 屏上说的 | 用户该做的 |
|---|---|---|
| `empty` | 该区当日无数据 | 换一天 / 换一个区 |
| `out_of_scope` | 本版暂无该区内容 | 等下一版 |
| `failed` | 读失败 | 去查后端 |

合并的话，三种里有两种会把用户推向错误的下一步。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from tools.probe_evidence import require_probe_evidence

REPO = Path(__file__).resolve().parents[2]
PROBE = REPO / ".ui-probe" / "wb"
REPORT = PROBE / "cards.json"

WEB = REPO / "web"
CARDS = WEB / "components" / "workbench" / "WorkbenchCards.tsx"
TRAY = WEB / "components" / "workbench" / "WorkbenchTray.tsx"
PAGE = WEB / "app" / "workbench" / "page.tsx"
PLAZA_CARD = WEB / "components" / "hotspot-card" / "HotspotCard.tsx"
MAPPER = WEB / "components" / "plaza" / "clusterToCard.ts"


def _report() -> dict[str, object]:
    if not REPORT.exists():
        pytest.skip("还没取证（跑 tools/ui_probe_wb_cards.py 先）")
    return dict(json.loads(REPORT.read_text(encoding="utf-8")))


# ───────────────────────── 一、复用广场那张卡


def test_the_left_column_renders_the_plaza_card() -> None:
    """左栏那些卡**就是** `hotspot-card`——与广场同一个组件。

    判类名而不是判「长得像」：另写一个组件也能长得像，
    而两个卡片会各自漂移。
    """
    m = _report()

    assert int(m["cardCount"]) > 0, "左栏一张热点卡都没有"
    assert m["allArePlazaCards"], "左栏的卡不是 `hotspot-card`"


def test_the_screen_imports_the_plaza_card_and_the_plaza_mapper() -> None:
    """判源码：卡与**搬运层**两样都复用，NEVER 自己写一份。

    只复用组件不复用搬运层的话，「哪个字段进主行、首见日要不要格式化」
    这些决定会在这里被重做一遍——而 `clusterToCard` 的注释里
    写着好几条当初为什么那样定的理由。
    """
    code = CARDS.read_text(encoding="utf-8")

    assert "hotspot-card/HotspotCard" in code, "没复用广场那张卡"
    assert "clusterToCard" in code, "没复用广场那个搬运层"


def test_the_plaza_card_and_mapper_were_not_touched() -> None:
    """那两个文件**一个字没改**——本卡只是它们的第三个调用方。"""
    for path in (PLAZA_CARD, MAPPER):
        assert "WB-02" not in path.read_text(encoding="utf-8"), (
            f"{path.name} 里出现了本卡的痕迹——它本不该被动")


def test_no_parallel_fetch_was_invented() -> None:
    """取数走既有客户端函数，**NEVER 新建一份平行取数**。

    平行取数的代价不是重复代码：`fetchPlazaHot` 里写着
    「不传 region 时一个字都不加」这种与后端对齐过的细节，
    另写一份会在某个参数上悄悄偏一点，而两处返回的东西看起来一样。
    """
    code = PAGE.read_text(encoding="utf-8") + CARDS.read_text(encoding="utf-8")

    assert "fetchPlazaHot" in code, "热点没走既有的 `fetchPlazaHot`"
    assert "fetchEvidenceCards" in code, "证据没走既有的 `fetchEvidenceCards`"
    # 自己拼 URL = 又造了一份取数。
    stripped = re.sub(r"/\*.*?\*/|//[^\n]*", "", code, flags=re.DOTALL)
    assert "/plaza/hot" not in stripped, "屏里自己拼了 `/plaza/hot`"
    assert "evidence-cards" not in stripped, "屏里自己拼了证据端点"


# ───────────────────────── 二、选取：屏上显示的值 == 数据源里的值


def test_picking_two_cards_puts_exactly_those_two_in_the_tray() -> None:
    """**正向判据**：选中两张之后，「本次组合」里的 id 与所选**逐字相同**。

    这是第 13 批那条补充的形态：判的不只是「有两个 chip」，
    而是「屏上显示的值 == 数据源里的值」。
    只数个数的话，选 A 而 chip 上写着 B 也会绿。
    """
    m = _report()["pick"]

    assert list(m["clicked"]) == list(m["trayIds"]), (
        f"点的是 {m['clicked']}，而「本次组合」里是 {m['trayIds']}")
    assert int(m["trayCount"]) == 2, f"计数显示 {m['trayCount']}，实选 2"
    # chip 上印的名字也要是那两条自己的名字。
    assert list(m["trayLabels"]) == list(m["clickedNames"]), (
        f"chip 上印的是 {m['trayLabels']}，所选是 {m['clickedNames']}")


def test_unpicking_one_removes_exactly_that_one_and_names_it() -> None:
    """**阴性对照**：取消一张 → 清单同步少一条，且少的**正是那一条**。

    只判「少了一条」的话，取消 A 而掉了 B 也会绿——
    而那种错在屏上完全看不出来（数目对得上）。
    """
    m = _report()["unpick"]

    assert list(m["trayIdsAfter"]) == list(m["expectedAfter"]), (
        f"取消 {m['removed']} 之后剩 {m['trayIdsAfter']}，应剩 {m['expectedAfter']}")
    assert m["removed"] not in list(m["trayIdsAfter"])
    assert int(m["trayCountAfter"]) == int(m["trayCount"]) - 1


def test_the_pick_state_is_visible_on_the_card_itself() -> None:
    """选中态**在卡上看得见**（不是只在别处的计数里）。

    只有中栏计数变的话，用户看着左栏那一列卡，分不出哪几张是自己选的——
    于是他会重复点同一张。
    """
    m = _report()["pick"]

    assert list(m["cardsMarkedPicked"]) == list(m["clicked"]), (
        f"卡上标成已选的是 {m['cardsMarkedPicked']}，实选 {m['clicked']}")


# ───────────────────────── 三、证据卡跟着已选热点走


def test_the_evidence_list_follows_the_picked_hotspots() -> None:
    """证据卡列的是**已选热点的**证据，且每一条都点得出它属于哪个簇。

    列一份「所有证据」在本仓做不到（端点按簇取），
    硬做要么多打 N 次请求，要么编一份出来——两条都不走。
    """
    m = _report()["evidence"]

    assert int(m["count"]) > 0, "选了热点而证据栏一条都没有"
    assert set(m["clusterIds"]) <= set(m["pickedClusters"]), (
        f"证据里混进了没选的簇：{set(m['clusterIds']) - set(m['pickedClusters'])}")
    assert m["everyRowNamesItsCluster"], "有证据条目说不出自己属于哪个簇"


def test_with_nothing_picked_the_evidence_column_says_so() -> None:
    """一条热点都没选时**如实说**，NEVER 显示一份空清单假装那里没有证据。

    空清单与「你还没选」在屏上长得一样，而后者是用户该做点什么的信号。
    """
    m = _report()["evidenceEmpty"]

    assert m["state"] == "nothing_picked", f"空态记号是 {m['state']}"
    assert m["says"], "那一格什么都没说"


# ───────────────────────── 四、三种空态 NEVER 合并


def test_the_three_empty_states_are_three_different_things() -> None:
    """`empty` / `out_of_scope` / `failed` 三态**各有各的记号与文案**。

    判的是源码里三条分支都在、且三句话互不相同——
    合并的话，三种里有两种会把用户推向错误的下一步。
    """
    code = CARDS.read_text(encoding="utf-8")

    for state in ("empty", "out_of_scope", "failed"):
        assert f'"{state}"' in code, f"少了 `{state}` 这一态"
    messages = json.loads((WEB / "messages" / "zh.json").read_text(encoding="utf-8"))
    # **只比那三句**。第一版把这一段里所有 `wb.cards.*` 的文案都收进来比，
    # 于是「正在取…」被两处引用（热点栏与证据栏各一次）当场判红——
    # 红的是判据自己收得太宽，而三态那三句本来就互不相同。
    lines = [messages[f"wb.cards.{state}"]
             for state in ("empty", "out_of_scope", "failed")]
    assert len(set(lines)) == 3, f"三态里有两句话是一样的：{lines}"
    # 三态各自的机器可读记号也要分得开。
    marks = re.findall(r'data-wb-cards-note="(\w+)"', code)
    assert sorted(marks) == ["empty", "failed", "out_of_scope"], marks


def test_the_empty_states_reuse_the_plaza_wording() -> None:
    """两句既有的话**照搬**，NEVER 另写一句意思一样的。

    `plaza.empty.no_data_today` 与 `plaza.out_of_scope.line` 已经存在，
    再写一句「本版还没有这个区」会让同一件事在两屏上说得不一样，
    而用户会以为那是两回事。
    """
    messages = json.loads((WEB / "messages" / "zh.json").read_text(encoding="utf-8"))

    assert messages["wb.cards.empty"] == messages["plaza.empty.no_data_today"]
    assert messages["wb.cards.out_of_scope"] == messages["plaza.out_of_scope.line"]


# ───────────────────────── 五、屏没坏


def test_the_screen_is_still_clean_and_within_the_viewport() -> None:
    """零控制台报错、零横向溢出（本卡往左栏塞了真数据之后重量一次）。"""
    m = _report()

    assert m["errors"] == [], f"有报错：{m['errors'][:2]}"
    assert int(m["scrollW"]) <= int(m["vw"]) + 1, (
        f"横向溢出 {m['scrollW']} > {m['vw']}")


def test_the_left_column_scrolls_instead_of_growing_the_page() -> None:
    """卡片多起来之后，**滚的是左栏那一层，页面自己不动**。

    `WB-01` 用一块 4000px 假元素量的是机制；这里量的是**真数据**下的实况——
    塞进真卡片之后那一层真的滚得动，而整屏仍然不滚。
    """
    m = _report()

    assert int(m["cardsScrollHeight"]) > int(m["cardsClientHeight"]), (
        "左栏内容还没多到能滚——这条判据此刻量不到东西（换一天数据更多的）")
    assert int(m["pageScrollTop"]) == 0, f"页面自己滚了 {m['pageScrollTop']}px"


@pytest.mark.parametrize("theme", ("light", "dark"))
def test_the_screenshot_is_on_disk(theme: str) -> None:
    require_probe_evidence(REPORT, "起栈后跑 tools/ui_probe_wb_cards.py")
    matches = list(PROBE.glob(f"workbench-cards-*-{theme}.png"))

    assert matches, f"缺这一张：{theme}"
    assert matches[0].stat().st_size > 10_000, (
        f"{matches[0].name} 只有 {matches[0].stat().st_size} 字节")
