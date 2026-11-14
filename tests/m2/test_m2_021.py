"""M2-021 acceptance tests: QueryBuilder protocol assembly (four steps).

Acceptance (tasks.json M2-021):
  - build() emits compliant Query lists for support/refute/landscape
  - signature matches the frozen protocol verbatim (mypy strict backstop)
"""
from __future__ import annotations

from pathlib import Path

from flint.domain.models import JSON, Query
from flint.llm.cache import LLMJudgmentCache
from flint.norm.terms import load_term_map
from flint.retrieval.query_builder import FourStepQueryBuilder

REPO_ROOT = Path(__file__).resolve().parents[2]

EXPANSION: JSON = {
    "synonyms": ["all-solid-state battery"],
    "broader": ["energy storage"],
    "narrower": ["sulfide electrolyte"],
}


class ScriptedProvider:
    def generate(self, prompt: str, tools: list[JSON] | None) -> object:
        raise NotImplementedError

    def generate_structured(self, prompt: str, schema: JSON, max_retries: int) -> JSON:
        if "扩展" in prompt:
            return EXPANSION
        return {"english": "fallback term"}


def make_builder() -> FourStepQueryBuilder:
    return FourStepQueryBuilder(
        term_map=load_term_map(REPO_ROOT / "assets" / "term-map.yaml"),
        provider=ScriptedProvider(),  # type: ignore[arg-type]
        cache=LLMJudgmentCache(),
    )


def test_support_intent_builds_expanded_paper_queries() -> None:
    queries = make_builder().build(["固态电池"], intent="support", locale="zh-CN")
    assert queries and all(isinstance(q, Query) for q in queries)
    assert all(q.intent == "support" for q in queries)
    texts = [q.text for q in queries]
    assert any("solid-state battery" in t for t in texts), "standardized via term map"
    assert any("all-solid-state battery" in t for t in texts), "expansion terms included"
    assert all("paper" in q.source_kinds for q in queries)


def test_refute_intent_activates_template_families() -> None:
    queries = make_builder().build(["固态电池"], intent="refute", locale="zh-CN")
    assert len(queries) >= 5, "five refute families per standardized term"
    assert all(q.intent == "refute" for q in queries)
    assert any("retraction" in q.text for q in queries)


def test_landscape_intent_targets_competitor_sources() -> None:
    queries = make_builder().build(["固态电池"], intent="landscape", locale="zh-CN")
    assert all(q.intent == "landscape" for q in queries)
    assert any("product" in q.source_kinds for q in queries)


def test_locale_passthrough_and_dedup() -> None:
    queries = make_builder().build(["固态电池", "固態電池"], intent="support", locale="zh-CN")
    assert all(q.locale == "zh-CN" for q in queries)
    texts = [q.text for q in queries]
    assert len(texts) == len(set(texts)), "duplicate standardized terms collapse"
