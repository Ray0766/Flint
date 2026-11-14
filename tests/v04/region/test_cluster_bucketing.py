"""REGION-04 验收：聚类 region 分桶 + 簇血缘 region 维度。

acceptance:
  ① 双区同事件 fixture → 2 簇 0 合并
  ② 簇成员 region 单一性断言 all(len({m.region})==1)

PRINCIPLES#B5：聚类 MUST 先按 region 分桶再执行；跨区关联的唯一合法通道
= same_event_group 显式建立，NEVER 靠 embedding 相似度自动合并。
"""
from __future__ import annotations

from dataclasses import dataclass

import pytest

from flint.region.bucketing import (
    ClusterMember,
    RegionCluster,
    bucket_and_cluster,
)

# ── 双区同事件 fixture ────────────────────────────────────────

@dataclass(frozen=True)
class _Item:
    """模拟待聚类条目（只需 region + 相似度判据用的 id）。"""
    item_id: str
    region: str
    event_text: str


# 同一事件「固态电池量产线」在 US 和 JP 两区各有报道
US_ITEMS = [
    _Item("us-1", "US", "Toyota solid-state battery mass production line"),
    _Item("us-2", "US", "Toyota announces battery factory in Kentucky"),
]
JP_ITEMS = [
    _Item("jp-1", "JP", "トヨタ、全固体電池の量産ラインを稼働"),
    _Item("jp-2", "JP", "トヨタ固体電池工場の建設計画を発表"),
]


def _same_bucket(a: _Item, b: _Item) -> bool:
    """模拟聚类相似度判定——同区内全部归一簇（测试用）。"""
    return True


# ── ① 双区同事件 → 2 簇 0 合并 ──────────────────────────────

def test_same_event_different_regions_produce_two_clusters() -> None:
    """US 和 JP 的同一事件 NEVER 合并成一个簇。"""
    clusters = bucket_and_cluster(
        items=US_ITEMS + JP_ITEMS,
        region_of=lambda item: item.region,
        are_similar=_same_bucket,
    )
    assert len(clusters) == 2, f"应产出 2 簇（US 一个 JP 一个），实际 {len(clusters)}"
    regions = {c.region for c in clusters}
    assert regions == {"US", "JP"}


# ── ② 簇成员 region 单一性 ──────────────────────────────────

def test_all_cluster_members_share_single_region() -> None:
    clusters = bucket_and_cluster(
        items=US_ITEMS + JP_ITEMS,
        region_of=lambda item: item.region,
        are_similar=_same_bucket,
    )
    for cluster in clusters:
        member_regions = {m.region for m in cluster.members}
        assert len(member_regions) == 1, (
            f"簇 {cluster.region} 含多区成员: {member_regions}")


def test_cluster_region_matches_its_members() -> None:
    clusters = bucket_and_cluster(
        items=US_ITEMS + JP_ITEMS,
        region_of=lambda item: item.region,
        are_similar=_same_bucket,
    )
    for cluster in clusters:
        for m in cluster.members:
            assert m.region == cluster.region


# ── 边界 ─────────────────────────────────────────────────────

def test_single_region_items_produce_one_cluster() -> None:
    clusters = bucket_and_cluster(
        items=JP_ITEMS,
        region_of=lambda item: item.region,
        are_similar=_same_bucket,
    )
    assert len(clusters) == 1
    assert clusters[0].region == "JP"


def test_empty_input_produces_no_clusters() -> None:
    clusters = bucket_and_cluster(
        items=[],
        region_of=lambda item: item.region,
        are_similar=_same_bucket,
    )
    assert clusters == []


def test_three_regions_produce_three_clusters() -> None:
    """三区各有条目 → 三个独立簇。"""
    items = US_ITEMS + JP_ITEMS + [
        _Item("au-1", "AU", "Toyota battery plant in Melbourne"),
    ]
    clusters = bucket_and_cluster(
        items=items,
        region_of=lambda item: item.region,
        are_similar=_same_bucket,
    )
    assert len(clusters) == 3
    assert {c.region for c in clusters} == {"US", "JP", "AU"}


