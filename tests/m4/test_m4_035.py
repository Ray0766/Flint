"""M4-035 acceptance tests: trial sample three (cross-category) + index.

Acceptance (tasks.json M4-035):
  - cross-category scenario (M0 precedent regression) produces a pack
  - three-sample bound index
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from fixtures._generate_trial_specs import generate_all

pytestmark = pytest.mark.compose

TRIALS = Path(__file__).resolve().parents[2] / "assets" / "trial_specs"


def test_cross_category_pack() -> None:
    generate_all()
    meta = json.loads(
        (TRIALS / "three" / "meta.json").read_text(encoding="utf-8")
    )
    assert meta["case_id"] == "gold-C-04"
    assert "×" in meta["category"], "cross-category pair recorded"
    assert meta["gates"] == {
        "dag_errors": 0, "registry_violations": 0, "export_allowed": True,
    }
    assert (TRIALS / "three" / "pack.zip").stat().st_size > 0


def test_three_sample_index() -> None:
    generate_all()
    index = json.loads((TRIALS / "index.json").read_text(encoding="utf-8"))
    samples = index["samples"]
    assert [s["name"] for s in samples] == ["one", "two", "three"]
    for sample in samples:
        assert (TRIALS / str(sample["path"])).is_file(), sample["path"]
        assert sample["gates"]["export_allowed"] is True
    tiers = {s["tier"] for s in samples}
    assert tiers == {"C_opportunity", "B_red_ocean"}, (
        "C / B / cross-category-C mix per card plan"
    )
