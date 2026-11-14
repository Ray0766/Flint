"""M3-026 acceptance tests: shrink (compress under protection).

Acceptance (tasks.json M3-026):
  - shrink touches only unprotected blocks; protected stay verbatim
  - citation integrity survives compression (no dangling fact_id)
"""
from __future__ import annotations

from flint.compose.shrink import shrink_section
from flint.domain.models import Block, ParagraphContent, TextSpan


def para(block_id: str, text: str, order: int, *, locked: bool = False,
         author: str = "system", user_modified: bool = False,
         fact_ids: list[str] | None = None) -> Block:
    return Block(
        block_id=block_id, deliverable_id="d-1", section_id="s-1", order=order,
        type="paragraph",
        content=ParagraphContent(kind="paragraph",
                                 spans=[TextSpan(kind="text", text=text)]),
        claim_ids=[], fact_ids=fact_ids or [], author=author,  # type: ignore[arg-type]
        revision=1, locked=locked, user_modified=user_modified,
    )


def compressor(blocks: list[Block]) -> list[Block]:
    """脚本化压缩器：丢弃一半非首块（保留引用块）。"""
    kept = [b for i, b in enumerate(blocks) if i == 0 or b.fact_ids]
    return kept


def test_protected_blocks_stay_verbatim() -> None:
    blocks = [
        para("b-1", "开头", 0),
        para("b-2", "用户改过", 1, user_modified=True),
        para("b-3", "锁定", 2, locked=True),
        para("b-4", "用户写的", 3, author="user"),
        para("b-5", "冗余", 4),
    ]
    result = shrink_section(blocks, compressor)
    ids = [b.block_id for b in result]
    assert "b-2" in ids and "b-3" in ids and "b-4" in ids, "protected all kept"
    protected = {b.block_id: b for b in result}
    assert protected["b-2"] == blocks[1], "verbatim, not rewritten"
    assert "b-5" not in ids, "unprotected redundancy compressed away"


def test_citation_integrity_kept() -> None:
    blocks = [
        para("b-1", "开头", 0),
        para("b-2", "带引用", 1, fact_ids=["f-1"]),
        para("b-3", "冗余", 2),
    ]
    result = shrink_section(blocks, compressor)
    cited = [f for b in result for f in b.fact_ids]
    assert "f-1" in cited, "no dangling citation loss"


def test_order_reindexed_stable() -> None:
    blocks = [para("b-1", "a", 0), para("b-2", "b", 3, locked=True),
              para("b-3", "c", 7)]
    result = shrink_section(blocks, compressor)
    assert [b.order for b in result] == list(range(len(result)))
    assert [b.block_id for b in result] == ["b-1", "b-2"], "relative order kept"
