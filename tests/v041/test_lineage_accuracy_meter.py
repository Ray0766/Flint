"""BL-10：血缘准确率度量器（S4 出口断言 ≥90%、50 簇的那把尺子）。

## 为什么再要一把

`eval/lineage.py`（M1-039）已经能对着 `assets/labels.yaml` 算准确率，但它有三处
与 S4 的出口断言对不上：

1. **没有样本量闸**：S4 写的是「≥90%（**50 簇**）」，而它拿 3 簇也照样报 100% 并
   `exit 0`——**小样本算出的数字长得与真判定一模一样**；
2. **它会判**：低于 `--min` 退 1。本卡要的是**恒 report_only** 的度量器（S4 的
   θ_rel / δ / 血缘线都还是未决项，判定归 owner）；
3. **口径没写死**：什么算一次正确的血缘、少一个事件怎么算、标注里有而实际没有
   怎么算——不写清，下次量出的数与这次不可比。

## 口径（度量器 docstring 逐字，测试逐条守）

- 一次「正确」= 该簇的 **(day, kind) 全序列逐项相等**（顺序敏感）；
- **簇级全或无**：少一个、多一个、顺序不同都算这一簇错；
- 标注里有、实际里找不到的簇 → **计入分母、不计分子**（跳过会让准确率虚高）；
- 实际里有、标注里没有的簇 → 不计入准确率，但**报出条数**（它可能说明标注集不全）。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from harness.lineage_accuracy import (
    EXIT_LINE,
    MIN_GOLD_CLUSTERS,
    ClusterLabel,
    measure,
    render,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def _label(key: str, *events: tuple[str, str]) -> ClusterLabel:
    return ClusterLabel(cluster_key=key, expected=tuple(events))


def _labels(n: int) -> list[ClusterLabel]:
    return [_label(f"c-{i}", ("2026-07-01", "new")) for i in range(n)]


def _actual(n: int) -> dict[str, list[tuple[str, str]]]:
    return {f"c-{i}": [("2026-07-01", "new")] for i in range(n)}


# ───────────────────────── 一、算得对


def test_a_cluster_matches_only_when_the_whole_timeline_matches() -> None:
    """一次「正确」= (day, kind) 全序列逐项相等。"""
    labels = [_label("c-1", ("2026-07-01", "new"), ("2026-07-05", "split"))]
    actual = {"c-1": [("2026-07-01", "new"), ("2026-07-05", "split")]}

    assert measure(labels, actual).matched == 1


def test_one_missing_event_makes_the_whole_cluster_wrong() -> None:
    """**簇级全或无**：少一个事件，这一簇就算错。

    按事件计分的话，「漏了一次 split」看起来只丢一点点——而血缘是一条时间线，
    错一处后面全错位。
    """
    labels = [_label("c-1", ("2026-07-01", "new"), ("2026-07-05", "split"))]
    actual = {"c-1": [("2026-07-01", "new")]}

    report = measure(labels, actual)

    assert report.matched == 0
    assert report.total == 1


def test_one_extra_event_also_makes_it_wrong() -> None:
    """多一个事件同样算错——多出来的那次血缘是编的。"""
    labels = [_label("c-1", ("2026-07-01", "new"))]
    actual = {"c-1": [("2026-07-01", "new"), ("2026-07-09", "merge")]}

    assert measure(labels, actual).matched == 0


def test_the_order_matters() -> None:
    """顺序不同算错：先分裂后合并与先合并后分裂是两件事。"""
    labels = [_label("c-1", ("2026-07-01", "split"), ("2026-07-05", "merge"))]
    actual = {"c-1": [("2026-07-05", "merge"), ("2026-07-01", "split")]}

    assert measure(labels, actual).matched == 0


def test_a_labelled_cluster_that_is_missing_counts_in_the_denominator() -> None:
    """标注里有、实际里找不到 → **计入分母、不计分子**。

    跳过它的话分母变小，准确率虚高——而「压根没产出这个簇」是最严重的一种错。
    """
    report = measure([_label("c-1", ("2026-07-01", "new"))], {})

    assert (report.total, report.matched) == (1, 0)
    assert report.mismatches[0]["actual"] == []


def test_an_unlabelled_cluster_is_reported_but_not_scored() -> None:
    """实际里有、标注里没有 → 不进准确率，但**报出条数**。

    它可能说明标注集不全——不报出来，这件事没人知道。
    """
    report = measure([_label("c-1", ("2026-07-01", "new"))],
                     {"c-1": [("2026-07-01", "new")], "c-2": [("2026-07-02", "new")]})

    assert report.total == 1
    assert report.unlabelled == 1


# ───────────────────────── 二、样本不足不判定（acceptance②）


def test_the_sample_size_line_is_the_one_s4_wrote() -> None:
    """S4 原话：≥90%（**50 簇**）。两个数都写死在度量器里。"""
    assert MIN_GOLD_CLUSTERS == 50
    assert EXIT_LINE == 0.90


def test_a_small_sample_is_not_judgeable() -> None:
    """acceptance②：不足 50 簇 → **不判定**，并说出「样本 N 不足 50」。"""
    report = measure(_labels(3), _actual(3))

    assert report.judgeable is False
    assert "3" in report.note
    assert "50" in report.note
    assert "不判定" in report.note


def test_a_small_sample_still_reports_the_number_it_computed() -> None:
    """不判定**不等于**不算：数字照给，只是不许拿它当出口判定。

    不给数字的话，人会自己去算一个——而那个算法没人看得见。
    """
    report = measure(_labels(3), _actual(3))

    assert report.accuracy == 1.0
    assert report.total == 3


def test_a_full_sample_is_judgeable() -> None:
    """阴性对照：够 50 簇就可判定——这道闸拦的是样本量，不是拦所有判定。"""
    report = measure(_labels(50), _actual(50))

    assert report.judgeable is True
    assert "不判定" not in report.note


def test_the_boundary_is_inclusive_of_fifty() -> None:
    """整整 50 簇就算够（S4 写的是「50 簇」，不是「超过 50」）。"""
    assert measure(_labels(49), _actual(49)).judgeable is False
    assert measure(_labels(50), _actual(50)).judgeable is True


def test_being_judgeable_is_not_the_same_as_passing() -> None:
    """够样本量 ≠ 达线：两件事分开报，NEVER 混成一个「通过」。"""
    labels = _labels(50)
    actual = _actual(50)
    for i in range(10):                       # 10 簇错 → 80%
        actual[f"c-{i}"] = [("2026-07-01", "merge")]

    report = measure(labels, actual)

    assert report.judgeable is True
    assert report.accuracy == pytest.approx(0.80)
    assert report.meets_line is False


# ───────────────────────── 三、恒 report_only（acceptance②）


def test_the_meter_never_exits_nonzero_even_when_below_the_line() -> None:
    """**恒 report_only**：即使 80% 也不退非零——判定归 owner（S4 未决项）。

    度量器一旦会判，它就变成了门；而这条线本身还没定。
    """
    from harness.lineage_accuracy import main

    labels_file = REPO_ROOT / "assets" / "labels.yaml"
    if not labels_file.exists():
        pytest.skip("assets/labels.yaml 不在盘上")

    assert main(["--labels", str(labels_file), "--offline"]) == 0


def test_the_module_has_no_nonzero_exit_at_all() -> None:
    """源码面：本模块里没有任何 `return 1` / `sys.exit(1)`。

    「恒 report_only」这句话要挡得住下一个人顺手加一句判定。
    """
    import inspect

    from harness import lineage_accuracy

    code = "\n".join(
        ln for ln in inspect.getsource(lineage_accuracy).split("\n")
        if not ln.strip().startswith("#")
    )

    assert "return 1" not in code
    assert "exit(1)" not in code


def test_the_render_says_report_only_out_loud() -> None:
    """报告里成句写着 report_only——字段要人去查，句子会被读到。"""
    text = render(measure(_labels(3), _actual(3)))

    assert "report_only" in text
    assert "不判定" in text


def test_the_render_names_the_mismatches() -> None:
    """失配要点名，否则「85%」这个数没法往下查。"""
    labels = [_label("c-1", ("2026-07-01", "new")), _label("c-2", ("2026-07-02", "new"))]
    actual = {"c-1": [("2026-07-01", "new")], "c-2": [("2026-07-02", "merge")]}

    text = render(measure(labels, actual))

    assert "c-2" in text


# ───────────────────────── 四、口径与既有评测器一致


def test_the_comparison_rule_is_the_same_as_the_existing_evaluator() -> None:
    """既有 `eval/lineage.py` 用的也是「整条序列相等」——两处 NEVER 分叉。

    分叉的后果：同一批数据两把尺子给出两个准确率，而谁都说不清哪个算数。
    """
    source = (REPO_ROOT / "eval" / "lineage.py").read_text(encoding="utf-8")

    assert "actual == expected" in source


def test_the_docstring_states_the_counting_rules() -> None:
    """acceptance③：口径写进 docstring——口径不写清，下次量出的数不可比。"""
    from harness import lineage_accuracy

    doc = lineage_accuracy.__doc__ or ""

    for token in ("全或无", "顺序", "分母", "50", "report_only"):
        assert token in doc, f"口径里少了：{token}"


def test_the_existing_evaluator_is_untouched() -> None:
    """`eval/lineage.py` 一个字没动——本卡加一把尺子，不改既有那把。"""
    source = (REPO_ROOT / "eval" / "lineage.py").read_text(encoding="utf-8")

    assert "BL-10" not in source


# ───────────────────────── 五、真跑一次（CLI 形态）


def test_the_cli_runs_on_the_repo_labels_offline() -> None:
    """拿仓里的 `assets/labels.yaml` 跑一遍（离线口径，不连库）。"""
    labels_file = REPO_ROOT / "assets" / "labels.yaml"
    if not labels_file.exists():
        pytest.skip("assets/labels.yaml 不在盘上")

    done = subprocess.run(
        [sys.executable, "harness/lineage_accuracy.py",
         "--labels", str(labels_file), "--offline"],
        cwd=REPO_ROOT, capture_output=True, text=True, encoding="utf-8",
        errors="replace", check=False,
    )

    assert done.returncode == 0, done.stdout + done.stderr
    assert "report_only" in done.stdout
