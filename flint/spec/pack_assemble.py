"""vibe_pack 全包装配（M4-007，技术方案 E5 / v0.3.3 AI 执行包形态）。

- 九章合卷：S1~S9 逐章验头（`## S{i} ` 前缀）、顺序固定；缺章/错头即拒。
- Human Digest 为附件字段，NEVER 并入 markdown（不进 AI 上下文，
  CLAUDE.md 附录同构）。
- S2-8 自检：合卷 markdown 过 banned_word_hits，命中即拒并指认章号
  （生成包把关自身，双重狗粮）；digest 是监工视图非 spec，不在检查面。
- S3 章拼装器在此（vibe_core 只含 S1/S2/S4，M3-030 已冻结验收面）。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from flint.compose.vibe_core import banned_word_hits

CHAPTER_IDS: Final[tuple[str, ...]] = (
    "S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8", "S9",
)


class PackAssemblyError(Exception):
    pass


@dataclass(frozen=True)
class VibePack:
    markdown: str
    human_digest: str


def assemble_s3_contracts(pins: list[str], layout: str) -> str:
    pin_lines = "\n".join(f"- {pin}" for pin in pins)
    return (
        "## S3 Contracts\n\n"
        "**冻结件**：`contracts/models.py` + `contracts/protocols.py`——"
        "唯一真相，NEVER 修改；实现 MUST 与其类型逐字一致。\n\n"
        f"**技术选型（锁版）**：\n{pin_lines}\n\n"
        f"**目录结构**：\n```\n{layout}\n```\n"
    )


def assemble_pack(chapters: dict[str, str], human_digest: str) -> VibePack:
    problems: list[str] = []
    for cid in CHAPTER_IDS:
        body = chapters.get(cid)
        if body is None:
            problems.append(f"{cid}: chapter missing")
        elif not body.startswith(f"## {cid} "):
            problems.append(f"{cid}: header mismatch (must start with '## {cid} ')")
    extras = set(chapters) - set(CHAPTER_IDS)
    if extras:
        problems.append(f"unknown chapters: {sorted(extras)}")
    if problems:
        raise PackAssemblyError("; ".join(problems))

    markdown = "\n\n".join(chapters[cid].rstrip("\n") for cid in CHAPTER_IDS) + "\n"

    hits_by_chapter = {
        cid: banned_word_hits(chapters[cid]) for cid in CHAPTER_IDS
    }
    flagged = {cid: hits for cid, hits in hits_by_chapter.items() if hits}
    if flagged:
        detail = "; ".join(
            f"{cid}: {'、'.join(hits)}" for cid, hits in flagged.items()
        )
        raise PackAssemblyError(f"S2-8 banned words in pack: {detail}")
    return VibePack(markdown=markdown, human_digest=human_digest)
