"""REGION-08 验收：by_source 跨国分列（region 维度并入，禁合成）。

acceptance（tasks-v04.json#REGION-08）：
  ① 分歧 fixture 输出 **≥2 列**；**合成结论句黑名单零命中**；
  ② 复用既有分列机制（**import 来源断言**，H6）。

## 为什么「不合成」比「多列」更要紧

两国对同一件事的说法不一致时，把它们揉成一句「综合各国观点，总体而言……」
读起来最顺，也最有害：读者失去了「谁说的」这个唯一能判断可信度的东西，
而那句综合结论**没有任何一个来源支持它**——它是模型自己写的。
所以这里不仅断言列数 ≥2，还用**黑名单**扫合成句式。
"""
from __future__ import annotations

import inspect

import pytest

from flint.region import by_source_region
from flint.region.by_source_region import (
    SYNTHESIS_BLACKLIST,
    SourceStatement,
    check_no_synthesis,
    columns_by_region,
)

# 分歧 fixture：同一议题，US 与 JP 两国口径相反
DISAGREEMENT = [
    SourceStatement(source_id="s-us", region="US",
                    text="Regulators say the timeline is unrealistic."),
    SourceStatement(source_id="s-us2", region="US",
                    text="Analysts expect the launch to slip past 2028."),
    SourceStatement(source_id="s-jp", region="JP",
                    text="経済産業省は２０２７年の量産開始を支持している。"),
]


def test_disagreement_yields_at_least_two_columns() -> None:
    columns = columns_by_region(DISAGREEMENT)
    assert len(columns) >= 2, f"分歧应分列呈现，实得 {len(columns)} 列"
    assert {c.region for c in columns} == {"US", "JP"}


def test_each_column_keeps_its_own_statements() -> None:
    columns = {c.region: c for c in columns_by_region(DISAGREEMENT)}
    assert len(columns["US"].statements) == 2
    assert len(columns["JP"].statements) == 1
    for region, column in columns.items():
        assert all(s.region == region for s in column.statements)


def test_no_column_is_merged_away() -> None:
    """少数派**不被合并**：只有一条陈述的区照样单独成列。"""
    columns = columns_by_region(DISAGREEMENT)
    assert any(len(c.statements) == 1 for c in columns), "单条陈述的区被并掉了"


def test_original_text_is_not_translated() -> None:
    """分列只是分组，NEVER 顺手翻译（B9）。"""
    columns = {c.region: c for c in columns_by_region(DISAGREEMENT)}
    assert "経済産業省" in columns["JP"].statements[0].text


# ── 合成结论句黑名单 ────────────────────────────────────────────

@pytest.mark.parametrize("bad", [
    "综合各国观点，总体而言前景乐观。",
    "总的来说，两国立场一致。",
    "Overall, the consensus is positive.",
    "各方普遍认为该时间表可行。",
])
def test_blacklist_catches_synthesis_sentences(bad: str) -> None:
    hits = check_no_synthesis(bad)
    assert hits, f"合成句式未被拦下：{bad!r}"


def test_blacklist_is_zero_hit_on_the_fixture() -> None:
    """acceptance ①：分歧 fixture 的每一条陈述都不是合成句。"""
    for statement in DISAGREEMENT:
        assert check_no_synthesis(statement.text) == [], statement.text


def test_blacklist_does_not_flag_legitimate_text() -> None:
    """阴性对照：正常陈述 NEVER 被误判——否则黑名单会逼人删掉真话。"""
    for ok in ("Regulators say the timeline is unrealistic.",
               "経済産業省は２０２７年の量産開始を支持している。",
               "该公司公布了第三季度出货量。"):
        assert check_no_synthesis(ok) == [], ok


def test_blacklist_is_not_empty() -> None:
    assert len(SYNTHESIS_BLACKLIST) >= 4, "黑名单太短就等于没有"


# ── ② H6：复用既有分列机制 ──────────────────────────────────────

def test_reuses_existing_grouping_mechanism() -> None:
    """H6：分列复用既有 by_source 机制，NEVER 新写一套分组。"""
    source = inspect.getsource(by_source_region)
    assert "from flint.cards import" in source, (
        "应从既有 by_source 通道 import，而不是另写一份分组实现")


def test_module_does_not_define_its_own_ranking() -> None:
    exported = {n for n in dir(by_source_region) if not n.startswith("_")}
    assert "rank_top_links" not in exported or by_source_region.rank_top_links.__module__ == (
        "flint.cards"), "排序逻辑必须来自既有模块"


def test_top_links_per_region_delegates_to_existing_ranking() -> None:
    """H6 的复用是**真调用**，不是一句 noqa 的未使用 import。

    （首轮教训：ruff --fix 把那句未使用 import 删掉，本文件的 H6 断言当场变红——
     假复用被自己的测试抓住了。）
    """
    from flint.cards import LinkCandidate
    from flint.region.by_source_region import top_links_per_region

    per_region = {
        "US": [LinkCandidate(source_id="s-us", url="https://a.invalid", score=0.9),
               LinkCandidate(source_id="s-us", url="https://b.invalid", score=0.1)],
        "JP": [LinkCandidate(source_id="s-jp", url="https://c.invalid", score=0.5)],
    }
    got = top_links_per_region(per_region, top_n=1)
    assert got == {"US": ["https://a.invalid"], "JP": ["https://c.invalid"]}
