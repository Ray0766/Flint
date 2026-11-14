"""UI-04 · AI 设计工作台上屏（v2 屏 2.17）的结构判据。

交互判据在 vitest（`web/__tests__/app/ui04.test.tsx`，12 条）。这里判源码结构与取证实况。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
COMPONENT = REPO / "web" / "components" / "design-workbench" / "DesignWorkbench.tsx"
PAGE = REPO / "web" / "app" / "design" / "page.tsx"
PROBE = REPO / ".ui-probe" / "fe_smoke.json"
ROUTE = "/design"


def _code_only(text: str) -> str:
    text = re.sub(r"/\*[\s\S]*?\*/", "", text)
    return "\n".join(
        line for line in text.splitlines()
        if not line.lstrip().startswith(("//", "*"))
    )


def _source(path: Path) -> str:
    return _code_only(path.read_text(encoding="utf-8"))


# ───────────────────────── 一、两种阻断说两句话（v2 2.17 + E6）


def test_not_checked_and_registry_down_are_two_branches() -> None:
    """「没查过注册表」与「注册表不可用」在源码里是两条路。

    合成一条的话，没查过时屏上会写「注册表不可用」——**那是替后端下的结论**。
    """
    code = _source(COMPONENT)

    # DESIGN-03 扩成四态之后，「没查过」不再是 `null` 而是一个具名值。
    assert 'registryAvailable !== "ok"' in code or "not_checked" in code
    assert "registry_down" in code
    assert "not_checked" in code


def test_both_blocked_states_are_machine_readable() -> None:
    """取证时要分得出屏上是哪一种阻断。"""
    code = _source(COMPONENT)

    assert 'data-design-blocked=' in code


def test_the_blocked_button_says_why() -> None:
    """E6：阻断要说明原因（v2 2.17 原话「按钮置灰并说明原因」）。"""
    code = _source(COMPONENT)

    assert "blockedReason" in code
    assert "disabled={solidifyBlocked}" in code


def test_the_screen_declares_what_still_works() -> None:
    """E6 的另一半：说清**还能做什么**，否则用户以为整个设计台挂了。"""
    code = _source(COMPONENT)

    assert "design.explore.still_open" in code


# ───────────────────────── 二、预览（v2 2.17）


def test_preview_is_zero_build_and_scripts_are_off() -> None:
    """`iframe srcdoc` 零构建（v2 原话）；脚本关掉——预览的是设计，不是让它执行。"""
    code = _source(COMPONENT)

    assert "srcDoc" in code
    assert 'sandbox=""' in code


def test_a_failed_preview_shows_the_raw_artifact_and_the_error() -> None:
    """失败时给原始产物 + 错误本身。"""
    code = _source(COMPONENT)

    assert "design__raw" in code
    assert "design__error-detail" in code


def test_the_component_keeps_no_last_good_preview() -> None:
    """**NEVER 用上一次成功的预览顶替**（v2 原话）。

    源码里连一个「上一版」的存放处都不该有：有了那个变量，
    就迟早有人在失败分支里把它渲染出来。
    """
    code = _source(COMPONENT)

    assert not re.search(r"last(Good|Success|Preview)", code, re.IGNORECASE)
    assert "useState" not in code, "装配层不留状态：产物由调用方给"


def test_the_page_never_submits_a_job_on_mount() -> None:
    """**这条判据被 `DESIGN-02` 有意翻过来了，翻的理由写在这里。**

    改前判的是「这一屏一个请求都不发」，当时的理由是：`/design/*` 都没挂，
    发一个必然 404 的请求只会在控制台留一条假红。

    今天三条端点里**两条真通了**（`DESIGN-01` 接的）：`GET /jobs/{id}/events`
    与 `GET /design/sessions/{job_id}/replay`。不发请求就等于把它们晾着。
    第三条（提交）仍然没有，而**它照样要发**——「能不能提交」的真相在服务端，
    前端自带一份判断会与后端各自漂移：端点哪天挂上了，屏上仍然会显示「没有」。
    那条 404 噪声登记在 `tests/v041/test_design_workbench_ui.py` 里判等值。

    所以这条改判**更硬的那一件**：进屏的 effect 里 NEVER 提交作业。
    提交了的话，用户每刷新一次页面就多开一个作业，而他看到的只是「又从头开始了」。
    """
    code = _source(PAGE)
    effects = re.findall(r"useEffect\(([\s\S]*?)\n  \}, \[", code)

    assert effects, "进屏没有任何 effect —— 那就没有续跑"
    for body in effects:
        assert "submitDesign" not in body, "进屏就提交了一次作业"


def test_the_page_passes_null_not_false() -> None:
    """两个入参都是「没查过」。写成 `false` / 空产物就是替后端下结论。"""
    code = _source(PAGE)

    assert "not_checked" in code, "屏上没有「还没查过」这一态"
    assert "preview={null}" in code
    assert "registryAvailable={false}" not in code
    assert "registryAvailable={true}" not in code


# ───────────────────────── 三、零计算与 token 纪律


def test_no_continuous_quantity_and_no_hardcoded_token() -> None:
    code = _source(COMPONENT) + _source(PAGE)

    assert "%" not in code
    assert not re.search(r"#[0-9A-Fa-f]{3,8}\b", code), "写死的色值"
    assert not re.search(r":\s*\d+px", code), "写死的像素值"


def test_every_string_shown_to_the_user_goes_through_i18n() -> None:
    for path in (COMPONENT, PAGE):
        for literal in re.findall(r"[\"'`]([^\"'`]*)[\"'`]", _source(path)):
            assert not re.search(r"[一-龥]", literal), \
                f"{path.name} 里有裸中文：{literal!r}"


def test_the_keys_exist_in_both_dictionaries() -> None:
    zh = json.loads((REPO / "web" / "messages" / "zh.json").read_text(encoding="utf-8"))
    en = json.loads((REPO / "web" / "messages" / "en.json").read_text(encoding="utf-8"))
    # `t(` 前面要有词边界：不加的话 `.get("job")`／`format("x")` 都会被当成 key
    # ——DESIGN-02 给这一屏加了 `params.get("job")`，当场报「job 不在词典里」。
    # **报错的地方是对的，报的内容是假的**：那不是一个 key。
    used = set(re.findall(
        r'(?<![A-Za-z_])t\("([^"]+)"',
        COMPONENT.read_text(encoding="utf-8") + PAGE.read_text(encoding="utf-8")))

    assert used
    for key in used:
        assert key in zh, key
        assert key in en, key


# ───────────────────────── 四、取证实况（acceptance④）


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
