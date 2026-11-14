"""M3-030 acceptance tests: vibe_pack S1/S2/S4 assembly.

Acceptance (tasks.json M3-030):
  - rule-table assembly (section-class calls) produces S1 Charter /
    S2 Invariants / S4 decision table
  - the produced pack itself passes the S2-8 banned-word self-check
"""
from __future__ import annotations

from flint.compose.vibe_core import (
    BANNED_WORDS,
    assemble_s1_charter,
    assemble_s2_invariants,
    assemble_s4_decisions,
    banned_word_hits,
)

CHARTER_INPUT = {
    "goal": "四热点源日更 -> 证据卡 -> 判定 -> 报告 -> 计划书",
    "non_goals": ["实时热点", "英文界面"],
    "scope": "M1 数据与索引层全量任务",
}

INVARIANTS_INPUT = [
    {"rule": "结论必有引用", "kind": "MUST"},
    {"rule": "partial 的 claim 提升为 Fact", "kind": "NEVER"},
]

DECISIONS_INPUT = [
    {"id": "D1", "decision": "多入口 Origin", "source": "M0-决策记录.md"},
    {"id": "D7", "decision": "判定顺序写死", "source": "产品描述文档-v0.3.1.md#2.2"},
]


def test_s1_charter_assembled() -> None:
    text = assemble_s1_charter(CHARTER_INPUT)
    assert text.startswith("## S1 Charter")
    assert "四热点源日更" in text
    assert "非目标" in text and "实时热点" in text
    assert "NEVER 实现" in text, "non-goals carry normative force"


def test_s2_invariants_normative_markers() -> None:
    text = assemble_s2_invariants(INVARIANTS_INPUT)
    assert text.startswith("## S2 Invariants")
    assert "MUST" in text and "NEVER" in text
    assert "结论必有引用" in text


def test_s4_decision_table_with_sources() -> None:
    text = assemble_s4_decisions(DECISIONS_INPUT)
    assert text.startswith("## S4 Decision Log")
    assert "| D1 |" in text and "| D7 |" in text
    assert "M0-决策记录.md" in text, "every decision cites its source"


def test_pack_passes_own_banned_word_check() -> None:
    for text in (
        assemble_s1_charter(CHARTER_INPUT),
        assemble_s2_invariants(INVARIANTS_INPUT),
        assemble_s4_decisions(DECISIONS_INPUT),
    ):
        assert banned_word_hits(text) == [], "dogfood: the pack obeys S2-8"


def test_banned_word_detector_catches_violations() -> None:
    assert banned_word_hits("适当调整参数") == ["适当"]
    hits = banned_word_hits("大约需要若干资源")
    assert hits == ["大约", "若干"]
    assert banned_word_hits("幂等提交与等价类") == [], "compound words exempt"
    assert sorted(BANNED_WORDS) == ["大约", "尽量", "必要时", "等", "若干", "适当", "合理"] or len(BANNED_WORDS) == 7
