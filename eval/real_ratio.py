"""生产口径验证②：真实配比偏差（M4-041，M3 出口携带条件）。

- 与 M3 自证口径的本质区别：字量来自**真实渲染内容实测**（M3 的
  ratio_deviation_report 用 filled=round(share×scale) 构造恒等式）。
- 同一度量器：偏差公式与门槛（RATIO_DEVIATION_LINE=0.15）直接引用
  eval.doc_metrics；声明配比同一来源（load_template spec.sections）。
- 字量口径：CJK 逐字 + 拉丁按词（whitespace 切分），与渲染器无关的
  纯文本计量；N≥12 硬门同①。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from eval.doc_metrics import RATIO_DEVIATION_LINE, TEMPLATES
from eval.semantic_answers import (
    MIN_COMPOSITIONS,
    Composition,
    InsufficientCompositions,
)
from flint.compose.templates import load_template

# owner 裁决 @2026-07-30-c：绝对 ≤0.15 配比硬门**作废**（依外部权威：精确控
# 长度超当前 SOTA——LIFEBench 报告 GPT-4 亦难精确控长、精确命中 ≤5%~43%；
# LongWriter 长度变异 31.6%）。②改为「经修复环尽力控长度、**不作 M4 硬阻塞**」
# （best-effort）。
# 诚实红线：① RATIO_DEVIATION_LINE=0.15 **保留作参考线**，NEVER 倒推到自家数
#   ——本方 worst-deviation（qwen 关环 0.589 / gemma 关环 0.243 / Claude 开环
#   0.206）全 >0.15，系「依证据作废不现实的线」，非「调到刚好过」；
# ② 本方 worst-deviation 与 LIFEBench/LongWriter 指标**非同一物**，外部证据
#   是**方向性佐证**，NEVER 假精确对比；
# ③ ratio 度量的 tokens↔汉字单位 bug 登记为**独立卫生项**（docs/v0.4-问题单，
#   备忘），本次不修但不得掩盖——日后若把②升回硬门 MUST 先修。
# meets_line / usable_for_gate 仍作**报告参考字段**保留（语义不变），只是不再
# 作 M4 关门硬阻塞。
RATIO_HARD_GATE_VOIDED = True

_CJK = re.compile(r"[一-鿿]")
_LATIN_WORD = re.compile(r"[A-Za-z0-9]+")


def word_count(text: str) -> int:
    return len(_CJK.findall(text)) + len(_LATIN_WORD.findall(text))


@dataclass(frozen=True)
class RatioRecord:
    composition_id: str
    section_id: str
    declared_share: float
    actual_share: float
    relative_deviation: float


@dataclass(frozen=True)
class RealRatioReport:
    n_compositions: int
    worst_deviation: float
    meets_line: bool
    records: list[RatioRecord]
    # 整改令第 4 步新增两面（旧字段语义不变）：
    # words 单位节对照模板自身 min/max_words 的越界清单
    bound_violations: list[str] = field(default_factory=list)
    # unit=tokens 节与汉字计量不可比——冲突清单（问题单登记项）
    unit_conflicts: list[str] = field(default_factory=list)
    # owner 裁决 1-3：关配比门只认此位——三与（线内 ∧ 零越界 ∧ 零单位
    # 冲突）；meets_line 语义不变
    usable_for_gate: bool = False


def real_ratio_report(
    compositions: list[Composition],
    templates_dir: Path = TEMPLATES,
) -> RealRatioReport:
    if len(compositions) < MIN_COMPOSITIONS:
        raise InsufficientCompositions(
            f"need >= {MIN_COMPOSITIONS} real compositions, got "
            f"{len(compositions)} — blocked, not degraded"
        )
    records: list[RatioRecord] = []
    bound_violations: list[str] = []
    unit_conflicts: list[str] = []
    for composition in compositions:
        spec, _sections = load_template(
            templates_dir / f"{composition.template_id}.yaml"
        )
        declared = {sid: ratio.share for sid, ratio in spec.sections}
        counts = {
            sid: word_count(composition.sections.get(sid, ""))
            for sid in declared
        }
        for sid, ratio in spec.sections:
            count = counts[sid]
            if ratio.unit != "words":
                unit_conflicts.append(
                    f"{composition.composition_id}/{sid}: unit={ratio.unit} "
                    "与汉字计量不可比（v0.4-问题单登记，不作越界判定）"
                )
                continue
            if count < ratio.min_words:
                bound_violations.append(
                    f"{composition.composition_id}/{sid}: {count} < "
                    f"min_words {ratio.min_words}"
                )
            elif count > ratio.max_words:
                bound_violations.append(
                    f"{composition.composition_id}/{sid}: {count} > "
                    f"max_words {ratio.max_words}"
                )
        total = sum(counts.values())
        if total == 0:
            raise InsufficientCompositions(
                f"{composition.composition_id}: empty rendering cannot enter "
                "the production-caliber sample"
            )
        # owner 裁决 1-4：tokens 单位节完全退出配比判定面——不进
        # records、不参与 worst/meets_line（换算口径另裁后再议回归）
        words_units = {
            sid for sid, ratio in spec.sections if ratio.unit == "words"
        }
        words_total = sum(counts[sid] for sid in words_units)
        words_share_total = sum(
            share for sid, share in declared.items() if sid in words_units
        )
        for sid in words_units:
            share = declared[sid] / words_share_total
            actual = counts[sid] / words_total if words_total else 0.0
            records.append(RatioRecord(
                composition_id=composition.composition_id,
                section_id=sid,
                declared_share=share,
                actual_share=actual,
                relative_deviation=abs(actual - share) / share,
            ))
    worst = max((r.relative_deviation for r in records), default=0.0)
    meets_line = bool(records) and worst <= RATIO_DEVIATION_LINE
    return RealRatioReport(
        n_compositions=len(compositions),
        worst_deviation=worst,
        meets_line=meets_line,
        records=records,
        bound_violations=bound_violations,
        unit_conflicts=unit_conflicts,
        usable_for_gate=(
            meets_line and not bound_violations and not unit_conflicts
        ),
    )
