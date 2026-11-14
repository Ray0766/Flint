"""组稿三通道约束接线（M3-023，铁律 2 进组稿路径）。

- draft_section_with_channels = M3-022 ledger-only 门 + M3-016 三通道
  互斥门叠加：任一违规抛 DraftViolation（全量清单）——违规草稿不出厂。
- channel_manifest：block 树内三通道引用摊平（facts / price_entries /
  profile_paths，判别可溯源）——质量卡与审计面的通道清点入口。
"""
from __future__ import annotations

from flint.compose.channels import validate_channels
from flint.compose.draft import BlockGenerator, DraftViolation, draft_section
from flint.domain.models import (
    Block,
    FactsLedger,
    PriceEntry,
    SectionSpec,
    UserProfile,
)
from flint.ledger.disputed import usable_fact_pool


def draft_section_with_channels(
    spec: SectionSpec,
    ledger: FactsLedger,
    generator: BlockGenerator,
    entries_by_id: dict[str, PriceEntry],
    profile: UserProfile,
) -> list[Block]:
    blocks = draft_section(spec, ledger, generator)
    known_fact_ids = {f.fact_id for f in usable_fact_pool(ledger.facts)}
    violations = validate_channels(blocks, known_fact_ids, entries_by_id, profile)
    if violations:
        raise DraftViolation(violations)
    return blocks


def channel_manifest(blocks: list[Block]) -> dict[str, list[str]]:
    facts: list[str] = []
    price_entries: list[str] = []
    profile_paths: list[str] = []
    for block in blocks:
        for fact_id in block.fact_ids:
            if fact_id not in facts:
                facts.append(fact_id)
        content = block.content
        if content.kind == "table":
            for row in content.rows:
                for cell in row:
                    if cell.kind == "fact" and cell.fact_id not in facts:
                        facts.append(cell.fact_id)
                    elif (
                        cell.kind == "price"
                        and cell.price_entry_id not in price_entries
                    ):
                        price_entries.append(cell.price_entry_id)
        elif content.kind == "paragraph":
            for span in content.spans:
                if span.kind == "profile" and span.field_path not in profile_paths:
                    profile_paths.append(span.field_path)
    return {
        "facts": facts,
        "price_entries": price_entries,
        "profile_paths": profile_paths,
    }
