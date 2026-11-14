"""FE-CORE-008（软硬化卡，owner 裁 B）：正文裸数字 needs_review 软扫描。

了结 v0.4-问题单登记的「正文裸数字不被 validate_channels 检出」观察。**软标非硬拒**：
命中带单位可疑数字（初始单位集 %、万、亿、$）→ 置 block.needs_review（advisory），
记录触发 token 供复核 UI；NEVER 进 hard violations、NEVER DraftViolation。结构化
fact/price 单元里的数字不由本扫描经手（走 validate_channels 硬门）。
"""
from __future__ import annotations

from flint.compose.naked_numbers import mark_naked_numbers
from flint.domain.models import (
    Block,
    FactCell,
    ParagraphContent,
    TableContent,
    TextCell,
    TextSpan,
)


def _para(text: str, block_id: str = "b1") -> Block:
    return Block(
        block_id=block_id, deliverable_id="d1", section_id="s1", order=0,
        type="paragraph",
        content=ParagraphContent(kind="paragraph", spans=[TextSpan(kind="text", text=text)]),
        claim_ids=[], fact_ids=[], author="system", revision=1, locked=False,
    )


def test_unsourced_unit_numbers_flagged() -> None:
    marked, report = mark_naked_numbers([
        _para("市场规模约 500万，渗透率 40%，客单价 $3000，年增速 12.5亿"),
    ])
    assert marked[0].needs_review is True
    assert marked[0].review_severity == "advisory"
    toks = report["b1"]
    joined = " ".join(toks)
    assert "500万" in joined
    assert "40%" in joined
    assert "$3000" in joined
    assert "12.5亿" in joined


def test_dates_ordinals_counts_not_flagged() -> None:
    """防误报：日期 / 序号 / 计数（个/节/项）无单位 → NEVER 标。"""
    marked, report = mark_naked_numbers([
        _para("2026-07-30 分 3个步骤完成，见第4节，共 5 项，版本 v2"),
    ])
    assert marked[0].needs_review is False
    assert "b1" not in report


def test_structured_fact_cells_untouched() -> None:
    """结构化 fact/price 单元里的数字不由本扫描经手（走 validate_channels 硬门）。"""
    tbl = Block(
        block_id="t1", deliverable_id="d1", section_id="s1", order=0, type="table",
        content=TableContent(kind="table", header=["项", "值"],
                             rows=[[TextCell(kind="text", text="市场"),
                                    FactCell(kind="fact", fact_id="fact-9")]]),
        claim_ids=[], fact_ids=[], author="system", revision=1, locked=False,
    )
    marked, report = mark_naked_numbers([tbl])
    assert marked[0].needs_review is False
    assert report == {}


def test_soft_mark_never_mutates_input_and_preserves_other_fields() -> None:
    original = _para("客单价 $3000")
    marked, _ = mark_naked_numbers([original])
    assert original.needs_review is False  # 输入不被就地改（functional replace）
    assert marked[0].block_id == "b1" and marked[0].author == "system"
    assert marked[0].locked is False


def test_clean_prose_not_flagged() -> None:
    marked, report = mark_naked_numbers([_para("本项目聚焦数据标注效率提升。")])
    assert marked[0].needs_review is False
    assert report == {}
