"""M4-042 acceptance tests: non-blocking memo digestion batch.

Acceptance (tasks.json M4-042):
  - codeable items dispatched: drill7 mypy fix confirmed + S7 global gate
    widened (flint eval harness) landed in the Makefile
  - per-item disposition list recorded (non-codeable items reserved for
    the owner revision channel)
"""
from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.compose

REPO_ROOT = Path(__file__).resolve().parents[2]
DIGEST = (REPO_ROOT / "docs" / "v0.4-digest.md").read_text(encoding="utf-8")
MAKEFILE = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")


def test_makefile_gate_widened_to_eval_and_harness() -> None:
    assert "mypy --strict flint eval harness" in MAKEFILE
    assert "mypy --strict flint &&" not in MAKEFILE, "old narrow gate removed"


def test_drill7_fix_stands_without_ignore() -> None:
    drill7 = (REPO_ROOT / "harness" / "drill7.py").read_text(encoding="utf-8")
    fix_line = next(
        line for line in drill7.splitlines() if "from_url" in line
    )
    assert "Redis.from_url" in fix_line, "class-method form (typed), not module fn"
    assert "type: ignore" not in fix_line, "memo fix carries no ignore"


def test_digest_records_every_disposition() -> None:
    for pointer in (
        "claim_idempotency", "parse_last_event_id", "Redis.from_url",
        "draft_section_with_channels", "StoredLedgerVersionConflict",
        "flint-pdf:69",
    ):
        assert pointer in DIGEST, f"disposition pointer missing: {pointer}"
    assert DIGEST.count("owner 修订通道") >= 4, "3 reserved rows + legend"
    assert DIGEST.count("开放硬化项") >= 3, "2 open rows + legend"
    assert "append-only" in DIGEST, "source memo ledger never trimmed"


def test_owner_channel_items_untouched() -> None:
    claude_md = (REPO_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    assert "ruff check . && mypy --strict flint && pytest -q" in claude_md, (
        "CLAUDE.md S7 line is owner-channel: this batch must not edit it"
    )
    issue_doc = (REPO_ROOT / "docs" / "v0.4-问题单.md").read_text(encoding="utf-8")
    assert "S7 全局门由 `mypy --strict flint` 扩为" in issue_doc, (
        "original memo preserved in the append-only issue ledger"
    )
