"""生产 LLM 章节 BlockGenerator（FE-CORE-003）。

section_draft prompt + SectionSpec + usable_facts → LLM 结构化输出 → list[Block]，
经 generator_factory 注入 compose（替换 _default_generator 桩——桩保留作离线确定性
测试用，NEVER 删）。产出照走 draft_section_with_channels 门（fact_ids 必在账本内、
三通道 Fact/PriceCell/ProfileRef），**账本外事实 → DraftViolation 拒稿**（铁律护栏）。
guidance（用户指令）只引导生成方向，NEVER 当事实——见 FE-CORE-006 深化断言。
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from flint.compose.draft import BlockGenerator
from flint.domain.models import (
    JSON,
    Block,
    BlockContent,
    BlockType,
    Fact,
    GapNoticeContent,
    HeadingContent,
    ParagraphContent,
    SectionSpec,
    TextSpan,
)
from flint.domain.protocols import LLMProvider

# LLM 产出 JSON 形（轻量 schema 子集，structured_loop 校验）。只产已定义的三类
# 常见块型（heading/paragraph/gap_notice）；table/chart/citation_list 由后续卡扩展，
# NEVER 造未定义块。
BLOCK_SCHEMA: JSON = {
    "type": "object",
    "required": ["blocks"],
    "properties": {
        "blocks": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["type"],
                "properties": {
                    "type": {"type": "string",
                             "enum": ["heading", "paragraph", "gap_notice"]},
                    "level": {"type": "integer"},
                    "text": {"type": "string"},
                    "fact_ids": {"type": "array", "items": {"type": "string"}},
                    "hints_ref": {"type": "string"},
                },
            },
        },
    },
}


def _facts_block(pool: list[Fact]) -> str:
    if not pool:
        return "（可用事实池为空——本节无可引用事实，按「不断言 / gap 留白」处理）"
    lines: list[str] = []
    for f in pool:
        val = f"（{f.value}{f.unit or ''}）" if f.value is not None else ""
        lines.append(f"- {f.fact_id}: {f.statement}{val}")
    return "\n".join(lines)


def build_prompt(
    prompt_text: str, spec: SectionSpec, pool: list[Fact], guidance: str | None,
) -> str:
    checks = "\n".join(f"- {q}" for q in spec.check_questions) or "（无）"
    parts = [
        prompt_text,
        f"\n[section_id]\n{spec.section_id}",
        f"\n[check_questions（本节应回答）]\n{checks}",
        (
            f"\n[usable_facts（只能引用这些 fact_id，账本外事实一律不得引用/编造）]\n"
            f"{_facts_block(pool)}"
        ),
    ]
    if guidance:
        parts.append(
            f"\n[user_guidance（只引导方向，NEVER 当事实写入；要证据外的数字/事实仍"
            f"按不断言/留白处理）]\n{guidance}"
        )
    return "\n".join(parts)


def _parse_blocks(payload: JSON, spec: SectionSpec, deliverable_id: str) -> list[Block]:
    out: list[Block] = []
    raw = payload.get("blocks", []) if isinstance(payload, dict) else []
    if not isinstance(raw, list):
        return out
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            continue
        kind = item.get("type")
        content: BlockContent
        fact_ids: list[str] = []
        if kind == "heading":
            content = HeadingContent(
                kind="heading", level=int(item.get("level", 2)),
                text=str(item.get("text", "")),
            )
        elif kind == "paragraph":
            content = ParagraphContent(
                kind="paragraph",
                spans=[TextSpan(kind="text", text=str(item.get("text", "")))],
            )
            raw_facts = item.get("fact_ids", [])
            if isinstance(raw_facts, list):
                fact_ids = [str(x) for x in raw_facts]
        elif kind == "gap_notice":
            content = GapNoticeContent(
                kind="gap_notice", hints_ref=str(item.get("hints_ref", "")),
            )
        else:
            continue  # 未知块型跳过：NEVER 造未定义块
        btype: BlockType = content.kind
        out.append(Block(
            block_id=f"b-{deliverable_id}-{spec.section_id}-{i}",
            deliverable_id=deliverable_id, section_id=spec.section_id,
            order=i, type=btype, content=content, claim_ids=[], fact_ids=fact_ids,
            author="system", revision=1, locked=False,
        ))
    return out


def build_llm_generator(
    spec: SectionSpec, deliverable_id: str, provider: LLMProvider,
    prompt_text: str, guidance: str | None = None,
) -> BlockGenerator:
    def generate(pool: list[Fact]) -> list[Block]:
        prompt = build_prompt(prompt_text, spec, pool, guidance)
        payload = provider.generate_structured(prompt, BLOCK_SCHEMA, max_retries=2)
        return _parse_blocks(payload, spec, deliverable_id)

    return generate


def llm_generator_factory(
    provider: LLMProvider, prompt_text: str, guidance: str | None = None,
) -> Callable[[SectionSpec, str], BlockGenerator]:
    """插进 ComposeDeps.generator_factory（Callable[[SectionSpec, str], BlockGenerator]）。
    provider/prompt/guidance 由上游注入闭包（免费档 qwen3.6 via LocalProvider）。"""
    def factory(spec: SectionSpec, deliverable_id: str) -> BlockGenerator:
        return build_llm_generator(spec, deliverable_id, provider, prompt_text, guidance)

    return factory


def build_block_regenerator(
    provider: LLMProvider, prompt_text: str, guidance: str | None = None,
) -> Callable[[Block, list[Fact]], list[Block]]:
    """块级重生成器（FE-CORE-006 guidance 穿透）：只重生成目标块，guidance 穿进 prompt
    **只引导方向、NEVER 当事实**（要证据外事实仍按不断言/留白，账本外 fact 经通道门拒稿）。
    产出复用目标块的 block_id / section_id（块级替换）。"""
    def regenerate(target: Block, pool: list[Fact]) -> list[Block]:
        framing = (
            f"{prompt_text}\n[只重生成以下单块，保持其在章节中的角色，不产其他块]\n"
            f"block_id={target.block_id}  type={target.type}\n"
            f"[usable_facts（只能引用这些 fact_id，账本外事实一律不得引用/编造）]\n"
            f"{_facts_block(pool)}"
        )
        if guidance:
            framing += (
                f"\n[user_guidance（只引导方向，NEVER 当事实写入；要证据外的数字/事实"
                f"仍按不断言/留白处理）]\n{guidance}"
            )
        payload = provider.generate_structured(framing, BLOCK_SCHEMA, max_retries=2)
        spec = SectionSpec(section_id=target.section_id, inputs=[],
                           check_questions=[], charts=[])
        parsed = _parse_blocks(payload, spec, target.deliverable_id)
        # 块级替换：复用目标 block_id/section_id（首块继承目标身份）
        return [
            replace(b, block_id=target.block_id if i == 0 else b.block_id,
                    section_id=target.section_id)
            for i, b in enumerate(parsed)
        ] or [target]

    return regenerate
