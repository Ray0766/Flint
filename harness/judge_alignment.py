"""JUDGE-02：DeepSeek 与 Claude 的判官对齐检验。

## 本模块的产品是分歧清单

一致率是一个数字；**分歧样本**才是信息：两个判官对同一段文字给出相反结论的地方，
就是判准写得不够清的地方。

## 每条路径都返回报告，没有一条抛错

owner 2026-08-04：连跑不能因为一致率不达标而停住。降级链：

1. 两家不一致 → 拉第三票；
2. 三家里两家一致 → 采纳那两家；
3. 都不一致 → 标 `needs_owner_review`，进分歧清单，**继续跑**；
4. 只剩一家（别家不可用）→ 用它，但 `calibrated=False`——
   **照实标注未校准**，NEVER 假装校准过。

所以本模块**一个 `raise` 都没有**（有断言按 AST 守着）：判官吵架、判词解析失败、
一条都没比成，全部表达成返回值。

## Claude 那一票取自既有录制

统一判官那次跑批（`assets/prod_caliber/unified_judge/claude-sonnet-5.json`）
实录花费 $1.214648。重跑一遍会把整个校准储备花光，而额度是**拿来买信息**的——
所以新花的钱只用在分歧样本上。

## 题库只读

`assets/heldout_questions.yaml` 是既有红线（owner 起草、NEVER 由工作 AI 修改）。
本模块只读它的指纹，一个字节不写。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
BANK: Final[Path] = REPO_ROOT / "assets" / "heldout_questions.yaml"
JUDGED: Final[Path] = REPO_ROOT / "assets" / "prod_caliber" / "unified_judge" / "claude-sonnet-5.json"
COMPOSED: Final[Path] = REPO_ROOT / "assets" / "prod_caliber" / "claude-sonnet-5.json"
DOC: Final[Path] = REPO_ROOT / "docs" / "判官对齐-v041.md"

JUDGE_PURPOSE: Final[str] = "judge_alignment"


@dataclass(frozen=True)
class JudgeItem:
    """一条待判样本：**问题 + 被判的那段正文**。

    只带问题的话，第二个判官判的是另一件事——而那种「不一致」不是判准的问题。
    """

    composition_id: str
    section_id: str
    question_id: str
    question: str
    section_text: str
    reference: bool | None = None

    @property
    def item_key(self) -> str:
        """样本的唯一键。**question_id 单独用不行**：同一个 question_id 会出现在
        12 份组稿产物里（题库按 (template, section) 出题，每份产物都答一遍）。
        只按它做键，12 条会互相覆盖成 1 条——而且覆盖是无声的。
        """
        return f"{self.composition_id}/{self.section_id}/{self.question_id}"


@dataclass(frozen=True)
class JudgeVote:
    """一票。`available=False` 表示**这一票没投出来**（判词坏了 / 服务不可达），

    与「判为未作答」严格分开：混起来的话，一次判官故障会被算成模型判得不一样。
    """

    judge: str
    answered: bool | None
    answer: str | None
    available: bool = True


@dataclass(frozen=True)
class Resolved:
    answered: bool | None
    calibrated: bool
    needs_owner_review: bool
    votes: tuple[JudgeVote, ...] = ()


@dataclass(frozen=True)
class Disagreement:
    question_id: str
    composition_id: str
    section_id: str
    question: str
    section_text: str
    left: bool
    right: bool


@dataclass(frozen=True)
class AlignmentReport:
    compared: int
    agreed: int
    skipped: int
    disagreements: list[Disagreement] = field(default_factory=list)

    @property
    def rate(self) -> float:
        # 0 条里 0 条不一致数学上是 1.0，而那正是最没有意义的 1.0
        return self.agreed / self.compared if self.compared else 0.0

    @property
    def judgeable(self) -> bool:
        return self.compared > 0


def load_items(
    judged: Path = JUDGED, composed: Path = COMPOSED, *, limit: int = 120
) -> list[JudgeItem]:
    """从既有录制里重建样本（问题 + 正文 + Claude 那一票）。

    正文从组稿产物里按 `(composition_id, section_id)` 取——判官当初判的就是它。
    """
    records = json.loads(judged.read_text(encoding="utf-8"))["records"]
    sections = json.loads(composed.read_text(encoding="utf-8"))["compositions"]
    items: list[JudgeItem] = []
    for record in records:
        composition = sections.get(record["composition_id"], {})
        text = (composition.get("sections") or {}).get(record["section_id"], "")
        if not str(text).strip():
            continue
        items.append(JudgeItem(
            composition_id=record["composition_id"], section_id=record["section_id"],
            question_id=record["question_id"], question=record["question"],
            section_text=str(text), reference=bool(record["answered"]),
        ))
        if len(items) >= limit:
            break
    return items


def build_judge_prompt(item: JudgeItem) -> str:
    """判词：**抽取式**——把答案抽出来，抽不出来才算未作答。

    题库的原话：判断句（「是否…？」）在内容缺失时可被判官以「答：否」判为已作答，
    语义歧义；抽取式在内容缺失时必然 `answered=false`，判定面干净。
    """
    return (
        "You are judging whether a document section answers a specific question.\n"
        "Do NOT answer the question yourself. **extract** the sentence from the "
        "section that answers it. If no sentence in the section answers it, "
        "the section did not answer the question.\n\n"
        f"Question: {item.question}\n\n"
        f"Section:\n{item.section_text}\n\n"
        'Reply with JSON only: {"answered": true|false, "answer": "the extracted '
        'sentence, verbatim from the section; empty string if answered is false"}'
    )


def parse_verdict(payload: str, *, judge: str) -> JudgeVote:
    """解析一票。**坏了记 `available=False`**，NEVER 记成「未作答」。"""
    text = payload.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        data = json.loads(text)
    except ValueError:
        return JudgeVote(judge=judge, answered=None, answer=None, available=False)
    if not isinstance(data, dict) or not isinstance(data.get("answered"), bool):
        return JudgeVote(judge=judge, answered=None, answer=None, available=False)
    answered = bool(data["answered"])
    answer = str(data.get("answer") or "").strip()
    if answered and not answer:
        # 说「答了」却抽不出原句 = 判官在猜。抽取式判定的全部意义就在这句上。
        return JudgeVote(judge=judge, answered=None, answer=None, available=False)
    return JudgeVote(judge=judge, answered=answered, answer=answer or None)


def resolve_votes(votes: list[JudgeVote]) -> Resolved:
    """降级链（见模块 docstring）。**任何输入都返回一份结果**。"""
    live = [v for v in votes if v.available and v.answered is not None]
    if not live:
        return Resolved(answered=None, calibrated=False, needs_owner_review=True,
                        votes=tuple(votes))
    if len(live) == 1:
        # 只剩一家：用它，但照实标未校准
        return Resolved(answered=live[0].answered, calibrated=False,
                        needs_owner_review=False, votes=tuple(votes))
    yes = sum(1 for v in live if v.answered)
    no = len(live) - yes
    if yes == no:
        # 打平（两家对吵、或三家里恰好一半）：进 owner 清单，**继续跑**
        return Resolved(answered=None, calibrated=False, needs_owner_review=True,
                        votes=tuple(votes))
    return Resolved(answered=yes > no, calibrated=True, needs_owner_review=False,
                    votes=tuple(votes))


def align(
    items: list[JudgeItem], left: dict[str, bool], right: dict[str, bool]
) -> AlignmentReport:
    """两侧判定的一致率 + 分歧清单。

    **一边没判的条目不进分母**：算进去的话，判官挂掉越多、一致率看起来越好。
    """
    agreed = 0
    compared = 0
    skipped = 0
    disagreements: list[Disagreement] = []
    for item in items:
        a = left.get(item.item_key)
        b = right.get(item.item_key)
        if a is None or b is None:
            skipped += 1
            continue
        compared += 1
        if a == b:
            agreed += 1
            continue
        disagreements.append(Disagreement(
            question_id=item.question_id, composition_id=item.composition_id,
            section_id=item.section_id, question=item.question,
            section_text=item.section_text, left=a, right=b,
        ))
    return AlignmentReport(compared=compared, agreed=agreed, skipped=skipped,
                           disagreements=disagreements)


def judge_all(provider: Any, items: list[JudgeItem]) -> dict[str, JudgeVote]:
    """让一个 provider 判完一批。**判词坏了不中断**——那一条记 `available=False`。"""
    votes: dict[str, JudgeVote] = {}
    judge = getattr(provider, "model", "unknown")
    for item in items:
        completion = provider.generate_with_purpose(
            build_judge_prompt(item), purpose=JUDGE_PURPOSE)
        votes[item.item_key] = parse_verdict(
            str(getattr(completion, "text", "")), judge=judge)
    return votes
