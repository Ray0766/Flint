"""generate_structured 主路与分级降级（M2-003，D9 / 技术方案 E5）。

- 主路：tool use 输出 → 本方 schema 校验（轻量 JSON-Schema 子集，零新依赖）；
  失败把校验错误逐字回喂重试，上限 max_retries=2（S2-3）——绝无第三次盲试。
- 分级降级：verdict 类全败 → VerdictStructuredFailure（job failed 并说明，
  绝不猜）；section 类全败 → StructuredResult(degraded=True)（该章标缺口
  继续，不阻塞）。
- 失败计数经 failed_attempts 返回并累加 AnthropicProvider.structured_output_failures
  ——GenerationRecord.structured_output_failures 的进账通道。
"""
from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from flint.domain.models import JSON, Completion

GenerateFn = Callable[[str], Completion]
CallType = Literal["verdict", "section"]

_RETRY_TEMPLATE = (
    "{prompt}\n\n上一次输出未通过 schema 校验，错误：{errors}。"
    "请修正后重新只输出合规 JSON。"
)


class StructuredOutputExhausted(Exception):
    def __init__(self, failed_attempts: int, errors: list[str]) -> None:
        super().__init__(
            f"structured output failed after {failed_attempts} attempts: {errors}"
        )
        self.failed_attempts = failed_attempts
        self.errors = errors


class VerdictStructuredFailure(Exception):
    """D9：verdict 类结构化输出耗尽 → job failed 并说明，绝不猜。"""

    def __init__(self, failed_attempts: int, errors: list[str]) -> None:
        super().__init__(
            f"verdict structured output exhausted after {failed_attempts} attempts "
            f"(绝不猜测，job failed): {errors}"
        )
        self.failed_attempts = failed_attempts
        self.errors = errors


@dataclass(frozen=True)
class StructuredResult:
    payload: JSON | None
    degraded: bool
    failed_attempts: int


# ── 轻量 JSON-Schema 子集校验（type/properties/required/enum/
#    additionalProperties/minLength/maxLength/items）────────


def validate_schema(schema: JSON, value: Any, path: str = "$") -> list[str]:
    errors: list[str] = []
    expected_type = schema.get("type")
    if expected_type is not None and not _type_ok(expected_type, value):
        return [f"{path}: type must be {expected_type}"]

    if expected_type == "object" and isinstance(value, dict):
        properties: JSON = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{path}.{key}: required field missing")
        if schema.get("additionalProperties") is False:
            for key in value:
                if key not in properties:
                    errors.append(f"{path}.{key}: additionalProperties forbidden")
        for key, sub_schema in properties.items():
            if key in value:
                errors.extend(validate_schema(sub_schema, value[key], f"{path}.{key}"))

    if expected_type == "array" and isinstance(value, list):
        item_schema = schema.get("items")
        if item_schema is not None:
            for i, item in enumerate(value):
                errors.extend(validate_schema(item_schema, item, f"{path}[{i}]"))

    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: enum violation, allowed {schema['enum']}")
    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            errors.append(f"{path}: minLength {schema['minLength']} violated")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            errors.append(f"{path}: maxLength {schema['maxLength']} violated")
    return errors


def _type_ok(expected: str, value: Any) -> bool:
    mapping: dict[str, tuple[type, ...]] = {
        "object": (dict,),
        "array": (list,),
        "string": (str,),
        "integer": (int,),
        "number": (int, float),
        "boolean": (bool,),
    }
    allowed = mapping.get(expected)
    if allowed is None:
        return True
    if expected in ("integer", "number") and isinstance(value, bool):
        return False
    return isinstance(value, allowed)


# ── 重试环 ────────────────────────────────────────────────


def _extract_payload(completion: Completion) -> tuple[Any, list[str]]:
    if completion.tool_calls:
        return completion.tool_calls[0].get("arguments"), []
    text = completion.text.strip()
    if text:
        try:
            return json.loads(text), []
        except json.JSONDecodeError as err:
            return None, [f"$: text is not valid JSON ({err.msg})"]
    return None, ["$: neither tool call nor text payload present"]


def structured_loop(
    generate: GenerateFn, prompt: str, schema: JSON, max_retries: int
) -> tuple[JSON | None, int]:
    """Returns (payload, failed_attempts). Raises StructuredOutputExhausted
    when 1 + max_retries attempts all fail."""
    failed = 0
    current = prompt
    last_errors: list[str] = []
    for _attempt in range(1 + max_retries):
        payload, parse_errors = _extract_payload(generate(current))
        errors = parse_errors or validate_schema(schema, payload)
        if not errors:
            assert isinstance(payload, dict)
            return payload, failed
        failed += 1
        last_errors = errors
        current = _RETRY_TEMPLATE.format(prompt=prompt, errors="; ".join(errors))
    raise StructuredOutputExhausted(failed, last_errors)


def run_structured(
    generate: GenerateFn,
    prompt: str,
    schema: JSON,
    call_type: CallType,
    max_retries: int = 2,
) -> StructuredResult:
    """按调用点类型降级（D9）：verdict 绝不猜、section 标缺口。"""
    try:
        payload, failed = structured_loop(generate, prompt, schema, max_retries)
    except StructuredOutputExhausted as err:
        if call_type == "verdict":
            raise VerdictStructuredFailure(err.failed_attempts, err.errors) from err
        return StructuredResult(payload=None, degraded=True, failed_attempts=err.failed_attempts)
    return StructuredResult(payload=payload, degraded=False, failed_attempts=failed)
