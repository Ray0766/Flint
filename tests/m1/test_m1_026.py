"""M1-026 acceptance tests: lineage step 4 — dormancy & revival.

Acceptance (tasks.json M1-026):
  - N days without heat -> dormant
  - revival is flagged reactivated and reuses the same cluster ID
"""
from __future__ import annotations

from datetime import date

from flint.lineage.s4 import RevivalEvent, apply_dormancy, detect_revivals

TODAY = date(2026, 7, 23)


def make_states() -> dict[str, tuple[str, date]]:
    """cluster_id -> (status, last_active)"""
    return {
        "c-fresh": ("active", date(2026, 7, 22)),       # 1 day quiet
        "c-edge": ("active", date(2026, 7, 9)),         # exactly 14 days quiet
        "c-quiet": ("active", date(2026, 7, 1)),        # 22 days quiet
        "c-already-dormant": ("dormant", date(2026, 5, 1)),
        "c-merged": ("merged", date(2026, 5, 1)),       # merged is terminal
    }


def test_n_days_without_heat_becomes_dormant() -> None:
    to_dormant = apply_dormancy(make_states(), today=TODAY, dormant_after_days=14)
    assert to_dormant == ["c-edge", "c-quiet"]


def test_threshold_is_configurable() -> None:
    strict = apply_dormancy(make_states(), today=TODAY, dormant_after_days=2)
    assert strict == ["c-edge", "c-quiet"]  # c-fresh still inside 2 days
    lax = apply_dormancy(make_states(), today=TODAY, dormant_after_days=30)
    assert lax == []


def test_dormant_and_merged_never_reprocessed() -> None:
    to_dormant = apply_dormancy(make_states(), today=TODAY, dormant_after_days=1)
    assert "c-already-dormant" not in to_dormant
    assert "c-merged" not in to_dormant


def test_revival_reuses_id_and_flags_reactivated() -> None:
    statuses = {cid: status for cid, (status, _) in make_states().items()}
    events = detect_revivals(
        matched_cluster_ids=["c-fresh", "c-already-dormant"], statuses=statuses
    )
    assert events == [
        RevivalEvent(cluster_id="c-already-dormant", reactivated=True)
    ], "only dormant hits revive; the ID is reused, never re-minted"


def test_no_revival_without_dormant_hit() -> None:
    statuses = {cid: status for cid, (status, _) in make_states().items()}
    assert detect_revivals(["c-fresh"], statuses) == []
