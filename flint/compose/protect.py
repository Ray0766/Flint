"""保护条件执行器（M3-028，S2-5 / v0.3.2）。

- guard_rewrite：一切改写路径（regenerate/shrink/expand，M3-026/027/042）
  的统一出口校验——current 中每个受保护块（is_protected 单点三条件）必须
  在 proposal 中**逐字节原样**存在（order 位移属结构调整豁免）；缺失或被改
  → ProtectedBlockViolation（全量清单），current 分毫不动（无半写）。
- 与 PgBlockStore.replace_block 的单块防线（M3-009）构成双层：单块路径
  store 层拒、整树路径本层拒。
"""
from __future__ import annotations

from dataclasses import replace

from flint.compose.blocks import is_protected
from flint.domain.models import Block


class ProtectedBlockViolation(Exception):
    def __init__(self, violations: list[str]) -> None:
        super().__init__("; ".join(violations))
        self.violations = violations


def guard_rewrite(current: list[Block], proposal: list[Block]) -> list[Block]:
    proposal_by_id = {b.block_id: b for b in proposal}
    violations: list[str] = []
    for block in current:
        if not is_protected(block):
            continue
        candidate = proposal_by_id.get(block.block_id)
        if candidate is None:
            violations.append(
                f"protected block {block.block_id} dropped by rewrite (S2-5)"
            )
        elif replace(candidate, order=block.order) != block:
            violations.append(
                f"protected block {block.block_id} altered by rewrite (S2-5)"
            )
    if violations:
        raise ProtectedBlockViolation(violations)
    return proposal
