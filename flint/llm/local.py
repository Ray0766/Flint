"""LocalProvider：OpenAI 兼容本地端点适配（owner 裁决：免费档本地模型）。

- 冻结协议 LLMProvider 逐字实现：generate(prompt, tools)->Completion /
  generate_structured(prompt, schema, max_retries)->JSON；降级语义同
  M2-003（structured_loop 复用：失败回喂 ≤max_retries、耗尽抛
  StructuredOutputExhausted、失败数累入 structured_output_failures）。
- 传输走已锁版 httpx（零新依赖）；本地推理模型的 reasoning 字段在适配
  层丢弃（Completion.text 只取 content——思考过程不是产物）；结构化
  路径前置剥离 markdown 代码栅栏后交 _extract_payload 文本 JSON 解析。
- 记账：本地无 API 费用 → UsageMeter(FREE)，cost=0 是**实值**（免费档
  事实）而非占位；usage tokens 照 API 返回实录。
- key：可选（多数本地端点不需要）；只从构造参数注入（上游从环境读），
  NEVER 硬编码 / NEVER 写日志。
"""
from __future__ import annotations

import json
import re
from typing import Any

import httpx

from flint.domain.models import JSON, Completion
from flint.llm.production import FREE, UsageMeter
from flint.llm.structured import StructuredOutputExhausted, structured_loop

DEFAULT_MAX_TOKENS = 4096
DEFAULT_TIMEOUT = 600.0

_FENCE_RE = re.compile(r"\A```[a-zA-Z]*\s*|\s*```\Z")


class LocalProviderUnavailable(Exception):
    """本地端点不可达 / 非 200——与「模型答错」严格分离。"""


def _strip_fences(text: str) -> str:
    return _FENCE_RE.sub("", text.strip()).strip()


def _to_openai_tools(tools: list[JSON]) -> list[JSON]:
    """anthropic 形 {name, description, input_schema} → OpenAI 形。"""
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t.get("description", ""),
                "parameters": t.get("input_schema", {}),
            },
        }
        for t in tools
        if isinstance(t, dict)
    ]


class LocalProvider:
    def __init__(
        self,
        base_url: str,
        model: str,
        http_client: httpx.Client | None = None,
        api_key: str | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = 0.2,
        timeout: float = DEFAULT_TIMEOUT,
        disable_reasoning: bool = False,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self.model = model
        self._max_tokens = max_tokens
        self._temperature = temperature
        # 推理模型（如 gemma4:31b）默认先产大段推理 token（本适配层丢弃却
        # 耗 max_tokens 预算与时间）。置 True → 请求带 OpenAI 标准参数
        # reasoning_effort="none" 关推理（/v1 认此参、不认 think）。默认
        # False = 通用适配器行为逐字不变。
        self._disable_reasoning = disable_reasoning
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._client = http_client or httpx.Client(
            timeout=timeout, headers=headers
        )
        self.meter = UsageMeter(pricing=FREE)
        self.structured_output_failures = 0

    def generate(self, prompt: str, tools: list[JSON] | None) -> Completion:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": self._max_tokens,
            "temperature": self._temperature,
        }
        if self._disable_reasoning:
            body["reasoning_effort"] = "none"
        if tools is not None:
            body["tools"] = _to_openai_tools(tools)
        try:
            response = self._client.post(
                f"{self._base_url}/chat/completions", json=body
            )
        except httpx.HTTPError as err:
            raise LocalProviderUnavailable(
                f"local endpoint unreachable for {self.model}: {err}"
            ) from err
        if response.status_code != 200:
            raise LocalProviderUnavailable(
                f"local endpoint returned {response.status_code} "
                f"for {self.model}"
            )
        data: dict[str, Any] = response.json()
        message = data["choices"][0]["message"]

        tool_calls: list[JSON] = []
        for call in message.get("tool_calls") or []:
            arguments = call["function"].get("arguments")
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except ValueError:
                    arguments = None
            tool_calls.append({
                "id": call.get("id", ""),
                "name": call["function"]["name"],
                "arguments": arguments,
            })

        raw_usage = data.get("usage") or {}
        usage: JSON = {
            "input_tokens": int(raw_usage.get("prompt_tokens", 0)),
            "output_tokens": int(raw_usage.get("completion_tokens", 0)),
        }
        completion = Completion(
            text=message.get("content") or "",
            tool_calls=tool_calls,
            usage=usage,
        )
        self.meter.add(usage)
        return completion

    def _generate_cleaned(self, prompt: str) -> Completion:
        completion = self.generate(prompt, tools=None)
        return Completion(
            text=_strip_fences(completion.text),
            tool_calls=completion.tool_calls,
            usage=completion.usage,
        )

    def generate_structured(
        self, prompt: str, schema: JSON, max_retries: int
    ) -> JSON:
        # 文本 JSON 路径没有 tool input_schema 兜底——schema 必须进提示词
        # （与 anthropic tool-use 路径的 schema 可见性对齐）
        framed = (
            f"{prompt}\n\nJSON MUST 符合此 schema（字段名逐字一致，"
            f"不加多余字段）：\n{json.dumps(schema, ensure_ascii=False)}\n"
            "只输出 JSON 本体，不加代码栅栏。"
        )
        try:
            payload, failed = structured_loop(
                self._generate_cleaned, framed, schema, max_retries
            )
        except StructuredOutputExhausted as err:
            self.structured_output_failures += err.failed_attempts
            raise
        self.structured_output_failures += failed
        assert payload is not None
        return payload
