"""verdict 零猜测（M2-039，D9 / 技术方案 E5 落地）。

- verdict 类结构化输出耗尽（1 次主试 + ≤2 次重试）→ VerdictCallOutcome
  failed=True + 说明文案（含尝试次数与 schema 错误），编排层（M2-040）据此
  置 job failed——绝不猜测出一个判定。
- 失败计数与降级路径记入 GenerationRecord 副本：structured_output_failures
  累加、params[VERDICT_DEGRADATION_KEY] 记 path="job_failed_no_guess" 与
  错误清单；原记录不动（留档）。
- 「绝不猜」是结构不变量：failed=True 与 payload 互斥，构造期即抛错，
  下游拿不到一个「失败但有值」的判定。
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Final

from flint.domain.models import JSON, GenerationRecord
from flint.llm.structured import GenerateFn, VerdictStructuredFailure, run_structured

VERDICT_DEGRADATION_KEY: Final[str] = "verdict_degradation"


@dataclass(frozen=True)
class VerdictCallOutcome:
    payload: JSON | None
    failed: bool
    failure_reason: str | None
    record: GenerationRecord

    def __post_init__(self) -> None:
        if self.failed and self.payload is not None:
            raise ValueError("failed verdict call never carries a payload (D9)")
        if self.failed and not self.failure_reason:
            raise ValueError("failed verdict call requires an explanation")
        if not self.failed and self.payload is None:
            raise ValueError("successful verdict call requires a payload")


def run_verdict_structured(
    generate: GenerateFn,
    prompt: str,
    schema: JSON,
    record: GenerationRecord,
    max_retries: int = 2,
) -> VerdictCallOutcome:
    try:
        result = run_structured(
            generate, prompt, schema, call_type="verdict", max_retries=max_retries
        )
    except VerdictStructuredFailure as err:
        degraded_params: JSON = {
            **record.params,
            VERDICT_DEGRADATION_KEY: {
                "path": "job_failed_no_guess",
                "failed_attempts": err.failed_attempts,
                "errors": list(err.errors),
            },
        }
        failed_record = replace(
            record,
            params=degraded_params,
            structured_output_failures=(
                record.structured_output_failures + err.failed_attempts
            ),
        )
        return VerdictCallOutcome(
            payload=None,
            failed=True,
            failure_reason=str(err),
            record=failed_record,
        )
    updated = replace(
        record,
        structured_output_failures=(
            record.structured_output_failures + result.failed_attempts
        ),
    )
    return VerdictCallOutcome(
        payload=result.payload, failed=False, failure_reason=None, record=updated
    )
