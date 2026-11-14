"""M4-011 acceptance tests: PyPI registry client over recorded replay.

Acceptance (tasks.json M4-011):
  - existence + latest_stable parsing via recorded replay (CI zero network)
  - 404 vs network-error discrimination (unavailable != nonexistent)
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import httpx
import pytest

from flint.registry.pypi import (
    RegistryUnavailable,
    check_pypi,
    latest_stable_of,
)
from flint.testing.replay import HttpReplay, fixture_path

pytestmark = pytest.mark.compose

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"
FIXTURE = fixture_path(FIXTURES, "registry_pypi", date(2026, 7, 28))


def test_exists_with_latest_stable_from_replay() -> None:
    with HttpReplay(FIXTURE, "replay") as replay:
        status = check_pypi(replay.client(), "httpx")
    assert status.exists is True
    assert status.ecosystem == "pypi"
    assert status.latest_stable == "0.28.1", (
        "rc excluded; 0.9.0 < 0.28.1 numerically (not lexically)"
    )
    assert status.replaced_with is None and status.reason is None


def test_404_means_nonexistent_not_unavailable() -> None:
    with HttpReplay(FIXTURE, "replay") as replay:
        status = check_pypi(replay.client(), "flint-no-such-package")
    assert status.exists is False
    assert status.latest_stable is None
    assert status.reason == "not found on PyPI"


def test_5xx_is_unavailable() -> None:
    with (
        HttpReplay(FIXTURE, "replay") as replay,
        pytest.raises(RegistryUnavailable, match="503"),
    ):
        check_pypi(replay.client(), "flint-broken-registry")


def test_network_error_is_unavailable() -> None:
    def explode(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    client = httpx.Client(transport=httpx.MockTransport(explode))
    with pytest.raises(RegistryUnavailable, match="unreachable"):
        check_pypi(client, "httpx")


def test_latest_stable_ordering_is_numeric() -> None:
    assert latest_stable_of(["0.9.0", "0.28.1", "0.29.0rc1"]) == "0.28.1"
    assert latest_stable_of(["1.0.0.post1", "2.0.0b1"]) is None
