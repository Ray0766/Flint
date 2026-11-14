"""M1-039 acceptance tests: lineage accuracy evaluation (>=90% assertion).

Acceptance (tasks.json M1-039):
  - outputs an accuracy report against the labels
  - <90% turns the scheduled run red (non-zero exit)

Ground truth per owner directive (2026-07-27): assets/labels.yaml is emitted
directly by the fixture generator from the constructed scenarios — the same
pools that author the fixtures compute each keyword's expected lifecycle.
"""
from __future__ import annotations

import asyncio
import os
from datetime import date
from pathlib import Path
from typing import Any

import asyncpg
import pytest
import yaml

from eval.lineage import EvalReport, evaluate

pytestmark = pytest.mark.compose

REPO_ROOT = Path(__file__).resolve().parents[2]
DSN = os.environ.get("FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")
LABELS = REPO_ROOT / "assets" / "labels.yaml"


def run(coro: Any) -> Any:
    return asyncio.run(coro)


@pytest.fixture(scope="module")
def replay_ready() -> None:
    async def count() -> int:
        conn = await asyncpg.connect(DSN)
        try:
            value: int = await conn.fetchval("SELECT count(*) FROM lineage_results")
            return value
        finally:
            await conn.close()

    if run(count()) < 30:
        from harness.replay30 import run_replay

        run_replay(
            days=30, end=date(2026, 7, 23), dsn=DSN,
            fixtures_root=REPO_ROOT / "fixtures",
            trace_dir=REPO_ROOT / "docs" / "trace" / "replay30",
        )


def test_labels_are_generator_ground_truth() -> None:
    payload = yaml.safe_load(LABELS.read_text(encoding="utf-8"))
    assert payload["source"] == "generator-ground-truth"
    assert len(payload["clusters"]) == 50
    revival = [c for c in payload["clusters"] if c["canonical"] == "复活测试词"]
    assert len(revival) == 1
    kinds = [(e["day"], e["kind"]) for e in revival[0]["expected"]]
    assert ("2026-06-24", "new") in kinds
    assert ("2026-07-10", "dormant") in kinds
    assert ("2026-07-15", "revived") in kinds


def test_accuracy_meets_90_percent_line(replay_ready: None) -> None:
    report = run(evaluate(DSN, LABELS))
    assert isinstance(report, EvalReport)
    assert report.total == 50
    assert report.accuracy >= 0.90, f"lineage accuracy {report.accuracy:.2%} below line"


def test_report_contains_per_kind_breakdown(replay_ready: None) -> None:
    report = run(evaluate(DSN, LABELS))
    text = report.render()
    assert "accuracy" in text
    for kind in ("new", "continued", "revived", "dormant"):
        assert kind in text
    assert str(report.matched) in text


def test_below_line_turns_red(replay_ready: None, tmp_path: Path) -> None:
    """Tamper half the expectations: accuracy must drop and exit go non-zero."""
    payload = yaml.safe_load(LABELS.read_text(encoding="utf-8"))
    for entry in payload["clusters"][:30]:
        entry["expected"] = [{"day": "2026-01-01", "kind": "new"}]
    bad = tmp_path / "labels-bad.yaml"
    bad.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    report = run(evaluate(DSN, bad))
    assert report.accuracy < 0.90

    from eval.lineage import main

    exit_code = main(["--labels", str(bad), "--min", "0.90", "--dsn", DSN])
    assert exit_code == 1, "scheduled run must turn red below the line"


def test_verify_cmd_path_green(replay_ready: None) -> None:
    from eval.lineage import main

    assert main(["--labels", str(LABELS), "--min", "0.90", "--dsn", DSN]) == 0
