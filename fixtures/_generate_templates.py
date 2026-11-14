"""M3-017/018 模板规则表生成器（E12 种子：五套人类模板 + vibe_pack 章节族）。

- 人类模板五套（generic/thesis/startup/engineering/grant）：sections =
  (section_id, Ratio) 序 + check_questions + charts 位；Ratio.unit=words，
  share 合计 = 1.0（装载器校验）。
- vibe_pack（M3-018）：S1~S9 固定章节族 + human_digest 附件位（不进 AI
  上下文）；Ratio.unit=tokens（v0.3.3 双单位互斥）。
运行：python -m fixtures._generate_templates（写 assets/templates/*.yaml）。
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "assets" / "templates"

HUMAN = {
    "generic": [
        ("summary", 0.10, ["结论与档位是否一句话可读？"]),
        ("opportunity", 0.20, ["机会陈述是否全部挂证据？"]),
        ("market", 0.20, ["市场数字是否全部走 Fact/PriceCell 通道？"]),
        ("competition", 0.15, ["竞品强度是否与 signal 对齐？"]),
        ("plan", 0.20, ["里程碑是否可验证？"]),
        ("budget", 0.10, ["预算格是否全部 PriceCell？"]),
        ("risks", 0.05, ["风险是否含证伪面？"]),
    ],
    "thesis": [
        ("abstract", 0.08, ["贡献点是否可证伪？"]),
        ("related_work", 0.22, ["引用是否覆盖近三年？"]),
        ("method", 0.25, ["方法与基线差异是否明确？"]),
        ("evaluation_plan", 0.20, ["指标与数据集是否可获得？"]),
        ("timeline", 0.15, ["节点是否与学制对齐？"]),
        ("resources", 0.10, ["设备是否在 Profile 资产内？"]),
    ],
    "startup": [
        ("one_liner", 0.05, ["一句话是否含用户与形态？"]),
        ("problem", 0.15, ["痛点是否有一手证据？"]),
        ("solution", 0.20, ["方案是否与竞品差异化？"]),
        ("market_size", 0.15, ["规模数字是否全挂出处？"]),
        ("go_to_market", 0.15, ["首批用户路径是否具体？"]),
        ("business_model", 0.10, ["定价是否引 PriceBook？"]),
        ("team", 0.10, ["团队是否走 ProfileRef？"]),
        ("financials", 0.10, ["预算是否全 PriceCell？"]),
    ],
    "engineering": [
        ("goal", 0.10, ["目标是否可验收？"]),
        ("architecture", 0.25, ["选型是否过 registry 校验？"]),
        ("milestones", 0.25, ["里程碑是否有 verify 手段？"]),
        ("resources", 0.15, ["算力估算是否引 PriceBook？"]),
        ("risks", 0.15, ["技术风险是否含证伪证据？"]),
        ("budget", 0.10, ["预算格是否全部 PriceCell？"]),
    ],
    "grant": [
        ("significance", 0.15, ["意义陈述是否挂权威证据？"]),
        ("innovation", 0.15, ["创新点是否与文献对照？"]),
        ("approach", 0.25, ["技术路线是否含备选？"]),
        ("feasibility", 0.15, ["可行性是否引 track_record？"]),
        ("team_resources", 0.10, ["团队与设备是否走 ProfileRef？"]),
        ("budget_justification", 0.15, ["预算依据是否全 PriceCell？"]),
        ("timeline", 0.05, ["进度是否与资助期对齐？"]),
    ],
}

VIBE_SECTIONS = [
    ("S1_charter", 0.06), ("S2_invariants", 0.10), ("S3_contracts", 0.16),
    ("S4_decision_log", 0.10), ("S5_task_dag", 0.28), ("S6_context_manifest", 0.06),
    ("S7_verification", 0.10), ("S8_progress_ledger", 0.06), ("S9_escalation", 0.08),
]


def _ratio(share: float, unit: str) -> dict:
    scale = 6000 if unit == "words" else 40000
    return {
        "share": share, "unit": unit,
        "min_words": int(share * scale * 0.5),
        "max_words": int(share * scale * 1.5),
    }


def build_human(template_id: str) -> dict:
    sections = HUMAN[template_id]
    return {
        "template_id": template_id,
        "locale": "zh-CN",
        "audience": "human_reader",
        "sections": [
            {
                "section_id": sid,
                "ratio": _ratio(share, "words"),
                "check_questions": list(questions),
                "charts": [],
            }
            for sid, share, questions in sections
        ],
    }


def build_vibe_pack() -> dict:
    return {
        "template_id": "vibe_pack",
        "locale": "zh-CN",
        "audience": "ai_executor",
        "sections": [
            {
                "section_id": sid,
                "ratio": _ratio(share, "tokens"),
                "check_questions": ["本章 MUST/NEVER 是否可判定？"],
                "charts": [],
            }
            for sid, share in VIBE_SECTIONS
        ],
        "attachments": [
            {"attachment_id": "human_digest", "in_ai_context": False},
        ],
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for template_id in HUMAN:
        (OUT_DIR / f"{template_id}.yaml").write_text(
            yaml.safe_dump(build_human(template_id), allow_unicode=True,
                           sort_keys=False),
            encoding="utf-8",
        )
    (OUT_DIR / "vibe_pack.yaml").write_text(
        yaml.safe_dump(build_vibe_pack(), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    print(f"wrote {OUT_DIR}")


if __name__ == "__main__":
    main()
