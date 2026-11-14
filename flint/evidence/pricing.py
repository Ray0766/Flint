"""PricingParser：抓取原文 → LLM 结构化 → PricingRecord（M2-014，B5 / v0.2 §4.5）。

- 每份 plan 的 confidence 是 schema 硬必填：LLM 输出缺置信度会被结构化环
  拒到耗尽 → PricingStructureError → 零记录——**禁止输出不带置信度的数字**。
- price 可空（contact-us 形态）；低置信（< LOW_CONFIDENCE_THRESHOLD，配置化）
  或无价记录经 pending_confirmation 标「定价待确认」，前端携原文链接展示。
- 结构化重试/降级语义复用 M2-003（上限 2，绝无盲试）。
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Final

from flint.domain.models import JSON, PricingRecord
from flint.domain.protocols import LLMProvider
from flint.llm.structured import StructuredOutputExhausted

LOW_CONFIDENCE_THRESHOLD: Final[float] = 0.6

PRICING_SCHEMA: Final[JSON] = {
    "type": "object",
    "properties": {
        "plans": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "plan": {"type": "string", "minLength": 1},
                    "price": {"type": "number"},
                    "currency": {"type": "string", "minLength": 1},
                    "region": {"type": "string", "minLength": 1},
                    "confidence": {"type": "number"},
                },
                "required": ["plan", "currency", "region", "confidence"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["plans"],
    "additionalProperties": False,
}

_PROMPT = (
    "从以下定价页面原文抽取全部方案。每个方案给出 plan/currency/region/confidence；"
    "价格数字只在页面明确出现时给 price，contact-us 形态省略 price 并给低 confidence。"
    "confidence ∈ [0,1] 表示抽取可信度。只输出符合 schema 的 JSON。\n"
    "页面 URL：{url}\n页面原文：\n{raw}"
)


class PricingStructureError(Exception):
    """解析链失败或置信度非法——宁可零记录，不出裸数字（B5）。"""


def _utcnow() -> datetime:
    return datetime.now(UTC)


class LLMPricingParser:
    """冻结协议 PricingParser 的 LLM 实现。"""

    def __init__(
        self,
        provider: LLMProvider,
        now: Callable[[], datetime] = _utcnow,
        max_retries: int = 2,
    ) -> None:
        self._provider = provider
        self._now = now
        self._max_retries = max_retries

    def parse(self, raw: str, url: str) -> list[PricingRecord]:
        prompt = _PROMPT.format(url=url, raw=raw)
        try:
            payload = self._provider.generate_structured(
                prompt, PRICING_SCHEMA, self._max_retries
            )
        except StructuredOutputExhausted as err:
            raise PricingStructureError(
                f"pricing extraction exhausted ({err.failed_attempts} attempts); "
                "no numbers emitted without confidence"
            ) from err
        captured_at = self._now()
        records: list[PricingRecord] = []
        for plan in payload["plans"]:
            confidence = float(plan["confidence"])
            if not 0.0 <= confidence <= 1.0:
                raise PricingStructureError(
                    f"confidence out of range for plan {plan['plan']!r}: {confidence}"
                )
            price = plan.get("price")
            records.append(
                PricingRecord(
                    plan=plan["plan"],
                    price=float(price) if price is not None else None,
                    currency=plan["currency"],
                    region=plan["region"],
                    confidence=confidence,
                    captured_at=captured_at,
                    url=url,
                )
            )
        return records


def pending_confirmation(
    records: list[PricingRecord], threshold: float = LOW_CONFIDENCE_THRESHOLD
) -> list[PricingRecord]:
    """「定价待确认」子集：低置信或无价数字（前端配原文链接展示，B5）。"""
    return [r for r in records if r.confidence < threshold or r.price is None]
