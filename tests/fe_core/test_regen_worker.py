"""FE-CORE-005：Job→worker 接线（派发 action=regenerate_section/block → 重生成执行）。

补 owner 查明的缺口「regenerate Job 无人执行」。本卡建**派发 + 组树逻辑**（纯函数，
离线可验）：parse 载荷 → 按 block_id 路由块级(FE-CORE-004)/章节级 → 产新树（过通道门）
→ rebind/reindex（版本 +1 换绑的树面，落库属 PgRegenerateService）。生成器用合成/mock
注入（离线）。**真机 qwen3.6 端到端录制/验证 = 单一授权点，本轮 STOP 报 owner 后再跑。**
"""
from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

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
from flint.jobs.regenerate_worker import (
    RegenerateRequest,
    dispatch_regenerate,
    parse_regenerate_payload,
    rebind_and_reindex,
    regenerate_section_blocks,
)

NOW = datetime(2026, 7, 26, 12, 0, 0, tzinfo=UTC)
SPEC = SectionSpec(section_id="s1", inputs=[], check_questions=[], charts=[])


def _profile() -> UserProfile:
    return UserProfile(profile_id="p", owner=Principal(kind="user", id="u"),
                       identity={}, research={}, team=[], assets={}, constraints={},
                       track_record=[], locale="zh-CN", sensitivity_overrides={},
                       updated_at=NOW)


def _ledger(fact_ids: list[str]) -> FactsLedger:
    facts = [Fact(fact_id=f, statement="s", value=None, unit=None, citation_ids=[],
                  status="frozen", origin="injected", created_in_version=1)
             for f in fact_ids]
    return FactsLedger(ledger_id="l", project_id="p", version=1, parent_version=None,
                       derivation_reason="freeze", facts=facts, created_from=[],
                       created_at=NOW, actor="u")


def _para(bid: str, sid: str, order: int, text: str, *, locked: bool = False,
          author: str = "system", deliverable_id: str = "d-old") -> Block:
    return Block(block_id=bid, deliverable_id=deliverable_id, section_id=sid,
                 order=order, type="paragraph",
                 content=ParagraphContent(kind="paragraph", spans=[TextSpan(kind="text", text=text)]),
                 claim_ids=[], fact_ids=[], author=author,  # type: ignore[arg-type]
                 revision=1, locked=locked)


def test_parse_regenerate_payload_section_and_block() -> None:
    sec = parse_regenerate_payload({"action": "regenerate_section",
                                    "deliverable_id": "d1", "section_id": "s1",
                                    "project_id": "p1"})
    assert sec == RegenerateRequest("regenerate_section", "d1", "s1", "p1", None, None)
    blk = parse_regenerate_payload({"action": "regenerate_block", "deliverable_id": "d1",
                                    "section_id": "s1", "project_id": "p1",
                                    "block_id": "b2", "guidance": "更简洁"})
    assert blk.block_id == "b2" and blk.guidance == "更简洁"


def test_rebind_and_reindex() -> None:
    blocks = [_para("a", "s1", 5, "x"), _para("b", "s1", 9, "y"),
              _para("c", "s2", 2, "z")]
    out = rebind_and_reindex(blocks, "d-new")
    assert all(b.deliverable_id == "d-new" for b in out)
    by = {b.block_id: b.order for b in out}
    assert by["a"] == 0 and by["b"] == 1 and by["c"] == 0  # 逐节从 0 重排


def test_section_regen_carries_protected_and_passes_gate() -> None:
    section = [_para("b1", "s1", 0, "旧摘要"),
               _para("b2", "s1", 1, "锁定块", locked=True)]

    def gen(pool: list[Fact]) -> list[Block]:  # 合成生成器：产一个新未保护块
        return [_para("b1", "s1", 0, "新摘要", deliverable_id="d-old")]

    out = regenerate_section_blocks(section, gen, SPEC, _ledger([]), {}, _profile())
    by = {b.block_id: b for b in out}
    assert by["b1"].content.spans[0].text == "新摘要"   # 未保护块被重生成
    assert by["b2"] == section[1]                         # 保护块原样携带


def test_dispatch_routes_block_vs_section() -> None:
    tree = [_para("b1", "s1", 0, "兄弟"), _para("b2", "s1", 1, "目标旧"),
            _para("x1", "s2", 0, "别节")]

    def block_regen(target: Block, pool: list[Fact]) -> list[Block]:
        return [replace(target, content=ParagraphContent(
            kind="paragraph", spans=[TextSpan(kind="text", text="目标新")]))]

    def section_gen(pool: list[Fact]) -> list[Block]:
        return [_para("b1", "s1", 0, "整节新")]

    # 块级：只目标块变，兄弟 b1 与别节 x1 内容不变
    blk_req = RegenerateRequest("regenerate_block", "d-old", "s1", "p", "b2", None)
    out = dispatch_regenerate(blk_req, tree, SPEC, _ledger([]), {}, _profile(),
                              "d-new", section_gen, block_regen)
    by = {b.block_id: b for b in out}
    assert by["b2"].content.spans[0].text == "目标新"
    assert by["b1"].content.spans[0].text == "兄弟"   # 兄弟不变
    assert by["x1"].content.spans[0].text == "别节"   # 别节不变

    # 章节级：整节重生成
    sec_req = RegenerateRequest("regenerate_section", "d-old", "s1", "p", None, None)
    out2 = dispatch_regenerate(sec_req, tree, SPEC, _ledger([]), {}, _profile(),
                               "d-new", section_gen, block_regen)
    assert {b.block_id for b in out2 if b.section_id == "s1"} == {"b1"}
    assert next(b for b in out2 if b.block_id == "b1").content.spans[0].text == "整节新"


def test_dispatch_block_gate_enforced() -> None:
    """派发块级仍过真门：账本外 fact → DraftViolation。"""
    tree = [_para("b1", "s1", 0, "目标")]

    def bad_regen(target: Block, pool: list[Fact]) -> list[Block]:
        return [replace(target, fact_ids=["fact-99"])]

    req = RegenerateRequest("regenerate_block", "d-old", "s1", "p", "b1", None)
    with pytest.raises(DraftViolation):
        dispatch_regenerate(req, tree, SPEC, _ledger(["fact-1"]), {}, _profile(),
                            "d-new", lambda p: [], bad_regen)
