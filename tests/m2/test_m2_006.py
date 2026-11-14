"""M2-006 acceptance tests: idempotent judgment-call cache.

Acceptance (tasks.json M2-006):
  - relevance judging and cluster naming cache by content hash; hits skip
    the call (counter assertions)
  - generation-class calls are never cached (negative assertion)
"""
from __future__ import annotations

from flint.domain.models import JSON
from flint.llm.cache import LLMJudgmentCache


def make_compute(counter: list[int], payload: JSON) -> object:
    def compute() -> JSON:
        counter[0] += 1
        return dict(payload)

    return compute


def test_judgment_cached_by_content_hash() -> None:
    cache = LLMJudgmentCache()
    calls = [0]
    compute = make_compute(calls, {"relevant": True})

    first = cache.cached("judgment", "relevance|q1|doc-abc", compute)  # type: ignore[arg-type]
    second = cache.cached("judgment", "relevance|q1|doc-abc", compute)  # type: ignore[arg-type]
    assert first == second == {"relevant": True}
    assert calls[0] == 1, "cache hit must not re-invoke the model"
    assert cache.hits == 1 and cache.misses == 1


def test_different_content_misses() -> None:
    cache = LLMJudgmentCache()
    calls = [0]
    cache.cached("judgment", "naming|kw-a", make_compute(calls, {"name": "簇A"}))  # type: ignore[arg-type]
    cache.cached("judgment", "naming|kw-b", make_compute(calls, {"name": "簇B"}))  # type: ignore[arg-type]
    assert calls[0] == 2
    assert cache.misses == 2 and cache.hits == 0


def test_generation_class_never_cached() -> None:
    cache = LLMJudgmentCache()
    calls = [0]
    compute = make_compute(calls, {"draft": "章节文本"})
    cache.cached("generation", "section|same-key", compute)  # type: ignore[arg-type]
    cache.cached("generation", "section|same-key", compute)  # type: ignore[arg-type]
    assert calls[0] == 2, "generation calls always recompute"
    assert cache.hits == 0 and cache.misses == 0, "generation traffic bypasses counters"


def test_cached_result_is_isolated_copy() -> None:
    cache = LLMJudgmentCache()
    calls = [0]
    first = cache.cached("judgment", "k", make_compute(calls, {"relevant": True}))  # type: ignore[arg-type]
    first["relevant"] = False  # 调用方污染自己的副本
    second = cache.cached("judgment", "k", make_compute(calls, {"relevant": True}))  # type: ignore[arg-type]
    assert second == {"relevant": True}, "cache payload must not be mutated by callers"
