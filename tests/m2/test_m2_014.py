"""M2-014 acceptance tests: PricingParser (fetch -> LLM structure -> confidence).

Acceptance (tasks.json M2-014):
  - fetch -> LLM structuring -> PricingRecord full chain passes on replay
  - numbers without confidence are refused; low confidence marks 待确认
"""
from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import httpx
import pytest

from flint.domain.models import JSON, PricingRecord
from flint.evidence.pricing import (
    LOW_CONFIDENCE_THRESHOLD,
    LLMPricingParser,
    PricingStructureError,
    pending_confirmation,
)
from flint.llm.provider import AnthropicProvider
from flint.llm.structured import StructuredOutputExhausted
from flint.testing.replay import HttpReplay, fixture_path, load_fixture

REPO_ROOT = Path(__file__).resolve().parents[2]
PAGE_FIXTURE = REPO_ROOT / "fixtures" / "evidence6" / "pricing" / "solid-state-battery.json"
NOW = datetime(2026, 7, 28, 9, 0, 0, tzinfo=UTC)

GOOD_PLANS: JSON = {
    "plans": [
        {"plan": "Starter", "price": 29.0, "currency": "USD", "region": "global",
         "confidence": 0.92},
        {"plan": "Pro", "price": 99.0, "currency": "USD", "region": "global",
         "confidence": 0.95},
        {"plan": "Enterprise", "currency": "USD", "region": "global",
         "confidence": 0.30},
    ]
}


class ScriptedProvider:
    """generate_structured 脚本替身（结构化环行为已由 M2-003 钉死）。"""

    def __init__(self, payload: JSON | None = None, exhaust: bool = False) -> None:
        self.payload = payload
        self.exhaust = exhaust
        self.prompts: list[str] = []

    def generate(self, prompt: str, tools: list[JSON] | None) -> object:
        raise NotImplementedError

    def generate_structured(self, prompt: str, schema: JSON, max_retries: int) -> JSON:
        self.prompts.append(prompt)
        if self.exhaust:
            raise StructuredOutputExhausted(1 + max_retries, ["$.plans[0].confidence: required"])
        assert self.payload is not None
        return self.payload


def anthropic_tool_response(payload: JSON) -> dict[str, object]:
    return {
        "id": "m1", "type": "message", "role": "assistant",
        "model": "claude-sonnet-5",
        "content": [{"type": "tool_use", "id": "t1", "name": "emit", "input": payload}],
        "stop_reason": "tool_use",
        "usage": {"input_tokens": 200, "output_tokens": 80},
    }


def fetch_page_html() -> tuple[str, str]:
    exchange = load_fixture(PAGE_FIXTURE)[0]
    with HttpReplay(PAGE_FIXTURE, mode="replay") as session, session.client() as client:
        response = client.get(exchange.url)
    return response.text, exchange.url


def test_full_chain_replay(tmp_path: Path) -> None:
    """页面回放取原文 → LLM 调用录制/回放双模式 → PricingRecord 全链。"""
    raw, page_url = fetch_page_html()
    assert "Starter plan" in raw

    llm_fixture = fixture_path(tmp_path, source_id="anthropic-pricing", day=date(2026, 7, 28))
    live = httpx.MockTransport(
        lambda request: httpx.Response(200, json=anthropic_tool_response(GOOD_PLANS))
    )

    for mode, transport in (("record", live), ("replay", None)):
        with (
            HttpReplay(llm_fixture, mode=mode, live_transport=transport) as session,  # type: ignore[arg-type]
            session.client() as client,
        ):
            provider = AnthropicProvider(
                api_key="test-key", model="claude-sonnet-5", http_client=client
            )
            parser = LLMPricingParser(provider=provider, now=lambda: NOW)
            records = parser.parse(raw, page_url)
        assert len(records) == 3
        for record in records:
            assert isinstance(record, PricingRecord)
            assert record.url == page_url
            assert record.captured_at == NOW
            assert 0.0 <= record.confidence <= 1.0
        assert records[0].price == 29.0
        assert records[2].price is None, "contact-us plan carries no number"


def test_prompt_carries_page_and_url() -> None:
    provider = ScriptedProvider(payload=GOOD_PLANS)
    parser = LLMPricingParser(provider=provider, now=lambda: NOW)
    parser.parse("<html>Pro plan $99</html>", "https://vendor.example/pricing")
    assert "Pro plan $99" in provider.prompts[0]
    assert "https://vendor.example/pricing" in provider.prompts[0]


def test_numbers_without_confidence_are_refused() -> None:
    """B5 硬规则：解析链失败（缺 confidence 被 schema 拒到耗尽）→ 零记录，
    绝不输出裸数字。"""
    provider = ScriptedProvider(exhaust=True)
    parser = LLMPricingParser(provider=provider, now=lambda: NOW)
    with pytest.raises(PricingStructureError):
        parser.parse("<html>$99</html>", "https://vendor.example/pricing")


def test_confidence_out_of_range_refused() -> None:
    bad: JSON = {
        "plans": [
            {"plan": "Pro", "price": 99.0, "currency": "USD", "region": "global",
             "confidence": 1.5}
        ]
    }
    parser = LLMPricingParser(provider=ScriptedProvider(payload=bad), now=lambda: NOW)
    with pytest.raises(PricingStructureError):
        parser.parse("<html>$99</html>", "https://vendor.example/pricing")


def test_low_confidence_marks_pending_confirmation() -> None:
    parser = LLMPricingParser(provider=ScriptedProvider(payload=GOOD_PLANS), now=lambda: NOW)
    records = parser.parse("<html>page</html>", "https://vendor.example/pricing")
    pending = pending_confirmation(records)
    assert [r.plan for r in pending] == ["Enterprise"], "low conf / no price -> 待确认"
    strict = pending_confirmation(records, threshold=0.99)
    assert len(strict) == 3, "threshold is configurable"
    assert LOW_CONFIDENCE_THRESHOLD == 0.6


def test_contact_us_only_page() -> None:
    contact_only: JSON = {
        "plans": [
            {"plan": "Enterprise", "currency": "USD", "region": "global",
             "confidence": 0.2}
        ]
    }
    parser = LLMPricingParser(provider=ScriptedProvider(payload=contact_only), now=lambda: NOW)
    records = parser.parse("<html>Contact sales</html>", "https://vendor.example/pricing")
    assert len(records) == 1
    assert records[0].price is None
    assert pending_confirmation(records) == records
