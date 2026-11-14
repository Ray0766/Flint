"""UI-06 · 外链只读查看页（v2 屏 2.18）的结构判据。

交互判据在 vitest（16 条）。这里判源码结构与取证实况。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
COMPONENT = REPO / "web" / "components" / "share-viewer" / "ShareViewer.tsx"
PAGE = REPO / "web" / "app" / "share" / "[token]" / "page.tsx"
PROBE = REPO / ".ui-probe" / "fe_smoke.json"
ROUTE = "/share/[token]"


def _code_only(path: Path) -> str:
    text = re.sub(r"/\*[\s\S]*?\*/", "", path.read_text(encoding="utf-8"))
    return "\n".join(
        line for line in text.splitlines()
        if not line.lstrip().startswith(("//", "*"))
    )


# ───────────────────────── 一、四种处境四条路（v2 2.18）


def test_every_outcome_has_its_own_branch() -> None:
    """404 / 410 / 401 / 200 / 没查过——五种各一条路。

    后端 `flint/share/links.py` 的原话：全报 404 看起来「更安全」，
    实际是把三种完全不同的处境糊成一句「没有」，让持链人无从判断下一步。
    """
    code = _code_only(COMPONENT)

    for kind in ("not_provided", "unknown", "gone", "password_required"):
        assert f'outcome.kind === "{kind}"' in code or f'"{kind}"' in code, kind


def test_every_outcome_is_machine_readable() -> None:
    """取证时要分得出屏上是哪一种。"""
    code = _code_only(COMPONENT)

    assert "data-share-state=" in code
    assert "data-share-gone-reason=" in code


def test_a_410_without_a_reason_never_guesses() -> None:
    """后端两种都回 410，只有文案不同。拿不到理由时用**中性那句**。

    说成「已过期」而其实是被撤销的，持链人会去等一个永远不会来的续期。
    """
    code = _code_only(COMPONENT)

    assert "share.gone.unspecified" in code
    assert 'reason ?? "unspecified"' in code


def test_the_gone_state_offers_a_way_out() -> None:
    code = _code_only(COMPONENT)

    assert "share.gone.hint" in code


# ───────────────────────── 二、只读（v2 2.18）


def test_the_viewer_renders_no_intervention_control_at_all() -> None:
    """「只读：不显示任何干预控件」——源码里连控件标签都不该有。

    与保护块同一条纪律：置灰仍然告诉用户「这里本来能点」。
    """
    code = _code_only(COMPONENT)

    for tag in ("<button", "<input", "<textarea", "<select", "<form"):
        assert tag not in code, tag


def test_the_page_never_shows_the_token() -> None:
    """外链页面上不该出现内部 id（FB-10 A 类）。"""
    code = _code_only(PAGE)

    assert "void token" in code, "token 取出来是为了将来取数，此刻不渲染它"
    assert "{token}" not in code.replace("{ token }", "")


# ───────────────────────── 三、端点未接通：不发请求、不冒充 404


def test_the_page_sends_no_request() -> None:
    code = _code_only(PAGE)

    assert "fetch(" not in code
    assert "useEffect" not in code


def test_not_provided_is_not_rendered_as_unknown() -> None:
    """「没查过」NEVER 冒充「没有这个链接」——后者是查过了、后端说 404。"""
    code = _code_only(PAGE)

    assert 'kind: "not_provided"' in code
    assert 'kind: "unknown"' not in code


# ───────────────────────── 四、零计算与 token 纪律


def test_no_continuous_quantity_and_no_hardcoded_token() -> None:
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
    used = set(re.findall(
        r't\("([^"]+)"',
        COMPONENT.read_text(encoding="utf-8") + PAGE.read_text(encoding="utf-8")))

    assert used
    for key in used:
        assert key in zh, key
        assert key in en, key


# ───────────────────────── 五、取证实况


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
