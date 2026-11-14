"""draft_section：ledger-only 引用执行器（M3-022，B6 / 审10）。

- 生成器只拿到可用池（usable_fact_pool：disputed/retired 出池，M3-007）——
  第一道门在输入面。
- 产出校验第二道门（防生成器越权）：block.fact_ids 与表内 FactCell 逐一
  必须落在账本内且非 disputed/retired；违规抛 DraftViolation（全量清单）。
- 本层不定生成方式（LLM/规则皆可注入 generator）；三通道约束叠加归
  M3-023。
"""
from __future__ import annotations

from collections.abc import Callable

from flint.domain.models import Block, Fact, FactsLedger, SectionSpec
from flint.ledger.disputed import usable_fact_pool

BlockGenerator = Callable[[list[Fact]], list[Block]]


class DraftViolation(Exception):
    def __init__(self, violations: list[str]) -> None:
        super().__init__("; ".join(violations))
        self.violations = violations


def _cited_fact_ids(block: Block) -> list[str]:
    cited = list(block.fact_ids)
    if block.content.kind == "table":
        for row in block.content.rows:
            for cell in row:
                if cell.kind == "fact":
                    cited.append(cell.fact_id)
    return cited


def draft_section(
    spec: SectionSpec, ledger: FactsLedger, generator: BlockGenerator
) -> list[Block]:
    pool = usable_fact_pool(ledger.facts)
    pool_ids = {f.fact_id for f in pool}
    all_ids = {f.fact_id for f in ledger.facts}

    blocks = generator(pool)

    violations: list[str] = []
    for block in blocks:
        for fact_id in _cited_fact_ids(block):
            if fact_id not in all_ids:
                violations.append(
                    f"block {block.block_id}: fact {fact_id!r} is outside the "
                    "ledger (B6)"
                )
            elif fact_id not in pool_ids:
                violations.append(
                    f"block {block.block_id}: fact {fact_id!r} is disputed or "
                    "retired and excluded from generation (audit 10)"
                )
    if violations:
        raise DraftViolation(violations)
    return blocks
