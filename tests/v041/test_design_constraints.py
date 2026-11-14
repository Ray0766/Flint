"""AUDIT-02 · 交付包《技术约束清单》可执行化。

尺子是 `tools/check_design_constraints.mjs`（node）。本文件做三件事：

1. **每条规则一条阴性对照**：构造一段真违规的源码，断言那条规则报红。
   对一把扫描器来说，阴性对照就是变异考——变的是**被量的东西**，不是尺子。
   没有阴性对照的规则不算数：「没扫到违规」与「尺子瞎了」退出码一样。
2. **一条正向对照**：干净的源码上那条规则必须闭嘴（不误伤）。
3. **接进全局门**：这个文件本身就在 `pytest -q` 里，所以尺子每次合并都跑
   （F-11 的教训：一把不在门里的尺子，等于没建）。
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[2]
SCANNER = REPO / "tools" / "check_design_constraints.mjs"

# 本仓当前**已知且未修**的违规。逐条列出来，不是为了放过它们，
# 而是为了让**新增**的违规立刻可见：这张单子多一条或少一条，判据都红。
# 去向见 docs/blocked/S1-COMMON-STATES-MISSING.md。
# `UIX-01` 把这四行删空了——S1 三件通用件建好并接进那四个页面之后，
# A6 归零。**留着一行都不行**：判据判等值，多一行就是「登记了一个不存在的缺口」，
# 下一个人会去找一个已经修好的问题。
#
# 四条各自是怎么解的（写在这里，因为删掉之后就没别处记了）：
#
# | 页面 | 它缺的那一态在哪 |
# |---|---|
# | `app/deliverables/[id]/export` | 已有 `pending`，换成 `LoadingSkeleton`（既有 `data-export-pending` 断言面原样保留） |
# | `app/deliverables/[id]` | **async 服务器组件**：加载态只能在同目录 `loading.tsx`——组件内部没有「正在加载」那一刻可渲染 |
# | `app/demo` | 取数在 `DemoFlow` 里，**每处 await 都没有 catch**：失败时 `setBusy(false)` 永不执行，整屏卡死且不说话。补了 `run()` 包壳 + 三态 |
# | `app/jobs/[id]` | SSE 屏：`status === null` = 还没收到第一个事件 = 加载态；`failedReason` = 作业失败 = 错误态；有事件但无步骤 = 空态 |
KNOWN_GAPS: set[tuple[str, str, str]] = set()


def _scan(root: Path) -> dict[str, Any]:
    done = subprocess.run(
        ["node", str(SCANNER), str(root), "--json"],
        cwd=REPO, capture_output=True, text=True, encoding="utf-8", check=False)
    assert done.stdout.strip(), done.stderr
    out: dict[str, Any] = json.loads(done.stdout)
    return out


def _sample(tmp_path: Path, name: str, body: str) -> Path:
    root = tmp_path / "web"
    target = root / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")
    return root


def _rules_fired(tmp_path: Path, name: str, body: str) -> set[str]:
    return {f["rule"] for f in _scan(_sample(tmp_path, name, body))["findings"]}


# ───────────────────────── 一、每条规则的阴性对照（构造真违规 → 必须报红）


VIOLATIONS: list[tuple[str, str, str]] = [
    ("A1", "components/Score.tsx",
     "export const S = () => <span>★★★☆☆</span>;\n"),
    ("A1", "components/Bar.tsx",
     "export const B = ({ v }) => <div style={{ width: `${v * 100}%` }} />;\n"),
    ("A3", "components/DerefValue.tsx",
     "export const D = ({ citation_id }) => <span>{citation_id}</span>;\n"),
    ("A4", "components/StatusMark.tsx",
     "export const M = () => <i style={{ color: 'red' }} />;\n"),
    ("A5", "components/Hero.css",
     ".hero { background: var(--rust); }\n"),
    ("B8", "components/PlazaView.tsx",
     "export const P = ({ rows }) => rows.sort((a, b) => b.heat - a.heat);\n"),
    ("B9", "components/Agg.tsx",
     "const total = by_source.reduce((a, b) => a + b.value, 0);\n"),
    ("C17a", "components/Verdict.tsx",
     "const label = score > 3 ? 'A' : 'B';\n"),
    ("C17b", "components/Checked.tsx",
     "const ok = constraints_checked === true;\n"),
    ("C19", "components/Comp.tsx",
     "const weakish = s === 'unknown' || s === 'weak';\n"),
    ("D23", "components/Cell.tsx",
     "const amount = quantity * unitPrice;\n"),
    # 阴性对照必须是一屏**取数屏**：A6 只管发请求的那些（不发请求的屏没有
    # 「加载中」这回事，硬要它写一个只会写出永远进不去的死分支）。
    # `CHAIN-04` 把 A6 的读信号收窄成「进屏就会跑的那三样」
    # （`useScreenData` / `useEffect` / 具名 `fetchXxx(`）——原因是一张**写**屏
    # 只因 import 了 `chainClient` 就命中旧的 `Client\b`，被要求写一个它没有的空态。
    # 阴性对照跟着换成一屏**进屏真取数**的：判的仍是同一件事。
    ("A6", "app/thing/page.tsx",
     ("export default function Page() { useEffect(() => { fetch('/x'); }, []); "
      "return <div>x</div>; }\n")),
]


@pytest.mark.parametrize(("rule", "name", "body"), VIOLATIONS,
                         ids=[f"{r}-{n}" for r, n, _ in VIOLATIONS])
def test_a_real_violation_is_reported(
    rule: str, name: str, body: str, tmp_path: Path
) -> None:
    """阴性对照：这样写必须红。红不了的规则等于没有。"""
    assert rule in _rules_fired(tmp_path, name, body)


# ───────────────────────── 二、正向对照（干净源码上必须闭嘴）


CLEAN: list[tuple[str, str, str]] = [
    ("A1", "components/Progress.tsx",
     ("export const P = ({ progress }) => "
      "<div style={{ width: `${progress}%` }} />;\n")),
    ("A3", "components/DerefValue.tsx",
     ("export const D = ({ citation_id }) => "
      "<span>{citation_id ? '接口未提供' : null}</span>;\n")),
    ("A4", "components/StatusMark.tsx",
     "export const M = ({ shape }) => <i data-shape={shape} />;\n"),
    ("A5", "components/Blocking.css",
     ".blocking-mark { color: var(--rust); }\n"),
    ("B8", "components/PlazaView.tsx",
     "export const P = ({ rows }) => rows.map((r) => r.id);\n"),
    ("C19", "components/Comp.tsx",
     "const label = s === 'unknown' ? '未知' : s === 'weak' ? '弱' : '强';\n"),
    ("D23", "components/Cell.tsx",
     "const shown = String(quantity);\n"),
]


@pytest.mark.parametrize(("rule", "name", "body"), CLEAN,
                         ids=[f"{r}-clean" for r, _, _ in CLEAN])
def test_a_clean_sample_is_not_reported(
    rule: str, name: str, body: str, tmp_path: Path
) -> None:
    """正向对照：这样写必须闭嘴。**一把会误伤的尺子，用不了几天就没人看它。**"""
    assert rule not in _rules_fired(tmp_path, name, body)


# ───────────────────────── 三、尺子自己不能瞎


def test_no_rule_is_blind_on_the_real_tree() -> None:
    """一条规则一个文件都没落到 = 它是瞎的，而瞎的绿与真绿长得一样。"""
    report = _scan(REPO / "web")

    assert report["blind"] == [], f"这几条规则没落到任何文件：{report['blind']}"


def test_a_rule_with_no_subject_is_declared_not_silently_green() -> None:
    """无可量对象的规则要**说出来**，NEVER 当成「查过了、干净」。

    ## `UIX-03` 之后这条换了判法

    原判据是「`A4` 必须在名单里」——那是 `StatusMark` 组件还没建时的实况。
    `UIX-03` 把它建出来了，A4 有了可量对象，名单随之**空了**。

    再要求 A4 留在名单里，就是逼人把一个已经能量的规则挂回豁免。

    所以改判两件事：
    1. **机制还在**——名单里的每一条都要给出理由（`why` 非空）；
    2. **名单是空的**，且**没有规则是瞎的**（`blind` 也空）。
       瞎的规则与「跑过了、干净」在退出码上长得一模一样，
       所以两张名单要一起判——只判一张，另一张就成了盲区。
    """
    report = _scan(REPO / "web")

    assert all(item["why"] for item in report["noSubject"]), (
        "有规则挂了豁免却没写理由——那与悄悄跳过没有区别"
    )
    assert report["noSubject"] == [], (
        f"又有规则挂上豁免了：{report['noSubject']}——"
        f"若确实无可量对象，把理由写清楚并来这里登记"
    )
    assert report["blind"] == [], (
        f"这些规则一个文件都没落到，且没登记理由：{report['blind']}"
    )


def test_the_scanner_counts_every_rule_it_applied() -> None:
    report = _scan(REPO / "web")

    assert report["applied"]["A6"] >= 1
    assert report["applied"]["A1"] >= 10


def test_test_files_are_not_scanned() -> None:
    """测试文件里**故意**写着违规样例（就是上面那些）——扫它们等于自己咬自己。"""
    report = _scan(REPO / "web")

    assert not [f for f in report["findings"] if ".test." in f["file"]]


# ───────────────────────── 四、本仓实况：已知缺口逐条列出


def test_the_real_tree_has_exactly_the_known_gaps() -> None:
    """**这张单子多一条或少一条都红。**

    多一条 = 新引入了违规；少一条 = 有人修好了（那就更新单子）。
    把已知缺口写死在这里，是为了让**新增**的违规立刻可见——
    而不是为了放过它们：去向见 `docs/blocked/S1-COMMON-STATES-MISSING.md`。
    """
    report = _scan(REPO / "web")
    actual = {(f["rule"], f["file"].replace("\\", "/"), f["detail"])
              for f in report["findings"]}

    assert actual == KNOWN_GAPS


def test_the_known_gaps_have_a_ticket() -> None:
    """已知缺口 MUST 有去向。没有去向的「已知」就是「放着不管」。"""
    ticket = REPO / "docs" / "blocked" / "S1-COMMON-STATES-MISSING.md"

    assert ticket.exists()
    text = ticket.read_text(encoding="utf-8")
    for _, file, _ in KNOWN_GAPS:
        assert file in text, file


# ───────────────────────── 五、接进全局门（acceptance④）


def test_the_scanner_runs_from_the_command_line() -> None:
    done = subprocess.run(
        ["node", str(SCANNER), "web"], cwd=REPO, capture_output=True,
        text=True, encoding="utf-8", check=False)

    assert done.returncode in (0, 1)
    assert "技术约束清单" in done.stdout or "共" in done.stdout


def test_a_tree_with_no_violations_exits_zero(tmp_path: Path) -> None:
    """阴性对照的反面：真干净时必须 exit 0，否则这把尺子恒红、等于没有。"""
    root = _sample(tmp_path, "components/Fine.tsx",
                   "export const F = () => <span>干净</span>;\n")
    (root / "app" / "x").mkdir(parents=True)
    (root / "app" / "x" / "page.tsx").write_text(
        "export default function P() { return <div>Loading Empty Error</div>; }\n",
        encoding="utf-8")
    (root / "components" / "StatusMark.tsx").write_text(
        "export const M = ({ shape }) => <i data-shape={shape} />;\n",
        encoding="utf-8")
    (root / "components" / "DerefValue.tsx").write_text(
        "export const D = () => <span>接口未提供</span>;\n", encoding="utf-8")
    # B8 只落在 plaza/hotspot 这类文件上——合成树里没有的话它会被判成「瞎的」，
    # 于是这棵**干净**的树也退出 1。给它一个对象，才量得到「真干净」。
    (root / "components" / "PlazaView.tsx").write_text(
        "export const P = ({ rows }) => rows.map((r) => r.id);\n", encoding="utf-8")

    done = subprocess.run(
        ["node", str(SCANNER), str(root)], cwd=REPO, capture_output=True,
        text=True, encoding="utf-8", check=False)

    assert done.returncode == 0, done.stdout


def test_this_test_file_is_the_gate_wiring() -> None:
    """F-11 的教训：NEVER 建一把不在 `ruff && mypy && pytest` 里的尺子。

    这个文件在 `tests/` 下，所以 `pytest -q` 每次都会跑它，
    而它每一条都在调那把 node 尺子——**这就是接线本身**，
    不需要再往别处加一行配置（加了反而多一处会漂的真相）。
    """
    assert Path(__file__).parts[-3] == "tests"
    assert SCANNER.exists()


def test_node_is_available() -> None:
    """尺子是 node 写的。node 不在的话上面全部会红——**要红得说清原因**。"""
    done = subprocess.run(["node", "--version"], capture_output=True, text=True,
                          check=False)

    assert done.returncode == 0, "node 不可用：这把尺子跑不了，不是代码有问题"
    assert done.stdout.startswith("v"), done.stdout
