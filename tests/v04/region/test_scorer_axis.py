"""REGION-06 验收：证据强度三尺 —— authority 轴接入。

acceptance（tasks-v04.json#REGION-06）：
  ① axis 体系新增 authority 轴（**K3-01 之后：权重按档定值，不再是 1.0 占位**）；
  ② 金标回归子集 fixture 分数在**中性档（mainstream=1.00）下不漂移**（守护断言）。

## 权重从 1.0 占位换成了定值（K3-01，2026-08-04）

**改前**：五档一律 1.0，acceptance② 的守护断言是「任何档都不漂移」——
那正是「1.0 生效了」的证据。

**改后**：权重按 `AuthorityWeights` 定值（官方 1.15 / 主流 1.00 / 行业 0.77 /
社区 0.57 / 未知 0.57，推导见 `docs/authority权重-v041.md`）。守护断言随之收窄到
**锚点档**：`mainstream` 恒 1.00，所以金标在这一档下仍然一个不漂移。

**为什么必须收窄而不是删掉**：全档不漂移这条断言在定值之后是**自相矛盾**的——
它要求的正是「权重不起作用」。但守护点本身不能丢：`mainstream` 那一档
一旦漂移，说明改的不只是权重，而是打分本身。

## 轴落在 components 而不是 axis 字段（与卡措辞的偏离，已留单）

冻结件 `EvidenceScore.axis: EvidenceOrigin = Literal["retrieved","user_provided"]` 只有两值，
第三值会改冻结契约（§1.4：以 contracts/ 为准）。authority 因此记进 `components`，
`axis` 字段保持双尺语义不动。见 `docs/blocked/REGION-06-AXIS-WORDING.md`。
"""
from __future__ import annotations

from datetime import date

from flint.domain.models import Doc
from flint.region.authority_axis import (
    AUTHORITY_BASIS,
    AuthorityWeights,
    apply_authority_axis,
)
from flint.scoring.scorer import DualScaleScorer, ScorerContext

TODAY = date(2026, 8, 2)


def _doc(doc_id: str, kind: str = "paper", **meta: object) -> Doc:
    return Doc(
        doc_id=doc_id, source_id="s1", kind=kind, title="t",
        url="https://example.invalid/x", published_at=date(2026, 6, 1),
        meta=dict(meta), origin="retrieved", access="public")


# 金标回归子集：四种 kind 各一条，覆盖 retrieved 侧的全部计分分支
GOLD_DOCS = [
    _doc("g-paper", "paper", venue="nature", cited_by=40, peer_reviewed=True),
    _doc("g-patent", "patent", family_size=6),
    _doc("g-news", "news"),
    _doc("g-repo", "repo"),
]


def _scorer() -> DualScaleScorer:
    return DualScaleScorer(ScorerContext(
        today=TODAY, corpus_citations=[1, 5, 20, 50], corpus_family_sizes=[1, 3, 8],
        venue_tiers={"nature": 0.95}))


# ── ① 轴存在、权重 1.0、带 K3 标记 ──────────────────────────────

def test_the_anchor_tier_is_neutral_one() -> None:
    """锚点档恒 1.00：改的是**相对分量**，不是整体分数水位（K3-01）。"""
    assert AuthorityWeights().mainstream == 1.0


def test_weight_carries_its_provenance() -> None:
    """标记从「待 K3 定」换成了「这个值哪来的」——K3 已经有结论了。"""
    assert "方法论调研" in AUTHORITY_BASIS
    assert "本项目实测" in AUTHORITY_BASIS


def test_authority_axis_is_recorded_in_components() -> None:
    scorer = _scorer()
    base = scorer.strength(GOLD_DOCS[0])
    scored = apply_authority_axis(base, authority_tier="official")
    assert scored.components["authority_tier"] == "official"
    assert scored.components["authority_weight"] == AuthorityWeights().official
    assert "方法论调研" in str(scored.components["authority_basis"])


def test_axis_field_keeps_dual_scale_semantics() -> None:
    """冻结件 axis 只有两值——authority NEVER 挤进这个字段。"""
    scorer = _scorer()
    scored = apply_authority_axis(scorer.strength(GOLD_DOCS[0]), authority_tier="unknown")
    assert scored.axis == "retrieved"


# ── ② 金标不漂移 ──────────────────────────────────────────────

def test_gold_scores_do_not_drift_at_the_anchor_tier() -> None:
    """金标在锚点档（mainstream=1.00）下一个不变——守护点收窄后仍在守。

    这一档漂移的话，说明改的不只是权重，而是打分本身。
    """
    scorer = _scorer()
    for doc in GOLD_DOCS:
        base = scorer.strength(doc)
        scored = apply_authority_axis(base, authority_tier="mainstream")
        assert scored.strength == base.strength, (
            f"{doc.doc_id} 在锚点档下漂移了：{base.strength} → {scored.strength}")


def test_gold_scores_do_move_at_the_other_tiers() -> None:
    """阴性对照：**非锚点档要真的动**（K3-01 acceptance③）。

    没有这一条，「权重定了值」与「值还是 1.0」长得一模一样。
    """
    scorer = _scorer()
    moved = [
        (doc.doc_id, tier)
        for doc in GOLD_DOCS
        for tier in ("official", "community")
        if apply_authority_axis(scorer.strength(doc), authority_tier=tier).strength
        != scorer.strength(doc).strength
    ]

    assert moved, "五档打出同一个分——轴接了等于没接"


def test_original_components_are_preserved() -> None:
    """接轴只**增**三个键，既有 components 一个不改（否则质量卡口径会变）。"""
    scorer = _scorer()
    base = scorer.strength(GOLD_DOCS[0])
    scored = apply_authority_axis(base, authority_tier="official")
    for key, value in base.components.items():
        assert scored.components[key] == value, f"既有分量 {key} 被改动"
    assert set(scored.components) - set(base.components) == {
        "authority_tier", "authority_weight", "authority_basis"}


def test_applying_twice_is_stable() -> None:
    """重复接轴不叠乘。权重不再是 1.0 之后，**叠乘是真的会发生的事**。"""
    scorer = _scorer()
    once = apply_authority_axis(scorer.strength(GOLD_DOCS[0]), authority_tier="official")
    twice = apply_authority_axis(once, authority_tier="official")
    assert twice.strength == once.strength
    assert twice.components == once.components


def test_user_provided_scale_also_accepts_the_axis() -> None:
    """双尺两侧都能接轴——authority 是**第三个维度**，不是 retrieved 专属。"""
    scorer = _scorer()
    user_doc = Doc(
        doc_id="u1", source_id="s1", kind="report", title="t",
        url="https://example.invalid/u", published_at=date(2026, 7, 1),
        meta={"verifiable": 0.8, "firsthand": 0.9}, origin="user_provided", access="private")
    base = scorer.strength(user_doc)
    scored = apply_authority_axis(base, authority_tier="community")
    assert scored.axis == "user_provided"
    assert scored.strength == round(base.strength * AuthorityWeights().community)
