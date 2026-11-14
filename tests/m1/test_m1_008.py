"""M1-008 acceptance tests: HTTP record/replay mechanism (respx, E12).

Acceptance (tasks.json M1-008):
  - the same test passes in networked record mode AND offline replay mode

The "network" in record mode is an injected transport, so this suite itself
never leaves the machine (S2-7: CI never goes online). The identical request
+ assertion block runs twice: once recording through the injected transport,
once replaying purely from the written fixture file.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import httpx
import pytest

from flint.testing.replay import HttpReplay, ReplayMiss, fixture_path, load_fixture

DAY = date(2026, 7, 26)
URL = "https://api.example.com/trends?day=2026-07-26"


def fake_network() -> httpx.MockTransport:
    def responder(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "api.example.com"
        return httpx.Response(
            200,
            json={"keywords": ["solid-state battery", "agent memory"]},
            headers={"content-type": "application/json"},
        )

    return httpx.MockTransport(responder)


def run_scenario(client: httpx.Client) -> None:
    """The shared test body — must hold in both modes."""
    resp = client.get(URL)
    assert resp.status_code == 200
    assert resp.json()["keywords"] == ["solid-state battery", "agent memory"]


def test_record_then_replay_pass_same_assertions(tmp_path: Path) -> None:
    fixture = fixture_path(tmp_path, source_id="example", day=DAY)

    with (
        HttpReplay(fixture, mode="record", live_transport=fake_network()) as session,
        session.client() as client,
    ):
        run_scenario(client)
    assert fixture.exists(), "record mode must persist the fixture file"
    assert fixture == tmp_path / "example" / "2026-07-26.json", "E12 layout: {source}/{day}.json"

    with HttpReplay(fixture, mode="replay") as session, session.client() as client:
        run_scenario(client)  # identical assertions, zero network access


def test_recorded_fixture_captures_exchange_fields(tmp_path: Path) -> None:
    fixture = fixture_path(tmp_path, source_id="example", day=DAY)
    with (
        HttpReplay(fixture, mode="record", live_transport=fake_network()) as session,
        session.client() as client,
    ):
        client.get(URL)
    exchanges = load_fixture(fixture)
    assert len(exchanges) == 1
    ex = exchanges[0]
    assert ex.method == "GET"
    assert ex.url == URL
    assert ex.status_code == 200
    assert "solid-state battery" in ex.body_text


def test_replay_rejects_unrecorded_request(tmp_path: Path) -> None:
    """Silent pass-through would defeat S2-7; an unrecorded URL must raise."""
    fixture = fixture_path(tmp_path, source_id="example", day=DAY)
    with (
        HttpReplay(fixture, mode="record", live_transport=fake_network()) as session,
        session.client() as client,
    ):
        client.get(URL)

    with (
        HttpReplay(fixture, mode="replay") as session,
        session.client() as client,
        pytest.raises(ReplayMiss),
    ):
        client.get("https://api.example.com/other-endpoint")


def test_record_appends_multiple_exchanges(tmp_path: Path) -> None:
    fixture = fixture_path(tmp_path, source_id="example", day=DAY)

    def responder(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=f"echo:{request.url.path}")

    with HttpReplay(
        fixture, mode="record", live_transport=httpx.MockTransport(responder)
    ) as session, session.client() as client:
        client.get("https://api.example.com/a")
        client.get("https://api.example.com/b")

    exchanges = load_fixture(fixture)
    assert [e.url for e in exchanges] == [
        "https://api.example.com/a",
        "https://api.example.com/b",
    ]

    with HttpReplay(fixture, mode="replay") as session, session.client() as client:
        assert client.get("https://api.example.com/a").text == "echo:/a"
        assert client.get("https://api.example.com/b").text == "echo:/b"


def test_replay_missing_fixture_file_raises(tmp_path: Path) -> None:
    fixture = fixture_path(tmp_path, source_id="ghost", day=DAY)
    with pytest.raises(FileNotFoundError):
        HttpReplay(fixture, mode="replay").__enter__()
