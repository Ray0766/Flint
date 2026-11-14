"""JUDGE-02：DeepSeek 与 Claude 的判官对齐检验。

## 这张卡真正的产品是分歧清单

一致率是一个数字；**分歧样本**才是信息：两个判官对同一段文字给出相反结论的地方，
就是判准写得不够清的地方。卡面原话：「比一致率这个数字有价值得多」。

## 一致率不达标 NEVER 停机（owner 2026-08-04）

降级链三级：① 拉第三票；② 三家里两家一致的采纳；③ 三家都不一致的**单独列清单**、
标 `needs_owner_review`、**继续跑**。三家全不可用时降级为「只用 DeepSeek +
全量标注未校准」——**照实标注、继续跑**，NEVER 假装校准过。

所以本模块的每一条路径都返回报告，**没有任何一条抛错终止**。

## 题库只读

`assets/heldout_questions.yaml` 是既有红线（owner 起草、NEVER 由工作 AI 修改）。
本卡有 sha256 断言守着它一个字节没动。
"""
from __future__ import annotations

import hashlib
import inspect
from decimal import Decimal
from pathlib import Path

from harness.judge_alignment import (
    AlignmentReport,
    JudgeItem,
    JudgeVote,
    align,
    build_judge_prompt,
    load_items,
    parse_verdict,
    resolve_votes,
)

REPO = Path(__file__).resolve().parents[2]
BANK = REPO / "assets" / "heldout_questions.yaml"
JUDGED = REPO / "assets" / "prod_caliber" / "unified_judge" / "claude-sonnet-5.json"
COMPOSED = REPO / "assets" / "prod_caliber" / "claude-sonnet-5.json"
DOC = REPO / "docs" / "判官对齐-v041.md"

def _item(qid: str = "q1", text: str = "本节写明了使用者是研究机构。",
          composition: str = "c1") -> JudgeItem:
    return JudgeItem(
        composition_id=composition, section_id="summary", question_id=qid,
        question="本节写明这个项目服务的具体使用者是谁？", section_text=text,
    )


# ───────────────────────── 一、样本从既有产物取（acceptance①）


def test_the_bank_is_untouched() -> None:
    """题库**一个字节没动**（既有红线：owner 起草，NEVER 由工作 AI 修改）。

    指纹对不上就是有人改过它——那比测试红更要紧，所以断言直接钉 sha256。
    """
    actual = hashlib.sha256(BANK.read_bytes()).hexdigest()

    assert len(actual) == 64
    assert actual == _recorded_bank_sha(), "题库被改过了"


def _recorded_bank_sha() -> str:
    """指纹存在 doc 里（人可读），不写死在测试里——写死两处就有两个真相。"""
    for line in DOC.read_text(encoding="utf-8").splitlines():
        if line.startswith("bank_sha256:"):
            return line.split(":", 1)[1].strip()
    raise AssertionError("依据文档里没有记题库指纹")


def test_items_carry_the_text_that_was_judged() -> None:
    """样本要带**被判的那段正文**——只带问题的话，第二个判官判的是另一件事。"""
    items = load_items(JUDGED, COMPOSED, limit=20)

    assert len(items) == 20
    for item in items:
        assert item.section_text.strip(), f"{item.question_id} 没有正文"
        assert item.question.strip()


def test_the_sample_size_is_in_the_range_the_card_names() -> None:
    """卡面要 50~200 条：太少不够说明问题，太多是拿额度换一个更精确的小数点。"""
    items = load_items(JUDGED, COMPOSED, limit=120)

    assert 50 <= len(items) <= 200


def test_the_same_question_in_two_compositions_is_two_items() -> None:
    """同一个 `question_id` 在 12 份组稿产物里各出现一次——**它们是 12 条样本**。

    只按 `question_id` 做键的话，12 条会互相覆盖成 1 条，而且覆盖是无声的：
    一致率照样算得出来，只是分母悄悄少了一个数量级。
    实测撞上过：120 条样本里 `generic/plan/q2` 出现了不止一次。
    """
    a = _item("generic/plan/q2", composition="golddoc-generic-plain")
    b = _item("generic/plan/q2", composition="golddoc-generic-rich")

    assert a.item_key != b.item_key


def test_the_loaded_items_have_unique_keys() -> None:
    """真样本里**没有重复键**——有重复就说明键选窄了。"""
    items = load_items(JUDGED, COMPOSED, limit=120)

    assert len({i.item_key for i in items}) == len(items)


def test_the_reference_verdicts_come_from_the_recorded_run() -> None:
    """Claude 侧那一票取自**既有录制的统一判官跑批**，不是重跑一遍。

    重跑一遍会花掉整个校准储备（那次跑批实录 $1.21），而额度是拿来买信息的。
    """
    items = load_items(JUDGED, COMPOSED, limit=20)

    assert all(item.reference is not None for item in items)


