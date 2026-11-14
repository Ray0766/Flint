"""JUDGE-03：用 DeepSeek 重判旧基线，得一套自洽可比的新基线。

## 换判官会让旧数不可横比

M4 出口报告 §6.2 那三个数（0.434 / 0.395 / 0.357）是**统一判官 claude-sonnet-5**
判出来的。换成 DeepSeek 之后，三家的相对高低仍可比（同一个判官判的），
但**新数与旧数之间不可比**——判官换了，尺子就换了。

所以本卡做两件事，缺一不可：

1. 用 DeepSeek 把三家**现成产出**重判一遍（**只重判、不重跑组稿**：
   重跑组稿就等于连被判的东西也换了，那时连「三家相对高低」都不成立了）；
2. **旧的三个数原样保留作历史**：新产物落**另一个目录**，旧文件一个字节不动，
   文档里两套数**分节写**，NEVER 放进同一张表。

## 为什么「放进同一张表」是本卡最要防的事

一张表里并排两列数字，读的人**一定**会做差。而那个差是判官换掉造成的，
不是模型变好或变坏。写清楚「不可比」四个字挡不住这件事——**分开放**才挡得住。
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
OLD_DIR = REPO / "assets" / "prod_caliber" / "unified_judge"
NEW_DIR = REPO / "assets" / "prod_caliber" / "deepseek_judge"
DOC = REPO / "docs" / "新基线-v041.md"

MODELS = ("claude-sonnet-5", "gemma4_31b", "qwen3.6_27b")
# 旧基线的三个数（M4 出口报告 §6.2，判官 claude-sonnet-5）。**历史，NEVER 覆盖。**
OLD_RATES = {"claude-sonnet-5": 0.434, "gemma4_31b": 0.395, "qwen3.6_27b": 0.357}


def _new(model: str) -> dict:
    return json.loads((NEW_DIR / f"{model}.json").read_text(encoding="utf-8"))


def _old(model: str) -> dict:
    return json.loads((OLD_DIR / f"{model}.json").read_text(encoding="utf-8"))


# ───────────────────────── 一、只重判，不重跑组稿（acceptance①）


@pytest.mark.parametrize("model", MODELS)
def test_there_is_a_new_judgement_for_every_model(model: str) -> None:
    """三家都要有新判定——少一家就没法在新尺子下排序。"""
    payload = _new(model)

    assert payload["judge_model"], f"{model} 没记判官是谁"
    assert payload["questions"] > 0
    assert len(payload["records"]) == payload["questions"]


@pytest.mark.parametrize("model", MODELS)
def test_the_new_run_judged_the_same_items_as_the_old_one(model: str) -> None:
    """acceptance①：**只重判**——被判的样本与旧跑批逐条对得上。

    样本变了的话，「三家相对高低」这件事本身就不成立了：
    分数差可能来自被判的东西不同，而不是判官不同。
    """
    old_keys = {
        (r["composition_id"], r["section_id"], r["question_id"])
        for r in _old(model)["records"]
    }
    new_keys = {
        (r["composition_id"], r["section_id"], r["question_id"])
        for r in _new(model)["records"]
    }

    assert new_keys == old_keys, f"{model} 新旧判的不是同一批样本"


@pytest.mark.parametrize("model", MODELS)
def test_the_compositions_were_not_regenerated(model: str) -> None:
    """组稿产物**一个字节没动**：本卡只换判官，不重跑组稿。

    指纹记在新产物里，与盘上现算的对比——对不上就是有人重跑过组稿。
    """
    source = REPO / "assets" / "prod_caliber" / f"{model}.json"
    actual = hashlib.sha256(source.read_bytes()).hexdigest()

    assert _new(model)["source_sha256"] == actual, f"{model} 的组稿产物被改过"


@pytest.mark.parametrize("model", MODELS)
def test_every_record_carries_its_evidence(model: str) -> None:
    """判「答了」的条目要带**抽到的原句**——那是可复核的证据。

    没有原句的 `answered: true` 与判官猜的没有区别（JUDGE-02 同一条口径）。
    """
    for record in _new(model)["records"]:
        if record["answered"]:
            assert str(record.get("answer") or "").strip(), (
                f"{model} 的 {record['question_id']} 判了答但没抽出原句")


@pytest.mark.parametrize("model", MODELS)
def test_unavailable_verdicts_are_not_counted_as_unanswered(model: str) -> None:
    """判词坏掉的条目单独记，**不计入分母**——否则判官故障会压低作答率。"""
    payload = _new(model)
    unavailable = sum(1 for r in payload["records"] if r["answered"] is None)

    assert payload["unavailable"] == unavailable, "坏掉的条数没单独记"
    assert payload["judged"] == len(payload["records"]) - unavailable
    # 分母是 `judged` 不是 `questions`：拿总条数做分母的话，
    # 判词坏一条就等于白判一条，作答率被无声压低
    assert payload["rate"] == pytest.approx(payload["answered_count"] / payload["judged"])


# ───────────────────────── 二、旧数原样保留（acceptance②）


@pytest.mark.parametrize("model", MODELS)
def test_the_old_numbers_are_still_there(model: str) -> None:
    """acceptance②：旧的三个数**原样保留作历史**，NEVER 被覆盖。"""
    payload = _old(model)

    assert payload["judge_model"] == "claude-sonnet-5"
    assert payload["rate"] == pytest.approx(OLD_RATES[model], abs=0.001)


def test_the_new_artifacts_live_in_their_own_directory() -> None:
    """新产物落**另一个目录**：同目录同名会让「哪份是新的」变成一个要问的问题。"""
    assert NEW_DIR != OLD_DIR
    assert NEW_DIR.is_dir()
    assert {p.name for p in NEW_DIR.glob("*.json")} >= {f"{m}.json" for m in MODELS}


def test_the_old_directory_gained_nothing() -> None:
    """旧目录里**没有多出**新判官的文件——混在一起就分不清哪份是哪把尺子判的。"""
    for path in OLD_DIR.glob("*.json"):
        assert json.loads(path.read_text(encoding="utf-8"))["judge_model"] == "claude-sonnet-5"


# ───────────────────────── 三、两套数分开放（acceptance②③）


def test_the_document_keeps_the_two_baselines_in_separate_sections() -> None:
    """**分节写**。一张表里并排两列数字，读的人一定会做差——

    而那个差是判官换掉造成的，不是模型变好或变坏。
    写清楚「不可比」四个字挡不住这件事，分开放才挡得住。
    """
    doc = DOC.read_text(encoding="utf-8")

    assert "## 新基线" in doc
    assert "## 旧基线" in doc


def test_no_single_table_row_holds_both_baselines() -> None:
    """判据钉在**表格行**上：没有任何一行同时出现新旧两套数。

    只判「文档里两套数都在」没用——两套数当然都要在，问题是它们在不在同一行。
    """
    rows = [ln for ln in DOC.read_text(encoding="utf-8").splitlines()
            if ln.startswith("|")]
    old_marks = {f"{v:.3f}"[:5] for v in OLD_RATES.values()}

    for row in rows:
        numbers = set(re.findall(r"0\.\d{3}", row))
        if numbers & old_marks and numbers - old_marks:
            raise AssertionError(f"这一行把新旧两套数放在一起了：{row}")


def test_the_document_says_who_judged_and_when() -> None:
    """acceptance③：判官是谁、什么时候判的、题库版本——三样都要写。

    少任何一样，这套数半年后就没法解释：读的人不知道它是哪把尺子量的。
    """
    doc = DOC.read_text(encoding="utf-8")

    assert "judge_model:" in doc
    assert "judged_at:" in doc
    assert "bank_version:" in doc


def test_the_document_explains_why_the_two_are_not_comparable() -> None:
    """为什么不可横比要**说清机制**，不是丢一句「不可比」。

    判据落在**那一节里**：按全文判的话，「判官」「尺子」这两个词在别处也有，
    把讲机制的那句删掉照样绿（变异考实测：28 条全过）。
    """
    lines = DOC.read_text(encoding="utf-8").splitlines()
    heads = [i for i, ln in enumerate(lines) if ln.startswith("## ") and "不可横比" in ln]

    assert heads, "没有专讲「为什么不可横比」的那一节"
    end = next((i for i, ln in enumerate(lines[heads[0] + 1:], heads[0] + 1)
                if ln.startswith("## ")), len(lines))
    section = "\n".join(lines[heads[0]:end])

    assert "判官" in section and "尺子" in section, "那一节没说清换判官等于换尺子"
    assert "只重判" in section or "一个字没改" in section, (
        "那一节没说清产物本身没变——不写这句，读的人会以为分数差是产物变了"
    )


def test_the_document_records_the_cost() -> None:
    """acceptance④：成本记进文档与 trace，且在预算内。"""
    doc = DOC.read_text(encoding="utf-8")
    line = next(ln for ln in doc.splitlines() if ln.startswith("deepseek_spend_usd:"))

    assert float(line.split(":", 1)[1]) < 1.0


# ───────────────────────── 四、新基线自己站得住


def test_the_three_new_rates_are_all_present_and_in_range() -> None:
    """三家的新作答率都在 [0,1] 内，且**互不相同**。

    三个数一模一样时要么是判官没在判，要么是产物被搞混了——
    那种「整齐」是故障的样子，不是结果的样子。
    """
    rates = {m: _new(m)["rate"] for m in MODELS}

    assert all(0.0 <= r <= 1.0 for r in rates.values())
    assert len(set(rates.values())) == len(rates), f"三家判出同一个数：{rates}"


def test_the_new_baseline_is_internally_comparable() -> None:
    """新基线**内部可比**：三家是同一个判官、同一版题库判的。"""
    judges = {_new(m)["judge_model"] for m in MODELS}
    banks = {_new(m)["bank_version"] for m in MODELS}

    assert len(judges) == 1, f"三家不是同一个判官判的：{judges}"
    assert len(banks) == 1, f"三家用的题库版本不同：{banks}"


def test_the_ranking_is_stated_not_left_to_the_reader() -> None:
    """新尺子下的**排序**要在文档里写成一行，且与实测数据一致。

    判据要求**同一行**里按顺序出现三家：按词判（「文档里有『排序』二字」）
    的话，删掉那行照样绿——而「排序」这两个字在别处也有
    （变异考实测：28 条全过）。
    """
    doc = DOC.read_text(encoding="utf-8")
    ranked = [m.replace("_", ".").replace("qwen3.6.27b", "qwen3.6:27b")
              .replace("gemma4.31b", "gemma4:31b")
              for m in sorted(MODELS, key=lambda m: -_new(m)["rate"])]

    lines = doc.splitlines()

    def _states_order(line: str) -> bool:
        return all(name in line for name in ranked) and ">" in line

    # 至少有一行在**新基线那一节里**：全文找的话，
    # 「旧基线」那节引用 M4 出口报告的排名那句也含三个名字与 `>`，
    # 把新基线的排序整句删掉照样绿（变异考实测：28 条全过）。本仓第十七次同型。
    head = next(i for i, ln in enumerate(lines) if ln.startswith("## 新基线"))
    end = next((i for i, ln in enumerate(lines[head + 1:], head + 1)
                if ln.startswith("## ")), len(lines))
    assert any(_states_order(ln) for ln in lines[head:end]), (
        f"新基线那一节里没有把排序写成一行：期望顺序 {ranked}")

    stated = [ln for ln in lines if _states_order(ln)]
    # **每一行都要对**，不是第一行对就行：文档里不止一处写了排序
    # （摘要一处、结果表下一处），只判第一行的话，另一行写反了也不会红
    # （变异考实测：把第二处写反，28 条全过）。两处互相矛盾比没写更糟。
    for line in stated:
        positions = [line.index(name) for name in ranked]
        assert positions == sorted(positions), f"这一行的顺序与实测不一致：{line}"
