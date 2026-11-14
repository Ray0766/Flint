"""PriceCell 通道执行器（M3-013，铁律 2 之 PriceCell 面 / v0.2 §6.5）。

- make_price_cell 是预算数字进表的唯一受认可构造点：条目 source 为空 →
  PriceChannelViolation（「无出处的条目不可被预算表引用」）。
- validate_budget_table 是第二道门（防绕过构造点直写）：
  1) TextCell 文本为裸数字形态（剥 ¥/￥/逗号/空白后可解析为 float）→ 违规；
  2) PriceCell 引用未知 entry_id → 违规；
  3) PriceCell 引用 source 为空的条目 → 违规。
  FactCell 属 Fact 通道，不在本门管辖（跨通道互斥归 M3-016）。
"""
from __future__ import annotations

from flint.domain.models import PriceCell, PriceEntry, TableContent


class PriceChannelViolation(Exception):
    pass


def make_price_cell(entry: PriceEntry, quantity: float) -> PriceCell:
    if not entry.source:
        raise PriceChannelViolation(
            f"entry {entry.entry_id} has empty source and is never citable"
        )
    return PriceCell(kind="price", price_entry_id=entry.entry_id, quantity=quantity)


_UNIT_SUFFIXES = ("万元", "亿元", "元", "万", "亿", "%")


def _is_naked_number(text: str) -> bool:
    stripped = text.strip().lstrip("¥￥").replace(",", "").strip()
    for suffix in _UNIT_SUFFIXES:  # 中文单位/百分号尾缀同属价格通道口径
        if stripped.endswith(suffix):
            stripped = stripped[: -len(suffix)].strip()
            break
    if not stripped:
        return False
    try:
        float(stripped)
    except ValueError:
        return False
    return True


def validate_budget_table(
    table: TableContent, entries_by_id: dict[str, PriceEntry]
) -> list[str]:
    violations: list[str] = []
    for row_index, row in enumerate(table.rows):
        for col_index, cell in enumerate(row):
            where = f"row {row_index} col {col_index}"
            if cell.kind == "text" and _is_naked_number(cell.text):
                violations.append(
                    f"{where}: naked number {cell.text!r} must go through PriceCell"
                )
            elif cell.kind == "price":
                entry = entries_by_id.get(cell.price_entry_id)
                if entry is None:
                    violations.append(
                        f"{where}: unknown price entry {cell.price_entry_id!r}"
                    )
                elif not entry.source:
                    violations.append(
                        f"{where}: entry {entry.entry_id} has empty source "
                        "and is never citable"
                    )
    return violations
