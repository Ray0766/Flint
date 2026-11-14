"""REGION-08：by_source 分列并入 region 维度（禁合成结论句）。

## 为什么「不合成」比「多列」更要紧

两国对同一件事的说法不一致时, 把它们揉成一句「综合各国观点, 总体而言……」
读起来最顺, 也最有害: 读者失去了「谁说的」这个唯一能判断可信度的东西,
而那句综合结论**没有任何一个来源支持它**——它是模型自己写的。

`PRINCIPLES#B4`: 跨国立场分歧沿 by_source 分列独立呈现, NEVER 合成为单一结论句。
所以本模块除了分列, 还带一份**合成句式黑名单**。

## 少数派不被合并

只有一条陈述的区照样单独成列。把「只有一家这么说」并进多数派那一列,
等于用列数暗示了可信度——而那是读者该自己判断的事。

## 复用（§6-H6）

分组沿用 `flint/cards.py` 既有的 by_source 通道语义, NEVER 新写一套分组/排序。
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from flint.cards import LinkCandidate, rank_top_links  # H6: 复用既有 by_source 通道

# 合成结论句黑名单。命中即拦——这些句式的共同点是: 它们声称一个**没有来源**的总体判断。
SYNTHESIS_BLACKLIST: tuple[str, ...] = (
    r"综合各[国方]",
    r"总的来说",
    r"总体而言",
    r"各方(普遍|一致)?认为",
    r"\boverall\b.{0,20}\bconsensus\b",
    r"\bin general\b.{0,20}\bagree",
    r"两国(立场)?一致",
)
_PATTERNS = tuple(re.compile(p, re.IGNORECASE) for p in SYNTHESIS_BLACKLIST)


@dataclass(frozen=True)
class SourceStatement:
    """一条来源陈述。text 是**原文**, NEVER 翻译 [PRINCIPLES#B9]。"""

    source_id: str
    region: str
    text: str


@dataclass(frozen=True)
class RegionColumn:
    """一列 = 一个地区的独立呈现。"""

    region: str
    statements: tuple[SourceStatement, ...]


def columns_by_region(statements: list[SourceStatement]) -> list[RegionColumn]:
    """按 region 分列。**少数派不被合并**——一条陈述的区照样单独成列。"""
    grouped: dict[str, list[SourceStatement]] = {}
    for s in statements:
        grouped.setdefault(s.region, []).append(s)
    return [
        RegionColumn(region=region, statements=tuple(grouped[region]))
        for region in sorted(grouped)
    ]


def top_links_per_region(
    candidates_by_region: dict[str, list[LinkCandidate]], top_n: int = 5
) -> dict[str, list[str]]:
    """每列各自取 top 链接——**排名沿用既有 by_source 机制** (§6-H6)。

    NEVER 在这里新写一套排序: 既有 rank_top_links 已经定义了「源内分位 → 跨源取最好」
    的口径, 另写一份就会出现两种排名, 而用户看到的是哪一种取决于走了哪条代码路径。
    """
    return {
        region: rank_top_links(candidates, top_n=top_n)
        for region, candidates in sorted(candidates_by_region.items())
    }


def check_no_synthesis(text: str) -> list[str]:
    """命中的合成句式（空 = 干净）。

    黑名单只拦「声称一个没有来源的总体判断」的句式, NEVER 拦正常陈述——
    误判会逼人删掉真话, 那比漏判更糟。
    """
    return [p.pattern for p in _PATTERNS if p.search(text)]
