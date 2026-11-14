"""一次性模型预热（owner 修复令步 3）：正式组稿前用一个丢弃调用把模型
载入显存（长超时吸收冷加载）；被测的每节调用仍用 600s 紧超时。

预热用独立 client/provider——不入 fixture 录制、不进 usage 计量。
"""
from __future__ import annotations

import httpx

from flint.llm.local import DEFAULT_TIMEOUT
from harness.prod_caliber import WARMUP_TIMEOUT, _warmup_model


def _ok_response(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "choices": [{"message": {"content": "ok"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        },
    )


def test_warmup_issues_one_discarded_call() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return _ok_response(request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = _warmup_model(
        "http://local/v1", "gemma4:31b", http_client=client
    )
    assert result is None  # 结果丢弃
    assert len(calls) == 1  # 恰一次预热调用
    assert calls[0].url.path.endswith("/chat/completions")


def test_warmup_requests_minimal_generation() -> None:
    """预热只为载入显存——max_tokens=1，别浪费算力生成长文。"""
    seen: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json as _json

        seen.append(_json.loads(request.content))
        return _ok_response(request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    _warmup_model("http://local/v1", "gemma4:31b", http_client=client)
    assert seen[0]["model"] == "gemma4:31b"
    assert seen[0]["max_tokens"] == 1


def test_warmup_timeout_is_long_one_shot() -> None:
    """预热用一次性长超时（吸收冷加载），显著长于被测节的 600s 紧超时。"""
    assert WARMUP_TIMEOUT > DEFAULT_TIMEOUT  # DEFAULT_TIMEOUT == 600.0
    assert WARMUP_TIMEOUT >= 1800.0
