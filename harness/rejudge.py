"""统一判官横比（owner 任务）：固定 claude-sonnet-5 一个判官（output_config
.format 结构化判分），重判三家已存产出（gemma4:31b / qwen3.6:27b /
claude-sonnet-5 repair-on）的逐节文字，得可比作答率排名。

- **只重判、不重写组稿**：从各家自评 trail 装载 compositions（逐节文字），
  过同一 held-out 题库 v1.0（question_id 落 trail、与模板题零交集，装载器
  硬断言），judge=claude-sonnet-5；report_only（0.90 线 NEVER 应用）。
- 落数单列 assets/prod_caliber/unified_judge/{model}.json（新目录，与自评
  trail 不撞名、不覆盖，H-3）。
- 读数保留项：Claude 判 Claude 自身产出或略自家偏松（写入每家 trail）。
运行：python -m harness.rejudge （FLINT_ANTHROPIC_* 环境配置）
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict
from pathlib import Path

from eval.heldout import load_heldout_bank
from eval.semantic_answers import (
    Composition,
    llm_answer_fn,
    semantic_answer_report,
)
from flint.llm.production import (
    AnthropicTier,
    ModelPricing,
    PaidTierProvider,
    load_anthropic_tier,
)
from flint.testing.archive import archive_write

REPO_ROOT = Path(__file__).resolve().parents[1]
IN_DIR = REPO_ROOT / "assets" / "prod_caliber"
OUT_DIR = IN_DIR / "unified_judge"

# 被判三家现成产出（自评口径 trail）→ 统一 Claude 判官重判其逐节文字
SOURCE_TRAILS: dict[str, str] = {
    "gemma4:31b": "gemma4_31b.json",
    "qwen3.6:27b": "qwen3.6_27b.json",
    "claude-sonnet-5": "claude-sonnet-5.json",  # repair-on 那版
}

JUDGE_MAX_TOKENS = 2000  # 判分 JSON 极短；thinking 关 → 2000 富余


def _safe(model: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", model)


def load_compositions_from_trail(path: Path) -> list[Composition]:
    """从自评 trail 装载 compositions（逐节文字）——只读文字，不改组稿。"""
    data = json.loads(path.read_text(encoding="utf-8"))
    return [
        Composition(
            composition_id=cid,
            template_id=str(c["template_id"]),
            sections=dict(c["sections"]),
        )
        for cid, c in data["compositions"].items()
    ]


def build_judge(tier: AnthropicTier) -> PaidTierProvider:
    """判官恒定 claude-sonnet-5：output_config.format 结构化判分、thinking 关
    （JSON 干净、无思考成本）。每家一实例 → 计量互不竞态。"""
    pricing = ModelPricing(
        usd_per_mtok_input=tier.usd_per_mtok_input,
        usd_per_mtok_output=tier.usd_per_mtok_output,
    )
    return PaidTierProvider(
        api_key=tier.api_key, model=tier.model, pricing=pricing,
        max_tokens=JUDGE_MAX_TOKENS, disable_thinking=True,
    )


def main(argv: list[str] | None = None) -> int:
    tier = load_anthropic_tier()
    bank = load_heldout_bank()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    summary: dict[str, dict[str, object]] = {}
    for source_model, trail_file in SOURCE_TRAILS.items():
        judge = build_judge(tier)  # 每家独立判官实例（计量隔离）
        comps = load_compositions_from_trail(IN_DIR / trail_file)
        report = semantic_answer_report(
            comps, llm_answer_fn(judge), bank=bank
        )
        out = {
            "source_model": source_model,
            "source_trail": trail_file,
            "judge_model": tier.model,
            "caliber": (
                "unified-judge (claude-sonnet-5) via output_config.format, "
                "judge thinking=disabled, report_only"
            ),
            "self_judge_caveat": (
                "Claude judging Claude's own output may be slightly self-"
                "lenient (same-family leniency); read the claude-sonnet-5 row "
                "with this in mind, NEVER as unbiased."
            ),
            "bank_version": bank.bank_version,
            "questions": report.questions,
            "answered": report.answered,
            "rate": report.rate,
            "verdict": report.verdict,
            "judge_usage": {
                "calls": judge.meter.calls,
                "input_tokens": judge.meter.input_tokens,
                "output_tokens": judge.meter.output_tokens,
                "cost_usd": judge.meter.cost_usd,
            },
            "structured_output_failures": judge.structured_output_failures,
            "records": [asdict(r) for r in report.records],
        }
        out_path = OUT_DIR / f"{_safe(source_model)}.json"
        # H-3 通用归档保护：同名 trail 不覆盖已存在证据（先备份旧证据再写）。
        archive_write(
            out_path, json.dumps(out, ensure_ascii=False, indent=1)
        )
        summary[source_model] = {
            "rate": report.rate,
            "answered": report.answered,
            "questions": report.questions,
            "cost_usd": judge.meter.cost_usd,
            "structured_output_failures": judge.structured_output_failures,
        }
        print(json.dumps(
            {"source": source_model, **summary[source_model]},
            ensure_ascii=False,
        ))
    print(json.dumps({"unified_judge_summary": summary}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
