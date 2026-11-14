"""M4-033 acceptance tests: trial sample one (gold C-tier, full chain).

Acceptance (tasks.json M4-033):
  - goldcase C-tier scenario -> proposal -> vibe_pack full-chain pack
  - pack passes every gate (dag/registry/S2-8)
"""
from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pytest

from eval.pack_integrity import run_pack_integrity_eval
from fixtures._generate_trial_specs import (
    build_trial_pack,
    generate_all,
    scenario_one,
)

pytestmark = pytest.mark.compose

TRIALS = Path(__file__).resolve().parents[2] / "assets" / "trial_specs"


def test_full_chain_produces_pack_on_disk() -> None:
    generate_all()
    payload = (TRIALS / "one" / "pack.zip").read_bytes()
    meta = json.loads((TRIALS / "one" / "meta.json").read_text(encoding="utf-8"))
    assert meta["case_id"] == "gold-C-01"
    assert meta["tier"] == "C_opportunity"
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        claude_md = archive.read("CLAUDE.md").decode("utf-8")
    assert "方言语音标注平台" in claude_md
    for header in [f"## S{i} " for i in range(1, 10)]:
        assert header in claude_md, f"{header} chapter missing"


def test_pack_passes_all_gates() -> None:
    payload, meta = build_trial_pack(scenario_one())
    gates = meta["gates"]
    assert gates == {
        "dag_errors": 0, "registry_violations": 0, "export_allowed": True,
    }
    integrity = run_pack_integrity_eval(payload)
    assert integrity.all_ok, [r for r in integrity.rows if not r.ok]


def test_tasks_json_reconciles_with_scenario() -> None:
    payload, _meta = build_trial_pack(scenario_one())
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        data = json.loads(archive.read("tasks.json").decode("utf-8"))
    ids = [t["task_id"] for t in data["tasks"]]
    assert ids == [t.task_id for t in scenario_one().tasks]
    assert data["dag_report"]["acyclic"] is True
