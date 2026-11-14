"""M3-029 acceptance tests: five human templates run-through.

Acceptance (tasks.json M3-029):
  - one golden example per template: outline + ratio + check_questions all
    pass
  - any two templates produce distinguishable structures (templates really
    drive output)
"""
from __future__ import annotations

from itertools import combinations
from pathlib import Path

from flint.compose.human_templates import scaffold_deliverable

REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = REPO_ROOT / "assets" / "templates"
HUMAN_IDS = ("generic", "thesis", "startup", "engineering", "grant")


def test_each_template_scaffolds_cleanly() -> None:
    for template_id in HUMAN_IDS:
        scaffold = scaffold_deliverable(
            TEMPLATES / f"{template_id}.yaml", deliverable_id=f"d-{template_id}"
        )
        assert scaffold.template_id == template_id
        section_ids = [s.section_id for s in scaffold.sections]
        assert [b.section_id for b in scaffold.blocks] == section_ids, (
            "one heading block per section in outline order"
        )
        for section in scaffold.sections:
            assert section.check_questions, "every section carries its checks"
            assert section.word_budget[0] > 0
            assert section.word_budget[1] >= section.word_budget[0]
        assert [b.order for b in scaffold.blocks] == list(range(len(scaffold.blocks)))
        assert all(b.author == "system" for b in scaffold.blocks)


def test_any_two_templates_distinguishable() -> None:
    structures = {
        template_id: [
            s.section_id
            for s in scaffold_deliverable(
                TEMPLATES / f"{template_id}.yaml", deliverable_id="d-x"
            ).sections
        ]
        for template_id in HUMAN_IDS
    }
    for a, b in combinations(HUMAN_IDS, 2):
        assert structures[a] != structures[b], f"{a} vs {b} indistinguishable"


def test_budget_scales_with_share() -> None:
    scaffold = scaffold_deliverable(
        TEMPLATES / "startup.yaml", deliverable_id="d-s"
    )
    budgets = {s.section_id: s.word_budget for s in scaffold.sections}
    assert budgets["solution"][1] > budgets["one_liner"][1], (
        "larger share -> larger budget"
    )
