"""GAUGE-05 / F-12：卡面 `outputs` 声明 ↔ 仓库实况 对账器的验收。

## 被守的是一句承诺

隔离带六卡存在的全部理由是「owner 划掉一张 = 删一个文件，零返工」。终检查出这句话有一道
绕过去的路径：`flint/design/mock_syntax.py` 无卡认领，却被 DESIGN-28 与 DESIGN-29 的产物同时
import——**只删卡上声明的会留下孤儿，一并删掉会让另一张当场断线**。

## 这些测试的形状

对账器的三类判据各配一对：**真仓库上的现状断言**（把今天的事实钉住）+ **构造用例**
（证明新差异仍然红）。只有前者，规则一旦被放宽就没人知道；只有后者，白名单里的历史条目
悄悄失效也没人知道。

`test_every_whitelisted_row_is_still_a_real_finding` 是其中最要紧的一条反向断言：
**白名单里的每一条今天仍然必须能被检出**。一条豁免如果它豁免的东西已经不存在，
剩下的就只有它盖住的那个口子——那种白名单比没有白名单更危险。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools.check_outputs_declared import (
    LEGACY_SHARED,
    LEGACY_UNDECLARED,
    audit,
    classify_output,
    live,
    load_tasks,
    non_path_outputs,
)

REPO = Path(__file__).resolve().parents[2]
TASKS_V04 = REPO / "tasks-v04.json"

# 终检 F-12 逐字确证的三处少声明（本卡的回归钉）。
CONFIRMED_BY_REVIEW = (
    "flint/graph/roles.py",
    "flint/design/mock_syntax.py",
    "flint/design/comment_job.py",
)


def _real() -> tuple[list, list, list]:
    tasks, isolation = load_tasks(TASKS_V04)
    findings = audit(tasks, REPO, isolation)
    return tasks, findings, live(findings)


def _fake_repo(tmp_path: Path, modules: dict[str, str]) -> Path:
    (tmp_path / "flint").mkdir(parents=True, exist_ok=True)
    for rel, source in modules.items():
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source, encoding="utf-8")
    return tmp_path


def test_the_repo_has_no_new_difference() -> None:
    """真仓库：三类差异都只剩白名单里的历史条目。

    这一条是「今天的事实」；下面的构造用例证明规则本身没被放宽。
    """
    _, findings, remaining = _real()

    assert remaining == [], "\n".join(f"{f.kind} {f.path} {f.card} {f.detail}" for f in remaining)
    assert findings, "一条发现都没有：对账器很可能什么都没扫到"


def test_every_whitelisted_row_is_still_a_real_finding() -> None:
    """白名单反向断言：每一条豁免今天仍然必须对应一个真发现。

    豁免的东西已经不存在时，那条白名单剩下的只有它盖住的口子——这种「过期豁免」
    是规则被悄悄放宽的最常见形态（而它看起来永远是绿的）。
    """
    _, findings, _ = _real()
    detected_c = {f.key() for f in findings if f.kind == "C"}
    detected_b1 = {f.path for f in findings if f.kind == "B1"}

    stale_c = sorted(k for k in LEGACY_UNDECLARED if k not in detected_c)
    stale_b1 = sorted(p for p in LEGACY_SHARED if p not in detected_b1)

    assert stale_c == [], f"C 类白名单里这些条目已经不再是发现，该删掉它们：{stale_c}"
    assert stale_b1 == [], f"B1 类白名单里这些条目已经不再是发现：{stale_b1}"


def test_the_three_files_the_review_confirmed_are_all_caught() -> None:
    """终检逐字确证的三处少声明，一处不漏地被这把尺子检出（回归钉）。"""
    _, findings, _ = _real()
    caught = {f.path for f in findings if f.kind == "C"}

    assert set(CONFIRMED_BY_REVIEW) <= caught, f"漏掉了：{set(CONFIRMED_BY_REVIEW) - caught}"


def test_the_isolation_crack_is_reported_with_both_cards_named() -> None:
    """F-12 正题：无卡认领、却被两张隔离卡产物共用的文件，必须被点名且**两张卡都点到**。

    只说「有个文件有问题」没用——owner 要执行「划掉哪一张」，就得知道另一张是谁。
    """
    _, findings, _ = _real()
    b1 = [f for f in findings if f.kind == "B1"]

    assert [f.path for f in b1] == ["flint/design/mock_syntax.py"]
    assert "DESIGN-28" in b1[0].detail and "DESIGN-29" in b1[0].detail


def test_the_whitelist_exempts_a_pair_not_a_path(tmp_path: Path) -> None:
    """豁免按 `(路径, 卡号)` 逐条，NEVER 按路径整条豁免。

    按路径豁免的话，将来**另一张卡**再认领同一个文件也会跟着蒙混过关——而
    `mock_syntax.py` 恰恰就是被两张卡认领的那种文件，产权未定正是 F-12 的正题。
    这里用一个已在白名单里的路径 + 一个不在白名单里的卡号构造：必须仍然红。
    """
    whitelisted_path = "flint/graph/roles.py"
    assert any(path == whitelisted_path for path, _ in LEGACY_UNDECLARED)

    repo = _fake_repo(tmp_path, {whitelisted_path: '"""X-99：另一张卡认领同一个文件。"""\n'})
    findings = live(audit([{"id": "X-99", "outputs": []}], repo, []))

    assert [(f.kind, f.path, f.card) for f in findings] == [("C", whitelisted_path, "X-99")]


def test_a_declared_output_that_is_missing_is_red(tmp_path: Path) -> None:
    """A 类构造用例：卡面写了、磁盘上没有 → 红。"""
    tasks = [{"id": "X-01", "outputs": ["flint/nowhere.py"]}]

    findings = live(audit(tasks, _fake_repo(tmp_path, {}), []))

    assert [(f.kind, f.path, f.card) for f in findings] == [("A", "flint/nowhere.py", "X-01")]


def test_a_new_undeclared_module_is_red(tmp_path: Path) -> None:
    """C 类构造用例：新模块自述某张卡、无人声明 → 红（白名单挡不住新的）。"""
    repo = _fake_repo(tmp_path, {"flint/newthing.py": '"""X-02：新建的东西。"""\n'})
    tasks = [{"id": "X-02", "outputs": ["tests/x.py"]}, {"id": "X-01", "outputs": []}]
    (repo / "tests").mkdir(exist_ok=True)
    (repo / "tests" / "x.py").write_text("", encoding="utf-8")

    findings = live(audit(tasks, repo, []))

    assert [(f.kind, f.path, f.card) for f in findings] == [("C", "flint/newthing.py", "X-02")]


def test_a_new_shared_orphan_between_isolation_cards_is_red(tmp_path: Path) -> None:
    """B1 类构造用例：新的共用孤儿 → 红。

    形状与 `mock_syntax.py` 逐点相同：一个无卡认领的模块，被两张隔离卡的声明产物 import。
    """
    repo = _fake_repo(tmp_path, {
        "flint/shared.py": '"""无人认领。"""\n',
        "flint/left.py": "from flint.shared import thing\n",
        "flint/right.py": "from flint.shared import thing\n",
    })
    tasks = [
        {"id": "ISO-A", "outputs": ["flint/left.py"]},
        {"id": "ISO-B", "outputs": ["flint/right.py"]},
    ]

    findings = live(audit(tasks, repo, ["ISO-A", "ISO-B"]))

    assert [(f.kind, f.path) for f in findings] == [("B1", "flint/shared.py")]
    assert "ISO-A" in findings[0].detail and "ISO-B" in findings[0].detail


def test_an_isolation_output_used_from_outside_is_red(tmp_path: Path) -> None:
    """B2 类构造用例：隔离卡的声明产物被带外卡 import → 红（划掉会带塌带外的东西）。"""
    repo = _fake_repo(tmp_path, {
        "flint/inside.py": '"""隔离卡的产物。"""\n',
        "flint/outside.py": "from flint.inside import thing\n",
    })
    tasks = [
        {"id": "ISO-A", "outputs": ["flint/inside.py"]},
        {"id": "PLAIN-1", "outputs": ["flint/outside.py"]},
    ]

    findings = live(audit(tasks, repo, ["ISO-A"]))

    assert [(f.kind, f.path) for f in findings] == [("B2", "flint/inside.py")]
    assert "PLAIN-1" in findings[0].detail


def test_a_package_marker_rides_along_with_its_sibling(tmp_path: Path) -> None:
    """`__init__.py` 由同包兄弟带进来——但**只在真有兄弟时**。

    声明 `flint/pkg/thing.py` 的卡不可能不建 `flint/pkg/__init__.py`；而同包内没有该卡
    任何声明的 `__init__.py` 仍然是 C 类（仓库里 `flint/graph/__init__.py` 就是后一种）。
    """
    repo = _fake_repo(tmp_path, {
        "flint/pkg/__init__.py": '"""X-01：包标记。"""\n',
        "flint/pkg/thing.py": '"""X-01：本体。"""\n',
        "flint/lone/__init__.py": '"""X-02：没有兄弟的包标记。"""\n',
    })
    tasks = [{"id": "X-01", "outputs": ["flint/pkg/thing.py"]}, {"id": "X-02", "outputs": []}]

    findings = live(audit(tasks, repo, []))

    assert [(f.kind, f.path) for f in findings] == [("C", "flint/lone/__init__.py")]


def test_endpoint_shaped_outputs_are_listed_not_swallowed() -> None:
    """非路径形态的 outputs 单独列出，NEVER 悄悄丢掉。

    `api: POST /favorites` 声明的是端点不是文件，拿去 exists() 只会得到假红；
    但丢掉它就等于这把尺子替它们盖了章——所以它们必须出现在报告里。
    """
    tasks, _, _ = _real()
    listed = non_path_outputs(tasks)

    assert len(listed) == 5, [row[1] for row in listed]
    assert all(classify_output(raw)[0] == "non_path" for _, raw in listed)
    assert {card for card, _ in listed} == {"REGION-04", "REGION-05", "FAV-01", "FAV-02", "GRAPH-02"}


def test_annotated_paths_resolve_to_real_files() -> None:
    """带括号注解的 outputs 按去注解后的路径判存在，且今天全部命中。

    `contracts_v04/models_v04.py(增量区)` 说的是同一个文件的一段区域——按原样
    exists() 会得到一条永远修不好的假红，那种红最后总是被人整条忽略掉。
    """
    tasks, _, _ = _real()
    annotated = [
        (t["id"], raw) for t in tasks for raw in t.get("outputs", [])
        if classify_output(raw)[0] == "annotated"
    ]

    assert len(annotated) == 5
    for card, raw in annotated:
        core = classify_output(raw)[1]
        assert (REPO / core).exists(), f"{card} 的 {raw} 去注解后仍不存在：{core}"


def test_the_command_line_entry_point_agrees_with_the_library() -> None:
    """命令行出口与库函数结论一致（`--json` 供别的门消费）。"""
    done = subprocess.run(
        [sys.executable, "tools/check_outputs_declared.py", "--json"],
        cwd=REPO, capture_output=True, text=True, encoding="utf-8", check=False,
    )
    report = json.loads(done.stdout)
    _, findings, remaining = _real()

    assert done.returncode == (1 if remaining else 0)
    assert len(report["findings"]) == len(findings)
    assert report["live"] == [f.__dict__ for f in remaining]
    assert report["isolation"] == [
        "GRAPH-16", "DESIGN-27", "DESIGN-28", "DESIGN-29", "DESIGN-31", "DESIGN-32",
    ]
