"""M2-022 acceptance tests: RelevanceJudge (small-model hit rate).

Acceptance (tasks.json M2-022):
  - hit_rate samples top-k abstracts for judging (replay-style scripted LLM)
  - theta_rel configurable (initial 0.6, S4 Open Question on file)
"""
from __future__ import annotations

from datetime import UTC, date, datetime

from flint.domain.models import JSON, Doc, Query
from flint.llm.cache import LLMJudgmentCache
from flint.retrieval.relevance import THETA_REL, LLMRelevanceJudge

FETCHED = datetime(2026, 7, 28, 12, 0, 0, tzinfo=UTC).isoformat()
QUERY = Query(text="solid state battery", source_kinds=["paper"], intent="support", locale="en")


def make_doc(i: int, title: str) -> Doc:
    return Doc(
        doc_id=f"doc-{i}", source_id="crossref", kind="paper", title=title,
        url=f"https://a/{i}", published_at=date(2026, 1, 1),
        meta={"fetched_at": FETCHED}, origin="retrieved", access="public",
    )


class ScriptedProvider:
    def __init__(self, relevant_markers: list[str]) -> None:
        self.relevant_markers = relevant_markers
        self.calls: list[str] = []

    def generate(self, prompt: str, tools: list[JSON] | None) -> object:
        raise NotImplementedError

    def generate_structured(self, prompt: str, schema: JSON, max_retries: int) -> JSON:
        self.calls.append(prompt)
        abstract = prompt.split("文摘（doc_id=", 1)[1]  # 只看文摘段，防查询/指令文本串扰
        return {"relevant": any(m in abstract for m in self.relevant_markers)}


def test_theta_rel_initial_value() -> None:
    assert THETA_REL == 0.6


def test_hit_rate_over_sampled_docs() -> None:
    provider = ScriptedProvider(relevant_markers=["battery"])
    judge = LLMRelevanceJudge(provider=provider, cache=LLMJudgmentCache())  # type: ignore[arg-type]
    docs = [
        make_doc(0, "solid state battery survey"),
        make_doc(1, "battery electrolyte study"),
        make_doc(2, "unrelated drone economics"),
        make_doc(3, "battery cost curve"),
    ]
    rate = judge.hit_rate(QUERY, docs)
    assert rate == 0.75
    assert len(provider.calls) == 4


def test_top_k_sampling_caps_judgments() -> None:
    provider = ScriptedProvider(relevant_markers=["battery"])
    judge = LLMRelevanceJudge(provider=provider, cache=LLMJudgmentCache(), top_k=2)  # type: ignore[arg-type]
    docs = [make_doc(i, f"battery {i}") for i in range(6)]
    rate = judge.hit_rate(QUERY, docs)
    assert rate == 1.0
    assert len(provider.calls) == 2, "only the top-k sample is judged"


def test_empty_docs_rate_zero() -> None:
    judge = LLMRelevanceJudge(
        provider=ScriptedProvider([]), cache=LLMJudgmentCache()  # type: ignore[arg-type]
    )
    assert judge.hit_rate(QUERY, []) == 0.0


def test_judgment_cached_per_query_doc_pair() -> None:
    provider = ScriptedProvider(relevant_markers=["battery"])
    cache = LLMJudgmentCache()
    judge = LLMRelevanceJudge(provider=provider, cache=cache)  # type: ignore[arg-type]
    docs = [make_doc(0, "battery a")]
    judge.hit_rate(QUERY, docs)
    judge.hit_rate(QUERY, docs)
    assert len(provider.calls) == 1
    assert cache.hits == 1