def test_dissimilar_items_in_same_region_produce_separate_clusters() -> None:
    """同区内不相似的条目产出多个簇（聚类正常工作）。"""
    clusters = bucket_and_cluster(
        items=US_ITEMS,
        region_of=lambda item: item.region,
        are_similar=lambda a, b: False,  # 全部不相似
    )
    assert len(clusters) == 2
    assert all(c.region == "US" for c in clusters)


def test_no_auto_merge_path_exists() -> None:
    """NEVER 存在靠 embedding 自动建组的路径 [PRINCIPLES#B5]。

    bucket_and_cluster 的参数面里 NEVER 有 auto_merge / cross_region 开关。
    """
    import inspect

    sig = inspect.signature(bucket_and_cluster)
    param_names = set(sig.parameters.keys())
    forbidden = {"auto_merge", "cross_region", "merge_cross", "allow_cross"}
    assert not (param_names & forbidden), (
        f"自动跨区合并参数 {param_names & forbidden} NEVER 应存在")


# ── 以下由本会话（收尾方）补：卡 outputs 的两处缺口 ────────────────
# 并发会话写的红测覆盖了 acceptance 两条，但卡的 outputs 还要求
# `fixtures/US/…,fixtures/JP/… 双区样本`（E12 目录口径），且卡标题含
# 「簇血缘 region 维度」。两处补在这里，归属见 docs/trace/REGION-04.md。

import json
from pathlib import Path

from flint.region.bucketing import (
    CrossRegionLineageError,
    link_lineage,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_DAY = "2026-08-02.json"


def _load_region_fixture(region: str) -> list[_Item]:
    """从 E12 口径的 fixture 目录读双区样本：fixtures/{region}/{source_id}/{day}.json。"""
    path = REPO_ROOT / "fixtures" / region / "demo-wire" / FIXTURE_DAY
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["region"] == region
    return [
        _Item(item_id=i["item_id"], region=region, event_text=i["event_text"])
        for i in payload["items"]
    ]


def test_dual_region_fixture_files_exist_in_e12_layout() -> None:
    """卡 outputs 要的是**文件**样本，不是内联数据——内联的没法被别的卡复用。"""
    for region in ("US", "JP"):
        path = REPO_ROOT / "fixtures" / region / "demo-wire" / FIXTURE_DAY
        assert path.exists(), f"缺双区样本：{path}"


def test_fixture_driven_same_event_still_yields_two_clusters() -> None:
    """用**文件**里的双区同事件样本复跑 acceptance ①：2 簇 0 合并。"""
    items = _load_region_fixture("US") + _load_region_fixture("JP")
    clusters = bucket_and_cluster(
        items=items, region_of=lambda i: i.region, are_similar=_same_bucket)
    assert len(clusters) == 2
    assert {c.region for c in clusters} == {"US", "JP"}
    for cluster in clusters:
        assert len({m.region for m in cluster.members}) == 1


def test_japanese_fixture_text_is_not_translated() -> None:
    """样本里的日文原文 NEVER 被翻译（B7/B9）——译文进来会让聚类吃到派生物。"""
    jp = _load_region_fixture("JP")
    assert any("全固体電池" in i.event_text for i in jp), [i.event_text for i in jp]


# ── 簇血缘的 region 维度（卡标题要求） ────────────────────────────

def test_lineage_within_one_region_is_allowed() -> None:
    parents = bucket_and_cluster(
        items=_load_region_fixture("JP"), region_of=lambda i: i.region,
        are_similar=_same_bucket)
    child = RegionCluster(region="JP", members=[ClusterMember("jp-3", "JP")])
    linked = link_lineage(child, parents)
    assert linked.parent_cluster_ids


def test_cross_region_lineage_is_rejected() -> None:
    """血缘跨区 = 从另一头绕过 B5：簇没合并，但血缘把两国连成一条线。"""
    us = bucket_and_cluster(
        items=_load_region_fixture("US"), region_of=lambda i: i.region,
        are_similar=_same_bucket)
    child = RegionCluster(region="JP", members=[ClusterMember("jp-3", "JP")])
    with pytest.raises(CrossRegionLineageError, match="US"):
        link_lineage(child, us)
    assert child.parent_cluster_ids == [], "拒绝之后 NEVER 留下半挂的血缘"
