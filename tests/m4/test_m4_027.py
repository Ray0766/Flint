"""M4-027 acceptance tests: vibe additional export gate assembly.

Acceptance (tasks.json M4-027):
  - vibe_pack export gate = audit-11 blocking AND DagValidator pass AND
    registry 100% (triple conjunction)
  - any failure -> EXPORT_BLOCKED with categorized detail
"""
from __future__ import annotations

import pytest

from flint.domain.models import DagReport
from flint.registry.gate import RegistryGateResult
from flint.spec.export_gate import vibe_export_gate

pytestmark = pytest.mark.compose

CLEAN_DAG = DagReport(acyclic=True, orphans=[], unreachable=[], errors=[])
CLEAN_REGISTRY = RegistryGateResult(violations=[], gap=None)


def test_all_three_clean_allows() -> None:
    verdict = vibe_export_gate([], CLEAN_DAG, CLEAN_REGISTRY)
    assert verdict.allowed is True and verdict.violations == []


def test_each_leg_blocks_with_category() -> None:
    review = vibe_export_gate(["b-1"], CLEAN_DAG, CLEAN_REGISTRY)
    assert not review.allowed
    assert review.violations == ["review: blocking review open on block b-1"]

    dag = vibe_export_gate(
        [], DagReport(acyclic=False, orphans=["T-9"], unreachable=[],
                      errors=["cycle: A -> B -> A"]),
        CLEAN_REGISTRY,
    )
    assert not dag.allowed
    assert "dag: cycle: A -> B -> A" in dag.violations
    assert "dag: orphan terminal T-9" in dag.violations

    registry = vibe_export_gate(
        [], CLEAN_DAG,
        RegistryGateResult(violations=["httpx unavailable"], gap=None),
    )
    assert not registry.allowed
    assert registry.violations == ["registry: httpx unavailable"]


def test_triple_failure_lists_all_categories() -> None:
    verdict = vibe_export_gate(
        ["b-1"],
        DagReport(acyclic=True, orphans=[], unreachable=["T-x"], errors=[]),
        RegistryGateResult(violations=["dead-pkg missing"], gap=None),
    )
    assert not verdict.allowed
    prefixes = {v.split(":")[0] for v in verdict.violations}
    assert prefixes == {"review", "dag", "registry"}, (
        "conjunction failure itemized per category, nothing swallowed"
    )
