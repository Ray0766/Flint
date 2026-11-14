"""三通道互不混用执行器（M3-016，铁律 2 / S2-2）。

数字与涉我内容的三条类型化出处通道——Fact（跨文档冻结引用）/
PriceCell（预算数字）/ ProfileRef（涉我字段）——互斥且各自闭合：
1. FactCell.fact_id 落在价格 entry 命名空间 → 价格数字走了 Fact 通道，拒；
2. PriceCell.price_entry_id 落在 fact 命名空间 → fact 走了价格通道，拒；
3. FactCell 引用未知 fact → Fact 通道完整性破，拒；
4. 裸 profile 值 TextSpan → 必须走 ProfileRef（M3-015 执行器复用）；
5. 预算表裸数字 → 必须走 PriceCell（M3-013 执行器复用）。
本层聚合三门 + 跨通道组合，一次校验给全量违规清单（组稿 M3-023 消费）。
"""
from __future__ import annotations

from flint.domain.models import Block, PriceEntry, UserProfile
from flint.pricebook.cell import validate_budget_table
from flint.profile.ref import find_naked_profile_values


def validate_channels(
    blocks: list[Block],
    known_fact_ids: set[str],
    entries_by_id: dict[str, PriceEntry],
    profile: UserProfile,
) -> list[str]:
    violations: list[str] = []
    for block in blocks:
        prefix = f"block {block.block_id}"
        content = block.content
        if content.kind == "table":
            for v in validate_budget_table(content, entries_by_id):
                violations.append(f"{prefix}: {v}")
            for row in content.rows:
                for cell in row:
                    if cell.kind == "fact":
                        if cell.fact_id in entries_by_id:
                            violations.append(
                                f"{prefix}: price entry {cell.fact_id!r} smuggled "
                                "through the Fact channel"
                            )
                        elif cell.fact_id not in known_fact_ids:
                            violations.append(
                                f"{prefix}: unknown fact {cell.fact_id!r} "
                                "(Fact channel integrity)"
                            )
                    elif (
                        cell.kind == "price"
                        and cell.price_entry_id in known_fact_ids
                    ):
                        violations.append(
                            f"{prefix}: fact {cell.price_entry_id!r} smuggled "
                            "through the price channel"
                        )
        elif content.kind == "paragraph":
            for v in find_naked_profile_values(content.spans, profile):
                violations.append(f"{prefix}: {v}")
    return violations
