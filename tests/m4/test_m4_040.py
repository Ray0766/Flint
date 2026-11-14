"""M4-040 acceptance tests: semantic answer rate instrument (carried cond 1).

Acceptance (tasks.json M4-040):
  - after real-LLM wiring, N>=12 real compositions answered per check
    question semantically with trail
  - rate >=90% on the same doc_metrics instrument; honestly blocked when
    unavailable (owner supplies key/content source)

Offline scope: instrument mechanics (question actually used, trail,
N>=12 hard gate, shared line). The real-LLM run is the redemption act,
recorded via ledger blocked -> owner key -> rerun.
"""
from __future__ import annotations

import pytest

from eval.heldout import HeldoutBank, HeldoutQuestion
from eval.semantic_answers import (
    MIN_COMPOSITIONS,
    Composition,
    InsufficientCompositions,
    llm_answer_fn,
    semantic_answer_report,
)
from flint.domain.models import JSON, Completion

pytestmark = pytest.mark.compose


STUB_BANK = HeldoutBank(bank_version="stub", questions={
    ("generic", sid): [
        HeldoutQuestion(qid=f"stub/{sid}/q1", q=f"桩题-{sid}-甲？"),
        HeldoutQuestion(qid=f"stub/{sid}/q2", q=f"桩题-{sid}-乙？"),
    ]
    for sid in ("summary", "opportunity", "market", "competition",
                "plan", "budget", "risks")
})


def compositions(n: int) -> list[Composition]:
    sections = {
        sid: f"{sid} 节内容：目标市场规模一亿，验证方式为访谈。"
        for sid in (
            "summary", "problem", "solution", "market", "competition",
            "plan", "ask",
        )
    }
    return [
        Composition(
            composition_id=f"c-{i:02d}", template_id="generic",
            sections=sections,
        )
        for i in range(n)
    ]


def test_question_text_enters_the_call_and_trail() -> None:
    seen: list[str] = []

    def answer_fn(question: str, section_text: str) -> tuple[bool, str]:
        seen.append(question)
        return True, f"有据：{question[:8]}"

    report = semantic_answer_report(
        compositions(MIN_COMPOSITIONS), answer_fn, bank=STUB_BANK
    )
    assert report.n_compositions == 12
    assert report.questions == len(seen) > 0, "one call per question"
    assert len(set(seen)) > 1, "distinct question texts flow through"
    record = report.records[0]
    assert record.question == seen[0], "trail carries the question verbatim"
    assert record.answer.startswith("有据")


def test_rate_and_shared_line() -> None:
    flags = iter(
        [True] * 9 + [False] + [True] * 1000
    )

    def answer_fn(question: str, section_text: str) -> tuple[bool, str]:
        return next(flags), "x"

    report = semantic_answer_report(compositions(12), answer_fn, bank=STUB_BANK)
    assert report.rate == pytest.approx(
        report.answered / report.questions
    )
    assert report.verdict == "report_only", (
        "threshold_note: no line applied on the new exam surface"
    )


def test_n_below_12_is_blocked_not_degraded() -> None:
    with pytest.raises(InsufficientCompositions, match="11"):
        semantic_answer_report(
            compositions(11), lambda q, s: (True, "x"), bank=STUB_BANK
        )


def test_llm_answer_fn_adapts_structured_provider() -> None:
    class FakeProvider:
        def __init__(self) -> None:
            self.prompts: list[str] = []

        def generate(self, prompt: str, tools: list[JSON] | None) -> Completion:
            raise AssertionError("free-form path unused")

        def generate_structured(
            self, prompt: str, schema: JSON, max_retries: int
        ) -> JSON:
            self.prompts.append(prompt)
            return {"answered": True, "answer": "内容含市场规模数字"}

    provider = FakeProvider()
    answer_fn = llm_answer_fn(provider)
    answered, answer = answer_fn("市场规模是否有出处？", "规模一亿（Fact-1）")
    assert answered is True and "数字" in answer
    assert "市场规模是否有出处？" in provider.prompts[0]
    assert "规模一亿" in provider.prompts[0], "section text enters the prompt"
