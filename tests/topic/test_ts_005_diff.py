"""TS-005：[C1] 差异约束（两维 tag + embedding δ、重生成 ≤3）+ 计数 5~8 + [C2] 排序 +
诚实降级。

δ 真跑（NEVER report_only）：估计器从嵌入空间提临时初值。冲突 = 两维 tag 全同 或
embedding 距离 < δ；定点重生成 ≤3 轮仍冲突 → 诚实降级（丢冲突 + 标记，NEVER 硬造）。
"""
from __future__ import annotations

from datetime import date

import pytest

from flint.domain.models import Topic, Vector, WhyNow, WhyNowEvidence
from flint.topic.differentiate import (
    MAX_REGEN_ROUNDS,
    MAX_TOPICS,
    MIN_TOPICS,
    backfill_shortfall,
    cosine_distance,
    differentiate,
    estimate_delta,
    sort_by_confidence,
)

pytestmark = pytest.mark.compose


def _wn(spec: bool) -> WhyNow:
    ev = [] if spec else [WhyNowEvidence("e", date(2026, 7, 1), "cit-1")]
    return WhyNow(claim="c", evidences=ev, speculative=spec)


def mk(tid: str, emb: Vector, tu: str = "u", ff: str = "f",
       spec: bool = False, one: str = "x") -> Topic:
    return Topic(topic_id=tid, seed_id="s", one_liner=one, target_user_tag=tu,
                 form_factor_tag=ff, why_now=_wn(spec),
                 keyword_mapping={}, embedding=emb)


def test_cosine_distance_basics() -> None:
    assert cosine_distance([1.0, 0.0], [1.0, 0.0]) == pytest.approx(0.0)
    assert cosine_distance([1.0, 0.0], [0.0, 1.0]) == pytest.approx(1.0)
    assert cosine_distance([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(2.0)
    assert cosine_distance([0.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)  # 零向量


def test_estimate_delta_from_embedding_space_real() -> None:
    # 三对距离 {1,1,1}（两两正交）→ 分位=1，但 floor 保护下限
    embs = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    d = estimate_delta(embs)
    assert d > 0.0                      # 真跑出正阈值（NEVER report_only）
    assert d <= 1.0
    # 单个 embedding → 无成对距离 → 回退 floor
    assert estimate_delta([[1.0, 0.0]]) > 0.0


def test_no_conflict_all_kept() -> None:
    # 两维 tag 各异 + 正交 embedding → 全差异化
    topics = [mk(f"t{i}", [1.0 if k == i else 0.0 for k in range(6)],
                 tu=f"u{i}", ff=f"f{i}") for i in range(6)]
    out = differentiate(topics, regenerate=lambda t: t, delta=0.5)
    assert [t.topic_id for t in out.topics] == [f"t{i}" for i in range(6)]
    assert out.degraded is False and out.regen_rounds == 0 and out.dropped_conflicts == []


def test_upper_bound_truncates_to_max() -> None:
    topics = [mk(f"t{i}", [1.0 if k == i else 0.0 for k in range(9)],
                 tu=f"u{i}", ff=f"f{i}") for i in range(9)]
    out = differentiate(topics, regenerate=lambda t: t, delta=0.5)
    assert len(out.topics) == MAX_TOPICS == 8   # 越上界硬截断


def test_same_tags_both_dims_is_conflict_even_if_far() -> None:
    # embedding 远但两维 tag 全同 → 冲突（[C1] 需两者同时满足）
    a = mk("a", [1.0, 0.0], tu="u", ff="f")
    b = mk("b", [0.0, 1.0], tu="u", ff="f")   # 正交（远）但 tag 全同
    calls = {"n": 0}

    def regen(t: Topic) -> Topic:
        calls["n"] += 1
        return mk(t.topic_id, t.embedding, tu="u2", ff="f2")  # 补足 tag 差异

    out = differentiate([a, b], regenerate=regen, delta=0.5)
    assert calls["n"] >= 1                       # 触发定点重生成
    assert out.degraded is False and len(out.topics) == 2


def test_different_tags_but_close_embedding_is_conflict() -> None:
    # 锁 [C1] 的**距离腿**：两维 tag 各异，但 embedding 近于 δ → 仍冲突
    # （若删掉 cosine 检查、只看 tag，此对会被误判差异化 → 本测试失败）
    a = mk("a", [1.0, 0.0], tu="u1", ff="f1")
    b = mk("b", [0.99, 0.01], tu="u2", ff="f2")   # tag 全异，但近乎同向（距离≈0 < δ）
    assert cosine_distance(a.embedding, b.embedding) < 0.5

    def stubborn(t: Topic) -> Topic:
        return mk(t.topic_id, [0.99, 0.01], tu="u2", ff="f2")  # 重生成仍贴近

    out = differentiate([a, b], regenerate=stubborn, delta=0.5)
    assert out.regen_rounds == MAX_REGEN_ROUNDS         # 距离腿触发重生成用满
    assert out.degraded is True                          # 仍冲突 → 诚实降级
    assert out.dropped_conflicts == [("a", "b")]
    assert [t.topic_id for t in out.topics] == ["a"]     # 距离腿被真执行


def test_regeneration_resolves_conflict() -> None:
    a = mk("a", [1.0, 0.0], tu="u", ff="f")
    b = mk("b", [1.0, 0.0], tu="u", ff="f")     # 同 embedding 同 tag → 冲突
    resolved = mk("b", [0.0, 1.0], tu="u2", ff="f2")

    def regen(t: Topic) -> Topic:
        return resolved

    out = differentiate([a, b], regenerate=regen, delta=0.5)
    assert out.regen_rounds >= 1
    assert out.degraded is False
    assert {t.topic_id for t in out.topics} == {"a", "b"}


def test_honest_degrade_after_max_rounds_never_fabricate() -> None:
    a = mk("a", [1.0, 0.0], tu="u", ff="f")
    b = mk("b", [1.0, 0.0], tu="u", ff="f")     # 冲突

    def stubborn(t: Topic) -> Topic:
        return mk(t.topic_id, [1.0, 0.0], tu="u", ff="f")  # 重生成仍冲突

    out = differentiate([a, b], regenerate=stubborn, delta=0.5)
    assert out.regen_rounds == MAX_REGEN_ROUNDS == 3   # 用满上限
    assert out.degraded is True
    assert out.dropped_conflicts == [("a", "b")]       # 丢后者标冲突
    assert [t.topic_id for t in out.topics] == ["a"]    # 少出 Topic, NEVER 硬造


def test_sort_by_confidence_speculative_last_stable() -> None:
    t1 = mk("t1", [1.0], spec=False)
    t2 = mk("t2", [1.0], spec=True)
    t3 = mk("t3", [1.0], spec=False)
    t4 = mk("t4", [1.0], spec=True)
    ordered = sort_by_confidence([t1, t2, t3, t4])
    assert [t.topic_id for t in ordered] == ["t1", "t3", "t2", "t4"]  # 非 spec 先, 稳定


def test_backfill_shortfall_below_min() -> None:
    assert backfill_shortfall(3) == MIN_TOPICS - 3 == 2   # 越下界补生成数
    assert backfill_shortfall(5) == 0
    assert backfill_shortfall(8) == 0
