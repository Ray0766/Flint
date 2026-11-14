"""TS-005：[C1] 差异约束 + combo 计数 5~8 + [C2] 排序降权 + 诚实降级。

- [C1]（owner #1，保持 active、NEVER report_only）：任意两 Topic 须
  target_user_tag/form_factor_tag **≥1 维不同** 且 embedding 余弦距离 ≥ δ；
  冲突（两维全同 或 距离 < δ）→ 定点重生成 ≤3 轮。
- δ 真跑：`estimate_delta` 从嵌入空间提临时初值（成对距离分布分位点，带 floor），
  **NEVER 关成 report_only**；δ 是 Open Question（初值待金标标定，见
  docs/v0.4-问题单.md「[C1] 差异约束 embedding 距离阈值 δ」）。
- 诚实降级（owner #7）：重生成 ≤3 后仍冲突 → 丢冲突后者 + 标记 dropped_conflicts，
  **少出 Topic，NEVER 硬造假差异**。
- 计数（owner #2）：combo 上界 8 硬截断；下界 5 经 `backfill_shortfall` 报补生成数。
- [C2] 排序降权：`sort_by_confidence` 非 speculative 先、speculative 后（稳定）。
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Final

import numpy as np

from flint.domain.models import Topic, Vector

MIN_TOPICS: Final[int] = 5          # combo 目标下界（#2）；诚实降级可少出（#7）
MAX_TOPICS: Final[int] = 8          # combo 上界硬截断（#2）
MAX_REGEN_ROUNDS: Final[int] = 3    # 定点重生成上限（#1）

# δ 临时初值提取参数（真跑；待金标标定，Open Question）：
_DELTA_QUANTILE: Final[float] = 0.10   # 成对余弦距离分布的 10 分位
_DELTA_FLOOR: Final[float] = 0.05      # 临时下限，避免退化到 0（无成对样本时回退此值）


def cosine_distance(a: Vector, b: Vector) -> float:
    av = np.asarray(a, dtype=float)
    bv = np.asarray(b, dtype=float)
    na = float(np.linalg.norm(av))
    nb = float(np.linalg.norm(bv))
    if na == 0.0 or nb == 0.0:
        return 1.0
    return float(1.0 - (av @ bv) / (na * nb))


def _pairwise_distances(embeddings: Sequence[Vector]) -> list[float]:
    out: list[float] = []
    for i in range(len(embeddings)):
        for j in range(i + 1, len(embeddings)):
            out.append(cosine_distance(embeddings[i], embeddings[j]))
    return out


def estimate_delta(
    embeddings: Sequence[Vector],
    *,
    quantile: float = _DELTA_QUANTILE,
    floor: float = _DELTA_FLOOR,
) -> float:
    """从嵌入空间提 δ 临时初值（真跑，NEVER report_only）。

    成对余弦距离分布的低分位点——把最接近的一撮对判为冲突；带 floor 下限。
    无成对样本（<2 embedding）→ 回退 floor。
    """
    dists = _pairwise_distances(embeddings)
    if not dists:
        return floor
    return max(float(np.quantile(dists, quantile)), floor)


def _tags_differ(a: Topic, b: Topic) -> bool:
    return (
        a.target_user_tag != b.target_user_tag
        or a.form_factor_tag != b.form_factor_tag
    )


def _differentiated(a: Topic, b: Topic, delta: float) -> bool:
    # [C1]：两维 tag ≥1 不同 且 embedding 距离 ≥ δ（两者须同时满足）
    return _tags_differ(a, b) and cosine_distance(a.embedding, b.embedding) >= delta


def _first_conflict(topics: Sequence[Topic], delta: float) -> tuple[int, int] | None:
    for i in range(len(topics)):
        for j in range(i + 1, len(topics)):
            if not _differentiated(topics[i], topics[j], delta):
                return (i, j)
    return None


@dataclass
class DifferentiationOutcome:
    topics: list[Topic]                       # 差异化后保留的 Topic
    delta: float                              # 本次真跑用的 δ
    regen_rounds: int                         # 定点重生成轮数（≤3）
    degraded: bool                            # 是否触发诚实降级
    dropped_conflicts: list[tuple[str, str]]  # 降级丢弃的冲突对 (keep_id, dropped_id)


def differentiate(
    topics: Sequence[Topic],
    *,
    regenerate: Callable[[Topic], Topic],
    delta: float | None = None,
    max_rounds: int = MAX_REGEN_ROUNDS,
    max_topics: int = MAX_TOPICS,
) -> DifferentiationOutcome:
    kept = list(topics[:max_topics])          # 越上界硬截断（#2）
    used_delta = (
        delta if delta is not None
        else estimate_delta([t.embedding for t in kept])
    )
    rounds = 0
    while rounds < max_rounds:
        pair = _first_conflict(kept, used_delta)
        if pair is None:
            break
        _, j = pair
        kept[j] = regenerate(kept[j])         # 定点重生成冲突对后者（#1）
        rounds += 1
    # 重生成上限后仍冲突 → 诚实降级：丢后者 + 标记，NEVER 硬造（#7）
    dropped: list[tuple[str, str]] = []
    degraded = False
    pair = _first_conflict(kept, used_delta)
    while pair is not None:
        i, j = pair
        dropped.append((kept[i].topic_id, kept[j].topic_id))
        kept.pop(j)
        degraded = True
        pair = _first_conflict(kept, used_delta)
    return DifferentiationOutcome(
        topics=kept, delta=used_delta, regen_rounds=rounds,
        degraded=degraded, dropped_conflicts=dropped,
    )


def sort_by_confidence(topics: Sequence[Topic]) -> list[Topic]:
    """[C2] 排序降权：why_now.speculative 的 Topic 排后（稳定排序）。"""
    return sorted(topics, key=lambda t: t.why_now.speculative)


def backfill_shortfall(count: int, min_topics: int = MIN_TOPICS) -> int:
    """越下界补生成数（#2）：不足 min_topics 时返回需补的个数，否则 0。"""
    return max(0, min_topics - count)
