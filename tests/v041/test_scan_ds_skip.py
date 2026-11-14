"""DEF-04：`scan_ds_assets.mjs` 补目录跳过（E1 观察项）。

## 这一条为什么留到现在

`tools/scan_ds_assets.mjs` 的 `walk()` 一路递归到底，不跳 `node_modules` / `.next`；
另外那几把扫描器（`i18n_scan.mjs` / `lint_no_confidence_viz.mjs` / `no_external_fonts.mjs`）
第一行就跳。当前不影响判定——它的 verify_cmd 只指向 `web/public/_ds`，那底下没有
vendor 目录。**换个扫描面就不一样**：拿它扫 `web`，命中的全是 vendor 文件。

封版后不打无卡的补丁（DEC-021），所以留到 v0.4.1。

## 跳过是按**目录名**跳，不是按路径子串跳

`path.includes("node_modules")` 会把 `web/my_node_modules_notes/` 一起跳掉——
那是用户自己的目录。跳错方向的代价是**静默漏扫**：报告上写着「扫描 N 个文件」，
而少的那些一个字都不会提。

## 阴性对照是这把尺子的一半

「跳过 vendor」与「什么都不扫」在退出码上长得一模一样（都是 0）。
所以每条跳过用例旁边都有一条**同样的违规放在跳过目录之外**，必须红。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCANNER = REPO_ROOT / "tools" / "scan_ds_assets.mjs"
NODE = "node.exe" if sys.platform == "win32" else "node"

# 一处真违规：mono 字体 + 数值语义的名字 + 没有 tabular-nums
VIOLATION = """.total-count {
  font-family: var(--font-mono);
  font-size: 12px;
}
"""
# `.num` 类带 tabular-nums 是扫描器的另一条判据（缺了它也判红），
# 每个临时树都得有，否则测的就不是「跳过」而是「缺 .num 类」。
NUM_CLASS = ".num { font-variant-numeric: tabular-nums; }\n"


def run(target: Path, *flags: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [NODE, str(SCANNER), str(target), *flags],
        cwd=REPO_ROOT, capture_output=True, text=True, encoding="utf-8",
        errors="replace", check=False,
    )


def make_tree(root: Path, *, where: str) -> Path:
    """在 `where` 放一处违规，树根另放一个干净的 `.num` 声明。"""
    pkg = root / "pkg"
    (pkg / where).mkdir(parents=True, exist_ok=True)
    (pkg / where / "vendor.css").write_text(VIOLATION, encoding="utf-8")
    (pkg / "app.css").write_text(NUM_CLASS, encoding="utf-8")
    return pkg


def test_a_violation_inside_node_modules_is_skipped(tmp_path: Path) -> None:
    """acceptance①：`node_modules` 底下的命中不算数。"""
    pkg = make_tree(tmp_path, where="node_modules")

    done = run(pkg, "--tabular-nums")

    assert done.returncode == 0, done.stdout
    assert "扫描 1 个文件" in done.stdout, done.stdout


def test_a_violation_inside_dot_next_is_skipped(tmp_path: Path) -> None:
    """`.next` 同理——构建产物不是我们写的代码。"""
    pkg = make_tree(tmp_path, where=".next")

    done = run(pkg, "--tabular-nums")

    assert done.returncode == 0, done.stdout
    assert "扫描 1 个文件" in done.stdout, done.stdout


def test_the_same_violation_outside_those_dirs_is_still_red(tmp_path: Path) -> None:
    """**阴性对照**：跳过 vendor 与什么都不扫，在退出码上长得一模一样。

    同一份违规内容挪到 `src/` 底下，必须红——否则上面两条证明的是
    「这把尺子瞎了」，不是「它会跳过 vendor」。
    """
    pkg = make_tree(tmp_path, where="src")

    done = run(pkg, "--tabular-nums")

    assert done.returncode == 1, done.stdout
    assert "数字容器缺 tabular-nums：1 处" in done.stdout, done.stdout


def test_the_skip_is_by_directory_name_not_by_path_substring(tmp_path: Path) -> None:
    """按**目录名**跳，不按路径子串跳。

    `includes("node_modules")` 会把 `my_node_modules_notes/` 一起跳掉——那是用户
    自己的目录，而漏扫是**静默**的：报告上写着扫了 N 个文件，少的那些一个字不提。
    """
    pkg = make_tree(tmp_path, where="my_node_modules_notes")

    done = run(pkg, "--tabular-nums")

    assert done.returncode == 1, done.stdout


def test_a_whole_vendor_subtree_stays_off_the_scan_surface(tmp_path: Path) -> None:
    """整棵 vendor 子树都不在扫描面上（不只是顶层那一个文件）。

    **这一条不区分「跳在递归里」与「读完再筛」**：文件计数是筛完之后打印的，
    两种写法都会给出同一个数。变异考证实了这一点（读完再筛的变异体只被
    `test_the_idiom_is_the_same_as_the_other_scanners` 那条源码面判据抓住）。

    区别是性能上的：读完再筛意味着 `node_modules` 底下几万个文件照样被
    `statSync` 走一遍，扫一次 `web` 要多花几十秒。守它的是那条源码面判据，
    不是这一条——写清楚，免得下一个人以为这里已经守住了。
    """
    pkg = tmp_path / "pkg"
    deep = pkg / "node_modules" / "a" / "b" / "c"
    deep.mkdir(parents=True)
    for i in range(5):
        (deep / f"f{i}.css").write_text(VIOLATION, encoding="utf-8")
    (pkg / "app.css").write_text(NUM_CLASS, encoding="utf-8")

    done = run(pkg, "--tabular-nums")

    assert "扫描 1 个文件" in done.stdout, done.stdout


def test_the_idiom_is_the_same_as_the_other_scanners() -> None:
    """与另外三把口径一致：同样两个名字、同样在 walk 里 `continue`。

    各写各的那天，「跳哪些目录」这件事就有了四个版本，而其中哪一个漏跳了
    只有在某次换扫描面时才会发现——正是本卡这条观察项的由来。
    """
    source = SCANNER.read_text(encoding="utf-8")
    code = "\n".join(line for line in source.split("\n") if not line.strip().startswith("//"))

    assert 'entry === "node_modules"' in code
    assert 'entry === ".next"' in code

    for other in ("i18n_scan.mjs", "lint_no_confidence_viz.mjs", "no_external_fonts.mjs"):
        peer = (REPO_ROOT / "tools" / other).read_text(encoding="utf-8")
        assert 'entry === "node_modules" || entry === ".next"' in peer, other


def test_the_original_target_still_passes() -> None:
    """acceptance③：既有自证不倒——`web/public/_ds` 双开关仍然 exit 0。"""
    done = run(REPO_ROOT / "web" / "public" / "_ds", "--tabular-nums", "--no-warn-emoji")

    assert done.returncode == 0, done.stdout


def test_scanning_the_whole_web_tree_no_longer_drowns_in_vendor() -> None:
    """acceptance②：拿它扫 `web` 全树（真实结果记在 `docs/trace/DEF-04.md#4`）。

    改之前：扫描 14582 个文件，6 处 tabular 命中**全部**在 `.next` / `node_modules` 里，
    `--tabular-nums` 直接判红。改之后 vendor 不进扫描面，命中归零。
    """
    done = run(REPO_ROOT / "web", "--tabular-nums")

    assert "node_modules/" not in done.stdout, "vendor 文件仍在扫描面上"
    assert ".next/" not in done.stdout, "构建产物仍在扫描面上"
    assert done.returncode == 0, done.stdout
