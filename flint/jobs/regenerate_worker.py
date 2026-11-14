"""regenerate Job → worker 执行（FE-CORE-005）。

补 owner 查明缺口「regenerate Job 无人执行」：本模块建**派发 + 组树逻辑**（纯函数、
离线可验），供 worker 消费 `action=regenerate_section/block` 载荷：
- parse 载荷 → RegenerateRequest（含 block_id / guidance）；
- 按 block_id 路由：非 None → 块级（FE-CORE-004 regenerate_block）；None → 章节级；
- 产出照走 draft_section_with_channels 真门（NEVER 绕）；
- rebind/reindex：换绑 new_deliverable_id + 逐节 order 重排（版本 +1 的树面；落库由
  PgRegenerateService 同事务施加，与 M3-042 一致）。
生成器由上游注入（生产 = FE-CORE-003 llm_generator_factory(provider,prompt,guidance)；
测试 = 合成/mock）。**真机 qwen3.6 端到端录制/验证 = 单一授权点，STOP 报 owner 后再跑。**
"""
from __future__ import annotations

from dataclasses import dataclass, replace

from flint.compose.blocks import is_protected
from flint.compose.draft import BlockGenerator
from flint.compose.draft_channels import draft_section_with_channels
from flint.compose.protect import guard_rewrite
from flint.domain.models import (
    Block,
    FactsLedger,
    PriceEntry,
    SectionSpec,
    UserProfile,
)
from flint.intervene.block_regen import BlockRegenerator, regenerate_block


@dataclass(frozen=True)
class RegenerateRequest:
    action: str
    deliverable_id: str
    section_id: str
    project_id: str
    block_id: str | None = None
    guidance: str | None = None


def parse_regenerate_payload(payload: dict[str, object]) -> RegenerateRequest:
    def _opt(key: str) -> str | None:
        v = payload.get(key)
        return str(v) if isinstance(v, str) and v else None

    return RegenerateRequest(
        action=str(payload["action"]),
        deliverable_id=str(payload["deliverable_id"]),
        section_id=str(payload["section_id"]),
        project_id=str(payload["project_id"]),
        block_id=_opt("block_id"),
        guidance=_opt("guidance"),
    )


def rebind_and_reindex(blocks: list[Block], new_deliverable_id: str) -> list[Block]:
    """换绑 new_deliverable_id + 逐节 order 从 0 稳定重排（与 M3-042 版本复制同形）。"""
    rebound = [replace(b, deliverable_id=new_deliverable_id) for b in blocks]
    order_by_section: dict[str, int] = {}
    reindexed: list[Block] = []
    for block in sorted(rebound, key=lambda b: (b.section_id, b.order)):
        index = order_by_section.get(block.section_id, 0)
        reindexed.append(replace(block, order=index))
        order_by_section[block.section_id] = index + 1
    return reindexed


def regenerate_section_blocks(
    section_blocks: list[Block],
    generator: BlockGenerator,
    spec: SectionSpec,
    ledger: FactsLedger,
    entries_by_id: dict[str, PriceEntry],
    profile: UserProfile,
) -> list[Block]:
    """章节级：整节未保护块重生成（经真门），保护块原样携带（S2-5 guard_rewrite）。"""
    protected = [b for b in section_blocks if is_protected(b)]
    generated = draft_section_with_channels(spec, ledger, generator, entries_by_id, profile)
    generated_ids = {b.block_id for b in generated}
    proposal = generated + [b for b in protected if b.block_id not in generated_ids]
    guard_rewrite(section_blocks, proposal)
    return proposal


def dispatch_regenerate(
    req: RegenerateRequest,
    current_tree: list[Block],
    spec: SectionSpec,
    ledger: FactsLedger,
    entries_by_id: dict[str, PriceEntry],
    profile: UserProfile,
    new_deliverable_id: str,
    section_generator: BlockGenerator,
    block_regenerator: BlockRegenerator,
) -> list[Block]:
    """路由块级/章节级 → 产新全树（换绑 + 重排）。块级只动目标块（保护未选中兄弟块）；
    章节级整节重生成。两路产出均过 draft_section_with_channels 真门。"""
    section_blocks = [b for b in current_tree if b.section_id == req.section_id]
    other = [b for b in current_tree if b.section_id != req.section_id]
    if req.block_id is not None:
        new_section = regenerate_block(
            section_blocks, req.block_id, block_regenerator, spec, ledger,
            entries_by_id, profile,
        )
    else:
        new_section = regenerate_section_blocks(
            section_blocks, section_generator, spec, ledger, entries_by_id, profile,
        )
    return rebind_and_reindex([*other, *new_section], new_deliverable_id)
