"""M4-013 acceptance tests: version lock linkage.

Acceptance (tasks.json M4-013):
  - validation passed -> versions locked into the pack lock manifest
  - latest_stable vs requested conflict -> lock wins + note slot
"""
from __future__ import annotations

import pytest

from flint.domain.models import PackageStatus
from flint.registry.lock import LockError, lock_versions, render_lock

pytestmark = pytest.mark.compose


def ok(package: str, stable: str | None) -> PackageStatus:
    return PackageStatus(
        package=package, ecosystem="pypi", exists=True,
        latest_stable=stable, replaced_with=None, reason=None,
    )


def test_verified_packages_locked_into_manifest() -> None:
    entries = lock_versions(
        [ok("httpx", "0.28.1"), ok("tenacity", "9.1.2")],
        requested={"httpx": "0.28.1"},
    )
    assert [(e.package, e.locked_version) for e in entries] == [
        ("httpx", "0.28.1"), ("tenacity", "9.1.2"),
    ]
    assert entries[0].note is None, "no conflict, no note"
    manifest = render_lock(entries)
    assert "pypi: httpx==0.28.1" in manifest
    assert "pypi: tenacity==9.1.2" in manifest


def test_conflict_lock_wins_with_note() -> None:
    entries = lock_versions(
        [ok("httpx", "0.29.0")], requested={"httpx": "0.28.1"}
    )
    entry = entries[0]
    assert entry.locked_version == "0.28.1", "lock wins over latest_stable"
    assert entry.note is not None and "0.29.0" in entry.note
    assert "0.28.1" in render_lock(entries)


def test_nonexistent_package_never_locked() -> None:
    ghost = PackageStatus(
        package="ghost", ecosystem="pypi", exists=False,
        latest_stable=None, replaced_with=None, reason="not found",
    )
    with pytest.raises(LockError, match="ghost"):
        lock_versions([ghost], requested={})


def test_no_stable_version_rejected() -> None:
    with pytest.raises(LockError, match="no stable"):
        lock_versions([ok("beta-only", None)], requested={})
