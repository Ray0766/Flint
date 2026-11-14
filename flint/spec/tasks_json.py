"""包内 tasks.json 机读导出（M4-008，冻结件 DagReport 数据形）。

- 单真相互校：S5 章表格行 task_id 集与 tasks_payload 必须完全一致
  （同源构建的两投影互为校验，漂移即拒）；「任务 N 张」计数行同校。
- dag_report 附带：acyclic（图核心实算）+ critical_path_cycles +
  total_cycles + tasks 计数——与本仓 tasks.json 顶层同构。
"""
from __future__ import annotations

import json

from flint.dag.frontier import critical_path_cycles
from flint.dag.graph import analyze_graph
from flint.domain.models import TaskSpec
from flint.spec.vibe_s5 import S5Chapter


class TasksJsonExportError(Exception):
    pass


def _payload_tasks(chapter: S5Chapter) -> list[dict[str, object]]:
    payload = chapter.tasks_payload
    if not isinstance(payload, dict) or not isinstance(payload.get("tasks"), list):
        raise TasksJsonExportError("tasks_payload shape invalid")
    return [item for item in payload["tasks"] if isinstance(item, dict)]


def _table_ids(chapter: S5Chapter) -> list[str]:
    rows = [
        line for line in chapter.markdown.splitlines()
        if line.startswith("| ") and not line.startswith("| task_id")
        and not line.startswith("|---")
    ]
    return [row.split("|")[1].strip() for row in rows]


def _str_list(item: dict[str, object], key: str) -> list[str]:
    value = item[key]
    if not isinstance(value, list):
        raise TasksJsonExportError(f"payload field {key} must be a list")
    return [str(x) for x in value]


def _spec_of(item: dict[str, object]) -> TaskSpec:
    cycles = item["estimate_cycles"]
    return TaskSpec(
        task_id=str(item["task_id"]),
        title=str(item["title"]),
        inputs=_str_list(item, "inputs"),
        outputs=_str_list(item, "outputs"),
        acceptance=_str_list(item, "acceptance"),
        depends_on=_str_list(item, "depends_on"),
        milestone=str(item["milestone"]),
        estimate_days=None,
        estimate_cycles=float(cycles) if isinstance(cycles, int | float) else None,
        oneshot=bool(item["oneshot"]),
        verify_cmd=str(item["verify_cmd"]),
        context_refs=_str_list(item, "context_refs"),
        review_gate=bool(item["review_gate"]),
    )


def export_tasks_json(chapter: S5Chapter) -> str:
    items = _payload_tasks(chapter)
    payload_ids = [str(item["task_id"]) for item in items]
    table_ids = _table_ids(chapter)
    if payload_ids != table_ids:
        raise TasksJsonExportError(
            f"S5 table and payload diverged: table={table_ids} "
            f"payload={payload_ids}"
        )
    if f"任务 {len(items)} 张" not in chapter.markdown:
        raise TasksJsonExportError("S5 count line diverged from payload size")

    tasks = [_spec_of(item) for item in items]
    graph = analyze_graph(tasks)
    document = {
        "dag_report": {
            "tasks": len(tasks),
            "acyclic": graph.acyclic,
            "critical_path_cycles": critical_path_cycles(tasks),
            "total_cycles": sum(t.estimate_cycles or 0 for t in tasks),
        },
        "tasks": items,
    }
    return json.dumps(document, ensure_ascii=False, indent=1)
