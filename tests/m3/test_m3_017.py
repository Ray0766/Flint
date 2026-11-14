"""M3-017 acceptance tests: five human template rule tables.

Acceptance (tasks.json M3-017):
  - five templates (generic/thesis/startup/engineering/grant) as assets with
    sections + Ratio + check_questions
  - Ratio unit=words and shares sum to 1 (validated)
"""
from __future__ import annotations

from pathlib import Path

import pytest

from fixtures._generate_templates import build_human
from flint.compose.templates import load_template
from flint.domain.models import Ratio, TemplateSpec

REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = REPO_ROOT / "assets" / "templates"
HUMAN_IDS = ("generic", "thesis", "startup", "engineering", "grant")


def test_five_templates_load_as_frozen_spec() -> None:
    for template_id in HUMAN_IDS:
        spec, sections = load_template(TEMPLATES / f"{template_id}.yaml")
        assert isinstance(spec, TemplateSpec)
        assert spec.template_id == template_id
        assert spec.audience == "human_reader"
        assert spec.locale == "zh-CN"
        assert len(spec.sections) >= 6
        for _section_id, ratio in spec.sections:
            assert isinstance(ratio, Ratio)
            assert ratio.unit == "words"
            assert ratio.max_words >= ratio.min_words > 0
        assert all(s.check_questions for s in sections), "every section checked"


def test_shares_sum_to_one() -> None:
    for template_id in HUMAN_IDS:
        spec, _sections = load_template(TEMPLATES / f"{template_id}.yaml")
        total = sum(ratio.share for _sid, ratio in spec.sections)
        assert total == pytest.approx(1.0), template_id


def test_bad_share_sum_rejected(tmp_path: Path) -> None:
    import yaml

    payload = build_human("generic")
    payload["sections"][0]["ratio"]["share"] = 0.5
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="share"):
        load_template(bad)


def test_assets_match_generator() -> None:
    import yaml

    for template_id in HUMAN_IDS:
        on_disk = yaml.safe_load(
            (TEMPLATES / f"{template_id}.yaml").read_text(encoding="utf-8")
        )
        assert on_disk == build_human(template_id)
