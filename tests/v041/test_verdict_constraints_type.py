"""TYPE-03 · `Verdict.constraints_checked` 前端标成 boolean，后端是对象。

## 为什么这条错类型一直没出事

`GateView` **不渲染这个字段**（它只渲染 verdict / 引用 / 理由 / 竞品 / gaps），
所以那行 `constraints_checked: boolean` 一次都没被执行到。

**危险在于它看起来是对的**：下一个人要把「判定依据」做成可展开面板时，
会照着类型写 `{verdict.constraints_checked ? …}`——
**一个非空对象恒为真**，于是屏上出现一个永远展开、内容为 `true` 的面板，
而真正的六项依据一项都不显示。

## 本文件最要紧的一条：**真造一次那种误用**

只断言「类型已经改成对象」是不够的——那只说明字面量变了。
要证明的是**那种误用现在写不出来**：所以这里跑一次真 `tsc`，
拿一个照 boolean 写法的片段喂给它，断言它**被拦下来**。

阴性对照同样跑真 `tsc`：正确写法必须**通过**。
两条都跑，才能分清「拦住了」和「见谁都拦」。
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
WEB = REPO / "web"
CLIENT = WEB / "lib" / "viewsClient.ts"
ENGINE = REPO / "flint" / "gate" / "engine.py"
TICKET = REPO / "docs" / "blocked" / "VERDICT-CONSTRAINTS-CHECKED-TYPE.md"


def _declared(interface: str) -> set[str]:
    """某个接口**自己**声明的顶层字段名。"""
    source = CLIENT.read_text(encoding="utf-8")
    match = re.search(
        rf"export interface {interface} \{{(.*?)\n\}}", source, re.DOTALL)
    assert match, f"viewsClient.ts 里没有 {interface}"
    return set(re.findall(r"^  (\w+)\??:", match.group(1), re.MULTILINE))


def _backend_keys() -> set[str]:
    """后端**真的会放进去**的键，从 `engine.py` 那个字面量 dict 抽。

    NEVER 手抄——手抄的清单不会跟着后端变。
    """
    source = ENGINE.read_text(encoding="utf-8")
    match = re.search(r"constraints_checked: JSON = \{(.*?)\n    \}", source, re.DOTALL)
    assert match, "engine.py 里找不到 constraints_checked 的构造"
    # 只取**顶层**键：缩进恰好 8 空格的那些（内层规则的键缩进更深）。
    return set(re.findall(r'^        "(\w+)":', match.group(1), re.MULTILINE))


# ───────────────────────── acceptance①：改成对象，字段逐字对齐


def test_the_field_is_no_longer_a_boolean() -> None:
    source = CLIENT.read_text(encoding="utf-8")

    assert not re.search(r"constraints_checked:\s*boolean", source), (
        "还是 boolean——后端一直回的是对象"
    )
    assert re.search(r"constraints_checked:\s*ConstraintsChecked", source)


def test_the_object_declares_exactly_what_the_backend_puts_in() -> None:
    """判**等值**：前端声明的顶层字段 == 后端构造的顶层键。

    少一个 → 有数据没人知道；多一个 → 写下去拿到 `undefined`，
    而 TypeScript 会说它有类型。
    """
    assert _declared("ConstraintsChecked") == _backend_keys()


def test_the_three_rules_keep_their_own_sub_fields() -> None:
    """三条规则各有各的子字段——摊平成一个 `satisfied` 就丢了复盘依据。

    `engine.py` 的 docstring 原话：「摊平三规则的评估痕迹，供 VerdictShift 重跑复盘」。
    """
    source = CLIENT.read_text(encoding="utf-8")
    body = re.search(r"export interface ConstraintsChecked \{(.*?)\n\}",
                     source, re.DOTALL)
    assert body
    text = body.group(1)

    for rule, fields in (
        ("rule_a", ("satisfied", "used_user_evidence_only", "blocked_pending_optin")),
        ("rule_b", ("satisfied", "by_count", "by_strength", "reachable_count",
                    "strong_names")),
        ("rule_c", ("satisfied", "failed_conditions", "blocking_competitors")),
    ):
        segment = text.split(f"{rule}: {{")[1].split("};")[0]
        for name in fields:
            assert name in segment, f"{rule} 少了 {name}"


def test_the_counts_are_numbers_not_ratios() -> None:
    """`reachable_count` / `gap_count` 是**计数**，NEVER 是比率。

    前端零计算：屏上那个数是后端数出来的，不是前端除出来的。
    """
    source = CLIENT.read_text(encoding="utf-8")
    body = re.search(r"export interface ConstraintsChecked \{(.*?)\n\}",
                     source, re.DOTALL)
    assert body

    assert re.search(r"reachable_count:\s*number", body.group(1))
    assert re.search(r"gap_count:\s*number", body.group(1))
    assert "%" not in body.group(1) and "ratio" not in body.group(1)


# ───────────────────────── acceptance②：真造一次误用，看 tsc 拦不拦


def _typecheck(snippet: str, tmp_path: Path) -> subprocess.CompletedProcess[str]:
    """把片段丢进 `web/` 下的临时文件，跑真 `tsc` 看它怎么说。

    **NEVER 只读源码判断**：能不能写出那种误用，只有编译器说了算。
    临时文件用完即删（`finally`），NEVER 留在产品树里。
    """
    npx = shutil.which("npx")
    assert npx is not None, "找不到 npx：这条门量不了，NEVER 当它通过"
    probe = WEB / "_type03_probe.ts"
    probe.write_text(snippet, encoding="utf-8")
    try:
        return subprocess.run(
            [npx, "tsc", "--noEmit", "--strict", "--skipLibCheck",
             "--target", "ES2020", "--moduleResolution", "bundler",
             "--module", "esnext", str(probe)],
            cwd=WEB, capture_output=True, text=True, encoding="utf-8",
            errors="replace", check=False)
    finally:
        probe.unlink(missing_ok=True)


_MISUSE = '''import type { Verdict } from "./lib/viewsClient";

// 照 boolean 写法用它——**一个非空对象恒为真**，
// 于是面板永远展开、内容是 `true`。
export function panelIsOpen(v: Verdict): boolean {
  const flag: boolean = v.constraints_checked;
  return flag;
}
'''

_CORRECT = '''import type { Verdict } from "./lib/viewsClient";

// 正确写法：读它的字段，而不是把整个对象当真值。
export function gapCount(v: Verdict): number {
  return v.constraints_checked.gap_count;
}
'''


@pytest.mark.parametrize(("snippet", "should_fail", "why"), [
    (_MISUSE, True, "把对象当 boolean 用，编译器必须拦下来"),
    (_CORRECT, False, "正确写法必须通过——见谁都拦的类型同样没用"),
])
def test_tsc_rejects_the_boolean_misuse_and_accepts_the_right_one(
        snippet: str, should_fail: bool, why: str, tmp_path: Path) -> None:
    done = _typecheck(snippet, tmp_path)
    output = done.stdout + done.stderr

    if should_fail:
        assert done.returncode != 0, f"{why}\n{output[:400]}"
        assert "constraints_checked" in output or "boolean" in output, output[:400]
    else:
        assert done.returncode == 0, f"{why}\n{output[:600]}"


def test_the_probe_file_is_not_left_in_the_tree() -> None:
    """临时探针用完即删——NEVER 留在产品树里。"""
    assert not (WEB / "_type03_probe.ts").exists()


# ───────────────────────── acceptance③：单子关掉


def test_the_ticket_is_closed_with_a_banner_and_a_date() -> None:
    text = TICKET.read_text(encoding="utf-8")
    head = "\n".join(text.splitlines()[:14])

    assert "已关闭" in head
    assert "2026-08-05" in head
    assert "TYPE-03" in head


def test_the_existing_fixture_was_fixed_too() -> None:
    """既有夹具里那个 `constraints_checked: true` 也要改掉。

    夹具照着错类型写，于是**两边一起错**——谁都看不出来。
    改类型的那一刻 `tsc` 当场拦下了那一行，这条把它钉住。
    """
    fixture = (WEB / "components" / "views" / "views.test.tsx").read_text(
        encoding="utf-8")

    assert "constraints_checked: true" not in fixture
    assert '"order"' in fixture or "order:" in fixture


def test_the_gate_view_still_does_not_render_it() -> None:
    """`GateView` 此刻**仍然不渲染**这个字段——本卡只改类型，不做渲染。

    判它是为了让「哪天有人开始渲染」这件事被看见：
    到那天这条会红，而那正是该回头看一眼「面板是不是照六项依据画的」的时刻。
    """
    view = (WEB / "components" / "views" / "GateView.tsx").read_text(encoding="utf-8")

    assert "constraints_checked" not in view, (
        "有人开始渲染判定依据了——去确认它是按六项画的，"
        "而不是 `{v.constraints_checked ? …}`，然后把本条改成断言渲染正确"
    )


def test_the_backend_shape_is_read_from_the_engine_not_hand_copied() -> None:
    """本文件的期望值来自 `engine.py`，不是手抄的清单。"""
    source = Path(__file__).read_text(encoding="utf-8")

    assert "_backend_keys()" in source
    assert json.dumps(sorted(_backend_keys()), ensure_ascii=False) not in source
