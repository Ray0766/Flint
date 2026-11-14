"""付费档跑批 provider（owner 任务）：组稿用可配 max_tokens；判分用 Claude
原生结构化输出 output_config.format（JSON 干净、非 tool-use 往返）；thinking
可关（本次跑批口径 thinking disabled，写入 trail）。记账继承 MeteredAnthropic。

CI 零外部：httpx.MockTransport 拦截 anthropic SDK 的 HTTP（M4-039 先例）。
"""
from __future__ import annotations

import json

import httpx
import pytest

from flint.llm.production import (
    MeteredAnthropicProvider,
    ModelPricing,
    PaidTierProvider,
)
from flint.llm.structured import StructuredOutputExhausted

PRICING = ModelPricing(usd_per_mtok_input=2.0, usd_per_mtok_output=10.0)
ANSWER_SCHEMA = {
    "type": "object",
    "properties": {
        "answered": {"type": "boolean"},
        "answer": {"type": "string"},
    },
    "required": ["answered", "answer"],
    "additionalProperties": False,
}


def _msg(text: str, in_tok: int = 100, out_tok: int = 50) -> dict[str, object]:
    return {
        "id": "msg_1", "type": "message", "role": "assistant",
        "model": "claude-sonnet-5", "stop_reason": "end_turn",
        "stop_sequence": None,
        "content": [{"type": "text", "text": text}],
        "usage": {"input_tokens": in_tok, "output_tokens": out_tok},
    }


def _provider(
    handler: object, max_tokens: int = 8000, disable_thinking: bool = True,
) -> tuple[PaidTierProvider, list[dict[str, object]]]:
    bodies: list[dict[str, object]] = []

    def transport(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content.decode("utf-8")))
        return handler(request)  # type: ignore[operator]

    provider = PaidTierProvider(
        api_key="sk-test", model="claude-sonnet-5", pricing=PRICING,
        max_tokens=max_tokens, disable_thinking=disable_thinking,
        http_client=httpx.Client(transport=httpx.MockTransport(transport)),
    )
    return provider, bodies


def test_compose_disables_thinking_and_honors_max_tokens() -> None:
    def handler(_r: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_msg("正文内容", out_tok=50))

    provider, bodies = _provider(handler, max_tokens=8000)
    completion = provider.generate("组稿", tools=None)
    assert completion.text == "正文内容"
    assert bodies[0]["max_tokens"] == 8000
    assert bodies[0]["thinking"] == {"type": "disabled"}
    assert provider.meter.output_tokens == 50  # 记账


def test_judge_uses_native_output_config_not_tool_use() -> None:
    def handler(_r: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_msg(
            '{"answered": true, "answer": "命中"}', in_tok=200, out_tok=8,
        ))

    provider, bodies = _provider(handler)
    payload = provider.generate_structured("判分", ANSWER_SCHEMA, 2)
    assert payload == {"answered": True, "answer": "命中"}
    # 原生结构化：output_config.format，非 tool-use
    assert bodies[0]["output_config"] == {
        "format": {"type": "json_schema", "schema": ANSWER_SCHEMA}
    }
    assert "tools" not in bodies[0]
    assert provider.structured_output_failures == 0  # JSON 干净，零失败
    assert provider.meter.input_tokens == 200
    assert provider.meter.output_tokens == 8


def test_judge_thinking_disabled_in_body() -> None:
    def handler(_r: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_msg('{"answered": false, "answer": ""}'))

    _provider_obj, bodies = _provider(handler)
    _provider_obj.generate_structured("判分", ANSWER_SCHEMA, 2)
    assert bodies[0]["thinking"] == {"type": "disabled"}


def test_thinking_omitted_when_not_disabled() -> None:
    # disable_thinking=False → 省略 thinking 参数（Sonnet 5 默认自适应思考）
    def handler(_r: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_msg("x"))

    provider, bodies = _provider(handler, disable_thinking=False)
    provider.generate("x", tools=None)
    assert "thinking" not in bodies[0]


def test_malformed_json_counts_failure_and_raises() -> None:
    # output_config.format 应保证合法 JSON；防御路径：非法 JSON 计失败并抛
    def handler(_r: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_msg("not json at all"))

    provider, _bodies = _provider(handler)
    with pytest.raises(StructuredOutputExhausted):
        provider.generate_structured("判分", ANSWER_SCHEMA, 2)
    assert provider.structured_output_failures == 1


def test_length_repair_loop_fires_with_paid_provider() -> None:
    """佐证：长度修复环对 PaidTierProvider 真的生效（owner 复跑前置）。
    组稿恒短内容 → 每节 draft + MAX_LENGTH_REPAIRS 次修复（provider.generate
    共 3 次/节）；修复提示词含「草稿」。"""
    from harness.prod_caliber import MAX_LENGTH_REPAIRS, compose_sample

    bodies: list[dict[str, object]] = []

    def make(max_tokens: int) -> PaidTierProvider:
        def transport(request: httpx.Request) -> httpx.Response:
            bodies.append(json.loads(request.content.decode("utf-8")))
            return httpx.Response(200, json=_msg("字" * 40, out_tok=20))
        return PaidTierProvider(
            api_key="sk-test", model="claude-sonnet-5", pricing=PRICING,
            max_tokens=max_tokens, disable_thinking=False,
            http_client=httpx.Client(transport=httpx.MockTransport(transport)),
        )

    compose_sample(make, "golddoc-generic-plain", "generic",
                   repair_enabled=True)
    per_section = 1 + MAX_LENGTH_REPAIRS
    assert len(bodies) == 7 * per_section, "draft + full repair rounds/section"
    prompts = [b["messages"][-1]["content"] for b in bodies]  # type: ignore[index]
    assert any("草稿" in str(p) for p in prompts), "repair prompt issued"


def test_metered_provider_backward_compatible_max_tokens() -> None:
    # MeteredAnthropicProvider 现接受 max_tokens，默认保持原行为
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        assert body["max_tokens"] == 1024  # DEFAULT 未变
        return httpx.Response(200, json=_msg("ok"))

    provider = MeteredAnthropicProvider(
        api_key="sk-test", model="claude-sonnet-5", pricing=PRICING,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    assert provider.generate("hi", tools=None).text == "ok"
