"""Z-01：一次通过率 Z 线画上——从 `report_only` 升为可判定。

## 之前为什么悬着

`eval/pass_rate.py` 的原话：「Z 线值**配置化且初值未定**（owner 待定）……
未定线 → verdict='report_only'（只报告不判定，NEVER 代 owner 画线）」。
M4 出口报告那一行至今是「⚠️ 待 owner：19 卡 rate=1.0（report_only）」。

owner 2026-08-04 指示：**NEVER 因为本地条件通不过就把线一直悬着——
线先画上，达不到是另一件事**。

## 线画在 0.95，一半来自权威一半来自实测

- **权威那一半**：DORA 2024 报告里 elite 档的变更失败率 **≤5%**，
  换算成一次通过率就是 **≥0.95**。这是行业公开的分档线，不是我们发明的；
- **实测那一半**：本项目 M4 19 卡 rate=1.0、v0.4 台账 122 卡零 `review_failed`、
  v0.4.1 第 2 批 56 卡 1 处返工痕迹。**实测高于 0.95，所以这条线不是画着好看的**。

## 为什么不画 1.0

实测确实是 1.0，但 1.0 是**没有余量的线**：20 张卡里返工一次就判 fail，
而返工在本仓是**被鼓励的**（同一原因连续 2 次失败才升级）。
把线画成 1.0 等于把「返工」定义成「不合格」，那与 §7 的返工环自相矛盾。

## 误差有多大（acceptance④）

零失败样本的置信区间用**三法则**：n 次试验 0 次失败时，失败率的 95% 置信上界
≈ 3/n。本项目 n≈197（19 + 122 + 56），上界 ≈ 1.5%，即通过率的 95% 下界 ≈ **0.985**。
0.95 落在这个下界**之下**——也就是说「本项目超过这条线」不是运气好，
是样本量撑得住的结论。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from eval.pass_rate import pass_rate_report
from flint.config import (
    Z_LINE_BASIS,
    Z_LINE_INITIAL,
    ZLineError,
    load_z_line,
)

REPO = Path(__file__).resolve().parents[2]
DOC = REPO / "docs" / "Z线初值-v041.md"


# ───────────────────────── 一、依据文档（acceptance①④）


def test_the_basis_document_is_on_disk() -> None:
    assert DOC.exists(), "没有依据文档 = 这条线是拍出来的"


def test_the_document_separates_authority_from_our_own_measurement() -> None:
    """acceptance④：**哪部分来自权威、哪部分来自本项目实测**要分得开。

    混在一起写的话，读的人无从判断这条线是行业口径还是我们自己的成绩单，
    而这两者在被质疑时的答法完全不同。
    """
    doc = DOC.read_text(encoding="utf-8")

    assert "## 一、权威那一半" in doc
    assert "## 二、本项目实测那一半" in doc
    assert "## 三、误差" in doc


def test_the_authority_half_carries_a_link() -> None:
    """权威口径**逐行附出处**：没有链接的行业标准与凭印象说的没有区别。

    判的是「每一行都有」而不是「这一节里有」：判后者的话，删掉某一行的链接
    时别的行会把断言喂饱（变异考实测：删一行的链接，19 条全绿）。
    表头与数据行的分界**按分隔行定位**，不按行数偏移。
    """
    lines = DOC.read_text(encoding="utf-8").splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.startswith("## 一、"))
    end = next(i for i, ln in enumerate(lines[start + 1:], start + 1)
               if ln.startswith("## "))
    table = [ln for ln in lines[start:end] if ln.lstrip().startswith("|")]
    separator = next(i for i, ln in enumerate(table) if set(ln) <= set("| -:"))
    rows = table[separator + 1:]

    assert len(rows) >= 3, f"权威那一节只有 {len(rows)} 行"
    assert [ln for ln in rows if "http" not in ln] == [], "有不带出处的行"


def test_the_measured_half_states_the_sample_size() -> None:
    """实测那一半要写**样本量**：没有 n 的通过率是无法解释的数。"""
    lines = DOC.read_text(encoding="utf-8").splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.startswith("## 二、"))
    end = next(i for i, ln in enumerate(lines[start + 1:], start + 1)
               if ln.startswith("## "))
    section = "\n".join(lines[start:end])

    for token in ("19", "122", "56"):
        assert token in section, f"实测那一节没写 {token} 这一批的样本量"


def test_the_error_bar_is_written_down() -> None:
    """acceptance④：**误差多大**。三法则的**算式**与结果都要在文档里。

    只判「文中出现 0.985」的话，把算式整段删掉、只留结论那句，断言照样绿——
    而一个没有算式的置信下界与拍出来的数没有区别。
    """
    doc = DOC.read_text(encoding="utf-8")

    assert "三法则" in doc
    assert "3/197" in doc, "没有算式：只给结论的置信下界与拍出来的没有区别"
    assert "0.985" in doc, "没写出通过率的 95% 下界"


def test_the_document_says_why_not_one() -> None:
    """为什么不画 1.0 要写清——1.0 是实测值，不写就显得这条线画低了。"""
    doc = DOC.read_text(encoding="utf-8")

    assert "为什么不画 1.0" in doc
    assert "返工" in doc


# ───────────────────────── 二、初值进配置（acceptance②）


def test_the_initial_value_is_the_authority_floor() -> None:
    """初值 = DORA elite 档换算出来的 0.95。"""
    assert Z_LINE_INITIAL == 0.95


def test_the_basis_note_travels_with_the_number() -> None:
    """数与它的来由一体：分开放，下一段代码就会只带走那个数。"""
    assert "DORA" in Z_LINE_BASIS
    assert "Z线初值-v041" in Z_LINE_BASIS


def test_the_config_reads_the_env_override() -> None:
    """配置可覆盖：调线是 owner 的动作，**改配置不改代码**。"""
    assert load_z_line({"FLINT_Z_LINE": "0.8"}) == 0.8


def test_an_empty_env_falls_back_to_the_initial_value() -> None:
    """没设环境变量时回落初值——**NEVER 回落到 None**。

    回落 None 就又回到 `report_only`，等于这张卡没做。
    """
    assert load_z_line({}) == Z_LINE_INITIAL


@pytest.mark.parametrize("bad", ["abc", "1.5", "-0.1"])
def test_a_bad_override_is_refused_not_ignored(bad: str) -> None:
    """写错的值**报错**，NEVER 静默回落初值：静默回落会让 owner 以为自己调了线。"""
    with pytest.raises(ZLineError):
        load_z_line({"FLINT_Z_LINE": bad})


def test_the_initial_value_lives_in_exactly_one_place() -> None:
    """0.95 只写一处——第二处迟早与第一处不一致。

    两边都判：`pass_rate.py` 里不许有，`config.py` 的**代码面**里恰好一次。
    只判前者的话，回落分支里再抄一个 `return 0.95` 判不出来
    （变异考实测：19 条全绿，且那次变异当下**不改行为**——正是这种改动
    最容易活到它开始改行为的那天）。
    """
    import ast

    assert "0.95" not in (REPO / "eval" / "pass_rate.py").read_text(encoding="utf-8"), (
        "pass_rate.py 里抄了一份初值"
    )

    # 数的是 **AST 里的数字字面量**，不是文本里的 "0.95"：
    # `Z_LINE_BASIS` 那句来由说明里也写着这个数（它该写），按文本数会把说明算成第二份。
    tree = ast.parse((REPO / "flint" / "config.py").read_text(encoding="utf-8"))
    literals = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and node.value == 0.95
        and not isinstance(node.value, bool)
    ]

    assert len(literals) == 1, (
        f"config.py 里 0.95 这个数出现了 {len(literals)} 次——第二处迟早与第一处不一致"
    )


# ───────────────────────── 三、从 report_only 升为可判定（acceptance②③）


def test_the_verdict_is_no_longer_report_only() -> None:
    """acceptance②：拿配置的线去判，**结果是 pass 或 fail，不再是 report_only**。"""
    outcomes = [(f"t{i}", True) for i in range(19)]

    report = pass_rate_report(outcomes, z_line=load_z_line({}))

    assert report.verdict == "pass"
    assert report.z_line == Z_LINE_INITIAL


def test_a_failing_run_is_reported_as_failing() -> None:
    """acceptance②后半：**不达标就说不达标**。

    这条与上一条必须成对：只测 pass 的话，「线在起作用」与
    「这个函数永远返回 pass」长得一模一样。
    """
    outcomes = [(f"t{i}", i < 18) for i in range(20)]  # 18/20 = 0.90 < 0.95

    report = pass_rate_report(outcomes, z_line=load_z_line({}))

    assert report.verdict == "fail"
    assert report.rate == 0.9


def test_the_boundary_counts_as_pass() -> None:
    """恰好压线算过（`rate >= z_line` 的既有语义），边界写死免得日后各说各的。"""
    outcomes = [(f"t{i}", i < 19) for i in range(20)]  # 19/20 = 0.95

    assert pass_rate_report(outcomes, z_line=load_z_line({})).verdict == "pass"


def test_the_project_own_history_clears_the_line() -> None:
    """拿**本项目真实台账**跑一遍：这条线不是画着好看的。

    读的是 `docs/progress-v041.jsonl` 里真实发生的事件，不是构造数据——
    构造数据只能证明函数会算，证明不了这条线对本项目是否成立。
    """
    ledger = REPO / "docs" / "progress-v041.jsonl"
    events: dict[str, list[str]] = {}
    for line in ledger.read_text(encoding="utf-8-sig").splitlines():
        row = json.loads(line)
        events.setdefault(row["task_id"], []).append(row["event"])

    verified = {k: v for k, v in events.items() if "verified" in v}
    outcomes = [(k, "review_failed" not in v) for k, v in verified.items()]

    report = pass_rate_report(outcomes, z_line=load_z_line({}))

    assert report.total >= 19, "台账里 verified 的卡太少，这条断言说明不了问题"
    assert report.verdict == "pass", f"本项目自己的历史没过线：rate={report.rate}"


def test_the_owner_instruction_is_recorded_not_just_obeyed() -> None:
    """acceptance③：owner 那句「线先画上，达不到是另一件事」要落成文字。

    只照做不记录的话，下一个人看到 0.95 只会问「谁定的」。
    """
    doc = DOC.read_text(encoding="utf-8")

    assert "2026-08-04" in doc
    assert "线先画上" in doc
