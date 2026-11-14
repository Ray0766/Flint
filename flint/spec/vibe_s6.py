"""vibe_pack S6 Context Manifest 章（M4-004，CLAUDE.md#S6 同构）。

- 三组规则：恒装（S2+S3+当前任务卡）/ 按需（逐任务 context_refs 表）/
  预算行（上限引用 flint.dag.quality_gate.CONTEXT_BUDGET_TOKENS，单一定义）。
- 悬空 ref 拒绝：known_anchors 之外的引用 = 生成包指向不存在的章节，
  执行方会装载失败——生成期即拒；无 refs 的任务同拒（S6 规则无从建立）。
"""
from __future__ import annotations

from flint.dag.quality_gate import CONTEXT_BUDGET_TOKENS
from flint.domain.models import TaskSpec


class S6RefError(Exception):
    pass


def build_s6(tasks: list[TaskSpec], known_anchors: frozenset[str]) -> str:
    problems: list[str] = []
    for task in tasks:
        refs = task.context_refs or []
        if not refs:
            problems.append(f"{task.task_id}: context_refs missing")
        for ref in refs:
            if ref not in known_anchors:
                problems.append(f"{task.task_id}: dangling ref {ref}")
    if problems:
        raise S6RefError("; ".join(problems))
    lines = [
        "## S6 Context Manifest",
        "",
        "- **恒装**：S2 + S3 + 当前任务卡；",
        (
            "- **按需**：任务卡 context_refs（下表），记法 `文件#锚点`，"
            "只装列出的章节，NEVER 整包装载；"
        ),
        (
            f"- **预算**：单 cycle 装载 MUST ≤{CONTEXT_BUDGET_TOKENS} tokens；"
            "超 → 收窄 refs 或拆任务，并在 trace 记录实际装载清单。"
        ),
        "",
        "| task_id | context_refs |",
        "|---|---|",
    ]
    for task in tasks:
        lines.append(f"| {task.task_id} | {', '.join(task.context_refs or [])} |")
    return "\n".join(lines)
