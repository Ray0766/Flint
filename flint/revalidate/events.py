"""event 触发（M3-050，冻结协议 Revalidator docstring：revival·momentum、
refute 新强证据）。

- 三事件源：簇 revival 信号 / momentum 信号 / refute 新强证据；其余信号
  不触发。
- 去重窗口 14 天（写死）：同 deliverable 同事件类窗口内一次；跨
  deliverable 不互抑。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Final, Literal

EVENT_DEDUP_WINDOW_DAYS: Final[int] = 14

EventKind = Literal["cluster_revival", "momentum", "refute_strong_evidence"]


@dataclass(frozen=True)
class EventTrigger:
    deliverable_id: str
    event_kind: EventKind
    trigger: Literal["event"]
    evidence_refs: tuple[str, ...]


def derive_event_triggers(
    deliverable_id: str,
    cluster_flags: list[str],
    momentum_flag: bool,
    new_strong_refute_doc_ids: list[str],
    recent: list[tuple[str, str, date]],
    today: date,
) -> list[EventTrigger]:
    cutoff = today - timedelta(days=EVENT_DEDUP_WINDOW_DAYS)
    suppressed = {
        kind
        for did, kind, fired_on in recent
        if did == deliverable_id and fired_on >= cutoff
    }

    candidates: list[tuple[EventKind, tuple[str, ...]]] = []
    if "revival" in cluster_flags:
        candidates.append(("cluster_revival", ()))
    if momentum_flag:
        candidates.append(("momentum", ()))
    if new_strong_refute_doc_ids:
        candidates.append(
            ("refute_strong_evidence", tuple(new_strong_refute_doc_ids))
        )

    return [
        EventTrigger(
            deliverable_id=deliverable_id, event_kind=kind,
            trigger="event", evidence_refs=refs,
        )
        for kind, refs in candidates
        if kind not in suppressed
    ]
