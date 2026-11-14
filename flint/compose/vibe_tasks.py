"""vibe_pack S5 任务卡结构化输出（M3-031，技术方案 E5 / 冻结件 TaskSpec）。

- schema = TaskSpec 判别字段全集（ai 路径四件套 estimate_cycles/verify_cmd/
  context_refs/review_gate 全必填）；结构化耗尽 → 章节类降级（S5 章标缺口，
  NEVER 猜任务）。
- shape_check（DagValidator 形校验前移，E5「生成时即校验」）：
  estimate_cycles ≤2、verify_cmd 非空、悬空依赖检出、task_id 唯一——
  M4 DagValidator 实调在导出门禁复检。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final

from flint.domain.models import JSON, GapHint, TaskSpec
from flint.domain.protocols import LLMProvider
from flint.llm.structured import StructuredOutputExhausted

TASK_CARD_SCHEMA: Final[JSON] = {
    "type": "object",
    "properties": {
        "tasks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "minLength": 1},
                    "title": {"type": "string", "minLength": 1},
                    "inputs": {"type": "array", "items": {"type": "string"}},
                    "outputs": {"type": "array", "items": {"type": "string"}},
                    "acceptance": {"type": "array", "items": {"type": "string"}},
                    "depends_on": {"type": "array", "items": {"type": "string"}},
                    "milestone": {"type": "string", "minLength": 1},
                    "estimate_cycles": {"type": "number"},
                    "oneshot": {"type": "boolean"},
                    "verify_cmd": {"type": "string", "minLength": 1},
                    "context_refs": {"type": "array", "items": {"type": "string"}},
                    "review_gate": {"type": "boolean"},
                },
                "required": [
                    "task_id", "title", "inputs", "outputs", "acceptance",
                    "depends_on", "milestone", "estimate_cycles", "oneshot",
                    "verify_cmd", "context_refs", "review_gate",
                ],
                "additionalProperties": False,
            },
        }
    },
    "required": ["tasks"],
    "additionalProperties": False,
}

_PROMPT = (
    "把以下规划素材拆解为 AI 执行任务卡（ai_executor 双单位口径：只填 "
    "estimate_cycles，上限 2；verify_cmd 必填）。只输出符合 schema 的 JSON。\n"
    "素材：\n{source}"
)

MAX_CYCLES: Final[float] = 2.0


@dataclass
class S5Extraction:
    tasks: list[TaskSpec] = field(default_factory=list)
    degraded: bool = False
    gap: GapHint | None = None


def extract_task_cards(
    provider: LLMProvider, section_source: str, max_retries: int = 2
) -> S5Extraction:
    try:
        payload = provider.generate_structured(
            _PROMPT.format(source=section_source), TASK_CARD_SCHEMA, max_retries
        )
    except StructuredOutputExhausted:
        return S5Extraction(
            degraded=True,
            gap=GapHint(
                missing_what="S5 任务卡拆解未完成（结构化输出耗尽，不猜任务）",
                cause="missing_data",
                suggested_sources=["重试本章生成", "人工拆解任务卡"],
                action="search",
            ),
        )
    tasks = [
        TaskSpec(
            task_id=str(item["task_id"]),
            title=str(item["title"]),
            inputs=[str(x) for x in item["inputs"]],
            outputs=[str(x) for x in item["outputs"]],
            acceptance=[str(x) for x in item["acceptance"]],
            depends_on=[str(x) for x in item["depends_on"]],
            milestone=str(item["milestone"]),
            estimate_days=None,
            estimate_cycles=float(item["estimate_cycles"]),
            oneshot=bool(item["oneshot"]),
            verify_cmd=str(item["verify_cmd"]),
            context_refs=[str(x) for x in item["context_refs"]],
            review_gate=bool(item["review_gate"]),
        )
        for item in payload["tasks"]
    ]
    return S5Extraction(tasks=tasks)


def shape_check(tasks: list[TaskSpec]) -> list[str]:
    violations: list[str] = []
    ids = [t.task_id for t in tasks]
    known = set(ids)
    if len(ids) != len(known):
        violations.append("duplicate task_id in card set")
    for task in tasks:
        if task.estimate_cycles is None or task.estimate_cycles > MAX_CYCLES:
            violations.append(
                f"{task.task_id}: estimate_cycles must be <= {MAX_CYCLES}"
            )
        if not task.verify_cmd:
            violations.append(f"{task.task_id}: verify_cmd is mandatory (E3)")
        if not task.context_refs:
            violations.append(f"{task.task_id}: context_refs required (S6)")
        for dep in task.depends_on:
            if dep not in known:
                violations.append(f"{task.task_id}: unknown dependency {dep}")
    return violations
