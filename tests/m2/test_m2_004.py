"""M2-004 acceptance tests: prompt version library (file-as-version + hash).

Acceptance (tasks.json M2-004):
  - prompts/ loader emits a content hash for GenerationRecord.prompt_version
  - changing a prompt means a NEW file: in-place content change is rejected
"""
from __future__ import annotations

from pathlib import Path

import pytest

from flint.llm.prompts import (
    PromptDriftError,
    load_prompt,
    update_lock,
    verify_lock,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
PROMPTS_DIR = REPO_ROOT / "prompts"


def test_seed_prompts_exist_and_load() -> None:
    for name in ("gate1_verdict@1", "relevance_judge@1", "cluster_naming@1"):
        prompt = load_prompt(PROMPTS_DIR, name)
        assert prompt.text.strip(), f"{name} must carry real prompt text"
        assert prompt.version.startswith(f"{name}#")
        assert len(prompt.version.split("#")[1]) == 12, "12-hex content hash suffix"


def test_version_is_content_hash_stable() -> None:
    first = load_prompt(PROMPTS_DIR, "gate1_verdict@1")
    second = load_prompt(PROMPTS_DIR, "gate1_verdict@1")
    assert first.version == second.version


def test_repo_lock_is_current() -> None:
    """Committed prompts must match the committed lock — the CI-facing guard."""
    assert verify_lock(PROMPTS_DIR) == []


def test_in_place_change_rejected(tmp_path: Path) -> None:
    d = tmp_path / "prompts"
    d.mkdir()
    (d / "demo@1.md").write_text("判定以下方向", encoding="utf-8")
    update_lock(d)
    assert verify_lock(d) == []

    (d / "demo@1.md").write_text("判定以下方向（改动了措辞）", encoding="utf-8")
    drift = verify_lock(d)
    assert drift == ["demo@1"], "in-place edit must surface as drift"
    with pytest.raises(PromptDriftError):
        load_prompt(d, "demo@1", enforce_lock=True)


def test_new_file_is_the_sanctioned_path(tmp_path: Path) -> None:
    d = tmp_path / "prompts"
    d.mkdir()
    (d / "demo@1.md").write_text("v1 文本", encoding="utf-8")
    update_lock(d)
    (d / "demo@2.md").write_text("v2 文本（新文件新版本）", encoding="utf-8")
    drift = verify_lock(d)
    assert drift == ["demo@2"], "unlocked new file is flagged until lock update"
    update_lock(d)
    assert verify_lock(d) == []
    assert load_prompt(d, "demo@1").text == "v1 文本", "old version stays intact"


def test_missing_prompt_raises() -> None:
    with pytest.raises(FileNotFoundError):
        load_prompt(PROMPTS_DIR, "no_such_prompt@9")
