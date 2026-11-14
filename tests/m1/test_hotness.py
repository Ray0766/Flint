"""搜热点主榜综合分（H-1/H-3/H-5，读时算零契约）。

排序哲学（owner 定案）：主榜=跨源印证（稳/可信）、时间衰减中等、新颖度加分常年热降权。
纯单测（合成 heat_points 时序），零 DB/零联网。断言五法的可观测语义。
"""
from __future__ import annotations

from datetime import date, timedelta

from flint.hotness import ClusterSeries, HotnessConfig, compute_hotness, rank_hotness

TODAY = date(2026, 7, 26)
CFG = HotnessConfig()


def _series(cid: str, first_seen: date, agg_by_day: dict[date, float],
            by_source_today: dict[str, float]) -> ClusterSeries:
    return ClusterSeries(cluster_id=cid, first_seen=first_seen,
                         agg_by_day=agg_by_day, by_source_today=by_source_today)


def test_cross_source_corroboration_ranks_ahead_of_single_source() -> None:
    # 主榜核心：同 agg（100），跨源印证（2 源各 50，但都>θ？——用 65+65）排前，单源猎奇靠后。
    new = TODAY  # 同龄、同 agg → 只差跨源数
    multi = _series("multi", new, {TODAY: 130.0}, {"weibo": 65.0, "arxiv": 65.0})
    single = _series("single", new, {TODAY: 130.0}, {"weibo": 130.0})
    ranked = [c.cluster_id for c in rank_hotness([single, multi], TODAY, CFG)]
    assert ranked[0] == "multi", "跨源印证排前、单源猎奇靠后"


def test_velocity_and_acceleration_boost() -> None:
    # 同 agg 今日（80），一个平（历来 80）、一个在涨（20→50→80）→ 涨的排前。
    flat = _series("flat", TODAY - timedelta(days=30),
                   {TODAY: 80.0, TODAY - timedelta(1): 80.0, TODAY - timedelta(2): 80.0},
                   {"weibo": 80.0})
    rising = _series("rising", TODAY - timedelta(days=30),
                     {TODAY: 80.0, TODAY - timedelta(1): 50.0, TODAY - timedelta(2): 20.0},
                     {"weibo": 80.0})
    ranked = [c.cluster_id for c in rank_hotness([flat, rising], TODAY, CFG)]
    assert ranked[0] == "rising", "速度+加速度让上升中的排前"


def test_time_decay_and_novelty_favor_new_over_perennial() -> None:
    # 同 agg（90）、同单源，一个新簇（2 天）一个常年热（200 天）→ 新的排前（衰减+新颖度）。
    fresh = _series("fresh", TODAY - timedelta(days=2), {TODAY: 90.0}, {"weibo": 90.0})
    perennial = _series("perennial", TODAY - timedelta(days=200), {TODAY: 90.0},
                        {"weibo": 90.0})
    ranked = [c.cluster_id for c in rank_hotness([perennial, fresh], TODAY, CFG)]
    assert ranked[0] == "fresh", "时间衰减+新颖度：新簇>常年热"


def test_missing_days_treated_as_zero_velocity_base() -> None:
    # 时序缺日按 0：昨日无数据、今日 60 → 速度=60（真爆发），不炸。
    s = _series("burst", TODAY, {TODAY: 60.0}, {"weibo": 60.0})
    score = compute_hotness(s, TODAY, CFG)
    assert score.velocity == 60.0 and score.total > 0.0


def test_components_exposed_for_transparency() -> None:
    s = _series("c", TODAY, {TODAY: 100.0}, {"weibo": 62.0, "arxiv": 61.0})
    sc = compute_hotness(s, TODAY, CFG)
    assert sc.agg == 100.0 and sc.cross_count == 2 and sc.multi_boost > 1.0
    assert sc.decay_divisor > 0.0 and 0.0 <= sc.novelty_factor <= 1.0


def test_config_thresholds_are_tunable_not_report_only() -> None:
    # 参数临时初值可调（标定通道）——跨源权重↑ 放大印证优势，NEVER report_only 关约束。
    strong = HotnessConfig(cross_source_weight=2.0)
    multi = _series("multi", TODAY, {TODAY: 100.0}, {"weibo": 61.0, "arxiv": 61.0})
    base = compute_hotness(multi, TODAY, CFG).total
    boosted = compute_hotness(multi, TODAY, strong).total
    assert boosted > base
