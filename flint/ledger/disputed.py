"""disputed 排除面（M3-007，S2-4 / 审10 / 审11）。

- usable_fact_pool：新生成可用池 = status=="frozen" 全量——disputed 与
  retired 都不进池（disputed 是争议排除，retired 是移除排除，语义不同但
  池口径一致）。
- mark_advisory_for_disputed：引用 disputed fact 的 block 标
  needs_review(fact_disputed, advisory)；advisory NEVER 降格已在场的
  blocking（审11 严重度只升不降）；副本返回，输入不变。
"""
from __future__ import annotations

from dataclasses import replace

from flint.domain.models import Block, Fact


def usable_fact_pool(facts: list[Fact]) -> list[Fact]:
    return [f for f in facts if f.status == "frozen"]


def mark_advisory_for_disputed(
    blocks: list[Block], disputed_ids: set[str]
) -> list[Block]:
    marked: list[Block] = []
    for block in blocks:
        if not disputed_ids.intersection(block.fact_ids):
            marked.append(replace(block))
            continue
        if block.review_severity == "blocking":
            marked.append(replace(block))  # 严重度只升不降：blocking 保持
            continue
        marked.append(
            replace(
                block,
                needs_review=True,
                review_reason="fact_disputed",
                review_severity="advisory",
            )
        )
    return marked
