"""M4-036 acceptance tests: executor-simulation trial harness.

Acceptance (tasks.json M4-036):
  - three packs simulated card by card: context_refs loadable +
    verify_cmd form executable + DAG schedulable
  - oneshot pass-rate report on the M4-032 Z caliber
"""
from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pytest

from eval.pass_rate import PassRateReport
from fixtures._generate_trial_specs import generate_all
from harness.spec_trial import TrialRunResult, run_trials, simulate_pack

pytestmark = pytest.mark.compose

TRIALS = Path(__file__).resolve().parents[2] / "assets" / "trial_specs"


def test_three_packs_all_cards_green() -> None:
    generate_all()
    outcome = run_trials(TRIALS)
    results = outcome["results"]
    assert isinstance(results, list) and [
        r.pack_name for r in results
    ] == ["one", "two", "three"]
    for result in results:
        assert isinstance(result, TrialRunResult)
        assert result.schedulable, f"{result.pack_name} frontier stalled"
        assert result.schedule_rounds >= 2, "chain depth exercised"
        bad = [c for c in result.cards if not c.oneshot]
        assert bad == [], f"{result.pack_name}: {bad}"


def test_pass_rate_z_caliber() -> None:
    generate_all()
    overall_unset = run_trials(TRIALS)["overall"]
    assert isinstance(overall_unset, PassRateReport)
    assert overall_unset.rate == 1.0
    assert overall_unset.verdict == "report_only", "Z unset -> never judged"
    overall_judged = run_trials(TRIALS, z_line=0.9)["overall"]
    assert isinstance(overall_judged, PassRateReport)
    assert overall_judged.verdict == "pass"
    assert overall_judged.total == sum(
        len(r.cards) for r in run_trials(TRIALS)["results"]  # type: ignore[union-attr]
    )


def tamper_tasks_json(payload: bytes, mutate: str) -> bytes:
    with zipfile.ZipFile(io.BytesIO(payload)) as src:
        data = json.loads(src.read("tasks.json").decode("utf-8"))
        if mutate == "ghost-ref":
            data["tasks"][0]["context_refs"] = ["ghost.md#缺失"]
        else:
            data["tasks"][0]["verify_cmd"] = "bash run.sh"
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as dst:
            for name in src.namelist():
                body = (
                    json.dumps(data, ensure_ascii=False).encode("utf-8")
                    if name == "tasks.json" else src.read(name)
                )
                dst.writestr(name, body)
    return buffer.getvalue()


def test_defective_pack_detected_per_face() -> None:
    generate_all()
    payload = (TRIALS / "one" / "pack.zip").read_bytes()

    ghost = simulate_pack(tamper_tasks_json(payload, "ghost-ref"), "ghost")
    first = ghost.cards[0]
    assert first.refs_ok is False and "ghost.md" in first.notes[0]
    assert ghost.pass_report.rate < 1.0

    badcmd = simulate_pack(tamper_tasks_json(payload, "bad-cmd"), "badcmd")
    first = badcmd.cards[0]
    assert first.verify_ok is False
    assert any("pytest" in n for n in first.notes)


def test_anchor_resolution_inside_pack() -> None:
    generate_all()
    result = simulate_pack((TRIALS / "one" / "pack.zip").read_bytes(), "one")
    assert all(c.refs_ok for c in result.cards), (
        "contracts/models.py#TaskSpec and CLAUDE.md#S7 resolve in-pack"
    )
