"""M4-015 acceptance tests: registry batch validator.

Acceptance (tasks.json M4-015):
  - full tech_choices list batch-validated -> pass-rate report
  - any channel unavailable -> validation unavailable state (distinct
    from nonexistent)
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import httpx
import pytest

from flint.domain.models import PackageStatus
from flint.registry.batch import Ecosystem, validate_batch
from flint.registry.npm_crates import check_crates, check_npm
from flint.registry.pypi import RegistryUnavailable, check_pypi
from flint.testing.replay import HttpReplay, fixture_path

pytestmark = pytest.mark.compose

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"
DAY = date(2026, 7, 28)


def fake_status(package: str, ecosystem: Ecosystem, exists: bool) -> PackageStatus:
    return PackageStatus(
        package=package, ecosystem=ecosystem, exists=exists,
        latest_stable="1.0.0" if exists else None, replaced_with=None,
        reason=None if exists else "not found",
    )


def test_full_list_pass_rate_report() -> None:
    def check(package: str, ecosystem: Ecosystem) -> PackageStatus:
        return fake_status(package, ecosystem, exists=package != "ghost")

    report = validate_batch(
        check,
        [("httpx", "pypi"), ("ghost", "pypi"), ("zustand", "npm"), ("serde", "crates")],
    )
    assert report.total == 4 and report.existing == 3
    assert report.missing == ["ghost"]
    assert report.pass_rate == pytest.approx(0.75)
    assert report.available is True


def test_unavailable_distinct_from_missing() -> None:
    def check(package: str, ecosystem: Ecosystem) -> PackageStatus:
        if package == "flaky":
            raise RegistryUnavailable("pypi returned 503 for flaky")
        return fake_status(package, ecosystem, exists=True)

    report = validate_batch(check, [("httpx", "pypi"), ("flaky", "pypi")])
    assert report.available is False, "one unavailable channel poisons the batch"
    assert report.missing == [], "unavailable never counted as missing"
    flaky = next(i for i in report.items if i.package == "flaky")
    assert flaky.state == "unavailable" and flaky.status is None
    assert flaky.detail is not None and "503" in flaky.detail


def test_empty_list_zero_rate() -> None:
    report = validate_batch(
        lambda p, e: fake_status(p, e, True), []
    )
    assert report.total == 0 and report.pass_rate == 0.0


def test_three_ecosystems_over_recorded_replay() -> None:
    replays = {
        eco: HttpReplay(fixture_path(FIXTURES, f"registry_{eco}", DAY), "replay")
        for eco in ("pypi", "npm", "crates")
    }
    clients: dict[str, httpx.Client] = {}
    for eco, replay in replays.items():
        replay.__enter__()
        clients[eco] = replay.client()
    try:
        def check(package: str, ecosystem: Ecosystem) -> PackageStatus:
            if ecosystem == "pypi":
                return check_pypi(clients["pypi"], package)
            if ecosystem == "npm":
                return check_npm(clients["npm"], package)
            return check_crates(clients["crates"], package)

        report = validate_batch(
            check,
            [
                ("httpx", "pypi"),
                ("flint-no-such-package", "pypi"),
                ("zustand", "npm"),
                ("serde", "crates"),
                ("flint-broken-registry", "crates"),
            ],
        )
    finally:
        for replay in replays.values():
            replay.__exit__(None, None, None)

    assert report.total == 5 and report.existing == 3
    assert report.missing == ["flint-no-such-package"]
    assert report.available is False, "crates 503 poisons availability"
    assert report.pass_rate == pytest.approx(0.6)
