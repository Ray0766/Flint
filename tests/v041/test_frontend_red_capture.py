"""FIX-08 / FIX-15：那次没抓到名字的前端红。

**两张卡共用这一个文件**（`FIX-15` 是第三轮尝试，`verify_cmd` 指向同一处）。
判据因此按「每一轮都要成立的性质」写，而不是按某一轮的取值写——
按轮次写的话，上一轮的观测会随着那张卡的收工失去看守。

## 单子说的是什么

`docs/blocked/ONE-UNNAMED-FRONTEND-RED-NOT-CAPTURED.md`：
一次 `npm test -- --run` 红了，而当时的命令**只 grep 了汇总行**，
把用例名过滤掉了。于是那次红只剩下「1 failed」四个字——
不知道是哪个文件、哪条用例，也无从判断它与 `FIX-04` 修掉的那处是不是同一个。

## 本卡做三件

1. **按单子给的办法连跑 30 次，并把失败用例名留下来**；
2. 抓到就修并给根因；**30 次全绿则在单子里写明「30 次未复现」并保留单据开着**
   ——`NEVER 关单`：连跑 6 次全绿不能证明它不存在，
   `FIX-04` 那处是 **40 次里第 29 次**才复现的；
3. 把「连跑保留用例名」**固化成脚本**（`web/scripts/repeat-tests.mjs`），
   NEVER 让下一个人再丢一次现场。

## 判据判什么

- 脚本真的会**抓名字**（不是只抓汇总行）——用一段真实的 vitest 输出喂给它验；
- 连跑产物在，且**每一次红都带用例名**（名字为空 = 工具没抓住现场，那本身是缺陷）；
- 单据仍然**开着**，且写进了这一轮的观测次数。
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "web" / "scripts" / "repeat-tests.mjs"
ARTIFACT = REPO / ".ui-probe" / "frontend-red.json"
SHEET = REPO / "docs" / "blocked" / "ONE-UNNAMED-FRONTEND-RED-NOT-CAPTURED.md"
RUNBOOK = REPO / "docs" / "间歇红-连跑取证.md"

# 单子给的目标次数。**NEVER 调小**：调小之后「未复现」这句话的分量就变了。
REQUIRED_RUNS = 30


def _artifact() -> dict[str, object]:
    if not ARTIFACT.exists():
        pytest.skip(
            f"没有连跑产物：{ARTIFACT}——"
            f"跑法 node web/scripts/repeat-tests.mjs --runs {REQUIRED_RUNS}")
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


# ───────────────────────── 一、脚本真的会抓名字


def test_the_script_exists_and_is_the_one_the_sheet_asked_for() -> None:
    assert SCRIPT.exists(), "「连跑保留用例名」没有固化成脚本"
    source = SCRIPT.read_text(encoding="utf-8")

    assert "--reporter=verbose" in source, "没用 verbose，抓不到逐条用例"
    assert "NEVER 只 grep 汇总行" in source, "没写清这个脚本的由来"


def test_the_script_captures_names_not_just_the_summary_line() -> None:
    """**阴性对照**：喂一段真实形状的 vitest 输出，它必须抽出用例名。

    没有这一条，「30 次全绿」可能只是因为脚本根本不会抓名字——
    而那正是这张单子的由来。
    """
    node = shutil.which("node")
    if node is None:
        pytest.skip("本机没有 node")

    sample = (
        "     × 广场→点簇→工作台+combo→主题→选主题→Gate（路由到进度页） 1133ms\n"
        " FAIL  components/DemoFlow.test.tsx > DemoFlow 端到端可点击流\n"
        " Test Files  1 failed | 73 passed (74)\n"
        "      Tests  1 failed | 753 passed (754)\n"
    )
    probe = (
        "import {readFileSync} from 'node:fs';"
        f"const src = readFileSync({json.dumps(str(SCRIPT))}, 'utf8');"
        "const body = src.slice(src.indexOf('function failedNames'));"
        "const fn = new Function('text', body.slice(body.indexOf('{') + 1,"
        " body.indexOf('\\n}')) );"
        f"console.log(JSON.stringify(fn({json.dumps(sample)})));"
    )
    done = subprocess.run(
        [node, "--input-type=module", "-e", probe],
        capture_output=True, text=True, encoding="utf-8", cwd=REPO, check=False)

    assert done.returncode == 0, done.stderr[-400:]
    names = json.loads(done.stdout.strip().splitlines()[-1])
    assert any("广场→点簇" in n for n in names), f"没抓到行内失败用例名：{names}"
    assert any("DemoFlow" in n for n in names), f"没抓到汇总段的文件名：{names}"


def test_the_script_is_evidence_not_a_gate() -> None:
    """它恒退出 0。取证工具自己判红的话，「没复现」与「工具挂了」会长得一样。"""
    source = SCRIPT.read_text(encoding="utf-8")

    assert "退出码恒 0" in source
    assert "process.exit(1)" not in source


# ───────────────────────── 二、这一轮真的跑够了次数


def test_the_run_actually_happened_the_required_number_of_times() -> None:
    report = _artifact()

    assert report["runs"] >= REQUIRED_RUNS, (
        f"只跑了 {report['runs']} 次，单子要的是 {REQUIRED_RUNS} 次"
    )
    assert len(report["detail"]) == report["runs"]


def test_every_red_run_carries_its_test_names() -> None:
    """**名字为空 = 工具没抓住现场**，那本身就是缺陷（这张单子的由来）。"""
    report = _artifact()

    for row in report["detail"]:
        if row["green"]:
            continue
        assert row["failed"], f"第 {row['run']} 次红了却没留下用例名"


def test_each_run_recorded_its_summary_line() -> None:
    """汇总行是**给人核对的**那一条，与用例名互为佐证。"""
    report = _artifact()

    counted = [row for row in report["detail"] if row["summary"]]
    assert len(counted) == report["runs"], "有跑次没记下汇总行"


# ───────────────────────── 三、单据的处置：NEVER 关单


def test_the_sheet_is_still_open() -> None:
    """30 次全绿**不能证明它不存在**。

    `FIX-04` 那处是 40 次里第 29 次才复现的——那张 trace 逐字记着这件事。
    所以本卡 NEVER 关这张单，只把观测写进去。
    """
    head = SHEET.read_text(encoding="utf-8").splitlines()[:6]
    state = next((ln for ln in head if ln.startswith("**状态**")), "")

    assert state.startswith("**状态** open"), f"单据被关掉了：{state!r}"


def test_the_sheet_records_this_rounds_observation() -> None:
    """观测要写进单子——**只跑不记等于没跑**：下一个人看不到你跑过。"""
    text = SHEET.read_text(encoding="utf-8")
    report = _artifact()

    assert "FIX-08" in text, "第二轮（FIX-08）的观测记录不见了"
    assert "FIX-15" in text, "第三轮（FIX-15）的观测没写进单子"
    assert re.search(rf"{report['runs']}\s*次", text), (
        f"单子里没写这一轮跑了 {report['runs']} 次"
    )
    assert "NEVER 关单" in text or "保留单据" in text


def test_the_conclusion_matches_the_evidence() -> None:
    """单子里的结论与产物**逐字对得上**：红了就要有名字，全绿就要说「未复现」。

    对不上的话，单子会变成一份与事实无关的记录——而那比不记更坏。
    """
    text = SHEET.read_text(encoding="utf-8")
    report = _artifact()

    if report["reds"]:
        assert report["names"], "红了却没有名字"
        for name in report["names"][:1]:
            assert name.split(">")[-1].strip()[:8] in text, (
                f"抓到了 {name} 却没写进单子"
            )
    else:
        assert "未复现" in text, "全绿了却没写明「未复现」"


# ───────────────────────── FIX-15（第三轮）：写进 docs，不只写进单子


def test_the_runbook_lives_in_docs_not_only_in_the_ticket() -> None:
    """连跑办法**写进 `docs/`**（`FIX-15` acceptance③）。

    单子与 trace 里写过的东西**读的人不一定会翻到**——
    `docs/blocked/` 是「出了什么事」的地方，不是「该怎么做」的地方。
    下一个人遇到一次间歇红时，他会去 `docs/` 找，而不是去翻已关的单据。
    """
    assert RUNBOOK.exists(), "连跑办法没有进 docs/"
    text = RUNBOOK.read_text(encoding="utf-8")

    assert "repeat-tests.mjs" in text, "没写跑法"
    assert "--reporter=verbose" in text or "verbose" in text
    assert "第 29 次" in text, "没写清「绿多少次都不等于不存在」的那个实测依据"


def test_the_runbook_keeps_a_table_of_every_round() -> None:
    """历次观测在**一张表**里。

    散在三处单据段落里的话，「一共跑过多少次」这个问题要翻三个地方——
    而那正是判断「还要不要接着跑」的唯一依据。
    """
    text = RUNBOOK.read_text(encoding="utf-8")

    for round_card in ("FIX-05", "FIX-08", "FIX-15"):
        assert round_card in text, f"历次观测表里缺 {round_card}"
    assert "802" in text and "831" in text, "没记下每一轮的用例数（树变过）"


def test_this_rounds_run_is_bigger_than_the_last_one() -> None:
    """本轮的树**比上一轮大**——这是「新证据而不是重复一遍」的机器形态。

    同一棵树上再跑 30 次，只是把同一件事又做了一遍。
    本批新增了判据文件（802 → 831），且 `globals.css` 又改过——
    而第一次那条红正是在 `globals.css` 被反复改写时出现的。
    """
    report = _artifact()
    summaries = {row["summary"] for row in report["detail"]}

    assert len(summaries) == 1, f"30 次的用例数不一致，树在跑的过程中变了：{summaries}"
    count = int(re.search(r"(\d+) passed", next(iter(summaries))).group(1))
    assert count >= 831, f"本轮只跑了 {count} 条用例——比上一轮（802）没多"


def test_the_ticket_is_still_open_after_three_rounds() -> None:
    """三轮之后**仍然开着**，且写明为什么。

    三轮合计 60 次全绿，**仍然低于 `FIX-04` 那次的复现门槛（第 29 次 / 40 次循环）**。
    「跑不出来」与「不存在」不是一回事。
    """
    text = SHEET.read_text(encoding="utf-8")
    state = next(ln for ln in text.splitlines()[:6] if ln.startswith("**状态**"))

    assert state.startswith("**状态** open"), f"三轮全绿就把单子关了：{state!r}"
    assert "第三轮" in text
    assert "60 次" in text or "合计 60" in text, "没算出三轮合计跑了多少次"
