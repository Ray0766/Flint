"""LocalProvider adapter tests (owner ruling: free-tier local models).

Covers: frozen LLMProvider signature conformance over an OpenAI-compat
endpoint; reasoning discarded; fence-stripping on the structured path;
D9 retry/exhaustion accounting; cost=0 real accounting; tool mapping;
tier config loading; wire_provider mode=local. CI offline: MockTransport
(M4-039 precedent), zero network.
"""
from __future__ import annotations

import json

import httpx
import pytest

from flint.llm.local import (
    LocalProvider,
    LocalProviderUnavailable,
    _strip_fences,
)
from flint.llm.production import (
    LLMWiring,
    ProviderWiringError,
    load_local_tier,
    wire_provider,
)
from flint.llm.structured import StructuredOutputExhausted

pytestmark = pytest.mark.compose

BASE = "http://localhost:11434/v1"


def openai_response(
    content: str,
    reasoning: str = "",
    tool_calls: list[dict[str, object]] | None = None,
    prompt_tokens: int = 30,
    completion_tokens: int = 100,
) -> dict[str, object]:
    message: dict[str, object] = {"role": "assistant", "content": content}
    if reasoning:
        message["reasoning"] = reasoning
    if tool_calls is not None:
        message["tool_calls"] = tool_calls
    return {
        "id": "chatcmpl-1", "object": "chat.completion",
        "model": "qwen3:30b",
        "choices": [{"index": 0, "message": message, "finish_reason": "stop"}],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }


def provider_with(responses: list[dict[str, object]]) -> tuple[LocalProvider, list[dict[str, object]]]:
    bodies: list[dict[str, object]] = []
    queue = iter(responses)

    def respond(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content.decode("utf-8")))
        return httpx.Response(200, json=next(queue))

    provider = LocalProvider(
        base_url=BASE, model="qwen3:30b",
        http_client=httpx.Client(transport=httpx.MockTransport(respond)),
    )
    return provider, bodies


def test_generate_takes_content_discards_reasoning_maps_usage() -> None:
    provider, bodies = provider_with([
        openai_response("正文内容。", reasoning="长长的思考过程", completion_tokens=42)
    ])
    completion = provider.generate("写一段。", tools=None)
    assert completion.text == "正文内容。"
    assert "思考" not in completion.text, "reasoning never enters the product"
    assert completion.usage == {"input_tokens": 30, "output_tokens": 42}
    assert bodies[0]["model"] == "qwen3:30b"
    assert "tools" not in bodies[0]
    assert provider.meter.cost_usd == 0.0, "free tier: cost 0 is a real value"
    assert provider.meter.output_tokens == 42


def test_tools_mapped_to_openai_form_and_back() -> None:
    provider, bodies = provider_with([
        openai_response(
            "",
            tool_calls=[{
                "id": "call_1",
                "type": "function",
                "function": {"name": "emit", "arguments": '{"verdict": "A"}'},
            }],
        )
    ])
    completion = provider.generate(
        "判定。",
        tools=[{"name": "emit", "description": "输出", "input_schema": {"type": "object"}}],
    )
    sent = bodies[0]["tools"]
    assert sent == [{
        "type": "function",
        "function": {"name": "emit", "description": "输出",
                     "parameters": {"type": "object"}},
    }]
    assert completion.tool_calls == [
        {"id": "call_1", "name": "emit", "arguments": {"verdict": "A"}}
    ]


def test_structured_strips_fences_and_parses() -> None:
    provider, bodies = provider_with([
        openai_response('```json\n{"answered": true, "answer": "有据"}\n```')
    ])
    payload = provider.generate_structured(
        "回答。",
        {"type": "object",
         "properties": {"answered": {"type": "boolean"},
                        "answer": {"type": "string"}},
         "required": ["answered", "answer"], "additionalProperties": False},
        max_retries=2,
    )
    assert payload == {"answered": True, "answer": "有据"}
    assert provider.structured_output_failures == 0
    sent = str(bodies[0]["messages"])
    assert "MUST 符合此 schema" in sent
    assert '"answered"' in sent, (
        "schema embedded in prompt (text path has no tool input_schema)"
    )


def test_structured_retry_then_success_counts_failures() -> None:
    provider, _bodies = provider_with([
        openai_response("这不是 JSON"),
        openai_response('{"answered": false, "answer": "缺口"}'),
    ])
    payload = provider.generate_structured(
        "回答。",
        {"type": "object",
         "properties": {"answered": {"type": "boolean"},
                        "answer": {"type": "string"}},
         "required": ["answered", "answer"], "additionalProperties": False},
        max_retries=2,
    )
    assert payload["answered"] is False
    assert provider.structured_output_failures == 1, "D9 accounting channel"


