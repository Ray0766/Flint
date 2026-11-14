"""FE-CORE-001：冻结件最小修订守卫——regenerate_section 加 guidance + block_id。

owner 授权（@2026-07-30，Q-007/Q-008 resolved）的**唯一**冻结件改动：给
InterventionService.regenerate_section 增两个**可选**参数——guidance（用户指令，
只引导方向）+ block_id（块级寻址）。**最小性守卫**：只这一个方法多两参、其余冻结
签名逐字不变；contracts↔flint/domain 保真（M1-001 另守）。
"""
from __future__ import annotations

import inspect

from flint.domain.protocols import InterventionService


def test_regenerate_section_has_guidance_and_block_id() -> None:
    sig = inspect.signature(InterventionService.regenerate_section)
    params = sig.parameters
    assert "guidance" in params, "guidance param missing (owner-authorized addition)"
    assert "block_id" in params, "block_id param missing (block-level addressing)"
    # 可选（带默认）→ 向后兼容，NEVER 破既有 section-level 调用
    assert params["guidance"].default is None
    assert params["block_id"].default is None
    # 原有位置参数逐字保留（最小性）
    assert list(params)[:3] == ["self", "deliverable_id", "section_id"]


def test_other_intervention_signatures_unchanged() -> None:
    """最小性：lock / inject_evidence / dispute 冻结签名参数逐字不变（只 regenerate 多两参）。"""
    assert list(inspect.signature(InterventionService.lock).parameters) == [
        "self", "target_id", "scope",
    ]
    assert list(inspect.signature(InterventionService.inject_evidence).parameters) == [
        "self", "project_id", "ev",
    ]
    assert list(inspect.signature(InterventionService.dispute).parameters) == [
        "self", "d",
    ]
