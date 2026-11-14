"""块级重生成架构（FE-CORE-004，Q-007=块级）。

用已授权的 regenerate_section(..., block_id) 块级语义：block_id 非 None → 只重生成
目标块。核心不变量：
① **只重生成目标块**——同节未被选中的兄弟块（含未保护的）字节不变（用户没点的不动）；
② 保护块（locked∨author=='user'∨user_modified）NEVER 被改写（S2-5，复用 guard_rewrite）；
③ 产出照走 draft_section_with_channels 真门（三通道 + 账本外事实 DraftViolation 拒稿），
   NEVER 绕门（守 M3-042 备忘）。
纯函数（本模块）；版本 +1 换绑 + 落库属持久化层（PgRegenerateService 现有 version+1，
FE-CORE-005 接线块级路径时施加）。
"""
from __future__ import annotations

from collections.abc import Callable

from flint.compose.blocks import is_protected
from flint.compose.draft_channels import draft_section_with_channels
from flint.compose.protect import guard_rewrite
from flint.domain.models import (
    Block,
    Fact,
    FactsLedger,
    PriceEntry,
    SectionSpec,
    UserProfile,
)

# (目标块, 可用事实池) → 目标块的重生成替换（一或多块）。
BlockRegenerator = Callable[[Block, list[Fact]], list[Block]]


class BlockProtected(Exception):
    def __init__(self, block_id: str) -> None:
        super().__init__(f"block {block_id} is protected (S2-5); NEVER regenerate")
        self.block_id = block_id


class TargetNotInSection(KeyError):
    """block_id 不在本节。"""


def regenerate_block(
    section_blocks: list[Block],
    block_id: str,
    regenerator: BlockRegenerator,
    spec: SectionSpec,
    ledger: FactsLedger,
    entries_by_id: dict[str, PriceEntry],
    profile: UserProfile,
) -> list[Block]:
    """块级重生成：只重生成 block_id 目标块，其余块（保护 + 未保护兄弟）原样携带。
    返回本节新 block 树（已过通道门）；版本 +1 换绑由持久化层施加。"""
    target = next((b for b in section_blocks if b.block_id == block_id), None)
    if target is None:
        raise TargetNotInSection(block_id)
    if is_protected(target):  # ② S2-5：保护块 NEVER 被重生成改写
        raise BlockProtected(block_id)

    # 只重生成目标块——新块经**真** draft_section_with_channels 门校验（fact_ids 必在
    # 账本内、三通道、账本外事实 DraftViolation 拒稿）。NEVER 绕门。
    def _target_only_generator(pool: list[Fact]) -> list[Block]:
        return regenerator(target, pool)

    new_blocks = draft_section_with_channels(
        spec, ledger, _target_only_generator, entries_by_id, profile,
    )

    # ① 提案 = 逐块携带原样，仅目标块位替换为 new_blocks（兄弟块按对象身份携带 →
    # 字节不变）。
    proposal: list[Block] = []
    for block in section_blocks:
        if block.block_id == block_id:
            proposal.extend(new_blocks)
        else:
            proposal.append(block)

    # ② 保护块原样比对（复用 M3-042 guard_rewrite；未选中未保护兄弟由上面身份携带保证）。
    guard_rewrite(section_blocks, proposal)
    return proposal
