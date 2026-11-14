"""M4-038 acceptance tests: M4 regression harness.

Acceptance (tasks.json M4-038):
  - registry/dag/export-gate/pack-integrity/trial five lines run together
    offline
  - per-pack trace output byte-stable
"""
from __future__ import annotations

import pytest

from fixtures._generate_trial_specs import generate_all
from harness.m4_regress import TRACE_DIR, main, run_m4_regress

pytestmark = pytest.mark.compose


def test_five_lines_all_green_offline() -> None:
    generate_all()
    report = run_m4_regress()
    assert [l.name for l in report.lines] == [
        "registry", "dag", "export-gate", "pack-integrity", "trial",
    ]
    assert report.all_ok, [l for l in report.lines if not l.ok]
    assert "delegated" in report.lines[2].detail, (
        "DB/endpoint surfaces disclosed as delegated, not silently claimed"
    )


def test_per_pack_traces_byte_stable() -> None:
    generate_all()
    first = run_m4_regress()
    snapshots = {p: p.read_bytes() for p in first.traces}
    assert {p.name for p in first.traces} == {"one.md", "two.md", "three.md"}
    second = run_m4_regress()
    for path in second.traces:
        assert path.read_bytes() == snapshots[path], f"{path.name} drifted"
    for payload in snapshots.values():
        text = payload.decode("utf-8")
        assert "2026-" not in text, "zero timestamps in trace"
        assert "一次通过率=1.0" in text


def test_exit_code_semantics(capsys: pytest.CaptureFixture[str]) -> None:
    generate_all()
    assert main() == 0
    out = capsys.readouterr().out
    assert out.count("PASS") == 5 and "FAIL" not in out


def test_trace_carries_card_table() -> None:
    generate_all()
    run_m4_regress()
    trace_two = (TRACE_DIR / "two.md").read_text(encoding="utf-8")
    assert "gold-B-01" in trace_two
    assert trace_two.count("| T-0") == 7, "all seven cards in table"
    assert "竞争面卡：T-02, T-03, T-05, T-06" in trace_two
