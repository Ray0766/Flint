"""M2-016 acceptance tests: refute-material channel (retraction/archived/shutdown).

Acceptance (tasks.json M2-016):
  - retraction records, archived repos, product-shutdown news: one replay
    case each
  - material carries the refute-intent marker for B2 consumption
"""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from flint.evidence.negative import (
    NegativeSignal,
    fetch_archived_projects,
    fetch_retractions,
    fetch_shutdown_news,
)
from flint.testing.replay import HttpReplay

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "fixtures" / "evidence6"
NOW = datetime(2026, 7, 28, 12, 0, 0, tzinfo=UTC)
QUERY = "solid state battery"


def replay(path: Path, fetch: object) -> list[NegativeSignal]:
    with HttpReplay(path, mode="replay") as session, session.client() as client:
        return fetch(client, QUERY, lambda: NOW)  # type: ignore[operator]


def test_retraction_material_replay() -> None:
    signals = replay(FIXTURES / "paper" / "retraction-solid-state-battery.json", fetch_retractions)
    assert signals, "retraction material must exist"
    for signal in signals:
        assert signal.kind == "retraction"
        assert signal.doc.kind == "paper"
        assert signal.doc.meta["retraction_of"], "points at the retracted DOI"


def test_archived_project_material_replay() -> None:
    signals = replay(
        FIXTURES / "competitor" / "archived-solid-state-battery.json", fetch_archived_projects
    )
    assert signals
    for signal in signals:
        assert signal.kind == "archived"
        assert signal.doc.meta["archived"] is True


def test_shutdown_news_material_replay() -> None:
    signals = replay(FIXTURES / "news" / "shutdown-solid-state-battery.json", fetch_shutdown_news)
    assert signals
    for signal in signals:
        assert signal.kind == "shutdown"
        assert signal.doc.kind == "news"


def test_all_material_carries_refute_intent_marker() -> None:
    """B2 消费面：三类素材统一带 refute 意图标记与溯源三字段。"""
    all_signals = (
        replay(FIXTURES / "paper" / "retraction-solid-state-battery.json", fetch_retractions)
        + replay(FIXTURES / "competitor" / "archived-solid-state-battery.json", fetch_archived_projects)
        + replay(FIXTURES / "news" / "shutdown-solid-state-battery.json", fetch_shutdown_news)
    )
    assert len(all_signals) >= 3
    for signal in all_signals:
        assert signal.doc.meta["refute_intent"] is True
        assert signal.doc.meta["negative_kind"] == signal.kind
        assert signal.doc.meta["fetched_at"] == NOW.isoformat()
        assert signal.doc.url and signal.doc.source_id
