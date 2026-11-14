"""vibe_pack S7 Verification Harness 章（M4-005，CLAUDE.md#S7 同构）。

- 汇总逐任务 verify_cmd + 全局门声明（调用方给出目标仓的门命令）+
  返工环规则（同因连续 2 次失败 → 按 S9 升级，NEVER 第三次盲试）。
- 零容忍：任何任务缺 verify_cmd（None 或空串）即拒——S5 的 verify
  覆盖率 100% 在章生成处第二道把守。
"""
from __future__ import annotations

from flint.domain.models import TaskSpec


class S7VerifyError(Exception):
    pass


def build_s7(tasks: list[TaskSpec], global_gate: str) -> str:
    missing = [t.task_id for t in tasks if not t.verify_cmd]
    if missing:
        raise S7VerifyError(f"tasks without verify_cmd: {missing}")
    lines = [
        "## S7 Verification Harness",
        "",
        (
            "- **约定**：每任务 MUST 先写失败测试再实现（顺序不可倒）；"
            "verify_cmd exit 0 = 机器验收通过；"
        ),
        f"- **全局门**（每次合并强制）：`{global_gate}`；",
        (
            "- **返工环**：verify 或 review 失败 → 按意见修改重跑；"
            "同一原因连续 2 次失败 → MUST 按 S9 升级，NEVER 第三次盲试。"
        ),
        "",
        "| task_id | verify_cmd |",
        "|---|---|",
    ]
    for task in tasks:
        lines.append(f"| {task.task_id} | {task.verify_cmd} |")
    return "\n".join(lines)
