"""证伪检索模板族（M2-020，PDD v0.2 §4.2 B2）。

五族：limitations / failure / replication / retraction / discontinued。
intent=refute 时五族全部激活；retraction 面向论文库（撤稿记录），
discontinued 面向 repo/新闻/产品（archived、关停）——素材通道见 M2-016。
"""
from __future__ import annotations

from typing import Final

from flint.domain.models import DocKind, Query

REFUTE_FAMILIES: Final[dict[str, tuple[str, list[DocKind]]]] = {
    "limitations": ("{term} limitations shortcomings", ["paper"]),
    "failure": ("{term} failure case study", ["paper", "news"]),
    "replication": ("{term} failed replication", ["paper"]),
    "retraction": ("{term} retraction", ["paper"]),
    "discontinued": ("{term} archived discontinued", ["repo", "news", "product"]),
}


def refute_queries(term: str, locale: str) -> list[Query]:
    return [
        Query(
            text=template.format(term=term),
            source_kinds=list(kinds),
            intent="refute",
            locale=locale,
        )
        for template, kinds in REFUTE_FAMILIES.values()
    ]
