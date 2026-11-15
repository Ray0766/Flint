"""NARROW-05 · Weibo and Google Trends are frozen (`DEC-066`): closed by default, not deleted.

Two ways in existed:

1. `flint/sources/registry.py` enabled every registered source unless a flag said
   otherwise, so the two frozen sources counted as on;
2. `fixtures/_record_cn_real.py`, the only code that fetches a live source, fetched
   all four whenever the owner authorised a run.

The daily ingest itself only replays fixtures (no live path is wired today), so it is
left alone; the replays of recorded Weibo and Google Trends days keep working.

Closing the way in is checked together with "nothing was deleted": the adapters stay
registered, and an explicit flag still turns a frozen source back on, which is what
an owner ruling to unfreeze would flip.
"""
from __future__ import annotations

import importlib
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from flint.config import FeatureFlags, InMemoryFlagStore
from flint.sources.registry import FROZEN_SOURCE_IDS, SourceRegistry, source_flag_name

ALL = ("arxiv", "ghtrend", "gtrends", "weibo")


def _registry() -> tuple[SourceRegistry, FeatureFlags]:
    flags = FeatureFlags(store=InMemoryFlagStore(), now=lambda: 0.0)
    registry = SourceRegistry(flags=flags)
    for sid in ALL:
        registry.register(sid, lambda: None)  # type: ignore[arg-type, return-value]
    return registry, flags


def test_the_frozen_pair_is_exactly_weibo_and_google_trends() -> None:
    assert frozenset({"weibo", "gtrends"}) == FROZEN_SOURCE_IDS


def test_frozen_sources_are_off_unless_a_flag_turns_them_on() -> None:
    registry, flags = _registry()

    assert registry.enabled_source_ids() == ["arxiv", "ghtrend"]
    assert registry.source_ids() == list(ALL), "closing is not unregistering"

    flags.set(source_flag_name("weibo"), True)
    assert registry.is_enabled("weibo") is True
    assert registry.is_enabled("gtrends") is False


def test_the_live_recorder_skips_frozen_sources_even_when_authorised(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    recorder = importlib.import_module("fixtures._record_cn_real")
    fetched: list[str] = []

    def fake_record(source_id: str, day: date, throttle: Any) -> dict[str, Any]:
        fetched.append(source_id)
        return {"source": source_id, "outcome": "ok"}

    monkeypatch.setattr(recorder, "_record_one", fake_record)
    monkeypatch.setattr(recorder, "RECEIPT", tmp_path / "receipt.json")

    assert recorder.main(["--owner-is-here", "--day", "2026-11-15"]) == 0

    assert fetched == ["ghtrend", "arxiv"]
    import json

    results = json.loads((tmp_path / "receipt.json").read_text(encoding="utf-8"))["results"]
    frozen = {r["source"]: r for r in results if r["outcome"] == "frozen"}
    assert set(frozen) == {"weibo", "gtrends"}
    assert all("DEC-066" in r["detail"] for r in frozen.values())
