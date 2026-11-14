"""FactDiff 与 needs_review 映射（M3-005，冻结协议 LedgerStore.diff / 审11）。

- compute_diff 三分类（版本对比）：
  changed  = 两版都在、新版 frozen、内容（statement/value/unit/citations）变；
  removed  = 旧版在而新版缺席，或新版 status=="retired"；
  disputed = 两版都在、新版 disputed 且旧版非 disputed（新生争议）。
- apply_review_marks：只有引用变更 fact 的 block 标 needs_review（零污染）；
  映射 changed→(fact_changed, advisory)、removed→(fact_removed, blocking)、
  disputed→(fact_disputed, advisory)；一块命中多类取最强（blocking 优先，
  审11 严重度只升不降）；副本返回。
"""
from __future__ import annotations

from dataclasses import replace

from flint.domain.models import (
    Block,
    Fact,
    FactDiff,
    ReviewReason,
    ReviewSeverity,
)


def _content_key(fact: Fact) -> tuple[str, str | float | None, str | None, tuple[str, ...]]:
    return (fact.statement, fact.value, fact.unit, tuple(fact.citation_ids))


def compute_diff(old: list[Fact], new: list[Fact]) -> FactDiff:
    old_by_id = {f.fact_id: f for f in old}
    new_by_id = {f.fact_id: f for f in new}
    changed: list[str] = []
    removed: list[str] = []
    disputed: list[str] = []
    for fact_id, old_fact in old_by_id.items():
        new_fact = new_by_id.get(fact_id)
        if new_fact is None or new_fact.status == "retired":
            removed.append(fact_id)
        elif new_fact.status == "disputed" and old_fact.status != "disputed":
            disputed.append(fact_id)
        elif (
            new_fact.status == "frozen"
            and _content_key(new_fact) != _content_key(old_fact)
        ):
            changed.append(fact_id)
    return FactDiff(changed=changed, removed=removed, disputed=disputed)


_MARKS: tuple[tuple[str, ReviewReason, ReviewSeverity], ...] = (
    ("removed", "fact_removed", "blocking"),      # 最强优先
    ("changed", "fact_changed", "advisory"),
    ("disputed", "fact_disputed", "advisory"),
)


def apply_review_marks(blocks: list[Block], diff: FactDiff) -> list[Block]:
    id_sets = {
        "changed": set(diff.changed),
        "removed": set(diff.removed),
        "disputed": set(diff.disputed),
    }
    marked: list[Block] = []
    for block in blocks:
        cited = set(block.fact_ids)
        hit: tuple[ReviewReason, ReviewSeverity] | None = None
        for category, reason, severity in _MARKS:
            if cited & id_sets[category]:
                hit = (reason, severity)
                break  # 顺序即优先级：removed(blocking) 最先
        if hit is None:
            marked.append(replace(block))
        else:
            marked.append(
                replace(
                    block,
                    needs_review=True,
                    review_reason=hit[0],
                    review_severity=hit[1],
                )
            )
    return marked
