"""FE-CORE-004：块级重生成架构（Q-007=块级）。

块级承诺（硬断言，test-first）：
① 只重生成目标块——**同节未被选中的兄弟块字节不变**（不只 locked 块，用户没点的也不动）；
② 保护块（locked∨author=='user'∨user_modified）NEVER 被改写（S2-5，复用 guard_rewrite）；
③ 产出照走 draft_section_with_channels 真门（三通道 + 账本外事实拒稿），NEVER 绕门。
离线 fixture：重生成内容取自 M4 已录制的真实 qwen3.6 产出（assets/prod_caliber/）。
（③版本 +1 换绑属持久化，PgRegenerateService 现有 version+1，FE-CORE-005 接线时施加。）
"""
from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from flint.compose.draft import DraftViolation
from flint.domain.models import (
    Block,
    Fact,
    FactsLedger,
    ParagraphContent,
    Principal,
    SectionSpec,
    TextSpan,
    UserProfile,
)
from flint.intervene.block_regen import (
    BlockProtected,
    TargetNotInSection,
    regenerate_block,
)

REPO = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 7, 26, 12, 0, 0, tzinfo=UTC)
SPEC = SectionSpec(section_id="s1", inputs=[], check_questions=[], charts=[])


def _real_qwen_prose() -> str:
    data = json.loads(
        (REPO / "assets" / "prod_caliber" / "qwen3.6_27b.json").read_text(encoding="utf-8")
    )
    comp = next(iter(data["compositions"].values()))
    return str(comp["sections"]["opportunity"])[:80]


def _profile() -> UserProfile:
    return UserProfile(
        profile_id="p-1", owner=Principal(kind="user", id="u-1"),
        identity={}, research={}, team=[], assets={}, constraints={},
        track_record=[], locale="zh-CN", sensitivity_overrides={}, updated_at=NOW,
    )


def _ledger(fact_ids: list[str]) -> FactsLedger:
    facts = [Fact(fact_id=f, statement=f"s-{f}", value=None, unit=None,
                  citation_ids=[], status="frozen", origin="injected",
                  created_in_version=1) for f in fact_ids]
    return FactsLedger(ledger_id="l1", project_id="p1", version=1, parent_version=None,
                       derivation_reason="freeze", facts=facts, created_from=[],
                       created_at=NOW, actor="u-1")


def _para(block_id: str, order: int, text: str, *, locked: bool = False,
          author: str = "system", user_modified: bool = False) -> Block:
    return Block(
        block_id=block_id, deliverable_id="d1", section_id="s1", order=order,
        type="paragraph",
        content=ParagraphContent(kind="paragraph", spans=[TextSpan(kind="text", text=text)]),
        claim_ids=[], fact_ids=[], author=author,  # type: ignore[arg-type]
        revision=1, locked=locked, user_modified=user_modified,
    )


def _section() -> list[Block]:
    return [
        _para("b1", 0, "兄弟块一（未保护、未选中）"),
        _para("b2", 1, "目标块旧内容"),
        _para("b3", 2, "锁定的保护块", locked=True),
        _para("b4", 3, "用户改过的保护块", user_modified=True),
    ]


def _regenerator(new_text: str, fact_ids: list[str]):
    def gen(target: Block, pool: list[Fact]) -> list[Block]:
        return [replace(
            target,
            content=ParagraphContent(kind="paragraph", spans=[TextSpan(kind="text", text=new_text)]),
            fact_ids=fact_ids,
        )]
    return gen


def test_only_target_regenerated_siblings_byte_unchanged() -> None:
    section = _section()
    prose = _real_qwen_prose()
    proposal = regenerate_block(
        section, "b2", _regenerator(prose, ["fact-1"]), SPEC, _ledger(["fact-1"]),
        entries_by_id={}, profile=_profile(),
    )
    by_id = {b.block_id: b for b in proposal}
    # ① 目标块变
    assert by_id["b2"].content.spans[0].text == prose
    # ① 未选中兄弟块（含未保护 b1）字节不变
    assert by_id["b1"] == section[0]
    # ② 保护块 b3/b4 字节不变
    assert by_id["b3"] == section[2]
    assert by_id["b4"] == section[3]


def test_protected_target_refused() -> None:
    """②：对保护块下重生成 → 拒（S2-5），NEVER 改写。"""
    section = _section()
    for pid in ("b3", "b4"):
        with pytest.raises(BlockProtected):
            regenerate_block(section, pid, _regenerator("x", []), SPEC,
                             _ledger([]), entries_by_id={}, profile=_profile())


def test_out_of_ledger_fact_rejected_through_real_gate() -> None:
    """③：产出经真 draft_section_with_channels 门；账本外 fact → DraftViolation。"""
    section = _section()
    with pytest.raises(DraftViolation):
        regenerate_block(section, "b2", _regenerator("宣称", ["fact-99"]), SPEC,
                         _ledger(["fact-1"]), entries_by_id={}, profile=_profile())


def test_unknown_target_raises() -> None:
    with pytest.raises(TargetNotInSection):
        regenerate_block(_section(), "nope", _regenerator("x", []), SPEC,
                         _ledger([]), entries_by_id={}, profile=_profile())
