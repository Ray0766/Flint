"""EvidenceCard 构建 · 七要素（M1-032，contracts/models.py#EvidenceCard）。

七要素（推导记录见 docs/trace/M1-032.md）：
  ① 稳定标识（card_id / cluster_id，§3.2 步骤 5 跨日可归因）
  ② 簇名 + 大类
  ③ 关键词集
  ④ 分源归一化曲线（norm + raw 双值随 HeatPoint 自带，A2 不跨源合成）
  ⑤ 信号角标（M1-031）
  ⑥ top_links（排序规则见 rank_top_links）
  ⑦ 缺口标注位（M1-015 DegradationNote → 广场角标文案）

top_links 排序规则：原始分跨源不可比（A2）——每条链接先在**本源内部**按分数
求百分位（(n - rank_index) / n），再按百分位全局排序；同分并列按 URL 升序
保证确定性；同 URL 去重保留最高百分位；截取 top_n。
"""
from __future__ import annotations

from dataclasses import dataclass

from flint.domain.models import Cluster, EvidenceCard, HeatPoint, SignalFlag
from flint.sources.degradation import DegradationNote, card_gap_annotations


@dataclass(frozen=True)
class LinkCandidate:
    url: str
    source_id: str
    score: float


@dataclass(frozen=True)
class CardView:
    """证据卡展示单元 = 冻结 EvidenceCard 行 + 展示侧四要素。"""

    card: EvidenceCard
    cluster_name: str
    category_id: str
    heat_curves: dict[str, list[HeatPoint]]
    gap_annotations: list[str]


def rank_top_links(candidates: list[LinkCandidate], top_n: int = 5) -> list[str]:
    by_source: dict[str, list[LinkCandidate]] = {}
    for cand in candidates:
        by_source.setdefault(cand.source_id, []).append(cand)

    percentile: dict[tuple[str, str], float] = {}
    for source_id, items in by_source.items():
        ordered = sorted(items, key=lambda c: (-c.score, c.url))
        n = len(ordered)
        for rank_index, cand in enumerate(ordered):
            percentile[(source_id, cand.url)] = (n - rank_index) / n

    best_per_url: dict[str, float] = {}
    for (_, url), p in percentile.items():
        if url not in best_per_url or p > best_per_url[url]:
            best_per_url[url] = p

    ranked = sorted(best_per_url.items(), key=lambda item: (-item[1], item[0]))
    return [url for url, _ in ranked[:top_n]]


def build_card(
    card_id: str,
    cluster: Cluster,
    keyword_ids: list[str],
    flags: list[SignalFlag],
    link_candidates: list[LinkCandidate],
    heat_points: list[HeatPoint],
    degradation_notes: list[DegradationNote],
    top_n: int = 5,
) -> CardView:
    curves: dict[str, list[HeatPoint]] = {}
    for point in heat_points:
        if point.cluster_id != cluster.cluster_id:
            raise ValueError(
                f"heat point for {point.cluster_id!r} mixed into card of "
                f"{cluster.cluster_id!r}"
            )
        curves.setdefault(point.source_id, []).append(point)
    for source_id, points in curves.items():
        curves[source_id] = sorted(points, key=lambda p: p.day)

    card = EvidenceCard(
        card_id=card_id,
        cluster_id=cluster.cluster_id,
        keyword_ids=list(keyword_ids),
        flags=list(flags),
        top_links=rank_top_links(link_candidates, top_n=top_n),
    )
    return CardView(
        card=card,
        cluster_name=cluster.canonical_name,
        category_id=cluster.category_id,
        heat_curves=curves,
        gap_annotations=card_gap_annotations(degradation_notes),
    )
