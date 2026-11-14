"""生产口径验证①：语义作答率（M4-040，M3 出口携带条件）。

- 与 M3 自证口径的本质区别：**逐 check 问题语义作答**——问题文本进入
  作答调用并逐条留痕（M3 的 check_answer_report 用 result["green"] 投影、
  `_question` 未被使用；本度量器补上生产口径）。
- 取题来源 = held-out 题库（owner 投放 v1.0，与模板 check_questions
  零交集——组稿输入面与考核面分离）；遍历序仍按模板节序。
- 门槛：threshold_note（owner）——CHECK_ANSWER_LINE=0.90 系对旧考核面
  所定 NEVER 沿用；首轮一律 report_only（不判达标不画线），门槛由
  owner 见首组真实数字后另裁。
- N≥12 真实组稿硬门：不足 → InsufficientCompositions（如实 blocked，
  NEVER 用小样本或合成样本冒充生产口径）。
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from eval.doc_metrics import TEMPLATES
from flint.compose.templates import load_template
from flint.domain.models import JSON
from flint.domain.protocols import LLMProvider


class HeldoutQuestionProto(Protocol):
    """题目载体：qid 全局唯一稳定（据 id 对齐历史），q 为 owner 原文。"""

    @property
    def qid(self) -> str: ...

    @property
    def q(self) -> str: ...


class HeldoutBankProto(Protocol):
    """取题面协议（实现：eval.heldout.HeldoutBank，owner 投放内容）。"""

    def for_section(
        self, template_id: str, section_id: str
    ) -> Sequence[HeldoutQuestionProto]: ...

MIN_COMPOSITIONS = 12

ANSWER_SCHEMA: JSON = {
    "type": "object",
    "properties": {
        "answered": {"type": "boolean"},
        "answer": {"type": "string"},
    },
    "required": ["answered", "answer"],
    "additionalProperties": False,
}

_PROMPT = (
    "以下是计划书一节的渲染内容。仅依据该内容回答 check 问题；内容不足以"
    "作答时 answered=false 并说明缺口。只输出符合 schema 的 JSON。\n"
    "【check 问题】{question}\n【节内容】\n{section_text}"
)


class InsufficientCompositions(Exception):
    """N<12：生产口径不可得，如实 blocked 而非降标。"""


@dataclass(frozen=True)
class Composition:
    composition_id: str
    template_id: str
    sections: dict[str, str]  # section_id -> rendered text


@dataclass(frozen=True)
class AnswerRecord:
    composition_id: str
    section_id: str
    question_id: str  # held-out 题 id（owner 指令 3：据 id 对齐历史）
    question: str
    answered: bool
    answer: str


@dataclass(frozen=True)
class SemanticAnswerReport:
    n_compositions: int
    questions: int
    answered: int
    rate: float
    # threshold_note（owner v1.0）：CHECK_ANSWER_LINE=0.90 是对旧考核面
    # 所定，考核面已换 NEVER 沿用——首轮一律 report_only，门槛由 owner
    # 拿到首组真实数字后另裁
    verdict: str
    records: list[AnswerRecord]


# owner 裁决 @2026-07-30：绝对 0.90 线**作废**（出处已断，系对旧「自评」考核
# 面所定）。相对参照门槛（held-out bank v1.0 + 统一 Claude 判官下，
# claude-sonnet-5=REFERENCE 为参照天花板，达 REFERENCE×GATE_RATIO 即过门）。
# 原始分数一律不改（semantic_answer_report 恒 report_only、可复现）。免费档系
# best-effort 分析 AI，NEVER 作绝对质量保证。
#
# 选型依据更正 @2026-07-30-b：本相对门槛**降级为内部参考工具**，**不再作
# 免费档选型的过/不过依据**。免费档默认模型 = qwen3.6:27b，依据**权威中文
# 能力榜**（C-Eval Qwen3.6 92.8 vs Gemma 81.4，中文综合能力——「中文分析
# AI」最相关维度）。内部覆盖指标与权威榜结论相反（gemma 0.395 > qwen 0.357），
# 但覆盖指标是**窄代理**（天花板 ~0.43），权威榜测的才是产品所需综合能力。
# GATE_RATIO **恒 0.85，NEVER 为让免费档默认过门而下调**（倒推门槛=作弊，
# 明令禁止；见 tests/m4/test_answer_gate.py 反倒推不变量）。门槛出处/依据详见
# docs/答作率门槛说明.md。
REFERENCE_RATE_UNIFIED_JUDGE = 0.434
#   出处：assets/prod_caliber/unified_judge/claude-sonnet-5.json（112/258，
#   claude-sonnet-5 统一判官、held-out bank v1.0、output_config.format 结构化）
GATE_RATIO = 0.85
#   参照 85% 线（内部参考工具，非选型依据）。事实：gemma4:31b 0.395/0.434=0.91
#   过、qwen3.6:27b 0.357/0.434=0.82 不过——但选型依权威中文榜（qwen3.6），
#   NEVER 倒推此线。ratio 为 owner 可修订参考线（PDD 修订通道），非绝对质量线。


@dataclass(frozen=True)
class RelativeAnswerGate:
    free_rate: float
    reference_rate: float
    ratio: float
    required: float                  # reference_rate × ratio
    proportion_of_reference: float   # free_rate / reference_rate
    passed: bool


def relative_answer_gate(
    free_rate: float,
    reference_rate: float = REFERENCE_RATE_UNIFIED_JUDGE,
    ratio: float = GATE_RATIO,
) -> RelativeAnswerGate:
    """相对参照门槛：免费档作答率达 参照 × ratio 即合格。参照与 ratio 出处见
    上方常量注释；原始分数 NEVER 改。参照≤0 → 不判合格（无参照不画线）。"""
    required = reference_rate * ratio
    proportion = free_rate / reference_rate if reference_rate > 0 else 0.0
    passed = reference_rate > 0 and free_rate >= required
    return RelativeAnswerGate(
        free_rate=free_rate, reference_rate=reference_rate, ratio=ratio,
        required=required, proportion_of_reference=proportion, passed=passed,
    )


AnswerFn = Callable[[str, str], tuple[bool, str]]


def llm_answer_fn(provider: LLMProvider, max_retries: int = 2) -> AnswerFn:
    def answer(question: str, section_text: str) -> tuple[bool, str]:
        payload = provider.generate_structured(
            _PROMPT.format(question=question, section_text=section_text),
            ANSWER_SCHEMA, max_retries,
        )
        if not isinstance(payload, dict):
            return False, "structured payload shape invalid"
        return bool(payload.get("answered")), str(payload.get("answer", ""))

    return answer


def semantic_answer_report(
    compositions: list[Composition],
    answer_fn: AnswerFn,
    bank: HeldoutBankProto,
    templates_dir: Path = TEMPLATES,
) -> SemanticAnswerReport:
    """owner 裁决 2-3：取题来源 = held-out 题库（owner 投放），NEVER 取
    模板 check_questions（组稿输入与考核面同源会导致喂则虚高不喂则虚低
    ——v3 实证）。遍历序保持模板节序。"""
    if len(compositions) < MIN_COMPOSITIONS:
        raise InsufficientCompositions(
            f"need >= {MIN_COMPOSITIONS} real compositions, got "
            f"{len(compositions)} — blocked, not degraded"
        )
    records: list[AnswerRecord] = []
    for composition in compositions:
        _spec, sections = load_template(
            templates_dir / f"{composition.template_id}.yaml"
        )
        for section in sections:
            section_text = composition.sections.get(section.section_id, "")
            for heldout_q in bank.for_section(
                composition.template_id, section.section_id
            ):
                answered, answer = answer_fn(heldout_q.q, section_text)
                records.append(AnswerRecord(
                    composition_id=composition.composition_id,
                    section_id=section.section_id,
                    question_id=heldout_q.qid,
                    question=heldout_q.q,
                    answered=answered,
                    answer=answer,
                ))
    total = len(records)
    answered_count = sum(1 for r in records if r.answered)
    rate = answered_count / total if total else 0.0
    return SemanticAnswerReport(
        n_compositions=len(compositions),
        questions=total,
        answered=answered_count,
        rate=rate,
        verdict="report_only",
        records=records,
    )
