"""M3-061 acceptance tests: golddocs asset (12 samples).

Acceptance (tasks.json M3-061):
  - five templates x2 + vibe_pack x2 = 12 samples with expected structure /
    channel placement / protection bits emitted by construction
  - offline completeness (reference closure / discriminated round trip /
    deterministic regeneration)
"""
from __future__ import annotations

import json
from pathlib import Path

from fixtures._generate_golddocs import build

REPO_ROOT = Path(__file__).resolve().parents[2]
ASSET = REPO_ROOT / "assets" / "golddocs" / "golddocs.json"


def samples() -> list[dict]:
    return list(json.loads(ASSET.read_text(encoding="utf-8"))["samples"])


def test_twelve_samples_across_six_templates() -> None:
    data = samples()
    assert len(data) == 12
    by_template: dict[str, list[str]] = {}
    for sample in data:
        by_template.setdefault(sample["template_id"], []).append(sample["variant"])
    assert sorted(by_template) == [
        "engineering", "generic", "grant", "startup", "thesis", "vibe_pack",
    ]
    assert all(sorted(v) == ["channels", "plain"] for v in by_template.values())
    vibe = [s for s in data if s["template_id"] == "vibe_pack"]
    assert all(s["audience"] == "ai_executor" for s in vibe)


def test_expected_carried_by_construction() -> None:
    for sample in samples():
        expected = sample["expected"]
        assert expected["sections"], "structure emitted"
        manifest = expected["channel_manifest"]
        assert manifest["facts"] == sample["facts"], "channel truth mirrors spec"
        assert manifest["price_entries"] == sample["price_entries"]
        assert manifest["profile_paths"] == sample["profile_paths"]
        assert expected["declaration_locked"] is True
        if sample["variant"] == "plain":
            assert manifest["price_entries"] == [] and manifest["profile_paths"] == []


def test_deterministic_regeneration() -> None:
    on_disk = json.loads(ASSET.read_text(encoding="utf-8"))
    assert on_disk == build()
    assert build() == build()


def test_sections_match_template_assets() -> None:
    from flint.compose.templates import load_template

    for sample in samples():
        spec, _sections = load_template(
            REPO_ROOT / "assets" / "templates" / f"{sample['template_id']}.yaml"
        )
        assert sample["expected"]["sections"] == [
            sid for sid, _r in spec.sections
        ], "structure truth = template declaration order"
