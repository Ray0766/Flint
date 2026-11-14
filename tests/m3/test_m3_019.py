"""M3-019 acceptance tests: outline (TemplateSpec -> section order).

Acceptance (tasks.json M3-019):
  - five templates each yield a deterministic outline; vibe_pack yields S1~S9
  - locale rule tables maintained per template (not translations)
"""
from __future__ import annotations

from pathlib import Path

from flint.compose.outline import outline_for

REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = REPO_ROOT / "assets" / "templates"


def test_five_templates_deterministic_outlines() -> None:
    expected_first = {
        "generic": "summary",
        "thesis": "abstract",
        "startup": "one_liner",
        "engineering": "goal",
        "grant": "significance",
    }
    for template_id, first in expected_first.items():
        outline = outline_for(TEMPLATES / f"{template_id}.yaml")
        assert outline[0] == first
        assert outline == outline_for(TEMPLATES / f"{template_id}.yaml"), (
            "deterministic"
        )
        assert len(outline) == len(set(outline)), "no duplicate sections"


def test_vibe_pack_outline_is_s1_to_s9() -> None:
    outline = outline_for(TEMPLATES / "vibe_pack.yaml")
    assert outline[0] == "S1_charter" and outline[-1] == "S9_escalation"
    assert len(outline) == 9


def test_locale_carried_per_template() -> None:
    from flint.compose.outline import outline_with_locale

    sections, locale = outline_with_locale(TEMPLATES / "generic.yaml")
    assert locale == "zh-CN"
    assert sections[0] == "summary"
