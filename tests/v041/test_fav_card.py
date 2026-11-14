"""FAV-CARD-01：收藏图书馆用与广场同样的卡片呈现。

## 实况

`FavoritesLibrary.tsx` 改前渲染的是
`<ul class="favorites__list"><li>` + **裸簇 id**（`c-20260810-002`）+ 三个按钮。

而 `FAV-SNAPSHOT`（第 11 批）已经让 `evidence_snapshot` 存了真内容——
**证据卡与真链接一直在库里，这一屏从来没渲染过它**。

## 一处要说清的实况差

owner 说「数据早就有了」——**一半对**：

| 快照里有的 | 快照里**没有**的 |
|---|---|
| 证据卡（`card_id` / `keyword_ids` / `top_links`，含真微博链接） | **卡面**：标题 / 首见日 / 地区 / 热度 |

也就是说：证据在，而「这条热点长什么样」不在。
所以本卡除了改这一屏，还让后端在取证时把卡面一并存下
（`flint/fav/snapshot_source.py#_cluster_face`）——
**NEVER 让收藏屏去实时查簇**：那样一条被清掉的热点会让收藏变成空壳，
而内嵌基线（`DEC-055`）的全部意义就是不让它变成壳。

## 复用，NEVER 另写

收藏项用的就是广场那个 `HotspotCard`，**`HotspotCard.tsx` 一个字没改**。

它的文件头早写好了这一天的恢复条件：

> 「或 `favorites` 落库后在**收藏屏**上说『你收藏的那份快照旧了』——
> 让那一处的产出方开始传 `stale`，这一槽自己就会亮；
> **改那一处即可，本文件不用动**」。

本卡就是那一处。

## 判据一律正向（第 13 批的纪律）

真栈量、带实测值；阴性对照把卡面摘掉 → 红且点名。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.probe_evidence import require_probe_evidence

REPO = Path(__file__).resolve().parents[2]
PROBE = REPO / ".ui-probe" / "favcard"
REPORT = PROBE / "report.json"
LIB = REPO / "web" / "components" / "favorites-library" / "FavoritesLibrary.tsx"
CARD = REPO / "web" / "components" / "hotspot-card" / "HotspotCard.tsx"
ADAPTER = REPO / "web" / "lib" / "screenAdapters.ts"
SOURCE = REPO / "flint" / "fav" / "snapshot_source.py"

SHOTS = [(w, t) for w in (1920, 1440, 390) for t in ("light", "dark")]


def _report() -> dict[str, dict[str, object]]:
    if not REPORT.exists():
        pytest.skip("还没取证（跑 FAV-CARD-01 的取证脚本先）")
    return dict(json.loads(REPORT.read_text(encoding="utf-8")))


@pytest.fixture(scope="module")
def shots() -> dict[str, dict[str, object]]:
    return _report()


# ───────────────────────── 一、与广场是同一张卡


@pytest.mark.parametrize("viewport,theme", SHOTS)
def test_the_favourite_uses_the_plaza_card(
    shots: dict[str, dict[str, object]], viewport: int, theme: str,
) -> None:
    """收藏项 MUST 用 `hotspot-card` **这一组类名**——与广场同一个组件。

    判类名而不是判「长得像」：另写一个组件也能长得像，
    而两个卡片会各自漂移，**它们呈现的是同一种东西**。
    """
    m = shots[f"{viewport}-{theme}"]

    assert int(m["cards"]) > 0, f"{viewport}×{theme}：收藏屏上一张卡都没有"
    assert m["sameClass"], f"{viewport}×{theme}：卡不是 `hotspot-card`"


def test_the_card_component_itself_was_not_touched() -> None:
    """`HotspotCard.tsx` **一个字没改**——本卡只是它的第二个产出方。

    改它的话，广场那一屏会跟着变，而本卡与广场的呈现无关。
    """
    text = CARD.read_text(encoding="utf-8")

    assert "FAV-CARD-01" not in text, (
        "`HotspotCard.tsx` 里出现了本卡的痕迹——它本不该被动")
    # 它文件头那句恢复条件仍在（本卡正是照它做的）
    assert "收藏屏" in text and "本文件不用动" in text


def test_the_favourites_screen_imports_the_plaza_card() -> None:
    """判源码：收藏屏 import 的是**广场那个组件**，NEVER 自己写一个。"""
    code = LIB.read_text(encoding="utf-8")

    assert "hotspot-card/HotspotCard" in code, "收藏屏没有复用广场那张卡"
    assert "<HotspotCard" in code


# ───────────────────────── 二、六个信息槽逐槽有值


@pytest.mark.parametrize("viewport,theme", SHOTS)
def test_every_slot_on_the_card_has_a_value(
    shots: dict[str, dict[str, object]], viewport: int, theme: str,
) -> None:
    """卡上的槽**逐槽有值**，NEVER 是一张空壳。

    实测五槽：`top` / `region` / `foot` / `first-seen` / `heat`
    （`nameDisplay` / `verdict` / `stale` 三槽按 `HotspotCard` 既有口径
    在没有值时**不渲染**——那是它的诚实态，不是缺失）。
    """
    m = shots[f"{viewport}-{theme}"]

    assert len(list(m["slots"])) >= 4, f"{viewport}×{theme}：槽太少 {m['slots']}"
    assert m["filled"], f"{viewport}×{theme}：有槽是空的"


@pytest.mark.parametrize("viewport,theme", SHOTS)
def test_the_three_actions_are_still_there(
    shots: dict[str, dict[str, object]], viewport: int, theme: str,
) -> None:
    """三个动作**一个不少**（看是否过时 / 更新到最新 / 取消收藏）。

    三条收藏 × 三个动作 = 9 个按钮。换卡片不能顺手把动作弄丢。
    """
    m = shots[f"{viewport}-{theme}"]

    assert int(m["actions"]) == int(m["cards"]) * 3, (
        f"{viewport}×{theme}：{m['cards']} 条收藏只有 {m['actions']} 个动作")


@pytest.mark.parametrize("viewport,theme", SHOTS)
def test_the_console_is_clean_and_nothing_overflows(
    shots: dict[str, dict[str, object]], viewport: int, theme: str,
) -> None:
    """零控制台报错、零横向溢出。"""
    m = shots[f"{viewport}-{theme}"]

    assert m["errors"] == [], f"{viewport}×{theme} 有报错：{m['errors'][:2]}"
    assert int(m["scrollW"]) <= int(m["vw"]) + 1, (
        f"{viewport}×{theme}：横向溢出 {m['scrollW']} > {m['vw']}")


# ───────────────────────── 三、屏上看不到裸簇 id（本卡的核心）


@pytest.mark.parametrize("viewport,theme", SHOTS)
def test_no_raw_cluster_id_is_shown(
    shots: dict[str, dict[str, object]], viewport: int, theme: str,
) -> None:
    """**屏上 NEVER 出现裸簇 id**（如 `c-20260810-002`）。

    那正是这一屏改前的样子——而一个 `c-20260810-002` 印在标题位上
    **看起来像「有内容」**，于是没有人会去查它其实没渲染快照。
    """
    m = shots[f"{viewport}-{theme}"]

    assert not m["rawId"], (
        f"{viewport}×{theme}：屏上还有裸簇 id——那是把 targetId 顶上去当标题了")


def test_removing_the_face_falls_back_honestly_and_names_it() -> None:
    """**阴性对照**：快照里没有卡面 → 走诚实态，且**有自己的记号**。

    判的是源码那两支：有卡面渲染 `HotspotCard`，没有则渲染
    `[data-favorite-no-face]` 那一句——**NEVER 拿 `targetId` 顶上去**。

    这一支今天走不到（三条收藏都刷成了新形状），
    而它是旧快照的必经之路：`FAV-SNAPSHOT` 那一版只存了证据卡。
    """
    code = LIB.read_text(encoding="utf-8")

    assert "data-favorite-no-face" in code, "没有「没有卡面」那一态的记号"
    assert "NEVER 拿 `targetId` 顶上去当标题" in code, "禁令没写下来"
    # 那个裸 id **NEVER 被印成可见文字**。
    #
    # 判「印出来」而不是判「出现」：`data-favorite-target={item.targetId}`
    # 是**给读屏与判据的标识**（属性），`{item.targetId}` 夹在标签之间
    # 才是**印在屏上**（子节点）。第一版没分清，把前者也拦了——
    # 而拦掉它等于让不看屏的人失去「这是哪一条」。
    body = code.split("item.face ?", 1)[1].split("</li>", 1)[0]
    printed = [ln for ln in body.splitlines()
               if "{item.targetId}" in ln and "data-favorite-target" not in ln]
    assert printed == [], (
        f"卡面那一支里把 targetId 印成了可见文字：{printed}")


# ───────────────────────── 四、卡面从哪来：后端在取证时一并存下


def test_the_backend_stores_the_card_face_with_the_evidence() -> None:
    """卡面与证据**一起存进快照**（`DEC-055` 的内嵌语义）。

    NEVER 让收藏屏实时查簇：那样一条被清掉的热点会让收藏变成空壳，
    而内嵌基线的全部意义就是不让它变成壳。
    """
    code = SOURCE.read_text(encoding="utf-8")

    assert "_cluster_face" in code, "后端没有取卡面那一步"
    assert '"cluster": face' in code, "卡面没进快照"
    assert "canonical_name" in code and "first_seen" in code


def test_the_refresh_action_also_self_fetches() -> None:
    """「更新到最新」也走**同一条自取路**。

    必填的话，那个按钮就要前端自己拼一份快照——
    而那正是 `DEC-055` 明禁的事（前端拼一份就是编一份证据）。
    """
    code = (REPO / "flint" / "api" / "favorites.py").read_text(encoding="utf-8")

    assert "fresh_snapshot: dict[str, Any] | None = None" in code, (
        "refresh 仍要求调用方自己拼快照")
    assert "_snapshot_for_target(" in code, "refresh 没走自取那条路"


def test_the_adapter_never_falls_back_to_the_target_id() -> None:
    """适配层拿不到卡面时回 `null`，**NEVER 编一个标题**。"""
    code = ADAPTER.read_text(encoding="utf-8")

    assert "cardFace(" in code, "适配层没带卡面"
    assert "NEVER 拿 targetId 顶上去当标题" in code
    face = code.split("function cardFace(", 1)[1].split("\n}", 1)[0]
    assert "targetId" not in face and "target_id" not in face, (
        "`cardFace` 里出现了 targetId——它会被拿去当标题")


# ───────────────────────── 五、六张截图在盘上


@pytest.mark.parametrize("viewport,theme", SHOTS)
def test_the_screenshot_is_on_disk(viewport: int, theme: str) -> None:
    """三视口 × 两主题共六张，逐张在盘上且不是空文件。"""
    require_probe_evidence(PROBE, "起栈后跑 tools/ui_probe_fav_card.py")
    matches = list(PROBE.glob(f"favorites-{viewport}x*-{theme}.png"))

    assert matches, f"缺这一张：{viewport} × {theme}"
    assert matches[0].stat().st_size > 10_000, (
        f"{matches[0].name} 只有 {matches[0].stat().st_size} 字节")
