"""user_provided 评分尺（M2-026，审7 双尺之二 / v0.3.2 终轮补丁）。

- 独立公式：40·可核验性 + 35·一手性 + 25·时效——与 retrieved 尺（B4 族）
  分数空间不同构，跨尺比较无意义。
- EvidenceScore.axis 回填 "user_provided"；assert_comparable 在类型层拒绝
  跨尺比较（UI 分区展示、区内排序的守卫）。
"""
from __future__ import annotations

from datetime import date

from flint.domain.models import EvidenceScore
from flint.scoring.paper import recency_decay


class CrossAxisComparisonError(TypeError):
    """跨尺分数比较被拒（审7：跨类不比较分数）。"""


def _require_unit(name: str, value: float) -> float:
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must be within [0, 1], got {value}")
    return value


def score_user_provided(
    verifiable: float,
    firsthand: float,
    published: date | None,
    today: date,
    half_life_days: int = 365,
) -> EvidenceScore:
    components = {
        "verifiable": 40 * _require_unit("verifiable", verifiable),
        "firsthand": 35 * _require_unit("firsthand", firsthand),
        "recency": 25 * recency_decay(published, today, half_life_days),
    }
    return EvidenceScore(
        strength=round(sum(components.values())),
        axis="user_provided",
        components=components,
    )


def assert_comparable(a: EvidenceScore, b: EvidenceScore) -> None:
    if a.axis != b.axis:
        raise CrossAxisComparisonError(
            f"scores on different axes are not comparable: {a.axis} vs {b.axis}"
        )
