"""DEF-03：undo 链三处接线的**源码面**尺子（行为面在 vitest）。

## 为什么 Python 这边也要有一把

行为验收在 `web/components/graph-undo/undoWiring.test.tsx`（24 条），跑法是
`cd web && npm test -- --run undo`——那条命令**不在** `pytest -q` 里。
删掉三处接线中的任意一处，Python 全局门照样全绿，而它是合并时唯一必跑的那道门
（GAUGE-02 的「在门内 / 门外」清点说的就是这件事）。

所以这把尺子只做一件事：**把三处接线的存在性搬进 Python 门**。
它不测行为——那是 vitest 的面，两边各测各的、NEVER 互相抄。

## 判断与注释分开

「源码里必须出现 X」同样会被注释骗：三个组件的抬头注释里都提到了撤销的理由。
所以一律**先剥注释再判**（口径与 `web/test-utils/source.ts#codeOnly` 一致，
那是前后踩了六次同一个坑之后抽出来的）。

## 卡面与实况

卡面说「三处操作点留了 pushUndo 调用位」。实况是三个组件里**零处**提到 undo，
留下的缝是另一样东西：三处的写操作都是注入的（`persist` / `onCreate` / `onBatchRole`），
撤销动作用同一个注入件反着做一次。narrowing 记在 `docs/trace/DEF-03.md#3`。
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB = REPO_ROOT / "web"
STACK = WEB / "lib" / "undo" / "undoStack.ts"
VITEST = WEB / "components" / "graph-undo" / "undoWiring.test.tsx"
SEAMS = {
    "GRAPH-04 拖动": WEB / "components" / "graph-drag" / "GraphDrag.tsx",
    "GRAPH-07 连线": WEB / "components" / "graph-edge" / "GraphEdgeDraft.tsx",
    "GRAPH-09 批量角色": WEB / "components" / "graph-multiselect" / "GraphMultiSelect.tsx",
}

_BLOCK_COMMENT = re.compile(r"/\*[\s\S]*?\*/")


def code_only(source: str) -> str:
    """剥注释，只留代码（口径同 `web/test-utils/source.ts#codeOnly`）。"""
    without_blocks = _BLOCK_COMMENT.sub("", source)
    return "\n".join(re.sub(r"//.*$", "", line) for line in without_blocks.split("\n"))


_SGR = re.compile(r"\x1b\[[0-9;]*m")

# The two summary lines byte for byte as a GitHub runner printed them
# (run 43694567536, unit job, 2026-11-15).
COLOURED_SUMMARY = (
    "\x1b[2m Test Files \x1b[22m \x1b[1m\x1b[32m2 passed\x1b[39m\x1b[22m\x1b[90m (2)\x1b[39m\n"
    "\x1b[2m      Tests \x1b[22m \x1b[1m\x1b[32m25 passed\x1b[39m\x1b[22m\x1b[90m (25)\x1b[39m\n"
)


def plain(text: str) -> str:
    """Drop terminal colour codes so a summary line reads the same in every shell.

    vitest 4.1 colours its output unless NO_COLOR is set or it detects an agent
    (`AI_AGENT`, `CLAUDECODE`, `CLAUDE_CODE`). A shell started by an agent therefore
    prints plain text; a person's terminal and a GitHub runner print colour codes
    between the words. Matching the raw text passed only in the first of the three.
    """
    return _SGR.sub("", text)


def test_plain_reads_the_summary_through_colour_codes() -> None:
    """The exact bytes that turned the first CI run red must read as a pass line."""
    assert "Test Files  2 passed" not in COLOURED_SUMMARY, "the recorded line no longer shows the trap"

    assert "Test Files  2 passed (2)" in plain(COLOURED_SUMMARY)
    assert "Tests  25 passed (25)" in plain(COLOURED_SUMMARY)
    assert "\x1b" not in plain(COLOURED_SUMMARY)
    assert plain(" Test Files  2 passed (2)\n") == " Test Files  2 passed (2)\n"


def test_code_only_strips_what_the_comments_say() -> None:
    """先证这把剥刀是真的——不然下面每一条都可能是被注释喂出来的绿。"""
    fake = 'const a = 1; // pushUndo\n/* pushUndo */\nconst b = 2;'

    assert "pushUndo" not in code_only(fake)
    assert "const b = 2;" in code_only(fake)


def test_all_three_seams_call_push_undo() -> None:
    """三处**都**接上了。少一处就点名是哪一处。

    `pushUndo(` 出现在代码里（不是注释里）+ 从 undoStack 导入——
    只查其中一样都能被绕过：光有 import 可以没调用，光有调用可能是同名的别的东西。
    """
    missing = []
    for name, path in SEAMS.items():
        code = code_only(path.read_text(encoding="utf-8"))
        if "pushUndo(" not in code or "lib/undo/undoStack" not in code:
            missing.append(f"{name}（{path.relative_to(REPO_ROOT).as_posix()}）")

    assert missing == [], f"这些操作点没接进 undo 链：{missing}"


def test_each_seam_pushes_only_after_the_write_succeeded() -> None:
    """入栈在**成功**那一支里，不在失败支、也不在请求发出之前。

    发出前就入栈的话，网络一断用户栈里就多了一条撤不掉的「操作」；
    而入栈等于向他承诺这一步撤得掉。

    判据是位置关系：`pushUndo(` 必须出现在 `.then(` 之后。
    """
    for name, path in SEAMS.items():
        code = code_only(path.read_text(encoding="utf-8"))
        push_at = code.index("pushUndo(")
        then_at = code.index(".then(")

        assert then_at < push_at, f"{name}：入栈没有落在成功那一支里"


def test_the_two_seams_that_need_an_undoer_refuse_to_push_without_one() -> None:
    """连线与批量角色**撤不回去就不入栈**：删不掉的边、造不出的还原点。

    两处各自的守门条件写死在这里，改掉守门条件这条就红——
    而那正是最容易在「让用例过」的压力下被悄悄拿掉的一行。
    """
    edge = code_only((WEB / "components" / "graph-edge" / "GraphEdgeDraft.tsx").read_text("utf-8"))
    assert "onUndoCreate === undefined" in edge, "连线：少了「没给撤销回调就不入栈」"

    multi = code_only(
        (WEB / "components" / "graph-multiselect" / "GraphMultiSelect.tsx").read_text("utf-8")
    )
    assert "snapshot === null" in multi, "批量角色：少了「拿不到操作前的角色就不入栈」"
    assert "onRestoreRoles === undefined" in multi, "批量角色：少了还原回调的守门"


def test_the_role_snapshot_is_taken_before_the_request_goes_out() -> None:
    """快照取在请求**之前**：回来之后 `roles` 可能已经是新值，那时取到的是操作**后**的角色。

    撤销会把角色「还原」成它现在的样子——什么都没变，而用户以为撤回去了。
    """
    code = code_only(
        (WEB / "components" / "graph-multiselect" / "GraphMultiSelect.tsx").read_text("utf-8")
    )

    assert code.index("const snapshot") < code.index("onBatchRole(selected")


def test_the_protected_block_guard_exists_and_uses_the_shared_predicate() -> None:
    """S2-5：受保护 block 的操作 NEVER 进栈，且**复用** `isProtected`。

    在这里另写一遍三条件（`locked || author === "user" || user_modified`）的那天，
    两处判定就会分叉——而分叉的那一侧会放进一条本不该存在的历史。
    """
    code = code_only(STACK.read_text(encoding="utf-8"))

    assert "export function pushBlockUndo" in code
    assert "isProtected(block)" in code
    assert 'author === "user"' not in code, "在 undoStack 里另写了一遍保护条件"


def test_push_block_undo_reports_whether_it_pushed() -> None:
    """挡下与入栈长得不一样：返回值是调用方唯一能发现「上游改了受保护 block」的地方。"""
    code = code_only(STACK.read_text(encoding="utf-8"))
    body = code[code.index("export function pushBlockUndo"):]

    assert "boolean" in body[:120], "pushBlockUndo 没有返回值"
    assert "return false" in body and "return true" in body


def test_the_behaviour_gauge_exists_and_the_verify_filter_hits_it() -> None:
    """卡面的 `npm test -- --run undo` 必须真能选中行为尺子。

    过滤词选不中任何文件时 vitest **退出码 0**——「一条都没跑」与「全绿」
    在命令行上长得一模一样（GAUGE-04 建的就是这条判据）。
    """
    assert VITEST.exists(), "行为尺子不在盘上"
    assert "undo" in VITEST.name.lower(), "verify_cmd 的过滤词 undo 选不中它"

    matched = [
        p for p in WEB.rglob("*.test.tsx")
        if "node_modules" not in p.parts and "undo" in p.as_posix().lower()
    ]
    assert VITEST in matched


def test_the_vitest_filter_actually_passes() -> None:
    """行为面在这里跑一次真的：源码面全对而行为是错的，这条会红。

    只查源码不跑行为，等于用「文件里有这个词」冒充「它真的能撤回去」——
    所以这一条直接把卡面的 verify_cmd 跑一遍。
    """
    done = subprocess.run(
        ["npm.cmd" if sys.platform == "win32" else "npm", "test", "--", "--run", "undo"],
        cwd=WEB, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )

    assert done.returncode == 0, f"{done.stdout[-3000:]}\n{done.stderr[-2000:]}"
    assert "Test Files  2 passed" in plain(done.stdout), plain(done.stdout)[-1500:]
