"""(a)-① 确定性接地校验器：单元规则 + 对 4 家录制资产的验收（owner 授权长跑 Phase 0）。

验收（owner 钉死，用现成 4 家录制当免费测试集，MUST 全过）：
- 抓出 deepseek 26%/92%/30% 编数字 → dirty；
- 抓出 gpt-4o-mini 2023 假日期 → dirty；
- claude 干净输出零误杀 → clean；
- qwen 诚实留白（无引用）→ unverifiable（NEVER 判 dirty）。
校验器纯函数、零联网：以 assets/topic_caliber/card_corpus.json（真机 PG 冻结的被引卡原文）
为被引卡真相；被判维度须由校验器判定，NEVER 人眼。
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from flint.grounding import (
    CardContent,
    GroundingConfig,
    check_citation,
    grade_asset,
    load_card_corpus,
)

pytestmark = pytest.mark.compose

REPO = Path(__file__).resolve().parents[2]
ASSET_ROOT = REPO / "assets" / "topic_caliber"
CORPUS = ASSET_ROOT / "card_corpus.json"

# 被引卡真相（真机冻结）：两卡均 2026-06-29、原文无任何数字。
CARD0 = CardContent(card_id="c0", day=date(2026, 6, 29), corpus="高考录取结果")


# ── 规则单测 ────────────────────────────────────────────────────────────

def test_clean_when_text_has_no_numbers_and_date_matches() -> None:
    c = check_citation("相关话题热度上升", date(2026, 6, 29), CARD0)
    assert c.verdict == "clean"


def test_dirty_on_fabricated_number_not_in_card() -> None:
    c = check_citation("效率突破26%", date(2026, 6, 29), CARD0)
    assert c.verdict == "dirty"
    assert any(f.rule == "number" and f.verdict == "dirty" for f in c.findings)


def test_dirty_on_year_outside_card_range() -> None:
    c = check_citation("2023年高考录取结果公布", date(2023, 7, 1), CARD0)
    assert c.verdict == "dirty"
    assert any(f.rule == "date" and f.verdict == "dirty" for f in c.findings)


def test_unverifiable_when_card_content_missing() -> None:
    c = check_citation("任何事件", date(2026, 6, 29), None)
    assert c.verdict == "unverifiable"


def test_number_present_in_card_is_clean() -> None:
    card = CardContent(card_id="c", day=date(2026, 6, 29), corpus="效率达到26%的钙钛矿")
    assert check_citation("效率突破26%", date(2026, 6, 29), card).verdict == "clean"


def test_percent_ratio_normalization_26pct_equals_0_26() -> None:
    # owner: 归一化 26%↔0.26
    card = CardContent(card_id="c", day=date(2026, 6, 29), corpus="转化率 0.26")
    assert check_citation("转化率26%", date(2026, 6, 29), card).verdict == "clean"


def test_thousands_separator_normalization() -> None:
    card = CardContent(card_id="c", day=date(2026, 6, 29), corpus="投入 1000 万元")
    assert check_citation("投入1,000万元", date(2026, 6, 29), card).verdict == "clean"


def test_tolerance_allows_near_match_when_configured() -> None:
    card = CardContent(card_id="c", day=date(2026, 6, 29), corpus="增长 25%")
    cfg = GroundingConfig(number_tolerance=0.1)  # ±10% 相对容差
    assert check_citation("增长26%", date(2026, 6, 29), card, cfg).verdict == "clean"
    assert check_citation("增长26%", date(2026, 6, 29), card).verdict == "dirty"  # 默认精确


def test_year_matching_card_range_is_clean() -> None:
    c = check_citation("2026年高考录取结果公布", date(2026, 6, 29), CARD0)
    assert c.verdict == "clean"


def test_entity_rule_off_by_default_flags_only_when_enabled() -> None:
    card = CardContent(card_id="c", day=date(2026, 6, 29), corpus="高考录取结果")
    # 默认不查实体：编造机构名不判 dirty（除非开启加严）
    assert check_citation("清华大学发布高考录取结果", date(2026, 6, 29), card).verdict == "clean"
    strict = GroundingConfig(check_entity=True)
    v = check_citation("清华大学发布高考录取结果", date(2026, 6, 29), card, strict)
    assert any(f.rule == "entity" for f in v.findings)


# ── 对 4 家录制资产的验收（校验器判，非人眼）───────────────────────────

def _asset(model: str) -> dict:
    p = ASSET_ROOT / f"{model.replace(':', '_')}.json"
    return json.loads(p.read_text(encoding="utf-8"))


@pytest.fixture
def cards() -> dict[str, CardContent]:
    return load_card_corpus(CORPUS)


def test_corpus_fixture_has_no_numbers(cards: dict[str, CardContent]) -> None:
    # 被引卡冻结真相：原文无数字（正是"引用≠取证干净"的根因）
    assert cards
    for c in cards.values():
        assert not any(ch.isdigit() for ch in c.corpus)


def test_deepseek_fabricated_numbers_are_dirty(cards: dict[str, CardContent]) -> None:
    graded = grade_asset(_asset("deepseek-chat"), cards)
    assert graded["dirty"] >= 1
    # 具体坐实：编造数字命中 number 规则
    assert any(
        any(f.rule == "number" and f.verdict == "dirty" for f in cc.findings)
        for t in graded["topics"] for cc in t["citations"]
    )


def test_gpt_fake_year_is_dirty(cards: dict[str, CardContent]) -> None:
    graded = grade_asset(_asset("gpt-4o-mini"), cards)
    assert graded["dirty"] >= 1
    assert any(
        any(f.rule == "date" and f.verdict == "dirty" for f in cc.findings)
        for t in graded["topics"] for cc in t["citations"]
    )


def test_claude_clean_zero_false_positive(cards: dict[str, CardContent]) -> None:
    graded = grade_asset(_asset("claude-sonnet-5"), cards)
    assert graded["dirty"] == 0        # 干净输出零误杀
    assert graded["clean_topics"] >= 1


def test_qwen_honest_abstention_is_unverifiable_not_dirty(
    cards: dict[str, CardContent],
) -> None:
    graded = grade_asset(_asset("qwen3.6:27b"), cards)
    assert graded["dirty"] == 0                      # 留白 NEVER 判 dirty
    assert graded["unverifiable_topics"] == len(graded["topics"])
