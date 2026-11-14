"""竞品强度判定（M2-032，PDD v0.3.1 §2.2 审1；保守面写死）。

映射（evaluated 三态 → 四档）：
- True 计数 >=2 → strong（任二 signal）；
- True 计数 ==1 → moderate；
- 四 signal 全为 False（证据全否证）→ weak；
- 其余（存在 None = 无法判定且 True 不足）→ **unknown，不是 weak**——
  未能判定强度的竞品可能是强竞品，判错 C 代价 > 判错 A/D（代价不对称，
  规则向保守一侧倾斜）。unknown 阻断 C 由 M2-036 消费。
- 定价待确认在 M2-031 已映射为 None：只丢一个 signal，绝不参与判定。
"""
from __future__ import annotations

from typing import Literal

from flint.competitor.extract import CompetitorRecord
from flint.competitor.signals import SignalEvaluation
from flint.domain.models import Competitor, PricingRecord, StrengthSignal

_ALL_SIGNALS: tuple[StrengthSignal, ...] = (
    "funded_or_scaled", "mature_pricing", "same_target_user", "active_last_12m",
)

# 域以 contracts/models.py#Competitor.strength 为准；冻结 Literal 变更时
# mypy 将在 build_competitor 构造点报错（S3：strict 是冻结边界执行器）
Strength = Literal["strong", "moderate", "weak", "unknown"]


def judge_strength(evaluation: SignalEvaluation) -> Strength:
    fired = sum(1 for s in _ALL_SIGNALS if evaluation.evaluated.get(s) is True)
    if fired >= 2:
        return "strong"
    if fired == 1:
        return "moderate"
    if all(evaluation.evaluated.get(s) is False for s in _ALL_SIGNALS):
        return "weak"
    return "unknown"


def build_competitor(
    record: CompetitorRecord,
    evaluation: SignalEvaluation,
    pricing_records: list[PricingRecord],
) -> Competitor:
    """组装冻结 Competitor：strength + 实证 signal 集 + 展示用最高置信定价
    （展示允许待确认记录；强度判定不受其影响——两条通道分离）。"""
    pricing = max(pricing_records, key=lambda p: p.confidence, default=None)
    return Competitor(
        name=record.name,
        url=record.url,
        strength=judge_strength(evaluation),
        strength_signals=list(evaluation.fired),
        pricing=pricing,
    )
