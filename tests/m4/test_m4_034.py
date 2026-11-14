"""M4-034 acceptance tests: trial sample two (B-tier competition-dense).

Acceptance (tasks.json M4-034):
  - B-tier differentiated pack (competition chapter weight discernible)
  - structurally distinguishable from sample one
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from fixtures._generate_trial_specs import (
    generate_all,
    scenario_one,
    scenario_two,
)

pytestmark = pytest.mark.compose

TRIALS = Path(__file__).resolve().parents[2] / "assets" / "trial_specs"


def competition_share(meta: dict[str, object]) -> float:
    ids = meta["competition_task_ids"]
    assert isinstance(ids, list)
    count = meta["task_count"]
    assert isinstance(count, int)
    return len(ids) / count


def test_competition_weight_discernible() -> None:
    generate_all()
    one = json.loads((TRIALS / "one" / "meta.json").read_text(encoding="utf-8"))
    two = json.loads((TRIALS / "two" / "meta.json").read_text(encoding="utf-8"))
    assert two["tier"] == "B_red_ocean" and one["tier"] == "C_opportunity"
    assert competition_share(two) > 2 * competition_share(one), (
        "B-tier pack visibly competition-heavy vs C-tier"
    )


def test_structures_distinguishable() -> None:
    one, two = scenario_one(), scenario_two()
    outputs_one = {o for t in one.tasks for o in t.outputs}
    outputs_two = {o for t in two.tasks for o in t.outputs}
    assert outputs_one.isdisjoint(outputs_two), "no shared outputs"
    assert len(two.tasks) != len(one.tasks)
    titles_one = {t.title for t in one.tasks}
    titles_two = {t.title for t in two.tasks}
    assert titles_one.isdisjoint(titles_two)
