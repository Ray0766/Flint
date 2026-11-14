"""M4-016 acceptance tests: registry unavailable -> whole-pack export ban.

Acceptance (tasks.json M4-016):
  - validation unavailable -> chapter GapHint + whole-pack export banned
    (quality gate registry=100%, not degradable)
  - human template path unaffected (fork assertion)
"""
from __future__ import annotations

import pytest

from flint.domain.models import PackageStatus
from flint.registry.batch import BatchItem, BatchReport
from flint.registry.gate import registry_pack_gate

pytestmark = pytest.mark.compose


def report(
    available: bool, missing: list[str], unavailable: list[str]
) -> BatchReport:
    items = [
        BatchItem(package=p, ecosystem="pypi", state="unavailable",
                  status=None, detail="503")
        for p in unavailable
    ] + [
        BatchItem(
            package=p, ecosystem="pypi", state="missing",
            status=PackageStatus(
                package=p, ecosystem="pypi", exists=False,
                latest_stable=None, replaced_with=None, reason="not found",
            ),
            detail="not found",
        )
        for p in missing
    ]
    existing = 0 if items else 1
    return BatchReport(
        items=items, total=len(items) or 1, existing=existing,
        missing=missing, pass_rate=0.0 if items else 1.0,
        available=available,
    )


def test_unavailable_bans_pack_with_gaphint() -> None:
    result = registry_pack_gate(
        report(available=False, missing=[], unavailable=["httpx"]),
        audience="ai_executor",
    )
    assert result.violations and "banned" in result.violations[0]
    assert "httpx" in result.violations[0]
    assert result.gap is not None
    assert result.gap.cause == "missing_data"
    assert "不可用 ≠ 不存在" in result.gap.missing_what


def test_missing_package_bans_without_unavailable_gap() -> None:
    result = registry_pack_gate(
        report(available=True, missing=["dead-pkg"], unavailable=[]),
        audience="ai_executor",
    )
    assert any("dead-pkg" in v for v in result.violations)
    assert result.gap is None, "missing goes to replacement flow, not the gap"


def test_clean_report_passes() -> None:
    result = registry_pack_gate(
        report(available=True, missing=[], unavailable=[]),
        audience="ai_executor",
    )
    assert result.violations == [] and result.gap is None


def test_human_path_unaffected() -> None:
    result = registry_pack_gate(
        report(available=False, missing=["dead-pkg"], unavailable=["httpx"]),
        audience="human_reader",
    )
    assert result.violations == [] and result.gap is None, (
        "human templates carry no lock manifest: fork never blocks them"
    )
