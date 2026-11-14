"""M2-017 acceptance tests: query term standardization step.

Acceptance (tasks.json M2-017):
  - zh->en goes through the term map with the hit-rate hook emitting output
  - map misses go to an LLM proposal that lands in the judgment cache
"""
from __future__ import annotations

from pathlib import Path

from flint.domain.models import JSON
from flint.llm.cache import LLMJudgmentCache
from flint.norm.terms import load_term_map
from flint.retrieval.terms import StandardizedTerm, standardize_terms

REPO_ROOT = Path(__file__).resolve().parents[2]


class ProposalProvider:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def generate(self, prompt: str, tools: list[JSON] | None) -> object:
        raise NotImplementedError

    def generate_structured(self, prompt: str, schema: JSON, max_retries: int) -> JSON:
        self.calls.append(prompt)
        return {"english": "proposed academic term"}


def setup() -> tuple[object, ProposalProvider, LLMJudgmentCache]:
    term_map = load_term_map(REPO_ROOT / "assets" / "term-map.yaml")
    return term_map, ProposalProvider(), LLMJudgmentCache()


def test_mapped_terms_use_the_map_not_llm() -> None:
    term_map, provider, cache = setup()
    results = standardize_terms(["大模型", "固态电池"], term_map, provider, cache)  # type: ignore[arg-type]
    assert [r.english for r in results] == ["large language model", "solid-state battery"]
    assert all(r.source == "term_map" for r in results)
    assert provider.calls == [], "map hits never touch the LLM"


def test_hit_rate_hook_emits_output() -> None:
    term_map, provider, cache = setup()
    standardize_terms(["大模型", "未收录冷门词"], term_map, provider, cache)  # type: ignore[arg-type]
    stats = term_map.stats()  # type: ignore[attr-defined]
    assert stats["lookups"] >= 2 and stats["hits"] >= 1 and stats["misses"] >= 1


def test_map_miss_goes_to_llm_and_caches() -> None:
    term_map, provider, cache = setup()
    first = standardize_terms(["未收录冷门词"], term_map, provider, cache)  # type: ignore[arg-type]
    assert first[0].english == "proposed academic term"
    assert first[0].source == "llm"
    assert len(provider.calls) == 1
    assert "未收录冷门词" in provider.calls[0]

    second = standardize_terms(["未收录冷门词"], term_map, provider, cache)  # type: ignore[arg-type]
    assert second[0].english == "proposed academic term"
    assert len(provider.calls) == 1, "second miss hits the judgment cache"
    assert cache.hits == 1


def test_result_type_keeps_original() -> None:
    term_map, provider, cache = setup()
    result = standardize_terms(["大模型"], term_map, provider, cache)[0]  # type: ignore[arg-type]
    assert isinstance(result, StandardizedTerm)
    assert result.original == "大模型"
