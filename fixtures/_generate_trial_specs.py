"""试跑 spec 三样本生成器（M4-033/034/035，技术方案 E12 生成器即真相）。

- 三场景取自金标：one=gold-C-01（C 档 cat-ai 方言语音标注平台）、
  two=gold-B-01（B 档竞争密集 会议纪要摘要工具）、three=gold-C-04
  （跨大类 quantum×geology 量子传感地质勘探，M0 判例回归）。
- 全链：任务卡 → S1~S9 合卷（S2-8 自检）→ tasks.json 互证 → contracts
  副本 → 三与门（dag/registry）→ zip。产物落 assets/trial_specs/{name}/
  （pack.zip + meta.json）+ 合卷索引 index.json。
- 结构可区分性由构造携带：B 档竞争任务占比显著高于 C 档（meta 记
  competition_task_ids，测试据此断言权重可辨）。
运行：python fixtures/_generate_trial_specs.py
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from flint.compose.vibe_core import (
    assemble_s1_charter,
    assemble_s2_invariants,
    assemble_s4_decisions,
)
from flint.dag.validator import validate
from flint.domain.models import PackageStatus, TaskSpec
from flint.registry.batch import Ecosystem, validate_batch
from flint.registry.gate import registry_pack_gate
from flint.registry.lock import lock_versions, render_lock
from flint.spec.contracts_copy import build_contracts_copy
from flint.spec.export_gate import vibe_export_gate
from flint.spec.pack_assemble import assemble_pack, assemble_s3_contracts
from flint.spec.pack_zip import PackBundle, build_zip
from flint.spec.tasks_json import export_tasks_json
from flint.spec.vibe_s5 import build_s5
from flint.spec.vibe_s6 import build_s6
from flint.spec.vibe_s7 import build_s7
from flint.spec.vibe_s89 import build_s8, build_s9

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_ROOT = REPO_ROOT / "assets" / "trial_specs"

ANCHORS = frozenset({
    "contracts/models.py#TaskSpec",
    "contracts/protocols.py#SpecExporter",
    "CLAUDE.md#S6", "CLAUDE.md#S7",
})

GLOBAL_GATE = "ruff check . && mypy --strict src && pytest -q"

PINS: list[tuple[str, Ecosystem]] = [("fastapi", "pypi"), ("httpx", "pypi")]


def _offline_check(package: str, ecosystem: Ecosystem) -> PackageStatus:
    return PackageStatus(
        package=package, ecosystem=ecosystem, exists=True,
        latest_stable="1.0.0", replaced_with=None, reason=None,
    )


def card(
    task_id: str, title: str, outputs: list[str], acceptance: list[str],
    depends_on: list[str], cycles: float = 1.0,
) -> TaskSpec:
    return TaskSpec(
        task_id=task_id, title=title, inputs=["repo-skeleton"],
        outputs=outputs, acceptance=acceptance, depends_on=depends_on,
        milestone="M1", estimate_days=None, estimate_cycles=cycles,
        oneshot=True, verify_cmd=f"pytest tests/test_{task_id.lower()}.py -q",
        context_refs=["contracts/models.py#TaskSpec", "CLAUDE.md#S7"],
        review_gate=False,
    )


@dataclass(frozen=True)
class TrialScenario:
    name: str
    case_id: str
    tier: str
    category: str
    goal: str
    tasks: list[TaskSpec]
    competition_task_ids: list[str]


def scenario_one() -> TrialScenario:
    tasks = [
        card("T-01", "语料采集接入（三方言区）", ["corpus.ingest"],
             ["三方言区各 100 小时语料入库", "采样率与授权字段全记录"], []),
        card("T-02", "标注工作台原型", ["ui.workbench"],
             ["标注/质检双角色流转", "快捷键覆盖切分与转写"], ["T-01"]),
        card("T-03", "质检一致率度量", ["qa.kappa"],
             ["双人标注 kappa 报表", "kappa<0.7 批次自动回退"], ["T-02"]),
        card("T-04", "竞品对照：通用标注平台差异面", ["docs.compare"],
             ["与两家通用平台的方言支持对照表", "差异点各附出处"], ["T-01"]),
        card("T-05", "按量计费账务", ["billing.metered"],
             ["按标注秒数计费流水", "对账单与流水零差额"], ["T-02"]),
        card("T-06", "交付验收包", ["release.bundle"],
             ["验收清单全绿", "样例数据集随包"], ["T-03", "T-04", "T-05"]),
    ]
    return TrialScenario(
        name="one", case_id="gold-C-01", tier="C_opportunity",
        category="cat-ai",
        goal="方言语音标注平台：面向语音模型训练方的方言语料标注与质检服务",
        tasks=tasks, competition_task_ids=["T-04"],
    )


def scenario_two() -> TrialScenario:
    tasks = [
        card("T-01", "纪要引擎接入两会议源", ["ingest.meetings"],
             ["两会议平台音频拉取", "断点重传全覆盖"], []),
        card("T-02", "竞品矩阵：头部五家功能面", ["compare.matrix"],
             ["五家竞品功能矩阵各附出处", "更新日期全记录"], []),
        card("T-03", "竞品定价对照与缺口定位", ["compare.pricing"],
             ["五家定价表逐项对照", "缺口清单每项附证据"], ["T-02"]),
        card("T-04", "差异化主打：行业术语纠错", ["diff.terms"],
             ["三行业术语库接入", "纠错率对照基线报表"], ["T-01"]),
        card("T-05", "竞品迁移导入器", ["migrate.import"],
             ["两家竞品导出格式一键导入", "字段映射全覆盖"], ["T-02"]),
        card("T-06", "定价页与对照证据链", ["pricing.page"],
             ["定价页引用 T-03 证据链", "引用可点开回溯"], ["T-03"]),
        card("T-07", "灰度发布与留存看板", ["launch.dashboard"],
             ["灰度开关分桶", "留存漏斗四指标上板"],
             ["T-04", "T-05", "T-06"]),
    ]
    return TrialScenario(
        name="two", case_id="gold-B-01", tier="B_red_ocean",
        category="cat-ai",
        goal="会议纪要摘要工具：红海市场以行业术语纠错与迁移成本为差异面",
        tasks=tasks,
        competition_task_ids=["T-02", "T-03", "T-05", "T-06"],
    )


def scenario_three() -> TrialScenario:
    tasks = [
        card("T-01", "量子磁力仪数据协议解析", ["sensor.protocol"],
             ["两型号磁力仪原始流解析", "校准帧判别全覆盖"], []),
        card("T-02", "地质剖面反演管线", ["geo.inversion"],
             ["反演结果与钻探对照误差报表", "网格分辨率可配"], ["T-01"]),
        card("T-03", "跨域术语对齐表", ["docs.glossary"],
             ["量子/地质双域术语对齐 60 条", "每条双域出处"], []),
        card("T-04", "竞品对照：传统航磁服务", ["compare.legacy"],
             ["与两家航磁服务精度/成本对照", "对照各附出处"], ["T-02"]),
        card("T-05", "勘探报告生成器", ["report.generator"],
             ["剖面图与置信区间入报告", "报告数字全带出处"],
             ["T-02", "T-03"]),
        card("T-06", "示范区试点交付", ["pilot.delivery"],
             ["示范区试点验收清单全绿", "试点数据回流入库"],
             ["T-04", "T-05"]),
    ]
    return TrialScenario(
        name="three", case_id="gold-C-04", tier="C_opportunity",
        category="cat-quantum×cat-geology",
        goal="量子传感地质勘探：量子磁力仪跨入地质勘探大类（M0 跨大类判例回归）",
        tasks=tasks, competition_task_ids=["T-04"],
    )


def build_trial_pack(scenario: TrialScenario) -> tuple[bytes, dict[str, object]]:
    batch = validate_batch(_offline_check, PINS)
    statuses = [i.status for i in batch.items if i.status is not None]
    locks = lock_versions(statuses, requested={})
    registry = registry_pack_gate(batch, audience="ai_executor")

    dag = validate(
        scenario.tasks, audience="ai_executor",
        external_inputs={"repo-skeleton"},
        exit_ids={scenario.tasks[-1].task_id},
    )
    verdict = vibe_export_gate([], dag, registry)
    if not verdict.allowed:
        raise RuntimeError(f"{scenario.name}: gate refused {verdict.violations}")

    s5 = build_s5(scenario.tasks)
    chapters = {
        "S1": assemble_s1_charter({
            "goal": scenario.goal,
            "non_goals": ["实时热点", "英文界面"],
            "scope": "M1 全量任务卡（本包 S5）",
        }),
        "S2": assemble_s2_invariants([
            {"kind": "MUST", "rule": "结论必有引用；数字必有出处"},
            {"kind": "NEVER", "rule": "修改 contracts/ 冻结件"},
            {"kind": "MUST", "rule": "每任务先写失败测试再实现"},
        ]),
        "S3": assemble_s3_contracts(
            pins=[render_lock(locks).strip()],
            layout="src/\n  domain/\ntests/",
        ),
        "S4": assemble_s4_decisions([
            {"id": "D1", "decision": f"金标判例 {scenario.case_id}"
             f"（{scenario.tier}）", "source": "assets/goldcases"},
        ]),
        "S5": s5.markdown,
        "S6": build_s6(scenario.tasks, known_anchors=ANCHORS),
        "S7": build_s7(scenario.tasks, global_gate=GLOBAL_GATE),
        "S8": build_s8(),
        "S9": build_s9(),
    }
    pack = assemble_pack(
        chapters,
        human_digest=(
            f"监工视图：{scenario.goal}；进度看 docs/progress.jsonl 尾部。"
        ),
    )
    bundle = PackBundle(
        claude_md=pack.markdown,
        human_digest=pack.human_digest,
        tasks_json=export_tasks_json(s5),
        contracts=build_contracts_copy(REPO_ROOT / "contracts"),
    )
    meta: dict[str, object] = {
        "name": scenario.name,
        "case_id": scenario.case_id,
        "tier": scenario.tier,
        "category": scenario.category,
        "goal": scenario.goal,
        "task_count": len(scenario.tasks),
        "competition_task_ids": scenario.competition_task_ids,
        "gates": {
            "dag_errors": len(dag.errors),
            "registry_violations": len(registry.violations),
            "export_allowed": verdict.allowed,
        },
    }
    return build_zip(bundle), meta


def generate_all() -> list[Path]:
    written: list[Path] = []
    index: list[dict[str, object]] = []
    for scenario in (scenario_one(), scenario_two(), scenario_three()):
        payload, meta = build_trial_pack(scenario)
        out_dir = OUT_ROOT / scenario.name
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "pack.zip").write_bytes(payload)
        (out_dir / "meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=1),
            encoding="utf-8", newline="\n",
        )
        index.append({**meta, "path": f"{scenario.name}/pack.zip"})
        written.append(out_dir / "pack.zip")
    (OUT_ROOT / "index.json").write_text(
        json.dumps({"samples": index}, ensure_ascii=False, indent=1),
        encoding="utf-8", newline="\n",
    )
    written.append(OUT_ROOT / "index.json")
    return written


if __name__ == "__main__":
    for path in generate_all():
        print(path)
