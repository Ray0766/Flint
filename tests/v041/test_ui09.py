"""UI-09 · 质量卡（R3）与陈旧重核横幅（R4）的结构判据。

交互判据在 vitest（18 条）。这里判源码结构与取证实况。
"""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
CARD = REPO / "web" / "components" / "quality" / "QualityCard.tsx"
BANNER = REPO / "web" / "components" / "quality" / "StalenessBanner.tsx"
PAGE = REPO / "web" / "app" / "deliverables" / "[id]" / "quality" / "page.tsx"
PROBE = REPO / ".ui-probe" / "fe_smoke.json"
ROUTE = "/deliverables/[id]/quality"


def _code_only(path: Path) -> str:
    text = re.sub(r"/\*[\s\S]*?\*/", "", path.read_text(encoding="utf-8"))
    return "\n".join(
        line for line in text.splitlines()
        if not line.lstrip().startswith(("//", "*"))
    )


# ───────────────────────── 一、NEVER 把布尔/枚举画成连续量


def test_the_quality_card_never_divides() -> None:
    """技术约束清单第 1 条。分子分母各一个数，中间那个「/」是排版不是除法。

    「引用覆盖率 17%」前端会拿它画进度条——**而那条进度条没有出处**。
    """
    # 先把字符串剥掉再判：`"../shell/NotProvided"` 里的 `/` 是路径分隔符，
    # 不是除法。不剥的话这条判据会把每一行 import 都报成除法——
    # 一把见谁咬谁的尺子，用不了几天就没人看它。
    code = re.sub(r"\"[^\"]*\"|'[^']*'|`[^`]*`", '""', _code_only(CARD))

    assert not re.search(r"\w\s*/\s*\w", code), "出现了除法"
    assert "%" not in code
    assert "toFixed" not in code
    assert "Math." not in code


def test_no_progress_bar_or_meter_markup() -> None:
    code = _code_only(CARD) + _code_only(BANNER)

    assert "<progress" not in code
    assert "aria-valuenow" not in code
    assert not re.search(r"width\s*:", code)


# ───────────────────────── 二、「没查过」不是「是 0」/「最新」


def test_unresolved_not_checked_is_a_separate_branch() -> None:
    code = _code_only(CARD)

    assert "unresolved === null" in code
    assert "quality.unresolved.not_checked" in code
    assert "data-unresolved-state" in code


def test_staleness_not_checked_is_never_rendered_as_fresh() -> None:
    """BE-04：快照没记账本版本时**连 `stale` 这个键都不给**。

    前端照办：`not_checked` 时说「还没判过」，且标记是 `unknown` 而不是 `false`。
    """
    code = _code_only(BANNER)

    assert 'status === "not_checked"' in code
    assert '"unknown"' in code
    assert "staleness.not_checked" in code


# ───────────────────────── 三、陈旧不隐藏内容（DESIGN-12）


def test_the_banner_cannot_reach_the_body_at_all() -> None:
    """够不着正文，也就藏不了。

    组件的 props 里没有 children、没有正文——判在**类型**上而不是行为上：
    行为判据只能证明「这次没藏」，类型判据证明「藏不了」。
    """
    code = _code_only(BANNER)

    assert "children" not in code
    assert "body" not in code.lower().replace("nobody", "")


def test_the_banner_is_not_rendered_when_nothing_is_known() -> None:
    """常驻位上不该有一条恒久的「未知」噪音。"""
    code = _code_only(BANNER)

    assert "staleness === null" in code
    assert "return null" in code


def test_not_revalidatable_says_why() -> None:
    code = _code_only(BANNER)

    assert "whyNot" in code
    assert 'data-revalidatable="false"' in code


# ───────────────────────── 四、屏本体与 token 纪律


def test_the_page_sends_no_request_and_passes_null() -> None:
    code = _code_only(PAGE)

    assert "fetch(" not in code
    assert "quality={null}" in code
    assert "staleness={null}" in code


def test_no_hardcoded_token_and_no_percentage() -> None:
    code = _code_only(CARD) + _code_only(BANNER) + _code_only(PAGE)

    assert "%" not in code
    assert not re.search(r"#[0-9A-Fa-f]{3,8}\b", code)
    assert not re.search(r":\s*\d+px", code)


def test_every_string_shown_to_the_user_goes_through_i18n() -> None:
    for path in (CARD, BANNER, PAGE):
        for literal in re.findall(r"[\"'`]([^\"'`]*)[\"'`]", _code_only(path)):
            assert not re.search(r"[一-龥]", literal), \
                f"{path.name} 里有裸中文：{literal!r}"


def test_the_keys_exist_in_both_dictionaries() -> None:
    zh = json.loads((REPO / "web" / "messages" / "zh.json").read_text(encoding="utf-8"))
    en = json.loads((REPO / "web" / "messages" / "en.json").read_text(encoding="utf-8"))
    source = "".join(p.read_text(encoding="utf-8") for p in (CARD, BANNER, PAGE))
    used = set(re.findall(r't\("([^"]+)"', source))

    assert used
    for key in used:
        assert key in zh, key
        assert key in en, key


def test_the_audit02_ruler_stays_green_on_these_files() -> None:
    """AUDIT-02 的 A1 规则（星级/雷达/合成百分比）在本卡两个组件上必须闭嘴。"""
    import subprocess

    done = subprocess.run(
        ["node", str(REPO / "tools" / "check_design_constraints.mjs"),
         str(REPO / "web"), "--json"],
        cwd=REPO, capture_output=True, text=True, encoding="utf-8", check=False)
    report = json.loads(done.stdout)
    mine = [f for f in report["findings"] if "quality" in f["file"]]

    assert mine == [], mine


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


def test_this_file_parses_as_python() -> None:
    """自检：判据文件本身要是合法 Python（写错了会整份被跳过）。"""
    ast.parse(Path(__file__).read_text(encoding="utf-8"))
