"""DEF-01 / §9-P1：收藏快照 pin —— 让 180 天周删跳过被收藏引用的快照。

owner 已采纳 P1（v0.4.1 第 2 批）。在此之前 `flint/fav/store.py` 的采纳位写着
「它只是注释，NEVER 成为真实现」——现在它成了真实现，但**内嵌那条路一个字都不动**。

## pin 是多一条路，不是换一条路

基线的冻结靠**内嵌**：收藏时把内容抄一份带走，于是「源被改了 / 被删了 /
被 180 天周删清了」都影响不到它——**冻结是结构性的，不依赖任何人记得去保护被引对象**。

pin 依赖有人记得钉。忘了钉，快照到期照样没。所以它是**补充**：
让「收藏引用 snapshot_id」这条更省空间的路也能安全走，而不是把内嵌那条换掉。

## 两条豁免，方向正好相反

`SnapshotStore` 承诺「保留 180 天」（F2：任何 Deliverable 可回放复现）。之上有两条例外：

- `RedactionRecord`（审9，owner 删除权）：**提前删**，不等 180 天；
- `pinned`（本模块）：**留过 180 天**，周删跳过。

**把两者混成一个「豁免」概念，迟早会写出「pinned 的也一并删掉」这种代码。**
两者撞上时**删除权赢**：反过来（pin 挡住 owner 的删除权）等于用一个便利功能架空了一项权利。

## NEVER 回填

收藏改存 `snapshot_id` 引用之后，**旧收藏里那份内嵌副本一个字都不动**。
原始值本来就在 `SnapshotHistoryStore` 里（FAV-02：历史保留**每一个**旧值）。
回填等于把「他收藏那天看到的东西」改写成今天的东西——而那正是 FAV-02 花力气保住的。

内存实现；SQL 实现随 E2 接入（与 `SnapshotHistoryStore` 同一房规）。
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Final

from flint.store.snapshot import RETENTION_DAYS as _RETENTION_DAYS

# 与 `flint/store/snapshot.py` 同一个数：**NEVER 在这里另写一个 180**——
# 两处各写一份的那天，周删与 pin 会按不同的期限干活，而谁都不会发现。
RETENTION_DAYS: Final[int] = _RETENTION_DAYS


@dataclass
class SnapshotPins:
    """被钉住的 snapshot_id。内存实现；SQL 实现随 E2 接入。"""

    _pinned: set[str] = field(default_factory=set)

    def pin(self, snapshot_id: str) -> None:
        """钉住。**幂等**——重放与重试都会撞上这一步。"""
        self._pinned.add(snapshot_id)

    def unpin(self, snapshot_id: str) -> None:
        """取消钉住。没钉过也不报错，理由同上。"""
        self._pinned.discard(snapshot_id)

    def is_pinned(self, snapshot_id: str) -> bool:
        return snapshot_id in self._pinned

    def pinned_ids(self) -> set[str]:
        """返回**副本**：改返回值 NEVER 影响库里那份（FAV-01 同款口径）。"""
        return set(self._pinned)


def expired_snapshot_ids(
    created_at: Mapping[str, datetime],
    *,
    now: datetime,
    pins: SnapshotPins,
    redacted: Iterable[str] = (),
    retention_days: int = RETENTION_DAYS,
) -> list[str]:
    """周删任务该清掉哪些快照。

    规则一句话：**过了保留期就删，钉住的除外；owner 要删的立刻删，钉住的也拦不住。**

    `now` 由调用方给：靠真实等待验 180 天的保留期是验不了的——那种测试要么永远不跑，
    要么被人改成 1 天然后忘了改回来。
    """
    redacted_set = set(redacted)
    cutoff = now - timedelta(days=retention_days)
    collected = []
    for snapshot_id, created in created_at.items():
        if snapshot_id in redacted_set:
            collected.append(snapshot_id)          # 删除权优先于一切
            continue
        if pins.is_pinned(snapshot_id):
            continue                                # 钉住的留过保留期
        if created < cutoff:
            collected.append(snapshot_id)
    return collected


def snapshot_reference(favorite_id: str, snapshot_id: str) -> dict[str, Any]:
    """收藏 → 被引快照的引用记录。

    **只记引用，不碰快照内容**：原始值在 `SnapshotHistoryStore` 里，
    这里既不读它也不改它（NEVER 回填）。
    """
    return {"favorite_id": favorite_id, "snapshot_id": snapshot_id}
