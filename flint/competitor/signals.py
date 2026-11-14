"""竞品四 signal 判定器（M2-031，PDD v0.3.1 §2.2；证据驱动零猜测）。

- 每个 signal 三态：True（证据实证）/ False（证据否证）/ None（无证据可判）。
  fired 只含 True——无证据的 signal 绝不产生；None 与 False 的区别是
  M2-032 strong/unknown 保守判定的输入面。
- mature_pricing：须有 price 非空且 confidence >= 阈值（0.6）的记录——
  「定价待确认」= None（无法判定），不是 False。
- active_last_12m：last_activity 距今 <=365 天；无活动数据 = None。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Final

from flint.domain.models import Doc, PricingRecord, StrengthSignal

MATURE_PRICING_CONFIDENCE: Final[float] = 0.6
ACTIVE_WINDOW_DAYS: Final[int] = 365


@dataclass(frozen=True)
class SignalInputs:
    funding_docs: list[Doc]
    pricing_records: list[PricingRecord]
    same_target_user: bool | None      # LLM 判定结果；None = 未判定
    last_activity: date | None
    today: date


@dataclass
class SignalEvaluation:
    evaluated: dict[StrengthSignal, bool | None] = field(default_factory=dict)
    evidence: dict[StrengthSignal, list[str]] = field(default_factory=dict)

    @property
    def fired(self) -> list[StrengthSignal]:
        return [s for s, v in self.evaluated.items() if v is True]


def derive_signals(inputs: SignalInputs) -> SignalEvaluation:
    evaluation = SignalEvaluation()

    # funded_or_scaled：融资/规模证据文档实证；无文档 = None（v1 FundingSource
    # 占位恒空 → 该 signal 常为 None，保守面由 M2-032 承接）
    if inputs.funding_docs:
        evaluation.evaluated["funded_or_scaled"] = True
        evaluation.evidence["funded_or_scaled"] = [d.doc_id for d in inputs.funding_docs]
    else:
        evaluation.evaluated["funded_or_scaled"] = None

    # mature_pricing：可信数字实证；只有待确认记录 = None；无记录 = None
    confident = [
        p for p in inputs.pricing_records
        if p.price is not None and p.confidence >= MATURE_PRICING_CONFIDENCE
    ]
    if confident:
        evaluation.evaluated["mature_pricing"] = True
        evaluation.evidence["mature_pricing"] = [p.url for p in confident]
    else:
        evaluation.evaluated["mature_pricing"] = None

    # same_target_user：显式判定三态直传
    evaluation.evaluated["same_target_user"] = inputs.same_target_user
    if inputs.same_target_user:
        evaluation.evidence["same_target_user"] = ["judgment:same_target_user"]

    # active_last_12m：活动日期证据
    if inputs.last_activity is None:
        evaluation.evaluated["active_last_12m"] = None
    else:
        active = (inputs.today - inputs.last_activity).days <= ACTIVE_WINDOW_DAYS
        evaluation.evaluated["active_last_12m"] = active
        if active:
            evaluation.evidence["active_last_12m"] = [inputs.last_activity.isoformat()]
    return evaluation
