"""doc_metrics 残留 0.90 门的**范围界定守卫**（owner 卫生清理 @2026-07-30）。

背景：eval/doc_metrics.py 的 CHECK_ANSWER_LINE=0.90 是**旧模板 check_questions
结构考核面**的门（check_answer_report：规则派生、合成 golddocs 上自证，M3 结构
里程碑度量；M3 出口报告已诚实标 ⚠️ 结构达标·非生产口径）。它**不是**现行
held-out 语义**生产口径**的门——生产答作率的绝对 0.90 线已依 owner 裁决
@2026-07-30 **作废**，改 eval/semantic_answers.py 的相对参照门（relative_answer
_gate，REFERENCE_RATE_UNIFIED_JUDGE × GATE_RATIO），二者**分治**。

本守卫为**范围界定**，非行为变更：① 0.90 常量与门表达式**逐字不变**（不改现行
行为——M3-066 仍用 check_answer_report 断言 rate>=0.9）；② 生产语义门与本结构门
**解耦**（relative_answer_gate 源码不引 CHECK_ANSWER_LINE）；③ doc_metrics 源码
带上范围界定注释（旧模板结构面 / 非生产口径 / 分治 / 生产绝对线已作废）。
"""
from __future__ import annotations

import inspect
from pathlib import Path

import pytest

import eval.doc_metrics as dm
import eval.semantic_answers as sa

pytestmark = pytest.mark.compose

DOC_METRICS_SRC = Path(dm.__file__).read_text(encoding="utf-8")


def test_check_answer_line_unchanged_not_reverse_engineered() -> None:
    """0.90 常量逐字不变——范围界定 NEVER 顺手改门值。"""
    assert dm.CHECK_ANSWER_LINE == 0.90


def test_gate_expression_behavior_preserved() -> None:
    """main() 的门表达式仍 `>= CHECK_ANSWER_LINE`——注释不动执法逻辑。
    M3-066 依赖 check_answer_report(...)['rate']>=0.9 仍成立。"""
    main_src = inspect.getsource(dm.main)
    assert ">= CHECK_ANSWER_LINE" in main_src
    # check_answer_report 仍在、签名不变（旧结构面度量器未被删）
    assert callable(dm.check_answer_report)


def test_production_semantic_gate_decoupled_from_structural_line() -> None:
    """生产语义门（relative_answer_gate）与本结构 0.90 门解耦：
    源码不引 CHECK_ANSWER_LINE，参照来自 REFERENCE_RATE_UNIFIED_JUDGE。"""
    gate_src = inspect.getsource(sa.relative_answer_gate)
    assert "CHECK_ANSWER_LINE" not in gate_src, "production gate must not reuse 0.90"
    assert sa.REFERENCE_RATE_UNIFIED_JUDGE == 0.434
    assert sa.GATE_RATIO == 0.85
    # 生产门要求值来自相对参照，非 0.90
    required = sa.REFERENCE_RATE_UNIFIED_JUDGE * sa.GATE_RATIO
    assert required != dm.CHECK_ANSWER_LINE


def test_scope_annotation_present_in_source() -> None:
    """doc_metrics 源码带范围界定注释：只管旧模板结构面、非生产口径、
    与生产语义门分治、生产绝对 0.90 已依 owner 裁决 @2026-07-30 作废。"""
    for token in ("旧模板", "结构", "非生产口径", "分治", "作废",
                  "2026-07-30", "relative_answer_gate"):
        assert token in DOC_METRICS_SRC, f"scope annotation missing: {token}"
