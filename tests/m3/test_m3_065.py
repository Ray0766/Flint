"""M3-065 acceptance tests: M3 regression harness (doc line offline).

Acceptance (tasks.json M3-065):
  - 12 gold samples fully green offline (zero network, S2-7)
  - per-sample trace (inputs + composition basis) produced, byte-stable
"""
from __future__ import annotations

import json
import socket
from pathlib import Path

import pytest

from harness.m3_regress import TRACE_DIR, main

REPO_ROOT = Path(__file__).resolve().parents[2]
GOLDDOCS = REPO_ROOT / "assets" / "golddocs" / "golddocs.json"


def sample_ids() -> list[str]:
    return [
        str(s["sample_id"])
        for s in json.loads(GOLDDOCS.read_text(encoding="utf-8"))["samples"]
    ]


def test_offline_full_run_green_with_network_disabled(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def deny(*args: object, **kwargs: object) -> object:
        raise AssertionError("network use forbidden in doc regression (S2-7)")

    monkeypatch.setattr(socket, "socket", deny)
    monkeypatch.setattr(socket, "create_connection", deny)
    assert main() == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["samples"] == 12
    assert summary["green"] == 12
    assert summary["all_green"] is True
    assert "pdf" in summary["delegated_coverage"], "delegation disclosed, not hidden"


def test_per_sample_traces_with_composition_basis() -> None:
    main()
    ids = sample_ids()
    assert len(ids) == 12
    for sample_id in ids:
        path = TRACE_DIR / f"{sample_id}.md"
        assert path.exists(), sample_id
        text = path.read_text(encoding="utf-8")
        assert "## inputs 清单" in text
        assert "## 组稿依据" in text
        assert "结论：green" in text


def test_traces_byte_stable() -> None:
    main()
    first = {p.name: p.read_text(encoding="utf-8")
             for p in TRACE_DIR.glob("golddoc-*.md")}
    main()
    second = {p.name: p.read_text(encoding="utf-8")
              for p in TRACE_DIR.glob("golddoc-*.md")}
    assert first == second
