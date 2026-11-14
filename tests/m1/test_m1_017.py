"""M1-017 acceptance tests: keyword cleaning pipeline, A3 stage one (PDD v0.2 §3.1).

Acceptance (tasks.json M1-017):
  - 20 golden dirty-sample groups (emoji / traditional-simplified / full-half width) all pass
"""
from __future__ import annotations

import pytest

from flint.norm.clean import clean

# 20 golden (dirty, expected) pairs — the acceptance corpus.
GOLDEN_CASES: list[tuple[str, str]] = [
    # full/half width + case
    ("　ＡＩ  Ａｇｅｎｔ　", "ai agent"),
    ("ＬＬＭ", "llm"),
    ("５Ｇ－Ａｄｖａｎｃｅｄ", "5g-advanced"),
    ("Ｗｅｂ３．０", "web3.0"),
    ("ＧＰＵ 短缺", "gpu 短缺"),
    ("數據中心（液冷）", "数据中心(液冷)"),
    # emoji / pictographs / variation selectors
    ("ChatGPT🔥🔥", "chatgpt"),
    ("量子計算✨", "量子计算"),
    ("🚀SpaceX 星艦", "spacex 星舰"),
    ("無人機配送👍", "无人机配送"),
    ("大語言模型❤️", "大语言模型"),
    # traditional -> simplified (char level)
    ("固態電池", "固态电池"),
    ("机器學習", "机器学习"),
    ("區塊鏈 ETF", "区块链 etf"),
    ("ＲＡＧ　檢索增強", "rag 检索增强"),
    ("云端運算", "云端运算"),
    ("AI＋醫療", "ai+医疗"),
    ("熱點分析", "热点分析"),
    # whitespace / invisible chars
    ("Solid   State    Battery", "solid state battery"),
    ("電動車\u200b補貼", "电动车补贴"),
]


@pytest.mark.parametrize(("dirty", "expected"), GOLDEN_CASES)
def test_golden_cases(dirty: str, expected: str) -> None:
    assert clean(dirty) == expected


def test_corpus_size_is_twenty() -> None:
    assert len(GOLDEN_CASES) == 20


@pytest.mark.parametrize(("dirty", "expected"), GOLDEN_CASES)
def test_clean_is_idempotent(dirty: str, expected: str) -> None:
    assert clean(clean(dirty)) == clean(dirty)


def test_empty_and_whitespace_only() -> None:
    assert clean("") == ""
    assert clean("　  \u200b") == ""
