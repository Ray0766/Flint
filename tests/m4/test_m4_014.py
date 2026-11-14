"""M4-014 acceptance tests: [replaced] marker.

Acceptance (tasks.json M4-014):
  - nonexistent package -> replacement suggestion + [replaced: reason]
    marked into the S3 pin line
  - no replacement available -> GapHint (never guess a package name)
"""
from __future__ import annotations

import pytest

from flint.domain.models import GapHint, PackageStatus
from flint.registry.replace import (
    ReplaceError,
    Replacement,
    pin_line,
    resolve_replacement,
)

pytestmark = pytest.mark.compose


def missing(package: str) -> PackageStatus:
    return PackageStatus(
        package=package, ecosystem="pypi", exists=False,
        latest_stable=None, replaced_with=None, reason="not found on PyPI",
    )


def existing(package: str, stable: str) -> PackageStatus:
    return PackageStatus(
        package=package, ecosystem="pypi", exists=True,
        latest_stable=stable, replaced_with=None, reason=None,
    )


def test_replacement_marked_into_s3_line() -> None:
    result = resolve_replacement(
        missing("dead-pkg"), [existing("live-pkg", "2.1.0")]
    )
    assert isinstance(result, Replacement)
    assert result.status.replaced_with == "live-pkg"
    assert result.status.exists is False
    line = pin_line(result)
    assert line.startswith("- live-pkg 2.1.0 [replaced: dead-pkg → live-pkg")
    assert "not found on PyPI" in line


def test_cross_ecosystem_candidate_not_used() -> None:
    npm_candidate = PackageStatus(
        package="live-js", ecosystem="npm", exists=True,
        latest_stable="1.0.0", replaced_with=None, reason=None,
    )
    result = resolve_replacement(missing("dead-pkg"), [npm_candidate])
    assert isinstance(result, GapHint)


def test_no_candidate_gaphint_never_guesses() -> None:
    result = resolve_replacement(missing("dead-pkg"), [])
    assert isinstance(result, GapHint)
    assert result.cause == "missing_data"
    assert result.action == "ask_user"
    assert "dead-pkg" in result.missing_what
    assert result.suggested_sources, "recovery paths offered, no invented names"


def test_nonexistent_candidates_skipped() -> None:
    result = resolve_replacement(missing("dead-pkg"), [missing("also-dead")])
    assert isinstance(result, GapHint)


def test_existing_package_rejected() -> None:
    with pytest.raises(ReplaceError, match="nonexistent"):
        resolve_replacement(existing("fine-pkg", "1.0.0"), [])
