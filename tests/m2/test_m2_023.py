"""M2-023 acceptance tests: rewrite-recheck loop (true-nothing vs missed-query).

Acceptance (tasks.json M2-023):
  - below theta_rel triggers rewrite-recheck, cap R=2 rounds (counted)
  - only after recheck still low may "insufficient" be emitted (boundary
    cases in both directions)
"""
from __future__ import annotations

from datetime import UTC, date, datetime

from flint.domain.models import Doc, Query
from flint.retrieval.rewrite_loop import MAX_REWRITES, RetrievalOutcome, search_with_rewrite

FETCHED = datetime(2026, 7, 28, 12, 0, 0, tzinfo=UTC).isoformat()


def make_doc(i: int) -> Doc:
    return Doc(
        doc_id=f"doc-{i}", source_id="crossref", kind="paper", title=f"t{i}",
        url=f"https://a/{i}", published_at=date(2026, 1, 1),
        meta={"fetched_at": FETCHED}, origin="retrieved", access="public",
    )


class FakeBuilder:
    def __init__(self) -> None:
        self.built_with: list[list[str]] = []

    def build(self, keywords: list[str], intent: str, locale: str) -> list[Query]:
        self.built_with.append(list(keywords))
        return [
            Query(text=" ".join(keywords), source_kinds=["paper"],
                  intent="support", locale=locale)  # type: ignore[arg-type]
        ]


class FakeJudge:
    """按轮次脚本给相关率。"""

    def __init__(self, rates: list[float]) -> None:
        self.rates = rates
        self.round = 0

    def hit_rate(self, q: Query, docs: list[Doc]) -> float:
        rate = self.rates[min(self.round, len(self.rates) - 1)]
        self.round += 1
        return rate


def searcher(query: Query) -> list[Doc]:
    return [make_doc(hash(query.text) % 97)]


def rewriter_factory(log: list[int]) -> object:
    def rewrite(keywords: list[str], round_index: int) -> list[str]:
        log.append(round_index)
        return [f"{k} (rewrite {round_index})" for k in keywords]

    return rewrite


def test_first_round_pass_no_rewrite() -> None:
    log: list[int] = []
    outcome = search_with_rewrite(
        FakeBuilder(), FakeJudge([0.8]), searcher, ["固态电池"],
        intent="support", locale="zh-CN", rewriter=rewriter_factory(log),  # type: ignore[arg-type]
    )
    assert isinstance(outcome, RetrievalOutcome)
    assert outcome.insufficient is False
    assert outcome.rounds_used == 1
    assert log == [], "above theta: no rewrite fired"
    assert outcome.hit_rate == 0.8


def test_missed_query_recovers_on_rewrite() -> None:
    """「没搜对」：低 → 改写后达标 → 不是信息不足。"""
    log: list[int] = []
    builder = FakeBuilder()
    outcome = search_with_rewrite(
        builder, FakeJudge([0.2, 0.7]), searcher, ["固态电池"],
        intent="support", locale="zh-CN", rewriter=rewriter_factory(log),  # type: ignore[arg-type]
    )
    assert outcome.insufficient is False
    assert outcome.rounds_used == 2
    assert log == [1], "exactly one rewrite round"
    assert len(builder.built_with) == 2
    assert "rewrite 1" in builder.built_with[1][0], "rewritten keywords fed back to builder"


def test_true_nothing_after_cap_r2() -> None:
    """「真没有」：改写满 R=2 轮仍低 → 信息不足，绝无第三轮。"""
    assert MAX_REWRITES == 2
    log: list[int] = []
    builder = FakeBuilder()
    outcome = search_with_rewrite(
        builder, FakeJudge([0.1, 0.2, 0.3]), searcher, ["冷门方向"],
        intent="support", locale="zh-CN", rewriter=rewriter_factory(log),  # type: ignore[arg-type]
    )
    assert outcome.insufficient is True
    assert outcome.rounds_used == 3, "1 initial + 2 rewrites"
    assert log == [1, 2], "rewrite cap enforced: no third rewrite"
    assert len(builder.built_with) == 3
    assert outcome.hit_rate == 0.3, "final round rate reported"


def test_pass_on_final_allowed_round() -> None:
    outcome = search_with_rewrite(
        FakeBuilder(), FakeJudge([0.1, 0.2, 0.9]), searcher, ["x"],
        intent="support", locale="zh-CN", rewriter=rewriter_factory([]),  # type: ignore[arg-type]
    )
    assert outcome.insufficient is False
    assert outcome.rounds_used == 3


def test_theta_configurable() -> None:
    outcome = search_with_rewrite(
        FakeBuilder(), FakeJudge([0.5]), searcher, ["x"],
        intent="support", locale="zh-CN", rewriter=rewriter_factory([]),  # type: ignore[arg-type]
        theta=0.4,
    )
    assert outcome.insufficient is False and outcome.rounds_used == 1


def test_outcome_carries_docs_and_rewrites() -> None:
    outcome = search_with_rewrite(
        FakeBuilder(), FakeJudge([0.2, 0.8]), searcher, ["固态电池"],
        intent="support", locale="zh-CN",
        rewriter=lambda kws, i: [f"{k}+alt" for k in kws],
    )
    assert outcome.docs, "docs of the final round are returned"
    assert outcome.rewrites == [["固态电池+alt"]]