# ───────────────────────── 二、判词与解析


def test_the_prompt_asks_for_an_extraction_not_a_yes_no() -> None:
    """题库的原话：全部题面是**抽取式**，NEVER 用「是否…？」。

    判断句在内容缺失时可被判官以「答：否」判为已作答——语义歧义。
    所以判词也要求**把答案抽出来**，抽不出来才是未作答。
    """
    prompt = build_judge_prompt(_item())
    lower = prompt.lower()

    # 三条缺一不可。只判「有没有 extract 这个词」不行：把「抽不出来就算未作答」
    # 那半句删掉，`extract` 还在别处，断言毫无反应（变异考实测：25 条全绿）。
    assert "do not answer the question yourself" in lower, "没禁止判官自己作答"
    assert "extract" in lower, "没要求抽取原句"
    assert "did not answer" in lower, "没写「抽不出来就算未作答」"
    assert "answered" in prompt


def test_the_prompt_carries_the_section_text() -> None:
    """正文逐字进判词——摘要会让判官判的是摘要，不是产物。"""
    prompt = build_judge_prompt(_item(text="独特的正文串-XYZ"))

    assert "独特的正文串-XYZ" in prompt


def test_a_verdict_parses_into_a_bool_and_a_quote() -> None:
    """判词回来的是「答没答 + 抽到的那句」。抽到的那句是**可复核的证据**。"""
    vote = parse_verdict('{"answered": true, "answer": "服务对象是研究机构"}',
                         judge="deepseek")

    assert vote.answered is True
    assert "研究机构" in (vote.answer or "")


def test_an_unparseable_verdict_is_unavailable_not_false() -> None:
    """判词坏了记 `available=False`，**NEVER 记成「未作答」**。

    记成 false 的话，一次判官故障会被算进一致率，看起来像模型判得不一样。
    """
    vote = parse_verdict("not json", judge="deepseek")

    assert vote.available is False
    assert vote.answered is None


def test_answered_true_without_a_quote_is_refused() -> None:
    """说「答了」却抽不出原句 = 判官在猜。抽取式判定的全部意义就在这句上。"""
    vote = parse_verdict('{"answered": true, "answer": ""}', judge="deepseek")

    assert vote.available is False


# ───────────────────────── 三、一致率与分歧清单（acceptance①④）


def test_alignment_counts_agreements_and_lists_disagreements() -> None:
    """acceptance①：算一致率**并给出分歧样本清单**。"""
    items = [_item("q1"), _item("q2"), _item("q3")]
    a = {i.item_key: v for i, v in zip(items, (True, True, False), strict=True)}
    b = {i.item_key: v for i, v in zip(items, (True, False, False), strict=True)}

    report = align(items, a, b)

    assert report.compared == 3
    assert report.agreed == 2
    assert [d.question_id for d in report.disagreements] == ["q2"]


def test_the_disagreement_carries_both_sides() -> None:
    """分歧清单要写**两边各判了什么**——只说「有分歧」没法拿去改判准。"""
    items = [_item("q1")]

    report = align(items, {items[0].item_key: True}, {items[0].item_key: False})

    entry = report.disagreements[0]
    assert entry.left is True and entry.right is False
    assert entry.question and entry.section_text


def test_an_item_only_one_side_judged_is_not_counted_as_agreement() -> None:
    """一边没判的条目**不进一致率的分母**，也不算一致。

    算进去的话，判官挂掉越多、一致率看起来越好。
    """
    items = [_item("q1"), _item("q2")]

    report = align(items, {items[0].item_key: True},
                   {items[0].item_key: True, items[1].item_key: False})

    assert report.compared == 1
    assert report.skipped == 1


def test_an_empty_comparison_reports_zero_not_one() -> None:
    """一条都没比成时一致率记 0 并标不可判——**NEVER 记 1.0**。

    0 条里 0 条不一致，数学上是 1.0，而那正是最没有意义的 1.0。
    """
    report = align([], {}, {})

    assert report.rate == 0.0
    assert report.judgeable is False


# ───────────────────────── 四、降级链：不达标 NEVER 停机（acceptance③⑤）


def test_two_of_three_wins() -> None:
    """降级链②：三家里两家一致的采纳。"""
    resolved = resolve_votes([
        JudgeVote(judge="deepseek", answered=True, answer="x"),
        JudgeVote(judge="claude", answered=False, answer=None),
        JudgeVote(judge="gpt", answered=True, answer="x"),
    ])

    assert resolved.answered is True
    assert resolved.needs_owner_review is False


