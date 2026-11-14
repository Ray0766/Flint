"""M3-050 acceptance tests: event triggers.

Acceptance (tasks.json M3-050):
  - three event sources (cluster revival, momentum signal, new strong refute
    evidence) each trigger; non-events never trigger
  - dedup: same deliverable + same event kind within the window fires once
"""
from __future__ import annotations

from datetime import date

from flint.revalidate.events import EventTrigger, derive_event_triggers

TODAY = date(2026, 7, 29)


def test_three_event_sources_trigger() -> None:
    triggers = derive_event_triggers(
        deliverable_id="d-1",
        cluster_flags=["revival"],
        momentum_flag=True,
        new_strong_refute_doc_ids=["doc-r1"],
        recent=[],
        today=TODAY,
    )
    kinds = [t.event_kind for t in triggers]
    assert kinds == ["cluster_revival", "momentum", "refute_strong_evidence"]
    assert all(isinstance(t, EventTrigger) for t in triggers)
    assert all(t.trigger == "event" for t in triggers)


def test_non_events_never_trigger() -> None:
    triggers = derive_event_triggers(
        deliverable_id="d-1", cluster_flags=["novelty"], momentum_flag=False,
        new_strong_refute_doc_ids=[], recent=[], today=TODAY,
    )
    assert triggers == []


def test_window_dedup_same_kind_once() -> None:
    recent = [("d-1", "cluster_revival", date(2026, 7, 20))]  # 9 天前已触发
    triggers = derive_event_triggers(
        deliverable_id="d-1", cluster_flags=["revival"], momentum_flag=False,
        new_strong_refute_doc_ids=[], recent=recent, today=TODAY,
    )
    assert triggers == [], "same kind within window fires once"

    stale = [("d-1", "cluster_revival", date(2026, 6, 1))]  # 窗口外
    again = derive_event_triggers(
        deliverable_id="d-1", cluster_flags=["revival"], momentum_flag=False,
        new_strong_refute_doc_ids=[], recent=stale, today=TODAY,
    )
    assert [t.event_kind for t in again] == ["cluster_revival"]


def test_other_deliverable_not_suppressed() -> None:
    recent = [("d-other", "momentum", date(2026, 7, 28))]
    triggers = derive_event_triggers(
        deliverable_id="d-1", cluster_flags=[], momentum_flag=True,
        new_strong_refute_doc_ids=[], recent=recent, today=TODAY,
    )
    assert [t.event_kind for t in triggers] == ["momentum"]
