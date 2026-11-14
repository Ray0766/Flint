"""UI-05 · 收藏图书馆屏（v2 屏 2.15）的结构判据。

交互判据在 vitest（13 条）。这里判源码结构与取证实况。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
COMPONENT = REPO / "web" / "components" / "favorites-library" / "FavoritesLibrary.tsx"
PAGE = REPO / "web" / "app" / "favorites" / "page.tsx"
PROBE = REPO / ".ui-probe" / "fe_smoke.json"
ROUTE = "/favorites"


def _code_only(path: Path) -> str:
    text = re.sub(r"/\*[\s\S]*?\*/", "", path.read_text(encoding="utf-8"))
    return "\n".join(
        line for line in text.splitlines()
        if not line.lstrip().startswith(("//", "*"))
    )


# ───────────────────────── 一、stale 只由后端说了算（v2 2.15）


def test_the_component_never_derives_staleness_from_a_timestamp() -> None:
    """前端 NEVER 自行按时间戳推断新旧（v2 2.15 原话）。

    按时间戳推断看起来总是对的：三个月前的收藏「显然」旧了。
    可事实一个字没变时，那个标记只让用户白重跑一次；
    而昨天的收藏也可能因一次事实移除而彻底失效。
    """
    code = _code_only(COMPONENT)

    assert "Date" not in code
    assert "now" not in code.lower().replace("know", "")
    assert not re.search(r"[<>]=?\s*\w*(at|time|day)", code, re.IGNORECASE)


def test_not_evaluated_is_a_third_state_not_fresh() -> None:
    """`stale === null` = 没判过。**NEVER 显示成「最新」**。"""
    code = _code_only(COMPONENT)

    assert "stale === null" in code
    assert "favorites.stale.not_checked" in code


def test_the_three_stale_states_are_machine_readable() -> None:
    code = _code_only(COMPONENT)

    assert "data-favorite-stale=" in code
    assert '"not_checked"' in code


# ───────────────────────── 二、列表 NEVER 出现空壳（v2 2.15）


def test_a_favorite_without_content_is_marked_not_rendered_blank() -> None:
    """内容不在了就说内容不在了。

    渲染成一张空卡片，看起来像「这条收藏没内容」——而真相是内容丢了。
    """
    code = _code_only(COMPONENT)

    assert "hasSnapshot" in code
    assert "favorites.content_gone" in code
    assert "data-favorite-no-content" in code


# ───────────────────────── 三、三态与零计算


def test_not_provided_and_empty_are_two_branches() -> None:
    code = _code_only(COMPONENT)

    assert "favorites === null" in code
    assert "favorites.length === 0" in code
    assert code.index("favorites === null") < code.index("favorites.length === 0")


def test_the_empty_state_offers_a_way_out() -> None:
    """空态要给出路（v2：「还没有收藏」+ 去广场的入口）。"""
    code = _code_only(COMPONENT)

    assert 'href="/plaza"' in code


def test_the_component_never_sorts_or_aggregates() -> None:
    code = _code_only(COMPONENT)

    assert ".sort(" not in code
    assert ".reduce(" not in code
    assert "%" not in code


def test_the_page_now_fetches_and_maps_both_answers() -> None:
    """**这条本来钉的是「一个请求都不发、恒传 null」**——那是这一族没挂上时的实情。

    `WIRE-11` 挂上、`WIRE-12` 让它在没有存储面时照实说 `not_provided` 之后，
    这一屏改成真取数，本条于是红了。**红得对**：它就是来提醒
    「这一屏的取数口径变了」的。改后的口径是——取数走 `useScreenData`，
    两种答复各翻各的（`not_provided` → `null`；`{"items": […]}` → 那个数组），
    而 **NEVER 把任何一种写死在页面里**。
    """
    code = _code_only(PAGE)

    assert "useScreenData" in code, "又退回写死了"
    assert "toFavoritesView" in code
    assert "favorites={null}" not in code
    assert "favorites={[]}" not in code


def test_no_hardcoded_token_value() -> None:
    code = _code_only(COMPONENT) + _code_only(PAGE)

    assert not re.search(r"#[0-9A-Fa-f]{3,8}\b", code)
    assert not re.search(r":\s*\d+px", code)


def test_every_string_shown_to_the_user_goes_through_i18n() -> None:
    for path in (COMPONENT, PAGE):
        for literal in re.findall(r"[\"'`]([^\"'`]*)[\"'`]", _code_only(path)):
            assert not re.search(r"[一-龥]", literal), \
                f"{path.name} 里有裸中文：{literal!r}"


def test_the_keys_exist_in_both_dictionaries() -> None:
    zh = json.loads((REPO / "web" / "messages" / "zh.json").read_text(encoding="utf-8"))
    en = json.loads((REPO / "web" / "messages" / "en.json").read_text(encoding="utf-8"))
    used = set(re.findall(
        r't\("([^"]+)"',
        COMPONENT.read_text(encoding="utf-8") + PAGE.read_text(encoding="utf-8")))

    assert used
    for key in used:
        assert key in zh, key
        assert key in en, key


# ───────────────────────── 四、取证实况


def _probe_rows() -> list[dict[str, object]]:
    if not PROBE.exists():
        pytest.skip("本机没跑过真栈冒烟：缺 .ui-probe/fe_smoke.json")
    report = json.loads(PROBE.read_text(encoding="utf-8"))
    if report.get("stack_down"):
        pytest.skip(f"上次实跑时栈没起：{report['stack_down']}")
    return [row for row in report["screens"] if row["route"] == ROUTE]


def test_the_new_screen_was_probed_in_both_themes() -> None:
    assert {str(row["theme"]) for row in _probe_rows()} == {"light", "dark"}


def test_the_new_screen_is_clean_on_the_real_stack() -> None:
    for row in _probe_rows():
        assert row["http_status"] == 200, row
        assert row["console_error_count"] == 0, row
        assert row["horizontal_overflow"] is False, row
        shot = REPO / ".ui-probe" / str(row["screenshot"])
        assert shot.exists() and shot.stat().st_size > 0, shot
