"""M4-012 acceptance tests: npm/crates registry clients.

Acceptance (tasks.json M4-012):
  - npm registry and crates.io share the protocol surface (one recorded
    fixture per source)
  - PackageStatus discrimination consistent across the three ecosystems
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import date
from pathlib import Path

import httpx
import pytest

from flint.domain.models import PackageStatus
from flint.registry.npm_crates import check_crates, check_npm
from flint.registry.pypi import RegistryUnavailable, check_pypi
from flint.testing.replay import HttpReplay, fixture_path

pytestmark = pytest.mark.compose

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"
DAY = date(2026, 7, 28)

Check = Callable[[httpx.Client, str], PackageStatus]

ECOSYSTEMS: list[tuple[str, Check, str, str]] = [
    ("registry_pypi", check_pypi, "httpx", "0.28.1"),
    ("registry_npm", check_npm, "zustand", "5.0.3"),
    ("registry_crates", check_crates, "serde", "1.0.219"),
]


@pytest.mark.parametrize(
    ("source", "check", "package", "expected_stable"),
    ECOSYSTEMS,
    ids=[e[0] for e in ECOSYSTEMS],
)
def test_exists_with_stable_version(
    source: str, check: Check, package: str, expected_stable: str
) -> None:
    with HttpReplay(fixture_path(FIXTURES, source, DAY), "replay") as replay:
        status = check(replay.client(), package)
    assert status.exists is True
    assert status.latest_stable == expected_stable, (
        "pre-release never wins latest_stable"
    )


@pytest.mark.parametrize(
    ("source", "check"),
    [(e[0], e[1]) for e in ECOSYSTEMS],
    ids=[e[0] for e in ECOSYSTEMS],
)
def test_404_discrimination_consistent(source: str, check: Check) -> None:
    with HttpReplay(fixture_path(FIXTURES, source, DAY), "replay") as replay:
        status = check(replay.client(), "flint-no-such-package")
    assert status.exists is False
    assert status.latest_stable is None
    assert status.reason is not None and "not found" in status.reason


@pytest.mark.parametrize(
    ("source", "check"),
    [(e[0], e[1]) for e in ECOSYSTEMS],
    ids=[e[0] for e in ECOSYSTEMS],
)
def test_5xx_unavailable_consistent(source: str, check: Check) -> None:
    with (
        HttpReplay(fixture_path(FIXTURES, source, DAY), "replay") as replay,
        pytest.raises(RegistryUnavailable, match="503"),
    ):
        check(replay.client(), "flint-broken-registry")
