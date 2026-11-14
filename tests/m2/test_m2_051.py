"""M2-051 acceptance tests: Gate1 regression harness (gold offline full run).

Acceptance (tasks.json M2-051):
  - 20 gold cases fully green offline (zero network, S2-7)
  - per-case trace (inputs list + verdict basis) produced
"""
from __future__ import annotations

import json
import socket
from pathlib import Path

import pytest

from harness.gate1_regress import TRACE_DIR, main

REPO_ROOT = Path(__file__).resolve().parents[2]
ASSET = REPO_ROOT / "assets" / "goldcases" / "goldcases.json"


def case_ids() -> list[str]:
    return [
        str(c["case_id"])
        for c in json.loads(ASSET.read_text(encoding="utf-8"))["cases"]
    ]


def test_offline_full_run_green_with_network_disabled(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """S2-7 零联网：socket 禁用下全跑必须绿——不是口头承诺，是硬断言。"""

    def deny(*args: object, **kwargs: object) -> object:
        raise AssertionError("network use is forbidden in the gold regression (S2-7)")

    monkeypatch.setattr(socket, "socket", deny)
    monkeypatch.setattr(socket, "create_connection", deny)
    assert main() == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["cases"] == 20
    assert summary["verdict_matches"] == 20
    assert summary["all_satisfied_matches"] == 20
    assert summary["macro_precision"] == 1.0
    assert summary["macro_recall"] == 1.0
    assert summary["alignment_consistency"] == 1.0
    assert summary["missed_d_rate"] == 0.0
    assert summary["green"] is True


def test_per_case_traces_produced() -> None:
    main()
    ids = case_ids()
    assert len(ids) == 20
    for case_id in ids:
        path = TRACE_DIR / f"{case_id}.md"
        assert path.exists(), f"missing trace for {case_id}"
        text = path.read_text(encoding="utf-8")
        assert "## inputs 清单" in text
        assert "## 判定依据" in text
        assert "比对：一致" in text, f"{case_id} must report gold agreement"


def test_traces_deterministic_across_reruns() -> None:
    main()
    first = {
        p.name: p.read_text(encoding="utf-8") for p in TRACE_DIR.glob("gold-*.md")
    }
    main()
    second = {
        p.name: p.read_text(encoding="utf-8") for p in TRACE_DIR.glob("gold-*.md")
    }
    assert first == second, "trace regeneration is byte-stable (no timestamps)"
