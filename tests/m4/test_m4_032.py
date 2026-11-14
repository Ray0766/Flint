"""M4-032 acceptance tests: Z-line pass-rate registration.

Acceptance (tasks.json M4-032):
  - oneshot pass-rate Z line configurable (initial value awaits owner,
    registered in S4 channel)
  - trial reports judged by Z; report-only while the line is unset
"""
from __future__ import annotations

from pathlib import Path

import pytest

from eval.pass_rate import (
    ZLineConfigError,
    pass_rate_report,
    z_line_from_env,
)

pytestmark = pytest.mark.compose

REPO_ROOT = Path(__file__).resolve().parents[2]

OUTCOMES = [("T-1", True), ("T-2", True), ("T-3", False), ("T-4", True)]


def test_unset_line_reports_only_never_draws_the_line() -> None:
    report = pass_rate_report(OUTCOMES, z_line=None)
    assert report.rate == pytest.approx(0.75)
    assert report.z_line is None
    assert report.verdict == "report_only"


def test_set_line_judges() -> None:
    assert pass_rate_report(OUTCOMES, z_line=0.7).verdict == "pass"
    assert pass_rate_report(OUTCOMES, z_line=0.8).verdict == "fail"


def test_env_config_parse_and_bounds() -> None:
    assert z_line_from_env({}) is None
    assert z_line_from_env({"FLINT_Z_LINE": ""}) is None
    assert z_line_from_env({"FLINT_Z_LINE": "0.85"}) == pytest.approx(0.85)
    with pytest.raises(ZLineConfigError, match="not a number"):
        z_line_from_env({"FLINT_Z_LINE": "high"})
    with pytest.raises(ZLineConfigError, match="out of"):
        z_line_from_env({"FLINT_Z_LINE": "1.5"})


def test_s4_registration_filed_in_owner_channel() -> None:
    issue_doc = (REPO_ROOT / "docs" / "v0.4-问题单.md").read_text(
        encoding="utf-8"
    )
    assert "Z 线" in issue_doc and "FLINT_Z_LINE" in issue_doc, (
        "open question registered for owner (S4 channel via issue ledger)"
    )
