"""M2-018 acceptance tests: synonym / broader / narrower expansion step.

Acceptance (tasks.json M2-018):
  - synonyms / broader / narrower 1~2 each (schema-validated structured output)
  - expansion failure degrades to the original term without blocking
"""
from __future__ import annotations

from flint.domain.models import JSON
from flint.llm.cache import LLMJudgmentCache
from flint.llm.structured import StructuredOutputExhausted
from flint.retrieval.expand import Expansion, expand_term


class ScriptedProvider:
    def __init__(self, payload: JSON | None = None, exhaust: bool = False) -> None:
        self.payload = payload
        self.exhaust = exhaust
        self.calls = 0

    def generate(self, prompt: str, tools: list[JSON] | None) -> object:
        raise NotImplementedError

    def generate_structured(self, prompt: str, schema: JSON, max_retries: int) -> JSON:
        self.calls += 1
        if self.exhaust:
            raise StructuredOutputExhausted(1 + max_retries, ["$.synonyms: required"])
        assert self.payload is not None
        return self.payload


GOOD: JSON = {
    "synonyms": ["all-solid-state battery", "ASSB"],
    "broader": ["energy storage"],
    "narrower": ["sulfide electrolyte battery", "oxide electrolyte battery", "extra-one"],
}


def test_expansion_capped_at_two_each() -> None:
    provider = ScriptedProvider(payload=GOOD)
    expansion = expand_term("solid-state battery", provider, LLMJudgmentCache())  # type: ignore[arg-type]
    assert isinstance(expansion, Expansion)
    assert expansion.synonyms == ["all-solid-state battery", "ASSB"]
    assert expansion.broader == ["energy storage"]
    assert expansion.narrower == ["sulfide electrolyte battery", "oxide electrolyte battery"], (
        "each family capped at 2 (v0.2 SS4.1: 各 1~2 条)"
    )
    assert expansion.degraded is False


def test_failure_degrades_to_original_term() -> None:
    expansion = expand_term(
        "solid-state battery", ScriptedProvider(exhaust=True), LLMJudgmentCache()  # type: ignore[arg-type]
    )
    assert expansion.degraded is True
    assert expansion.synonyms == [] and expansion.broader == [] and expansion.narrower == []
    assert expansion.term == "solid-state battery", "original term survives, never blocks"


def test_expansion_is_judgment_cached() -> None:
    provider = ScriptedProvider(payload=GOOD)
    cache = LLMJudgmentCache()
    expand_term("solid-state battery", provider, cache)  # type: ignore[arg-type]
    expand_term("solid-state battery", provider, cache)  # type: ignore[arg-type]
    assert provider.calls == 1, "identical term expansion hits the cache"
