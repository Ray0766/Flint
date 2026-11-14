"""QueryBuilder 协议装配（M2-021，PDD v0.2 §4.1 四步；冻结协议 QueryBuilder）。

步骤：术语标准化（M2-017）→ 同义/上下位扩展（M2-018）→ 按 intent 生成
多 query（support=论文族 / refute=五模板族 / landscape=竞品面）；结果合并
去重归检索执行层（M2-019/023 消费）。
"""
from __future__ import annotations

from typing import Literal

from flint.domain.models import Query
from flint.domain.protocols import LLMProvider
from flint.llm.cache import LLMJudgmentCache
from flint.norm.terms import TermMap
from flint.retrieval.expand import expand_term
from flint.retrieval.refute_templates import refute_queries
from flint.retrieval.terms import standardize_terms


class FourStepQueryBuilder:
    """冻结协议 QueryBuilder 实现。"""

    def __init__(
        self,
        term_map: TermMap,
        provider: LLMProvider,
        cache: LLMJudgmentCache,
        max_retries: int = 2,
    ) -> None:
        self._term_map = term_map
        self._provider = provider
        self._cache = cache
        self._max_retries = max_retries

    def build(
        self,
        keywords: list[str],
        intent: Literal["support", "refute", "landscape"],
        locale: str,
    ) -> list[Query]:
        standardized = standardize_terms(
            keywords, self._term_map, self._provider, self._cache, self._max_retries
        )
        english_terms: list[str] = []
        for item in standardized:
            if item.english not in english_terms:  # 同义关键词标准化后合并
                english_terms.append(item.english)

        queries: list[Query] = []
        seen_texts: set[str] = set()
        for term in english_terms:
            if intent == "refute":
                candidates = refute_queries(term, locale)
            elif intent == "landscape":
                # 竞品/landscape：R1 源（github/arxiv）能给的是**开源替代**（repo）+**研究面**
                # （paper）——用可被仓库/论文检索命中的裸术语查询，而非商业检索式
                # （"product platform vendor" 命中不了 github 仓库）。**商业竞品须市场源**
                # （微博/news/web，门 2 缓）——那部分接地如实标「待市场源」，NEVER 假造。
                candidates = [
                    Query(
                        text=term,
                        source_kinds=["repo", "product", "paper"],
                        intent="landscape",
                        locale=locale,
                    )
                ]
            else:
                expansion = expand_term(
                    term, self._provider, self._cache, self._max_retries
                )
                candidates = [
                    Query(
                        text=t, source_kinds=["paper"], intent="support", locale=locale
                    )
                    for t in expansion.all_terms()
                ]
            for query in candidates:
                if query.text not in seen_texts:
                    seen_texts.add(query.text)
                    queries.append(query)
        return queries
