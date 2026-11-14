"""UI-07 · 语言与地区设置屏（v2 屏 2.13）的结构判据。

交互判据在 vitest（16 条，含 18 组合遍历）。这里判源码结构与取证实况。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
COMPONENT = REPO / "web" / "components" / "locale-settings" / "LocaleSettings.tsx"
PAGE = REPO / "web" / "app" / "settings" / "locale" / "page.tsx"
PROBE = REPO / ".ui-probe" / "fe_smoke.json"
ROUTE = "/settings/locale"


def _code_only(path: Path) -> str:
    text = re.sub(r"/\*[\s\S]*?\*/", "", path.read_text(encoding="utf-8"))
    return "\n".join(
        line for line in text.splitlines()
        if not line.lstrip().startswith(("//", "*"))
    )


# ───────────────────────── 一、NEVER 用浏览器语言猜地区（v2 2.13）


def test_the_screen_never_reads_the_browser_locale() -> None:
    """浏览器语言推地区是**双重猜测**：先从语言猜国家，
    再把猜出来的国家当成他要看的热点集合。猜错时用户看到的是另一个国家的热点。
    """
    code = _code_only(COMPONENT) + _code_only(PAGE)

    assert "navigator" not in code
    assert "Accept-Language" not in code
    assert "languages" not in code


def test_the_defaults_are_declared_not_guessed() -> None:
    code = _code_only(PAGE)

    assert 'lang: "zh"' in code
    assert 'region: "CN"' in code
    assert "DEFAULTS" in code


def test_never_saved_is_said_out_loud() -> None:
    """没存过要说出来，否则默认值看起来像「他设过的」。"""
    code = _code_only(COMPONENT)

    assert "saved === null" in code
    assert "locale.unsaved" in code
    assert "data-locale-unsaved" in code


# ───────────────────────── 二、两轴正交（PRINCIPLES#A3）


def test_on_change_hands_out_one_axis_at_a_time() -> None:
    """把两值打包成一个对象交出去的那天，调用方就会顺手把另一根也写回去。

    （BE-07 那侧 `set_prefs` 的「只改传进来的那一项」是同一条纪律的后端形态。）
    """
    code = _code_only(COMPONENT)

    assert 'onChange?: (axis: "lang" | "region", value: string) => void' in code
    assert 'onChange?.("lang"' in code
    assert 'onChange?.("region"' in code


def test_the_page_keeps_the_other_axis_untouched() -> None:
    code = _code_only(PAGE)

    assert "...prev" in code, "另一根轴原样带过去，不重新计算"


# ───────────────────────── 三、保存中与保存失败（v2 2.13）


def test_saving_disables_both_selects() -> None:
    code = _code_only(COMPONENT)

    assert code.count("disabled={saving}") >= 3, "两个下拉 + 保存按钮"


def test_a_failed_save_keeps_the_users_choice() -> None:
    """屏上渲染的恒是 `draft`（用户选的），不是 `saved`（旧值）。

    回滚之后屏上是旧值、没有报错，用户会以为自己没点到——
    他会再点一次，然后再失败一次。
    """
    code = _code_only(COMPONENT)

    assert "value={draft.lang}" in code
    assert "value={draft.region}" in code
    assert "value={saved" not in code


def test_a_failed_save_says_so() -> None:
    code = _code_only(COMPONENT)

    assert 'status === "error"' in code
    assert "data-locale-error" in code


# ───────────────────────── 四、清单只有一份


def test_the_component_does_not_declare_its_own_region_list() -> None:
    """清单**谁都不持有**：由 `GET /settings/locale` 的 `options.region` 传进来。

    改前这条判的是「复用另一个组件里的那份常量」——那时全前端只有一份抄件，
    比两份好，但仍是抄件。`LOC-01` 之后连那一份也退役了（判据搬到
    `tests/v041/test_regions_from_backend.py`，在真栈上判源头）。

    所以这里改判「本组件既不自己声明、也不从别处借」：`regions` 是入参。
    """
    code = _code_only(COMPONENT)

    assert "regions" in code, "组件没有收清单的入参，那它的清单从哪来"
    assert 'from "../region-switch/RegionSwitch"' not in code, (
        "又去借那份常量了——它已经退役"
    )
    assert '"CN"' not in code
    assert '"JP"' not in code


# ───────────────────────── 五、零计算与 i18n


def test_no_hardcoded_token_and_no_continuous_quantity() -> None:
    code = _code_only(COMPONENT) + _code_only(PAGE)

    assert "%" not in code
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
    used = {k for k in re.findall(
        r't\("([^"]+)"',
        COMPONENT.read_text(encoding="utf-8") + PAGE.read_text(encoding="utf-8"))}
    # 动态 key 的候选也要有（`locale.lang.${code}`）。
    used |= {"locale.lang.zh", "locale.lang.en"}

    for key in used:
        assert key in zh, key
        assert key in en, key


def test_the_page_takes_what_the_backend_says_and_never_guesses() -> None:
    """`WIRE-03`：本屏改为真取数（`GET /settings/locale` 已由 `WIRE-01` 挂上）。

    原判据是「一个请求都不发 + `saved={null}`」——那是**未装配期间**的正确行为
    （`DEC-032`），装配落地后它自动失效。

    现在判两件事：**取的是那条端点**，且 **`saved` 来自后端而不是写死的 null**。
    后者是要害：写死 null 会让屏永远说「未保存」，而后端明明能答。
    """
    code = _code_only(PAGE)

    assert "useScreenData" in code and "/settings/locale" in code
    assert "saved={null}" not in code, "还在写死 null"
    assert "saved={saved}" in code
    # 屏自己不发 fetch：取数走 `useScreenData`，基址由 `API_BASE` 统一给。
    assert "fetch(" not in code


# ───────────────────────── 六、取证实况


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
