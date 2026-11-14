"""执行器模拟试跑 harness（M4-036，PDD v0.3.1 §7 M4 行）。

- 模拟对象 = 包 zip 字节（执行方视角，不触构建路径）；逐卡三面：
  ① context_refs 可装载——`文件#锚点` 在包内解析（文件是 zip 成员且
  锚点文本在该文件内命中）；② verify_cmd 形态可执行——pytest 形态 +
  tests/ 靶 + 退出码语义可判；③ DAG 可调度——ready_frontier 推进至
  全清（每轮前沿非空）。
- 一次通过率：卡三面首评全绿计一次通过；报告走 eval.pass_rate
  （M4-032 Z 口径：未定线 report_only，NEVER 代 owner 画线）。
"""
from __future__ import annotations

import io
import json
import zipfile
from dataclasses import dataclass
from pathlib import Path

from eval.pass_rate import PassRateReport, pass_rate_report
from flint.dag.frontier import ready_frontier
from flint.domain.models import TaskSpec


@dataclass(frozen=True)
class CardResult:
    task_id: str
    refs_ok: bool
    verify_ok: bool
    notes: list[str]

    @property
    def oneshot(self) -> bool:
        return self.refs_ok and self.verify_ok


@dataclass(frozen=True)
class TrialRunResult:
    pack_name: str
    cards: list[CardResult]
    schedulable: bool
    schedule_rounds: int
    pass_report: PassRateReport


def _anchor_token(anchor: str) -> str:
    return anchor.lstrip("#")


def _ref_loadable(ref: str, members: dict[str, str]) -> str | None:
    filename, _, anchor = ref.partition("#")
    body = members.get(filename)
    if body is None:
        return f"ref file not in pack: {filename}"
    if anchor and _anchor_token(anchor) not in body:
        return f"anchor {anchor} not found in {filename}"
    return None


def _verify_form(verify_cmd: str | None) -> str | None:
    if not verify_cmd:
        return "verify_cmd empty"
    if not verify_cmd.startswith("pytest "):
        return f"not a pytest form: {verify_cmd}"
    if "tests/" not in verify_cmd:
        return f"no tests/ target: {verify_cmd}"
    return None


def _spec_of(item: dict[str, object]) -> TaskSpec:
    def str_list(key: str) -> list[str]:
        value = item[key]
        assert isinstance(value, list)
        return [str(x) for x in value]

    cycles = item["estimate_cycles"]
    return TaskSpec(
        task_id=str(item["task_id"]), title=str(item["title"]),
        inputs=str_list("inputs"), outputs=str_list("outputs"),
        acceptance=str_list("acceptance"), depends_on=str_list("depends_on"),
        milestone=str(item["milestone"]), estimate_days=None,
        estimate_cycles=float(cycles) if isinstance(cycles, int | float) else None,
        oneshot=bool(item["oneshot"]), verify_cmd=str(item["verify_cmd"]),
        context_refs=str_list("context_refs"),
        review_gate=bool(item["review_gate"]),
    )


def simulate_pack(zip_bytes: bytes, pack_name: str) -> TrialRunResult:
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        members = {
            name: archive.read(name).decode("utf-8", errors="replace")
            for name in archive.namelist()
        }
    data = json.loads(members["tasks.json"])
    tasks = [_spec_of(item) for item in data["tasks"]]

    cards: list[CardResult] = []
    for task in tasks:
        notes: list[str] = []
        for ref in task.context_refs or []:
            problem = _ref_loadable(ref, members)
            if problem:
                notes.append(problem)
        refs_ok = not notes
        verify_problem = _verify_form(task.verify_cmd)
        if verify_problem:
            notes.append(verify_problem)
        cards.append(CardResult(
            task_id=task.task_id, refs_ok=refs_ok,
            verify_ok=verify_problem is None, notes=notes,
        ))

    done: set[str] = set()
    rounds = 0
    schedulable = True
    while len(done) < len(tasks):
        frontier = ready_frontier(tasks, done)
        if not frontier:
            schedulable = False
            break
        done.update(frontier)
        rounds += 1

    report = pass_rate_report(
        [(c.task_id, c.oneshot) for c in cards], z_line=None
    )
    return TrialRunResult(
        pack_name=pack_name, cards=cards, schedulable=schedulable,
        schedule_rounds=rounds, pass_report=report,
    )


def run_trials(trials_dir: Path, z_line: float | None = None) -> dict[str, object]:
    index = json.loads(
        (trials_dir / "index.json").read_text(encoding="utf-8")
    )
    results: list[TrialRunResult] = []
    outcomes: list[tuple[str, bool]] = []
    for sample in index["samples"]:
        payload = (trials_dir / str(sample["path"])).read_bytes()
        result = simulate_pack(payload, str(sample["name"]))
        results.append(result)
        outcomes.extend(
            (f"{result.pack_name}:{c.task_id}", c.oneshot)
            for c in result.cards
        )
    overall = pass_rate_report(outcomes, z_line=z_line)
    return {"results": results, "overall": overall}
