"""HOTSPOT-06：分析时效 stale 适配器（§6-H1 三个薄适配器之一）。

系统里已经有一套判「东西变没变」的机制：`LedgerStore.diff`（协议）→
`flint/ledger/diff.py#compute_diff` 三分类 + 那张严重度表
（`removed→blocking / changed→advisory / disputed→advisory`，审11 只升不降）。

**本模块一行比对逻辑都不写。** 再写一套的后果不是重复劳动，而是同一份分析
在两个地方被判成不同的新旧：收藏页说它陈旧、分析页说它是最新的，用户不知道该信哪个。
抄一份严重度表最坏的形态也不是抄错，而是**日后只改了一处**——同一次事实移除
在一个界面上是 blocking、在另一个上是 advisory。

适配器只做三件事：
1. 版本没动就不查（同版本还能判出陈旧，那只会是比对实现的 bug 被放行的入口）；
2. 版本前进时把 `(project_id, 旧版, 新版)` 原样交给注入的 `LedgerStore.diff` 通道；
3. 只看**这份分析真正引用过**的事实（零污染，与既有 block 标记同一条规则）——
   否则账本一动、全站分析统统标陈旧，「陈旧」这个标记就不再有信息量。
"""
from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from flint.domain.models import FactDiff, ReviewReason, ReviewSeverity
from flint.ledger.diff import _MARKS  # 唯一严重度真相；NEVER 在本模块抄一份

# 协议 `LedgerStore.diff` 的调用面（contracts/protocols.py#LedgerStore.diff）。
DiffChannel = Callable[[str, int, int], FactDiff]


@dataclass(frozen=True)
class StaleVerdict:
    stale: bool
    severity: ReviewSeverity | None
    reason: ReviewReason | None
    fact_ids: tuple[str, ...]


_FRESH = StaleVerdict(stale=False, severity=None, reason=None, fact_ids=())


def stale_from_fact_changes(
    diff: FactDiff, *, cited_fact_ids: Iterable[str],
) -> StaleVerdict:
    """把既有 FactDiff 映射成这份分析的陈旧判定。

    严重度顺序取自 `flint.ledger.diff._MARKS`（表首即最强），命中多类时取最强。
    """
    cited = set(cited_fact_ids)
    for kind, reason, severity in _MARKS:
        hit = tuple(f for f in getattr(diff, kind) if f in cited)
        if hit:
            return StaleVerdict(
                stale=True, severity=severity, reason=reason, fact_ids=hit,
            )
    return _FRESH


def analysis_stale(
    diff_channel: DiffChannel,
    *,
    project_id: str,
    analysed_at_version: int,
    current_version: int,
    cited_fact_ids: Iterable[str],
) -> StaleVerdict:
    """经注入的既有 diff 通道判这份分析是否陈旧。"""
    if current_version < analysed_at_version:
        raise ValueError(
            f"账本版本只前进：收到 analysed_at={analysed_at_version} > "
            f"current={current_version}，这是接线错了，NEVER 当成不陈旧放过"
        )
    if current_version == analysed_at_version:
        return _FRESH
    diff = diff_channel(project_id, analysed_at_version, current_version)
    return stale_from_fact_changes(diff, cited_fact_ids=cited_fact_ids)
