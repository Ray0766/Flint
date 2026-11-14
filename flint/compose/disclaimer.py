"""决策边界声明 block（M3-040，v0.3.1 §3.1 / D12）。

- 系统级 declaration（locked=True, author="system"）恒钉质量卡上方；
  文案模板注入检索时点；不可编辑删除由保护执行器（M3-028）天然覆盖
  （locked 即三条件之一）。
"""
from __future__ import annotations

import hashlib
from typing import Final

from flint.domain.models import Block, DeclarationContent

DISCLAIMER_TEXT: Final[str] = (
    "本报告基于截至 {retrieved_at} 的公开信息自动生成，供研究参考；"
    "不构成科研立项、投资、法律或其他专业决策建议。结论可信度与盲区见质量卡。"
)


def build_disclaimer_block(
    deliverable_id: str, section_id: str, retrieved_at: str
) -> Block:
    digest = hashlib.sha256(f"{deliverable_id}|disclaimer".encode()).hexdigest()[:12]
    return Block(
        block_id=f"b-decl-{digest}",
        deliverable_id=deliverable_id,
        section_id=section_id,
        order=0,
        type="declaration",
        content=DeclarationContent(
            kind="declaration",
            text=DISCLAIMER_TEXT.format(retrieved_at=retrieved_at),
        ),
        claim_ids=[],
        fact_ids=[],
        author="system",
        revision=1,
        locked=True,  # D2：系统块恒锁
    )


def pin_order(blocks: list[Block]) -> list[Block]:
    """declaration 恒排质量卡正上方（同节内），其余保持相对序。"""
    declarations = [b for b in blocks if b.type == "declaration"]
    quality_cards = [b for b in blocks if b.type == "quality_card"]
    rest = [
        b for b in blocks if b.type not in ("declaration", "quality_card")
    ]
    return declarations + quality_cards + sorted(rest, key=lambda b: b.order)
