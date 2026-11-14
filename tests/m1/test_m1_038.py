"""M1-038 acceptance tests: lineage labeling tool (sample 50 clusters -> yaml).

Acceptance (tasks.json M1-038):
  - the labeling format covers the four classes: continued / split / merged / new
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

from tool.labeling import export_labeling_sheet

pytestmark = pytest.mark.compose

REPO_ROOT = Path(__file__).resolve().parents[2]
DSN = os.environ.get("FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")


def run(coro: Any) -> Any:
    return asyncio.run(coro)


@pytest.fixture(scope="module")
def replay_ready() -> None:
    """The tool reads the 30-day replay corpus; rebuild it if absent."""

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


@pytest.fixture(scope="module")
def sheet(replay_ready: None, tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    out = tmp_path_factory.mktemp("labeling") / "lineage-50.yaml"
    run(export_labeling_sheet(DSN, out, sample_size=50, seed=42))
    loaded: dict[str, Any] = yaml.safe_load(out.read_text(encoding="utf-8"))
    return loaded


def test_sheet_has_50_sampled_clusters(sheet: dict[str, Any]) -> None:
    assert len(sheet["clusters"]) == 50


def test_format_covers_four_lineage_classes(sheet: dict[str, Any]) -> None:
    classes = sheet["label_classes"]
    for required in ("continued", "split", "merged", "new"):
        assert required in classes, f"four-class coverage: missing {required}"
    assert "revived" in classes and "dormant" in classes  # 完整生命周期可标注


def test_each_cluster_entry_is_annotatable(sheet: dict[str, Any]) -> None:
    for entry in sheet["clusters"]:
        assert entry["cluster_id"]
        assert entry["keywords"], "annotator needs the member keywords"
        assert entry["timeline"], "annotator needs the system timeline"
        for event in entry["timeline"]:
            assert event["day"]
            assert event["system_kind"] in sheet["label_classes"]
            assert event["label"] is None, "label slot must start empty"


def test_sampling_is_deterministic(replay_ready: None, tmp_path: Path) -> None:
    out1, out2 = tmp_path / "a.yaml", tmp_path / "b.yaml"
    run(export_labeling_sheet(DSN, out1, sample_size=50, seed=42))
    run(export_labeling_sheet(DSN, out2, sample_size=50, seed=42))
    assert out1.read_text(encoding="utf-8") == out2.read_text(encoding="utf-8")


def test_revival_cluster_forced_into_sample(sheet: dict[str, Any]) -> None:
    """The engineered revival scenario must be reviewable in the sheet."""
    revival_entries = [
        e for e in sheet["clusters"] if "复活测试词" in e["keywords"]
    ]
    assert len(revival_entries) == 1
    kinds = [ev["system_kind"] for ev in revival_entries[0]["timeline"]]
    assert "revived" in kinds and "dormant" in kinds
