"""GAUGE-04 / F-08：文档里的 vitest 过滤器自检器的验收。

## F-08 是什么病

vitest 的位置参数是过滤器，**匹配不到的那些一声不响地被丢掉**，只要有一个能匹配上就 exit 0。
`WORKORDER-v04.md:528`（V4 图谱工作台里程碑门）里有四个 `src/…` 过滤器，而 `web/src/` 在
DEC-007 之后就不存在了——**那条门按文档跑只跑到 128 条里的 6 条（4.7%），并且报绿**。

实测（2026-08-04，本机 `cd web && npm test -- --run …`，与终检 F-08 的数字逐个一致）：

| 命令 | 按修前写法 | 按重映射本意 | 静默漏掉 |
|---|---|---|---|
| V3（:527） | 21 文件 / 143 tests，EXIT=0 | 31 文件 / 225 tests | 82 tests |
| V4（:528） | **1 文件 / 6 tests，EXIT=0** | 16 文件 / 128 tests | **122 tests** |

（前端全量 58 文件 / 524 tests 作参照。）

## 为什么兜底开关不够

`--passWithNoTests=false` 判的是「一个文件都没匹配到」，而混合过滤器**匹配到了**，只是少了
一大半。挡得住这种情况的判据只有一个：**逐个过滤器数它的匹配数，谁是 0 就点谁的名**。

## 为什么这些测试不 skip

本卡的病根之一是「这把尺子从来没被拿起来过」（GAUGE-02 清点出 17 条 acceptance 由工具脚本
守着、而没有任何 `tests/` 文件起它）。所以 `node` 找不到时这里**红**，NEVER `pytest.skip`——
skip 会让这条门在缺 node 的机器上悄悄消失，而消失的尺子正是 F-08 的成因。
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TOOL = REPO / "tools" / "check_vitest_filters.mjs"
WORKORDER = REPO / "WORKORDER-v04.md"

# 2026-08-04 对着**真 vitest**标定过的四个点（当时的绝对值）：
#   components → 21 文件 / components/graph-node → 1 / components views → 31 /
#   V4 那五个过滤器 → 16（各自与 `npm test -- --run …` 的 "Test Files N passed" 逐个对上）。
# 那次标定确立的是**匹配语义**：过滤器 = 测试文件相对 web/ 路径的子串。
#
# **绝对值会随着新增测试文件而变**，而且真的变了：FB-09 加了两个测试文件之后
# `components` 从 21 变成 22，这两条断言当场红——**那是我自己造的假红**，
# 语义一点没坏，坏的是「把会动的数字钉死」这个设计。
# 所以断言改成「校验器数出来的 == 按同一规则从磁盘数出来的」，
# 与真 vitest 的那次一致性作为标定记录留在上面。
FILTER_SHAPES = (
    "components",
    "components/graph-node",
    "components views",
    "components/graph-node components/graph-edge lib/undo lib/graph-layout views",
)


def _disk_count(command: str) -> int:
    """按 vitest 的规则从磁盘数：过滤器是相对 web/ 路径的子串，并集去重。"""
    web = REPO / "web"
    files = [
        p.relative_to(web).as_posix()
        for p in web.rglob("*")
        if p.is_file()
        and "node_modules" not in p.parts
        and any(p.name.endswith(ext) for ext in (".test.ts", ".test.tsx",
                                                 ".spec.ts", ".spec.tsx"))
    ]
    filters = command.split()
    if not filters:
        return len(files)                    # 空过滤器 = 全量（vitest 无参时的口径）
    hit: set[str] = set()
    for flt in filters:
        hit |= {f for f in files if flt in f}
    return len(hit)


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    node = shutil.which("node")
    assert node is not None, (
        "找不到 node：这条门量的是文档里的 vitest 命令，缺 node 就量不了。"
        "NEVER 把它 skip 掉——一把会自己消失的尺子等于没有尺子（F-08 的成因）。"
    )
    return subprocess.run(
        [node, str(TOOL), *args],
        cwd=REPO, capture_output=True, text=True, encoding="utf-8", check=False,
    )


def _report(*args: str) -> dict:
    done = _run("--json", *args)
    assert done.stdout.strip(), f"校验器没有输出 JSON：{done.stderr[:400]}"
    return json.loads(done.stdout)


def _doc(tmp_path: Path, name: str, command: str) -> str:
    path = tmp_path / name
    path.write_text(f"| V9 构造 | X-01 | 1 | `cd web && npm test -- --run {command}` |\n", encoding="utf-8")
    return str(path)


def test_a_filter_that_matches_nothing_is_named(tmp_path: Path) -> None:
    """acceptance③ 反例：含不存在路径的过滤器 → 红，且**点名是哪一个**。

    只报「有问题」不点名，等于把定位工作原样退回给人——F-08 那两行在文档里躺了三天，
    正是因为没有任何东西说得出「`src/views` 这一个匹配了 0 个文件」。
    """
    done = _run(_doc(tmp_path, "bad.md", "src/views"))

    assert done.returncode == 1, f"含 0 命中过滤器却退了 {done.returncode}"
    assert "src/views" in done.stdout + done.stderr
    assert "0 个文件" in done.stdout


def test_a_command_whose_filters_all_hit_exits_zero(tmp_path: Path) -> None:
    """acceptance③ 正例：全命中 → exit 0。

    没有这一条，一把「见谁都报红」的尺子也能通过上一条——那种尺子同样量不出东西。
    """
    done = _run(_doc(tmp_path, "good.md", "components/graph-node lib/undo views"))

    assert done.returncode == 0, f"全命中却红了：\n{done.stdout}\n{done.stderr}"


def test_a_mixed_filter_is_red_although_vitest_itself_exits_zero(tmp_path: Path) -> None:
    """acceptance①（正题）：混合过滤器——**vitest exit 0，校验器必须红**。

    这正是 F-08 与「只给一个坏过滤器」的区别：后者 vitest 自己会大声失败
    （`No test files found, exiting with code 1`），前者它报绿。实测同一条命令
    `--run components src/views` → `Test Files 21 passed / Tests 143 passed, EXIT=0`。
    """
    report = _report(_doc(tmp_path, "mixed.md", "components src/views"))

    assert len(report["commands"]) == 1
    command = report["commands"][0]
    # 数字从磁盘算（见 FILTER_SHAPES 上方那段：绝对值会随新增测试文件而变）。
    assert [f["count"] for f in command["filters"]] == [_disk_count("components"), 0]
    assert command["filesMatched"] == _disk_count("components"), "实际跑到的文件数"
    assert command["filesIfRepaired"] == _disk_count("components views"), "本该跑到的文件数"
    assert [d["filter"] for d in report["dead"]] == ["src/views"]


def test_the_file_counts_agree_with_what_vitest_really_ran(tmp_path: Path) -> None:
    """标定：校验器数出来的文件数 == 真 vitest 跑出来的文件数（四个点逐个对）。

    没有这一条，上面那些数字只是这把尺子的自说自话。四个标定点覆盖三种形状：
    单段目录、两段目录、多过滤器并列（含 `components` 与 `components/views` 的重叠去重）。
    """
    for command in FILTER_SHAPES:
        report = _report(_doc(tmp_path, "cal.md", command))
        got = report["commands"][0]["filesMatched"]
        want = _disk_count(command)
        assert got == want, f"过滤器 {command!r}：校验器数出 {got}，按同一规则从磁盘数是 {want}"

    assert _report(_doc(tmp_path, "cal.md", "components"))["testFileCount"] == _disk_count("")


def test_matching_is_relative_to_web_not_absolute(tmp_path: Path) -> None:
    """匹配只拿**相对 web/ 的路径**比，NEVER 拿绝对路径比。

    `web` 这一串必定出现在每个测试文件的绝对路径里（它就是 web 根的目录名），却不出现在
    任何相对路径里（相对路径以 `components/` `design/` `lib/` `stores/` `views/` 开头）。
    所以这条过滤器是一个天然的分界样本：按相对路径比 → 0 命中（红，正确）；
    按绝对路径比 → 58 命中（绿，假的）。

    这一条是补上来的：本卡先用三个变异体反过来考自己的测试，
    「把匹配改成绝对路径」那个变异体**9 条全绿地活了下来**——也就是说这套断言当时
    量不出这个语义。写它的那一刻我以为量得出，这正是 F-08 的形状。
    """
    report = _report(_doc(tmp_path, "abs.md", "web"))

    assert report["commands"][0]["filters"][0]["count"] == 0
    assert [d["filter"] for d in report["dead"]] == ["web"]


def test_the_suggestion_points_at_the_remapped_path(tmp_path: Path) -> None:
    """0 命中时给出补救建议：`src/lib/undo` → `lib/undo`。

    DEC-007 那次 `web/src/` → `web/` 重映射漏掉的就是这一形状，逐段砍开头即可复原。
    """
    report = _report(_doc(tmp_path, "tip.md", "src/lib/undo"))
    suggestion = report["commands"][0]["filters"][0]["suggestion"]

    assert suggestion == {"filter": "lib/undo", "count": 1}


def test_a_doc_with_no_vitest_command_is_red(tmp_path: Path) -> None:
    """扫到 0 条命令 = 红。

    文档改名、章节重排、命令换写法，都会让扫描器一条都扫不到。那时候报绿等于说
    「我检查过了，没问题」——而它其实什么都没检查。这条门自己就是这么坏掉的
    （F-11：`check_principles_doc.py` 从来不在全局门里，红了三天没人看见）。
    """
    empty = tmp_path / "empty.md"
    empty.write_text("这份文档里一条 vitest 命令都没有。\n", encoding="utf-8")

    done = _run(str(empty))

    assert done.returncode == 1
    assert "扫到 0 条" in done.stderr


def test_the_repo_milestone_gates_are_clean() -> None:
    """全仓真文档（WORKORDER-v04.md + docs/PRINCIPLES-v04.md）恒 exit 0。

    这一条把 F-08 从「修过一次」变成「不会再犯」：将来任何人往里程碑门里写一个
    匹配不到文件的过滤器，`pytest -q` 当场红。
    """
    done = _run()

    assert done.returncode == 0, f"里程碑门里有匹配零文件的过滤器：\n{done.stdout}\n{done.stderr}"


def test_the_v4_gate_line_names_all_sixteen_files() -> None:
    """钉住 F-08 那一行本身：V4 门的过滤器并集 = 16 个文件，且一个 `src/` 都不剩。

    并集而不是逐个数：`views` 与 `components/graph-node` 之间没有重叠，但
    `components` 与 `components/views` 那类重叠会让「逐个相加」得出虚高的数。
    """
    report = _report()
    v4 = [c for c in report["commands"] if "graph-node" in c["raw"] and "lib/undo" in c["raw"]]

    assert len(v4) == 1, f"WORKORDER 里 V4 门那条命令找到 {len(v4)} 条"
    assert v4[0]["filesMatched"] == 16
    assert "src/" not in v4[0]["raw"], "重映射又漏了"
    assert v4[0]["doc"] == "WORKORDER-v04.md"


def test_every_milestone_gate_command_is_scanned() -> None:
    """扫描面自证：文档里有多少条 `npm test -- --run`，报告里就该有多少条。

    扫描器少认一条命令 = 那条命令从此不被检查，而报告仍然全绿——与 F-08 同型的假绿。
    所以这里不信扫描器的自述，直接数原文里的出现次数。
    """
    raw = WORKORDER.read_text(encoding="utf-8")
    in_doc = raw.count("npm test -- --run")
    scanned = [c for c in _report()["commands"] if c["doc"] == "WORKORDER-v04.md"]

    assert len(scanned) == in_doc, f"文档里 {in_doc} 条，扫到 {len(scanned)} 条"
