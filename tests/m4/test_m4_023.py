"""M4-023 acceptance tests: DagValidator assembly + dogfood.

Acceptance (tasks.json M4-023):
  - validate(tasks) yields one aggregated frozen DagReport
  - this repo's own tasks.json (232 cards) passes self-validation (dogfood)

卡数哨兵的摆放（2026-08-01 教训，勿再倒回去）：
  `len(tasks)` 是清单数量哨兵，**MUST 放在结构校验之后**。
  它曾被放在 validate() 之前——断言一炸，acyclic/unreachable/orphans/errors
  四条结构断言就整段不执行，把真实的 orphans 缺陷藏了约 28 小时并连穿多个 review_gate。
  哨兵先炸 ≠ 结构没问题；结构真相必须先跑出来。
"""
from __future__ import annotations

import json
from pathlib import Path

from flint.dag.validator import validate
from flint.domain.models import DagReport, TaskSpec

REPO_ROOT = Path(__file__).resolve().parents[2]

SELF_EXTERNALS = {
    "repo-skeleton", "frozen:models.py", "frozen:protocols.py",
    "eval.doc_metrics",  # M3 既有产物（里程碑间交接面）
}


def own_tasks() -> list[TaskSpec]:
    data = json.loads(
        (REPO_ROOT / "tasks.json").read_text(encoding="utf-8-sig")
    )
    return [
        TaskSpec(
            task_id=t["task_id"], title=t["title"], inputs=t["inputs"],
            outputs=t["outputs"], acceptance=t["acceptance"],
            depends_on=t["depends_on"], milestone=t["milestone"],
            estimate_days=t.get("estimate_days"),
            estimate_cycles=t.get("estimate_cycles"),
            oneshot=t.get("oneshot"), verify_cmd=t.get("verify_cmd"),
            context_refs=t.get("context_refs"),
            review_gate=t.get("review_gate"),
        )
        for t in data["tasks"]
    ]


def bad_task() -> TaskSpec:
    return TaskSpec(
        task_id="T-BAD", title="w", inputs=["phantom"], outputs=["x"],
        acceptance=["a"], depends_on=["T-GHOST"], milestone="M1",
        estimate_cycles=3, oneshot=False, verify_cmd=None,
        context_refs=[], review_gate=False,
    )


def test_aggregated_report_collects_every_layer() -> None:
    report = validate([bad_task()])
    assert isinstance(report, DagReport)
    joined = " ".join(report.errors)
    assert "T-GHOST" in joined, "graph layer"
    assert "phantom" in joined, "inputs layer"
    assert "estimate_cycles 3" in joined or "exceeds 2" in joined, "dual-unit"
    assert "verify_cmd" in joined, "quality gate"
    assert "context_refs" in joined


def test_dogfood_own_tasks_json_passes() -> None:
    tasks = own_tasks()
    report = validate(
        tasks, audience="ai_executor", external_inputs=SELF_EXTERNALS,
        allow_reference_days=True,  # S5：人日为参考值口径（生成路径不豁免）
        # 里程碑出口 = 图的终端卡（无人依赖者）。M2/M3 出口已被后续批依赖故非终端。
        #   M1-041     = M1 出口
        #   M4-044     = M4 出口
        #   FE-CORE-007 = 前端总出口（FE-004 被它依赖故非终端）
        #   TS-012 / TS-014 = TS 主题子系统的两张终点卡（owner 裁决 @2026-08-01 登记为出口）。
        #     注：TS-014 被登记为出口**只是图上的终点身份**，NEVER 代表授权它运行——
        #     它涉及付费云端调用，付费授权是独立的、另行给出的一件事。
        # 已移除 'FV-002'：它被 TS-008 依赖，**不是终端**，登记在此处纯属过期且不起作用
        #   （exit_ids 只对终端卡生效）。留着会在它将来真变成终端时静默吞掉 orphan 信号。
        exit_ids={"M1-041", "M4-044", "FE-CORE-007", "TS-012", "TS-014"},
    )
    # 结构校验先行：这四条是图的真相，任何哨兵都不得挡在它们前面（见模块 docstring）。
    assert report.acyclic is True
    assert report.unreachable == []
    assert report.orphans == []
    assert report.errors == [], report.errors[:5]
    # 清单数量哨兵：随卡片增减对账更新。放在结构断言之后，故它失败时不掩盖上面四条。
    assert len(tasks) == 232  # M1 41 / M2 52 / M3 66 / M4 44 / FE 5 / FE-CORE 8 / FV 2 / TS 14


def test_reference_days_waiver_never_for_generated_packs() -> None:
    from flint.compose.vibe_tasks import extract_task_cards

    class Scripted:
        def generate(self, prompt: str, tools: object) -> object:
            raise NotImplementedError

        def generate_structured(self, prompt: str, schema: object,
                                max_retries: int) -> dict:
            return {"tasks": [{
                "task_id": "G-1", "title": "t", "inputs": [], "outputs": ["x"],
                "acceptance": ["a"], "depends_on": [], "milestone": "M1",
                "estimate_cycles": 1, "oneshot": True,
                "verify_cmd": "pytest x", "context_refs": ["S3"],
                "review_gate": False,
            }]}

    generated = extract_task_cards(Scripted(), "素材").tasks  # type: ignore[arg-type]
    assert all(t.estimate_days is None for t in generated), (
        "generator emits days=None; strict exclusivity holds without waiver"
    )
    report = validate(generated, audience="ai_executor")
    assert report.errors == []
