"""改写重检环（M2-023，PDD v0.2 §4.1 第四步收口）。

「真没有」与「没搜对」的分界线：
- 相关率 < θ_rel → 关键词改写重检，上限 R=2 轮（S4 Open Question 初值）；
- 改写满额后仍低才允许 insufficient=True（信息不足）——绝无第三轮盲改；
- 任一轮达标即成功返回该轮 docs 与 rate。
改写器注入（生产走 LLM judgment 类；测试脚本化）。
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Final, Literal, Protocol

from flint.domain.models import Doc, Query
from flint.retrieval.multiquery import merge_results
from flint.retrieval.relevance import THETA_REL

MAX_REWRITES: Final[int] = 2

Rewriter = Callable[[list[str], int], list[str]]
Searcher = Callable[[Query], list[Doc]]


class _BuilderLike(Protocol):
    def build(
        self, keywords: list[str],
        intent: Literal["support", "refute", "landscape"], locale: str,
    ) -> list[Query]: ...


class _JudgeLike(Protocol):
    def hit_rate(self, q: Query, docs: list[Doc]) -> float: ...


@dataclass
class RetrievalOutcome:
    docs: list[Doc] = field(default_factory=list)
    hit_rate: float = 0.0
    rounds_used: int = 0
    insufficient: bool = False
    rewrites: list[list[str]] = field(default_factory=list)


def search_with_rewrite(
    builder: _BuilderLike,
    judge: _JudgeLike,
    searcher: Searcher,
    keywords: list[str],
    intent: Literal["support", "refute", "landscape"],
    locale: str,
    rewriter: Rewriter,
    theta: float = THETA_REL,
    max_rewrites: int = MAX_REWRITES,
) -> RetrievalOutcome:
    outcome = RetrievalOutcome()
    current = list(keywords)
    for round_index in range(1 + max_rewrites):
        queries = builder.build(current, intent, locale)
        result_sets = [searcher(query) for query in queries]
        docs = merge_results(result_sets, embedder=None)
        probe = queries[0] if queries else Query(
            text=" ".join(current), source_kinds=["paper"], intent=intent, locale=locale
        )
        rate = judge.hit_rate(probe, docs)
        outcome.docs = docs
        outcome.hit_rate = rate
        outcome.rounds_used = round_index + 1
        if rate >= theta:
            return outcome
        if round_index < max_rewrites:
            current = rewriter(current, round_index + 1)
            outcome.rewrites.append(list(current))
    outcome.insufficient = True  # 改写满额仍低：真没有（信息不足）
    return outcome
