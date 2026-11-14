"""M1-018 acceptance tests: CN-EN term map v0 (first 200 entries + loader).

Acceptance (tasks.json M1-018):
  - yaml loads with validation
  - the hit-rate stats hook produces output
"""
from __future__ import annotations

from pathlib import Path

import pytest

from flint.norm.terms import TermMap, TermMapError, load_term_map

REPO_ROOT = Path(__file__).resolve().parents[2]
TERM_MAP_PATH = REPO_ROOT / "assets" / "term-map.yaml"


@pytest.fixture(scope="module")
def term_map() -> TermMap:
    return load_term_map(TERM_MAP_PATH)


def test_loads_at_least_200_entries(term_map: TermMap) -> None:
    assert term_map.size >= 200


def test_lookup_zh_to_en_canonical(term_map: TermMap) -> None:
    assert term_map.lookup("人工智能") == "artificial intelligence"
    assert term_map.lookup("固态电池") == "solid-state battery"


def test_lookup_alias_and_en_identity(term_map: TermMap) -> None:
    assert term_map.lookup("llm") == "large language model"
    assert term_map.lookup("large language model") == "large language model"


def test_lookup_applies_clean_normalization(term_map: TermMap) -> None:
    """Keys pass through the A3 stage-one cleaner: width/case/t2s variants hit."""
    assert term_map.lookup("ＡＩ") == "artificial intelligence"
    assert term_map.lookup("人工智慧") == "artificial intelligence"


def test_miss_returns_none(term_map: TermMap) -> None:
    assert term_map.lookup("不存在的词条xyz") is None


def test_hit_rate_stats_hook_produces_output() -> None:
    tm = load_term_map(TERM_MAP_PATH)
    tm.lookup("人工智能")
    tm.lookup("固态电池")
    tm.lookup("不存在的词条xyz")
    stats = tm.stats()
    assert stats["hits"] == 2
    assert stats["misses"] == 1
    assert stats["lookups"] == 3
    assert stats["hit_rate"] == pytest.approx(2 / 3)


def test_validation_rejects_duplicate_keys(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "version: 0\nterms:\n"
        "  - zh: 人工智能\n    en: artificial intelligence\n"
        "  - zh: 人工智能\n    en: machine intelligence\n",
        encoding="utf-8",
    )
    with pytest.raises(TermMapError, match="duplicate"):
        load_term_map(bad)


def test_validation_rejects_missing_fields(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("version: 0\nterms:\n  - zh: 只有中文\n", encoding="utf-8")
    with pytest.raises(TermMapError, match="en"):
        load_term_map(bad)


def test_validation_rejects_non_list_aliases(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "version: 0\nterms:\n  - zh: 词\n    en: word\n    aliases: notalist\n",
        encoding="utf-8",
    )
    with pytest.raises(TermMapError, match="aliases"):
        load_term_map(bad)
