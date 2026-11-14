"""Owner bank v1.0 integration: loader_contract four assertions + isolation.

The bank file is OWNER-SIDE READ-ONLY input. These tests never author,
edit, or derive questions — stub banks in tmp files exercise error paths
only, with deliberately fake stub wording.
"""
from __future__ import annotations

import inspect
from pathlib import Path

import pytest
import yaml

from eval.heldout import (
    DEFAULT_BANK_PATH,
    HeldoutBank,
    HeldoutBankError,
    load_heldout_bank,
)
from eval.semantic_answers import Composition, semantic_answer_report

pytestmark = pytest.mark.compose

REPO_ROOT = Path(__file__).resolve().parents[2]


def real_bank() -> HeldoutBank:
    return load_heldout_bank()


# ── loader_contract ①：43 对全覆盖 ───────────────────────────


def test_contract_1_full_coverage_43_pairs() -> None:
    bank = real_bank()
    assert len(bank.questions) == 43
    assert sum(len(qs) for qs in bank.questions.values()) == 129
    assert bank.bank_version == "v1.0"


def _mutated_bank(tmp_path: Path, mutate: str) -> Path:
    data = yaml.safe_load(
        DEFAULT_BANK_PATH.read_text(encoding="utf-8")
    )
    if mutate == "missing-pair":
        del data["templates"]["generic"]["risks"]
    elif mutate == "extra-pair":
        data["templates"]["generic"]["ghost_section"] = [
            {"id": "generic/ghost_section/q1", "q": "桩：多余节占位问句？"}
        ]
    elif mutate == "dup-id":
        data["templates"]["generic"]["summary"][1]["id"] = (
            data["templates"]["generic"]["summary"][0]["id"]
        )
    elif mutate == "template-question":
        data["templates"]["generic"]["market"][0]["q"] = (
            "市场数字是否全部走 Fact/PriceCell 通道？"
        )
    path = tmp_path / "bank.yaml"
    path.write_text(
        yaml.safe_dump(data, allow_unicode=True), encoding="utf-8"
    )
    return path


def test_contract_1_missing_or_extra_pair_errors(tmp_path: Path) -> None:
    with pytest.raises(HeldoutBankError, match="generic/risks"):
        load_heldout_bank(_mutated_bank(tmp_path, "missing-pair"))
    with pytest.raises(HeldoutBankError, match="ghost_section"):
        load_heldout_bank(_mutated_bank(tmp_path, "extra-pair"))


# ── loader_contract ②：id 全局唯一 ───────────────────────────


def test_contract_2_globally_unique_ids(tmp_path: Path) -> None:
    bank = real_bank()
    ids = [hq.qid for qs in bank.questions.values() for hq in qs]
    assert len(ids) == len(set(ids)) == 129
    with pytest.raises(HeldoutBankError, match="duplicate"):
        load_heldout_bank(_mutated_bank(tmp_path, "dup-id"))


# ── loader_contract ③：与模板 check_questions 零交集 ─────────


def test_contract_3_zero_intersection(tmp_path: Path) -> None:
    real_bank()  # 真库自身零交集（装载即断言，通过=证明）
    with pytest.raises(HeldoutBankError, match="check_questions"):
        load_heldout_bank(_mutated_bank(tmp_path, "template-question"))


# ── loader_contract ④：组稿路径隔离 ──────────────────────────


def test_contract_4_compose_path_never_reads_bank() -> None:
    import harness.prod_caliber as pc

    compose_src = inspect.getsource(pc.compose_sample)
    for token in ("heldout", "bank", "load_heldout"):
        assert token not in compose_src, (
            f"compose path references {token!r}: isolation broken"
        )
    prompt_src = pc._SECTION_PROMPT
    assert "held" not in prompt_src.lower()


def test_contract_4_no_bank_question_in_compose_prompts() -> None:
    import harness.prod_caliber as pc
    from tests.m4.test_prod_caliber_switch import counting_provider

    provider, prompts = counting_provider("字" * 600)
    pc.compose_sample(
        lambda _mt: provider,
        "golddoc-generic-plain",
        "generic",
        repair_enabled=False,
    )
    bank = real_bank()
    generic_qs = [
        hq.q
        for (tid, _sid), qs in bank.questions.items()
        if tid == "generic"
        for hq in qs
    ]
    joined = "\n".join(prompts)
    for question in generic_qs:
        assert question not in joined, (
            "held-out question leaked into compose prompt"
        )


# ── 取题面 + question_id 落 trail（指令 3） ──────────────────


def test_report_sources_bank_with_question_ids() -> None:
    bank = real_bank()
    comps = [
        Composition(
            composition_id=f"c-{i:02d}", template_id="generic",
            sections={"summary": "内容甲", "market": "内容乙"},
        )
        for i in range(12)
    ]
    seen: list[str] = []

    def answer_fn(question: str, text: str) -> tuple[bool, str]:
        seen.append(question)
        return True, "有据"

    report = semantic_answer_report(comps, answer_fn, bank=bank)
    assert report.questions == 12 * 21, "generic: 7 sections x 3 questions"
    record = report.records[0]
    assert record.question_id == "generic/summary/q1"
    assert record.question.startswith("本节写明这个项目服务的具体使用者")
    assert report.verdict == "report_only", (
        "threshold_note: no line applied, first round report-only"
    )
    assert not hasattr(report, "meets_line"), (
        "0.90 line must not be consulted for the new exam surface"
    )
