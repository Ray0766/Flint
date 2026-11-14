"""M2-008 acceptance tests: first fixture batch for the six evidence sources.

Acceptance (tasks.json M2-008):
  - every source has >=3 query samples loadable by the replay layer
  - rate-limit and failure scenarios, one each per source
"""
from __future__ import annotations

from pathlib import Path

from flint.testing.replay import HttpReplay, load_fixture

REPO_ROOT = Path(__file__).resolve().parents[2]
ROOT = REPO_ROOT / "fixtures" / "evidence6"
SOURCES = ["paper", "patent", "news", "competitor", "funding", "pricing"]
QUERIES = ["solid-state-battery", "agent-memory", "low-altitude-economy"]


def test_three_query_samples_per_source_loadable() -> None:
    for source in SOURCES:
        for query in QUERIES:
            path = ROOT / source / f"{query}.json"
            assert path.is_file(), f"missing {path}"
            exchanges = load_fixture(path)
            assert exchanges and exchanges[0].status_code == 200
            with HttpReplay(path, mode="replay"):
                pass


def test_rate_limit_and_failure_scenarios_per_source() -> None:
    for source in SOURCES:
        limited = load_fixture(ROOT / source / "ratelimit.json")
        assert any(e.status_code == 429 for e in limited), f"{source}: no 429 sample"
        failed = load_fixture(ROOT / source / "failure.json")
        assert any(e.status_code >= 500 for e in failed), f"{source}: no 5xx sample"


def test_payload_shapes_match_native_apis() -> None:
    paper = load_fixture(ROOT / "paper" / "solid-state-battery.json")[0]
    assert '"DOI"' in paper.body_text and '"is-referenced-by-count"' in paper.body_text

    patent = load_fixture(ROOT / "patent" / "solid-state-battery.json")[0]
    assert '"family_size"' in patent.body_text and '"legal_status"' in patent.body_text

    news = load_fixture(ROOT / "news" / "solid-state-battery.json")[0]
    assert '"articles"' in news.body_text and '"media_tier"' in news.body_text

    competitor = load_fixture(ROOT / "competitor" / "solid-state-battery.json")[0]
    assert '"results"' in competitor.body_text and '"last_activity"' in competitor.body_text

    funding = load_fixture(ROOT / "funding" / "solid-state-battery.json")[0]
    assert '"organizations"' in funding.body_text

    pricing = load_fixture(ROOT / "pricing" / "solid-state-battery.json")[0]
    assert "pricing" in pricing.url
    assert "plan" in pricing.body_text.lower()


def test_pricing_includes_contact_us_low_confidence_case() -> None:
    """B5: JS 渲染/contact-us 页面是常态——语料必须包含这一形态。"""
    bodies = [
        load_fixture(ROOT / "pricing" / f"{q}.json")[0].body_text.lower()
        for q in QUERIES
    ]
    assert any("contact us" in b or "contact sales" in b for b in bodies)
    assert any("$" in b or "¥" in b for b in bodies), "at least one page with numbers"
