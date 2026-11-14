"""M3-018 acceptance tests: vibe_pack section family asset (S1~S9).

Acceptance (tasks.json M3-018):
  - S1~S9 fixed section family + human_digest attachment slot (not in AI
    context)
  - Ratio unit=tokens with dual-unit mutual exclusion validated
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from fixtures._generate_templates import build_vibe_pack
from flint.compose.templates import load_template

REPO_ROOT = Path(__file__).resolve().parents[2]
VIBE = REPO_ROOT / "assets" / "templates" / "vibe_pack.yaml"

EXPECTED_SECTIONS = [
    "S1_charter", "S2_invariants", "S3_contracts", "S4_decision_log",
    "S5_task_dag", "S6_context_manifest", "S7_verification",
    "S8_progress_ledger", "S9_escalation",
]


def test_nine_section_family_tokens_unit() -> None:
    spec, sections = load_template(VIBE)
    assert spec.template_id == "vibe_pack"
    assert spec.audience == "ai_executor"
    assert [sid for sid, _ratio in spec.sections] == EXPECTED_SECTIONS
    assert all(ratio.unit == "tokens" for _sid, ratio in spec.sections)
    total = sum(ratio.share for _sid, ratio in spec.sections)
    assert total == pytest.approx(1.0)
    assert all(s.check_questions for s in sections)


def test_s5_task_dag_gets_largest_share() -> None:
    spec, _sections = load_template(VIBE)
    shares = dict(spec.sections)
    assert shares["S5_task_dag"].share == max(r.share for _s, r in spec.sections), (
        "task DAG is the heart of an executor pack"
    )


def test_human_digest_attachment_outside_ai_context() -> None:
    payload = yaml.safe_load(VIBE.read_text(encoding="utf-8"))
    attachments = payload["attachments"]
    assert len(attachments) == 1
    assert attachments[0]["attachment_id"] == "human_digest"
    assert attachments[0]["in_ai_context"] is False


def test_dual_unit_mutual_exclusion_rejected(tmp_path: Path) -> None:
    payload = build_vibe_pack()
    payload["sections"][0]["ratio"]["unit"] = "words"
    bad = tmp_path / "bad.yaml"
    bad.write_text(yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8")
    with pytest.raises(ValueError, match="unit"):
        load_template(bad)


def test_asset_matches_generator() -> None:
    on_disk = yaml.safe_load(VIBE.read_text(encoding="utf-8"))
    assert on_disk == build_vibe_pack()
