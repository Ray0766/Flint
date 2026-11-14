"""audience 分叉入口（M3-032，v0.3.3 / 技术方案 E3 / 冻结件 ProposalContext）。

- audience 必选无默认（None 即拒——UI 在报告→计划书之间强制单选的服务端
  兜底）；ai_executor 强制 vibe_pack（人类模板混用被拒）；human_reader
  须五套之一（vibe_pack 被拒）。
- 双受众版本：钉同一 ledger 版本（不同即拒）+ sibling 互链存 deliverables
  .meta JSONB（E3 明文；迁移 0015——冻结 Deliverable 域对象不含该存储层
  元数据字段）。
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Final, Literal

import asyncpg

from flint.domain.models import Deliverable, DeliverableType

HUMAN_TEMPLATES: Final[frozenset[str]] = frozenset(
    {"generic", "thesis", "startup", "engineering", "grant"}
)


class AudienceForkError(Exception):
    pass


@dataclass(frozen=True)
class ProposalPlan:
    audience: Literal["human_reader", "ai_executor"]
    template_id: str
    deliverable_type: DeliverableType


def plan_proposal(
    audience: str | None, template_id: str | None
) -> ProposalPlan:
    if audience not in ("human_reader", "ai_executor"):
        raise AudienceForkError(
            "audience is mandatory with no default: human_reader | ai_executor"
        )
    if audience == "ai_executor":
        if template_id not in (None, "vibe_pack"):
            raise AudienceForkError(
                f"ai_executor is locked to vibe_pack; got {template_id!r}"
            )
        return ProposalPlan(
            audience="ai_executor", template_id="vibe_pack",
            deliverable_type="vibe_pack",
        )
    if template_id is None:
        raise AudienceForkError("human_reader requires a template choice")
    if template_id not in HUMAN_TEMPLATES:
        raise AudienceForkError(
            f"{template_id!r} is not a human template (five allowed)"
        )
    return ProposalPlan(
        audience="human_reader", template_id=template_id,
        deliverable_type="proposal",
    )


async def link_siblings(
    dsn: str, first: Deliverable, second: Deliverable
) -> None:
    if first.ledger_version != second.ledger_version:
        raise AudienceForkError(
            "sibling versions must pin the same ledger version: "
            f"{first.ledger_version} != {second.ledger_version}"
        )
    conn = await asyncpg.connect(dsn)
    try:
        async with conn.transaction():
            for a, b in ((first, second), (second, first)):
                await conn.execute(
                    "UPDATE deliverables SET meta = meta || $2::jsonb "
                    "WHERE deliverable_id = $1",
                    a.deliverable_id,
                    json.dumps(
                        {"sibling_deliverable_id": b.deliverable_id},
                        ensure_ascii=False,
                    ),
                )
    finally:
        await conn.close()