def test_structured_exhaustion_never_guesses() -> None:
    provider, _bodies = provider_with([
        openai_response("胡言"), openai_response("乱语"), openai_response("再错"),
    ])
    with pytest.raises(StructuredOutputExhausted):
        provider.generate_structured(
            "判定。", {"type": "object", "required": ["v"],
                       "properties": {"v": {"type": "string"}}},
            max_retries=2,
        )
    assert provider.structured_output_failures == 3


def test_transport_and_non200_are_unavailable() -> None:
    def explode(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=request)

    provider = LocalProvider(
        base_url=BASE, model="qwen3:30b",
        http_client=httpx.Client(transport=httpx.MockTransport(explode)),
    )
    with pytest.raises(LocalProviderUnavailable, match="unreachable"):
        provider.generate("x", tools=None)

    def five_hundred(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    provider2 = LocalProvider(
        base_url=BASE, model="qwen3:30b",
        http_client=httpx.Client(transport=httpx.MockTransport(five_hundred)),
    )
    with pytest.raises(LocalProviderUnavailable, match="500"):
        provider2.generate("x", tools=None)


def test_fence_stripping_variants() -> None:
    assert _strip_fences('```json\n{"a": 1}\n```') == '{"a": 1}'
    assert _strip_fences('```\n{"a": 1}\n```') == '{"a": 1}'
    assert _strip_fences('{"a": 1}') == '{"a": 1}'


def test_local_tier_config_from_env_only() -> None:
    tier = load_local_tier({
        "FLINT_LOCAL_BASE_URL": BASE,
        "FLINT_LOCAL_MODELS": "qwen3:30b, gemma4:31b, gemma4:26b, qwen3.6:27b",
        "FLINT_FREE_TIER_MODEL": "qwen3:30b",
    })
    assert tier.models == ("qwen3:30b", "gemma4:31b", "gemma4:26b", "qwen3.6:27b")
    assert tier.default_model == "qwen3:30b"
    assert tier.api_key is None

    with pytest.raises(ProviderWiringError, match="FLINT_LOCAL_BASE_URL"):
        load_local_tier({"FLINT_LOCAL_MODELS": "m", "FLINT_FREE_TIER_MODEL": "m"})
    with pytest.raises(ProviderWiringError, match="not in"):
        load_local_tier({
            "FLINT_LOCAL_BASE_URL": BASE,
            "FLINT_LOCAL_MODELS": "a,b",
            "FLINT_FREE_TIER_MODEL": "c",
        })


def test_wire_provider_local_mode() -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=openai_response("好"))

    provider = wire_provider(
        LLMWiring(mode="local", model="qwen3:30b", base_url=BASE),
        offline_inner=None,  # type: ignore[arg-type]
        http_client=httpx.Client(transport=httpx.MockTransport(respond)),
    )
    assert isinstance(provider, LocalProvider)
    assert provider.generate("你好", tools=None).text == "好"

    with pytest.raises(ProviderWiringError, match="base_url"):
        wire_provider(
            LLMWiring(mode="local", model="qwen3:30b"),
            offline_inner=None,  # type: ignore[arg-type]
        )


# ── disable_reasoning（owner 裁决 @2026-07-29：推理模型关思考）──────────
# gemma4:31b 等推理模型默认先产大段推理 token（被丢弃却耗预算/时间）；
# /v1 认 OpenAI 标准参数 reasoning_effort="none" 关推理（实测：think:false
# 不认，reasoning_effort:none 认——26 token 出净正文）。默认关此开关 =
# 通用适配器行为逐字不变。

def _reasoning_capture(
    disable: bool,
) -> tuple[LocalProvider, list[dict[str, object]]]:
    bodies: list[dict[str, object]] = []

    def respond(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content.decode("utf-8")))
        return httpx.Response(
            200, json=openai_response("正文。", completion_tokens=8)
        )

    provider = LocalProvider(
        base_url=BASE, model="gemma4:31b",
        http_client=httpx.Client(transport=httpx.MockTransport(respond)),
        disable_reasoning=disable,
    )
    return provider, bodies


def test_disable_reasoning_off_by_default() -> None:
    provider, bodies = _reasoning_capture(False)
    provider.generate("写一段。", tools=None)
    assert "reasoning_effort" not in bodies[0]


def test_disable_reasoning_sets_effort_none() -> None:
    provider, bodies = _reasoning_capture(True)
    provider.generate("写一段。", tools=None)
    assert bodies[0]["reasoning_effort"] == "none"


def test_disable_reasoning_applies_on_structured_path() -> None:
    bodies: list[dict[str, object]] = []

    def respond(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content.decode("utf-8")))
        return httpx.Response(200, json=openai_response(
            '{"answered": true, "answer": "x"}', completion_tokens=6
        ))

    provider = LocalProvider(
        base_url=BASE, model="gemma4:31b",
        http_client=httpx.Client(transport=httpx.MockTransport(respond)),
        disable_reasoning=True,
    )
    provider.generate_structured(
        "q", {"type": "object"}, max_retries=2
    )
    assert bodies[0]["reasoning_effort"] == "none"
