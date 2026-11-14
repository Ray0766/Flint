"""FE-CORE-002：生产章节起草 prompt 实体（版本化 + prompts.lock 登记）。

prompt 走既有版本库规格（flint/llm/prompts.py，M2-004）：文件即版本 + 内容 hash +
prompts.lock.json 登记；就地改动/未登记经 verify_lock 检出。本测 test-first 守：
- section_draft@1 可按锁加载（enforce_lock=True 不抛 PromptDrift）；
- 铁律约束在 prompt 在场（账本外事实不引用/不编造、三通道、gap 留白、guidance 只引导）；
- prompts.lock.json 全净（无 drift）。
"""
from __future__ import annotations

from pathlib import Path

from flint.llm.prompts import load_prompt, verify_lock

PROMPTS = Path(__file__).resolve().parents[2] / "prompts"


def test_section_draft_prompt_loads_under_lock() -> None:
    pv = load_prompt(PROMPTS, "section_draft@1", enforce_lock=True)
    assert pv.name == "section_draft@1"
    assert pv.version.startswith("section_draft@1#")


def test_section_draft_prompt_carries_iron_law_constraints() -> None:
    text = load_prompt(PROMPTS, "section_draft@1").text
    for token in ("账本外", "NEVER", "编造", "三通道", "gap_notice", "user_guidance"):
        assert token in text, f"iron-law constraint token missing: {token}"


def test_prompts_lock_clean() -> None:
    assert verify_lock(PROMPTS) == [], "prompts.lock.json drift (section_draft@1 unlocked?)"
