"""EYE-04：看屏取证——三条意见逐条对着截图验收。

## 这一条是本批的防空转闸

`UI-01~11` 那次挂了四条**禁止性**判据，全绿；
而那一屏是个 4072px 的裸 `<ul><li>`。

> **禁止性判据挡得住做错，挡不住没做。**

所以本卡逐条**正向**取证：三个视口 × 两主题 = 6 张截图，
每张同时满足四条，且每条都带实测数值。

## 六张截图

`.ui-probe/eye04/plaza-{视口}-{主题}.png`，另有一份 `report.json`
记着每张图当时量到的数——**截图与数一起落盘**：
只有图的话，下一个人无从判断它当时算不算合格。

## 四条逐张判

| 条件 | 实测（1920 暗底） |
|---|---|
| 顶栏是**一行**药丸条 | 九项 `offsetTop` 全 = 8 · `border-radius` 9999px |
| 主体 ≥ 视口 × 0.9（390 除外） | 1760/1920 = 0.92 |
| 无横向溢出 | `scrollWidth` == 视口宽 |
| 零控制台报错 | 0 条 |
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.probe_evidence import require_probe_evidence

REPO = Path(__file__).resolve().parents[2]
PROBE = REPO / ".ui-probe" / "eye04"
REPORT = PROBE / "report.json"
HOWTO = REPO / "docs" / "怎么测-v041.md"

#: 三视口 × 两主题。**六张一张都不能少**——少一张就是少一种组合没看过。
SHOTS = [(w, theme) for w in (1920, 1440, 390) for theme in ("light", "dark")]


def _report() -> dict[str, dict[str, object]]:
    if not REPORT.exists():
        pytest.skip("还没取证（跑 EYE-04 的取证脚本先）")
    return dict(json.loads(REPORT.read_text(encoding="utf-8")))


@pytest.fixture(scope="module")
def shots() -> dict[str, dict[str, object]]:
    return _report()


# ───────────────────────── 一、六张都在，且是真浏览器打真栈拍的


@pytest.mark.parametrize("viewport,theme", SHOTS)
def test_every_screenshot_is_on_disk(viewport: int, theme: str) -> None:
    """六张截图**逐张在盘上**，文件名写明视口与主题。

    文件名里带视口与主题，是为了 owner 不用打开就知道自己在看哪一张。
    """
    require_probe_evidence(PROBE, "跑 EYE-04 的取证脚本")
    matches = list(PROBE.glob(f"plaza-{viewport}x*-{theme}.png"))

    assert matches, f"缺这一张：{viewport} × {theme}"
    assert matches[0].stat().st_size > 10_000, (
        f"{matches[0].name} 只有 {matches[0].stat().st_size} 字节——那不是一张真截图")


def test_all_six_combinations_were_taken(shots: dict[str, dict[str, object]]) -> None:
    """**六种组合一种都不少**。

    少一种就是「那一种没看过」，而报告里会写成「都看过了」。
    """
    got = set(shots)
    want = {f"{w}-{t}" for w, t in SHOTS}

    assert got == want, f"缺这些组合：{sorted(want - got)}"


# ───────────────────────── 二、四条逐张成立（全部正向 + 实测值）


@pytest.mark.parametrize("viewport,theme", SHOTS)
def test_the_top_bar_is_one_pill_row(
    shots: dict[str, dict[str, object]], viewport: int, theme: str,
) -> None:
    """每一张：顶栏 MUST 是**一行药丸条**。

    实测九项 `offsetTop` 相等（全 = 8）· `border-radius` ≥999px · `position: fixed`。
    """
    m = shots[f"{viewport}-{theme}"]

    # 390 下**折行是对的**：`WB-01` 修 `NAV-BAR-OVERFLOWS-AT-390` 时选的就是折行——
    # 改前那条药丸条在 390 上把后三项整个推到屏外（`/workbench` 右缘 529 > 390），
    # 而「一行」与「零横向溢出」两条判据同时说没事（`fixed` 元素不撑 scrollWidth）。
    # 所以这条判据在窄屏改判**折成几行都行、但每一项都要在屏内**；
    # 宽屏那两档照旧钉「一行」。
    #
    # **NEVER 把窄屏这一档整个放过**：那样折行退回溢出时又没有人看着了。
    if viewport <= 390:
        assert len(m["tops"]) >= 1, f"{viewport}×{theme}：顶栏一项都没量到"
        assert not m["overflow"], f"{viewport}×{theme}：折行之后仍然横向溢出"
        assert float(m["rightmost"]) <= float(m["vw"]) + 0.5, (
            f"{viewport}×{theme}：最右元素右缘 {m['rightmost']} 跑出了视口 {m['vw']}")
        # 窄屏那一档是 24px 的圆角条（折行之后全圆角会把两行包成一个胶囊，
        # 看起来像两条堆在一起）。判**仍然是圆角的**，而不是判它还是不是胶囊。
        assert float(m.get("navRadius", 0)) >= 8, (
            f"{viewport}×{theme}：折行之后连圆角都没了（{m.get('navRadius')}）")
    else:
        assert m["oneRow"], f"{viewport}×{theme}：顶栏不是一行（offsetTop {m['tops']}）"
        assert m["pill"], f"{viewport}×{theme}：不是药丸条"
    assert m["fixed"], f"{viewport}×{theme}：条不是 fixed"
    assert m["navCentred"], f"{viewport}×{theme}：条没居中"


@pytest.mark.parametrize("viewport,theme",
                         [(w, t) for w, t in SHOTS if w != 390])
def test_the_body_fills_the_viewport(
    shots: dict[str, dict[str, object]], viewport: int, theme: str,
) -> None:
    """每一张（390 除外）：主体 MUST ≥ 视口 × 0.9。

    实测：1920 → 0.92 · 1440 → 0.97。
    390 除外是卡面写的——手机上留边比铺满更要紧。
    """
    m = shots[f"{viewport}-{theme}"]
    fill = float(m["fill"])

    assert fill >= 0.9, (
        f"{viewport}×{theme}：主体只有视口的 {fill:.2f}"
        f"（{m['bodyW']:.0f}px / {m['vw']:.0f}px）")


@pytest.mark.parametrize("viewport,theme", SHOTS)
def test_no_horizontal_overflow(
    shots: dict[str, dict[str, object]], viewport: int, theme: str,
) -> None:
    """每一张：**无横向溢出**。

    放宽容器与浮动条最容易在这里出事——判据量的是 `scrollWidth`。
    """
    m = shots[f"{viewport}-{theme}"]

    assert not m["overflow"], (
        f"{viewport}×{theme}：横向溢出 scrollWidth={m['scrollW']:.0f} "
        f"> 视口 {m['vw']:.0f}")


@pytest.mark.parametrize("viewport,theme", SHOTS)
def test_the_console_is_clean(
    shots: dict[str, dict[str, object]], viewport: int, theme: str,
) -> None:
    """每一张：**零控制台报错**。

    屏上看着对而控制台在报错，说明有一条路悄悄失败了——
    今天看不出来，换一台机器就看得出来。
    """
    errors = list(shots[f"{viewport}-{theme}"]["errors"])

    assert errors == [], f"{viewport}×{theme} 有 {len(errors)} 条报错：{errors[:2]}"


# ───────────────────────── 三、三条意见逐条对上（本卡的产品）


def test_opinion_one_the_navbar_is_a_pill_row(
    shots: dict[str, dict[str, object]],
) -> None:
    """**①「导航栏用我给的样式」+「做成一个横栏」**——六张都成立，且吉祥物在。"""
    for key, m in shots.items():
        # 「一个横栏」在 390 上的形态是**折行的那一条**（见上一条判据的注释）：
        # `WB-01` 修 390 溢出时选的就是折行，而那正是 owner 那条意见要的
        # 「所有入口都在这一条上」——把它判成没兑现，等于要求它退回溢出。
        narrow = key.startswith("390-")
        rounded = float(m.get("navRadius", 0)) >= 8
        assert (m["pill"] and m["oneRow"]) or (narrow and rounded), f"{key}：①没兑现"
        assert m["mascot"], f"{key}：吉祥物不在（owner 要「照蓝本做全」）"


def test_opinion_two_the_title_got_bigger(
    shots: dict[str, dict[str, object]],
) -> None:
    """**②「标题做大」**——1920 下 ≥40px（实测 48），且随视口分级。"""
    wide = float(shots["1920-light"]["title"])
    phone = float(shots["390-light"]["title"])

    assert wide >= 40, f"1920 下标题只有 {wide:.0f}px"
    assert phone >= 24, f"390 下标题只有 {phone:.0f}px"
    assert wide > phone, "字号没有随视口分级"


def test_opinion_three_the_content_fills_the_screen(
    shots: dict[str, dict[str, object]],
) -> None:
    """**③「铺满整个屏幕」**——1920 与 1440 下都 ≥0.9（实测 0.92 / 0.97）。"""
    assert float(shots["1920-dark"]["fill"]) >= 0.9
    assert float(shots["1440-dark"]["fill"]) >= 0.9


# ───────────────────────── 四、《怎么测》补了「界面」那一节


def test_the_howto_has_a_ui_section() -> None:
    """《怎么测》MUST 有「界面」一节：**打开哪一屏 / 该看到什么 / 看着不对时看哪张图**。

    三件缺一件，owner 看到不对也不知道该找哪张截图。
    """
    text = HOWTO.read_text(encoding="utf-8")

    assert "## 界面" in text, "《怎么测》没有「界面」那一节"
    assert ".ui-probe/eye04/" in text, "没写截图在哪"
    for must in ("药丸", "标题", "铺满"):
        assert must in text, f"界面那一节没提到「{must}」"


def test_the_howto_lists_all_six_shots() -> None:
    """六张截图路径**逐一列出**——owner 不用翻目录（`SHIP-13` acceptance⑤ 同一条）。"""
    text = HOWTO.read_text(encoding="utf-8")

    for w, theme in SHOTS:
        needle = f"plaza-{w}x"
        assert needle in text and theme in text, f"没列出 {w}×{theme} 那一张"
