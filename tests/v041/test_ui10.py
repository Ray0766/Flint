"""UI-10 · vibe_pack 查看器（蓝本 P12）的结构判据。

交互判据在 vitest（15 条）。这里判源码结构与取证实况。
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
COMPONENT = REPO / "web" / "components" / "pack-viewer" / "PackViewer.tsx"
PAGE = REPO / "web" / "app" / "deliverables" / "[id]" / "pack" / "page.tsx"
REPORT_SCREEN = REPO / "web" / "app" / "deliverables" / "[id]" / "page.tsx"
PROBE = REPO / ".ui-probe" / "fe_smoke.json"
ROUTE = "/deliverables/[id]/pack"


def _code_only(path: Path) -> str:
    text = re.sub(r"/\*[\s\S]*?\*/", "", path.read_text(encoding="utf-8"))
    return "\n".join(
        line for line in text.splitlines()
        if not line.lstrip().startswith(("//", "*"))
    )


# ───────────────────────── 一、与报告长得明显不同（清单第 31 条）


def test_the_pack_viewer_is_a_checklist_not_prose() -> None:
    """「它是给 AI 执行的包，排版上是否与给人读的报告明显不同？」

    报告是给人读的散文；vibe_pack 是喂给执行者的材料。两者长得一样的话，
    用户会把包当报告读（读不下去），或把报告当包喂（喂进去的是散文）。
    """
    code = _code_only(COMPONENT)

    assert 'data-pack-layout="checklist"' in code
    assert "<ol" in code
    assert "<table" in code


def test_chapter_bodies_are_preformatted() -> None:
    """要被逐字取走的东西走 `<pre>`：任何重排都会改到它。"""
    code = _code_only(COMPONENT)

    assert "<pre className=\"pack__chapter-body\">" in code


def test_the_pack_viewer_shares_no_component_with_the_report() -> None:
    """两屏不共用呈现组件——共用的那天它们就会长得一样。"""
    pack_imports = set(re.findall(r'from "([^"]+)"', _code_only(COMPONENT)))
    report_imports = set(re.findall(r'from "([^"]+)"', _code_only(REPORT_SCREEN)))
    shared = {i for i in pack_imports & report_imports if "components" in i}

    assert shared == set(), f"两屏共用了呈现组件：{shared}"


def test_no_completeness_score_is_synthesised() -> None:
    """BE-02 原话：章节数是**计数**不是分值，少一章是内容问题，不是「完成度 89%」。"""
    code = _code_only(COMPONENT)

    assert "%" not in code
    assert "/ 9" not in code
    assert not re.search(r"length\s*/", code)


# ───────────────────────── 二、Human Digest 不进 AI 上下文


def test_the_digest_flag_is_rendered() -> None:
    """不显示这条标记的话，用户会把监工视图和九章一起复制走。"""
    code = _code_only(COMPONENT)

    assert "for_ai_context" in code or "forAiContext" in code
    assert "pack.digest.not_for_ai" in code
    assert "data-for-ai-context" in code


def test_the_digest_is_outside_the_chapter_list() -> None:
    """结构上分开：digest 不在九章那个 `<ol>` 里。"""
    code = _code_only(COMPONENT)
    chapters_start = code.index("pack__chapters")
    chapters_end = code.index("</ol>")
    digest = code.index("pack__digest")

    assert not (chapters_start < digest < chapters_end)


# ───────────────────────── 三、三种「没有」


def test_not_provided_and_not_generated_are_two_branches() -> None:
    """BE-02：`bundle is None` → `status: "not_generated"`，**不是 404**。

    而「没查过」又是第三种。三者在屏上说三句话。
    """
    code = _code_only(COMPONENT)

    assert "pack === null" in code
    assert 'status === "not_generated"' in code
    assert code.index("pack === null") < code.index('status === "not_generated"')


def test_not_generated_renders_no_chapter_skeleton() -> None:
    code = _code_only(COMPONENT)
    branch = code[code.index('status === "not_generated"'):code.index("data-pack-layout")]

    assert "pack__chapter" not in branch, "还没生成时 NEVER 画九章骨架"


def test_the_page_sends_no_request_and_passes_null() -> None:
    code = _code_only(PAGE)

    assert "fetch(" not in code
    assert "pack={null}" in code
    assert "not_generated" not in code


# ───────────────────────── 四、token 纪律与 i18n


def test_no_hardcoded_token() -> None:
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


def test_the_audit02_ruler_stays_green_on_this_component() -> None:
    done = subprocess.run(
        ["node", str(REPO / "tools" / "check_design_constraints.mjs"),
         str(REPO / "web"), "--json"],
        cwd=REPO, capture_output=True, text=True, encoding="utf-8", check=False)
    report = json.loads(done.stdout)

    assert [f for f in report["findings"] if "pack" in f["file"]] == []


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
