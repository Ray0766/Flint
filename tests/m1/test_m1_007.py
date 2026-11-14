"""M1-007 acceptance tests: CI pipeline (lint + mypy + unit + compose smoke).

Acceptance (tasks.json M1-007):
  - PR check runs four stages, all green (E9 order: lint -> mypy strict ->
    unit tests -> compose integration smoke)

The pipeline itself runs on the forge; this suite pins its structure so a
drive-by edit cannot silently drop a stage, reorder the chain, or detach the
pipeline from the locked toolchain. All four stage commands are exactly the
ones used locally (S7 global gate + compose smoke split by marker).
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CI_PATH = REPO_ROOT / ".github" / "workflows" / "ci.yaml"


def ci_text() -> str:
    assert CI_PATH.is_file(), "missing .github/workflows/ci.yaml"
    return CI_PATH.read_text(encoding="utf-8")


def test_four_stages_present_in_e9_order() -> None:
    text = ci_text()
    jobs = ["lint:", "typecheck:", "unit:", "compose-smoke:"]
    positions = [text.index(j) for j in jobs]  # raises if any stage is missing
    assert positions == sorted(positions), "stages must appear in E9 order"


def test_stage_chain_is_sequential() -> None:
    text = ci_text()
    assert "needs: lint" in text
    assert "needs: typecheck" in text
    assert "needs: unit" in text


def test_stage_commands_match_local_gate() -> None:
    text = ci_text()
    assert "ruff check ." in text
    assert "mypy --strict flint" in text
    assert 'pytest -q -m "not compose"' in text
    assert 'pytest -q -m compose' in text
    assert "docker compose up -d --wait postgres redis" in text


def test_pipeline_pins_python_and_lockfile() -> None:
    text = ci_text()
    assert '"3.11"' in text or "'3.11'" in text
    assert "requirements.lock" in text


def test_compose_marker_registered_and_used() -> None:
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "compose:" in pyproject, "compose marker must be registered"
    m1_002 = (REPO_ROOT / "tests" / "m1" / "test_m1_002.py").read_text(encoding="utf-8")
    assert "pytest.mark.compose" in m1_002, "compose smoke tests must carry the marker"
