"""MAC-06：`.ui-probe/` 取证产物不在本机时，口径只有一种——skip 并说清楚。

## 为什么要这条

`.ui-probe/` 是本机运行产物（79MB 截图与报告），不进仓。换一台机器，它整个不在。
2026-11-14 在 macOS 上首跑全量时，同样是「这台机器没跑过取证」：

- 354 条判据 skip，写明「本机没跑过…」「还没取证」；
- 另外 68 条直接红，报「缺这一张」「没有 .ui-probe/fe_smoke.json」。

两种口径并存的后果：一个刚克隆下来的仓，门禁恒红，而红的原因与代码无关。
`docs/macOS-安装.md` 写的预期本来就是 skip。

## 口径

`require_probe_evidence(anchor, how)`：

- `anchor` 不在——这台机器没跑过这份取证——**skip**，写明缺什么、怎么补；
- `anchor` 在——取证跑过——什么都不做，**缺哪一张照旧由调用方判红**。

第二条是这条口径不等于「缺了就放过」的地方：跑过取证而少了一张图，仍然是红的。

## 有一类补不回来

开工前拍的历史对照（搬家前的颜色、换板前的用量、改码前的指纹）只存在于原来那台机器上，
重跑取证造不出来。它们各自以那份历史文件本身为 anchor，skip 的话里写明这一点。
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tools.probe_evidence import require_probe_evidence

REPO = Path(__file__).resolve().parents[2]
TESTS = REPO / "tests" / "v041"

# 2026-11-14 那 68 条红所在的函数。直接读盘的测试函数自己带守卫；
# 经由读取辅助函数的（`_rows` / `_smoke` / `_nav_snapshot`）守卫写在辅助函数里。
GUARDED: dict[str, tuple[str, ...]] = {
    "test_combo_wire.py": (
        "test_every_step_left_a_screenshot", "test_this_card_changed_nothing_under_web"),
    "test_eye04.py": ("test_every_screenshot_is_on_disk",),
    "test_eye05.py": ("test_the_screenshot_is_on_disk", "test_the_flow_screenshot_is_on_disk"),
    "test_fav_card.py": ("test_the_screenshot_is_on_disk",),
    "test_palette_onscreen.py": (
        "test_the_inventory_lists_which_artifacts_have_judges_reading_them",
        "test_the_old_shots_are_labelled_instead_of_left_as_current"),
    "test_palette_v4.py": ("test_the_swap_itself_touched_only_the_palette_file",),
    "test_tail_01.py": ("_nav_snapshot",),
    "test_theme_really_switches.py": (
        "test_there_is_recorded_evidence_to_judge",
        "test_the_browser_level_negative_control_is_recorded",
        "test_the_two_recorded_runs_differ_only_by_the_dark_blocks"),
    "test_ui_mainchain.py": ("_rows",),
    "test_ui_restyle.py": ("_smoke",),
    "test_wb_annotate.py": ("test_the_screenshot_is_on_disk",),
    "test_wb_cards.py": ("test_the_screenshot_is_on_disk",),
    "test_wb_generate.py": ("test_the_screenshot_is_on_disk",),
    "test_wb_layout.py": ("test_the_screenshot_is_on_disk",),
    "test_wb_preview.py": ("test_the_screenshot_is_on_disk",),
    "test_wb_sections.py": ("test_the_screenshot_is_on_disk",),
}


# ───────────────────────── 一、守卫自己干得对不对


def test_a_missing_anchor_skips_and_says_what_is_missing(tmp_path: Path) -> None:
    anchor = tmp_path / ".ui-probe" / "eye99"

    with pytest.raises(pytest.skip.Exception) as caught:
        require_probe_evidence(anchor, "跑 tools/ui_probe_eye99.py")

    message = str(caught.value)
    assert "eye99" in message, "skip 的话里没点名缺的是哪一份"
    assert "tools/ui_probe_eye99.py" in message, "skip 的话里没说怎么补"


def test_a_present_anchor_does_not_skip(tmp_path: Path) -> None:
    """取证跑过的机器上守卫是空操作——缺哪一张由调用方的断言照旧判红。

    这条是阴性对照：守卫要是无条件 skip，上一条照样绿。
    """
    anchor = tmp_path / ".ui-probe" / "eye99"
    anchor.mkdir(parents=True)

    require_probe_evidence(anchor, "跑 tools/ui_probe_eye99.py")

    shots = list(anchor.glob("plaza-*.png"))
    assert shots == [], "空目录里不该找得到截图——调用方接下来的断言会因此判红"


# ───────────────────────── 二、那 68 条所在的函数都过了守卫


def _functions(path: Path) -> dict[str, ast.FunctionDef]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}


def _first_real_statement(func: ast.FunctionDef) -> ast.stmt:
    body = func.body
    is_doc = (isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant)
              and isinstance(body[0].value.value, str))
    return body[1] if is_doc else body[0]


@pytest.mark.parametrize(
    ("filename", "name"),
    [(f, n) for f, names in sorted(GUARDED.items()) for n in names])
def test_the_function_checks_the_anchor_before_it_reads_the_disk(
        filename: str, name: str) -> None:
    """守卫必须是函数体的**第一句**：写在读盘之后，等于没写。"""
    funcs = _functions(TESTS / filename)
    assert name in funcs, f"{filename} 里没有 {name}——清单过期了"

    first = _first_real_statement(funcs[name])
    called = (
        first.value.func.id
        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Call)
        and isinstance(first.value.func, ast.Name) else None)

    assert called == "require_probe_evidence", (
        f"{filename}::{name} 的第一句不是守卫（是 {ast.unparse(first)[:80]}）")


def test_the_list_covers_all_sixteen_files() -> None:
    assert len(GUARDED) == 16
    assert sum(len(v) for v in GUARDED.values()) == 21
