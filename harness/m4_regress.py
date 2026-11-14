"""M4 回归 harness：spec 导出线五线离线合跑（M4-038，技术方案 E12）。

- 五线：registry（四态回放）/ dag（构造违规全景）/ 导出门禁（三与门
  三败一复原，进程内判定面）/ 包完整性（三试跑包四面）/ 试跑（逐卡
  三面 + 一次通过率）。
- 零联网（S2-7）：输入只有 fixtures/ 回放、assets/trial_specs、
  contracts/——主路径进程内。委托覆盖（不在本进程重复跑，summary
  注明）：fmt=pack 端点 E2E（DB/ASGI）→ tests/m4/test_m4_030；
  spec_export job（DB/kill-9）→ tests/m4/test_m4_029。
- 逐包 trace：docs/trace/m4-packs/{name}.md——零时间戳、输入确定则
  字节稳定（M4-038 验收第二行）。
- 退出码：任一线失败 → 1。
运行：python -m harness.m4_regress
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from eval.dag import run_dag_eval
from eval.pack_integrity import run_pack_integrity_eval
from eval.registry import run_registry_eval
from flint.domain.models import DagReport
from flint.registry.gate import RegistryGateResult
from flint.spec.export_gate import vibe_export_gate
from harness.spec_trial import TrialRunResult, simulate_pack

REPO_ROOT = Path(__file__).resolve().parents[1]
TRIALS = REPO_ROOT / "assets" / "trial_specs"
TRACE_DIR = REPO_ROOT / "docs" / "trace" / "m4-packs"

_CLEAN_DAG = DagReport(acyclic=True, orphans=[], unreachable=[], errors=[])
_CLEAN_REGISTRY = RegistryGateResult(violations=[], gap=None)


@dataclass(frozen=True)
class LineResult:
    name: str
    ok: bool
    detail: str


@dataclass(frozen=True)
class M4RegressReport:
    lines: list[LineResult]
    traces: list[Path]
    all_ok: bool


def registry_line() -> LineResult:
    report = run_registry_eval()
    return LineResult(
        name="registry", ok=report.all_ok,
        detail=f"{sum(r.ok for r in report.rows)}/{len(report.rows)} rows",
    )


def dag_line() -> LineResult:
    report = run_dag_eval()
    ok = (
        report.detected == report.expected_detections
        and report.false_positives == 0
    )
    return LineResult(
        name="dag", ok=ok,
        detail=f"detected {report.detected}/{report.expected_detections}, "
        f"fp {report.false_positives}",
    )


def export_gate_line() -> LineResult:
    blocked_review = vibe_export_gate(["b-1"], _CLEAN_DAG, _CLEAN_REGISTRY)
    blocked_dag = vibe_export_gate(
        [], DagReport(acyclic=False, orphans=[], unreachable=[],
                      errors=["cycle: A -> B -> A"]),
        _CLEAN_REGISTRY,
    )
    blocked_registry = vibe_export_gate(
        [], _CLEAN_DAG,
        RegistryGateResult(violations=["unavailable"], gap=None),
    )
    recovered = vibe_export_gate([], _CLEAN_DAG, _CLEAN_REGISTRY)
    ok = (
        not blocked_review.allowed and not blocked_dag.allowed
        and not blocked_registry.allowed and recovered.allowed
    )
    return LineResult(
        name="export-gate", ok=ok,
        detail="3 blocks + 1 recover (in-process; endpoint E2E delegated)",
    )


def _pack_names() -> list[str]:
    index = json.loads((TRIALS / "index.json").read_text(encoding="utf-8"))
    return [str(s["name"]) for s in index["samples"]]


def integrity_line() -> tuple[LineResult, dict[str, bool]]:
    per_pack: dict[str, bool] = {}
    for name in _pack_names():
        payload = (TRIALS / name / "pack.zip").read_bytes()
        per_pack[name] = run_pack_integrity_eval(payload).all_ok
    return (
        LineResult(
            name="pack-integrity", ok=all(per_pack.values()),
            detail=f"{sum(per_pack.values())}/{len(per_pack)} packs",
        ),
        per_pack,
    )


def trial_line() -> tuple[LineResult, dict[str, TrialRunResult]]:
    results: dict[str, TrialRunResult] = {}
    for name in _pack_names():
        payload = (TRIALS / name / "pack.zip").read_bytes()
        results[name] = simulate_pack(payload, name)
    ok = all(
        r.schedulable and r.pass_report.rate == 1.0 for r in results.values()
    )
    return (
        LineResult(
            name="trial", ok=ok,
            detail=f"{len(results)} packs simulated",
        ),
        results,
    )


def pack_trace(
    name: str, integrity_ok: bool, trial: TrialRunResult
) -> str:
    meta = json.loads(
        (TRIALS / name / "meta.json").read_text(encoding="utf-8")
    )
    lines = [
        f"# M4 回归 trace：试跑包 {name}",
        "",
        f"- case: {meta['case_id']}（{meta['tier']} / {meta['category']}）",
        (
            f"- 任务卡：{meta['task_count']} 张；竞争面卡："
            f"{', '.join(meta['competition_task_ids'])}"
        ),
        f"- 构建期门态：{json.dumps(meta['gates'], ensure_ascii=False, sort_keys=True)}",
        f"- 包完整性四面：{'全绿' if integrity_ok else '失败'}",
        (
            f"- 执行器模拟：可调度={trial.schedulable} "
            f"轮数={trial.schedule_rounds} 一次通过率={trial.pass_report.rate}"
        ),
        "",
        "| task_id | refs | verify |",
        "|---|---|---|",
    ]
    for card in trial.cards:
        lines.append(
            f"| {card.task_id} | {'ok' if card.refs_ok else 'FAIL'} "
            f"| {'ok' if card.verify_ok else 'FAIL'} |"
        )
    return "\n".join(lines) + "\n"


def run_m4_regress() -> M4RegressReport:
    lines: list[LineResult] = [registry_line(), dag_line(), export_gate_line()]
    integrity, per_pack = integrity_line()
    lines.append(integrity)
    trial, results = trial_line()
    lines.append(trial)

    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    traces: list[Path] = []
    for name in _pack_names():
        path = TRACE_DIR / f"{name}.md"
        path.write_text(
            pack_trace(name, per_pack[name], results[name]),
            encoding="utf-8", newline="\n",
        )
        traces.append(path)

    return M4RegressReport(
        lines=lines, traces=traces, all_ok=all(l.ok for l in lines),
    )


def main() -> int:
    report = run_m4_regress()
    for line in report.lines:
        print(f"{'PASS' if line.ok else 'FAIL'} {line.name}: {line.detail}")
    return 0 if report.all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