def test_all_three_disagreeing_goes_to_the_owner_list_and_keeps_running() -> None:
    """降级链③：三家都不一致 → 标 `needs_owner_review` **并继续**。

    这里 NEVER 抛错：连跑不能因为判官吵架就停住（owner 2026-08-04）。
    """
    resolved = resolve_votes([
        JudgeVote(judge="deepseek", answered=True, answer="x"),
        JudgeVote(judge="claude", answered=False, answer=None),
    ])

    assert resolved.needs_owner_review is True
    assert resolved.answered is None


def test_a_single_available_judge_is_marked_uncalibrated() -> None:
    """acceptance⑤：只剩一家时**照实标注未校准**，NEVER 假装校准过。"""
    resolved = resolve_votes([
        JudgeVote(judge="deepseek", answered=True, answer="x"),
        JudgeVote(judge="claude", answered=None, answer=None, available=False),
    ])

    assert resolved.answered is True
    assert resolved.calibrated is False


def test_two_agreeing_judges_are_calibrated() -> None:
    """阴性对照：两家一致时**是**校准过的——否则这个标记永远是 False，等于没有。"""
    resolved = resolve_votes([
        JudgeVote(judge="deepseek", answered=True, answer="x"),
        JudgeVote(judge="claude", answered=True, answer="y"),
    ])

    assert resolved.calibrated is True
    assert resolved.needs_owner_review is False


def test_no_judge_at_all_is_still_not_an_exception() -> None:
    """全不可用也只是一份「什么都没判」的结果——**连跑不停机**。"""
    resolved = resolve_votes([])

    assert resolved.answered is None
    assert resolved.calibrated is False
    assert resolved.needs_owner_review is True


def test_the_module_never_raises_to_stop_the_run() -> None:
    """判据钉在**代码面**：本模块没有任何 `raise` 用来中止连跑。

    只留解析层的返回值（`available=False`）与清单标记——
    抛错就等于「判官吵架 = 停机」，而那正是 owner 2026-08-04 禁掉的。
    """
    import ast

    from harness import judge_alignment

    tree = ast.parse(inspect.getsource(judge_alignment))
    raises = [n for n in ast.walk(tree) if isinstance(n, ast.Raise)]

    assert raises == [], f"模块里有 raise（第 {[n.lineno for n in raises]} 行）"


# ───────────────────────── 五、依据文档（acceptance②④）


def test_the_document_records_the_actual_spend() -> None:
    """acceptance②：Claude 侧实际花费**记进 trace 与文档**，且在 $1 以内。"""
    doc = DOC.read_text(encoding="utf-8")

    assert "claude_spend_usd:" in doc
    spend = Decimal(next(
        line.split(":", 1)[1].strip()
        for line in doc.splitlines() if line.startswith("claude_spend_usd:")
    ))
    assert spend <= Decimal("1.0"), f"超出校准储备：${spend}"


def test_the_document_lists_the_disagreements() -> None:
    """acceptance④：**分歧清单是本卡真正的产品**，它要在文档里逐条列出来。"""
    doc = DOC.read_text(encoding="utf-8")

    assert "## 分歧清单" in doc
    rows = [ln for ln in doc.splitlines() if ln.startswith("| `")]
    assert rows, "分歧清单是空的——那要么是没跑，要么是没记"


def test_the_document_says_what_the_third_judge_did() -> None:
    """第三票（GPT-5.6）用没用上、为什么，要写清楚。

    不写的话，读的人无从判断这次对齐是两票还是三票的结论。
    """
    lines = DOC.read_text(encoding="utf-8").splitlines()
    # 判据钉在**有没有这一节**上，不是「全文提到过第三票」：
    # 把小标题改掉、内容散在别处时，按词判照样绿（变异考实测：25 条全绿），
    # 而读的人就再也找不到这件事写在哪。
    heads = [i for i, ln in enumerate(lines) if ln.startswith("## ") and "第三票" in ln]

    assert heads, "文档里没有专讲第三票的那一节"
    end = next((i for i, ln in enumerate(lines[heads[0] + 1:], heads[0] + 1)
                if ln.startswith("## ")), len(lines))
    section = "\n".join(lines[heads[0]:end]).lower()
    assert "gpt" in section, "那一节没点名第三票是谁"
    assert "不可用" in section or "用上" in section, "没说第三票到底用没用上"


def test_the_alignment_report_is_a_dataclass_not_a_dict() -> None:
    """报告是有形状的值：dict 会让下游各取各的键，拼错了也不报错。"""
    assert AlignmentReport.__dataclass_fields__  # type: ignore[attr-defined]
