"""vibe_pack S1/S2/S4 拼装（M3-030，技术方案 E5：规则表拼装 + 少量改写）。

- 三章由结构化输入确定性拼装（章节类调用；LLM 改写为可选后置，拼装本身
  零生成）；S1 非目标带 NEVER 规范力、S2 逐条 MUST/NEVER 标记、S4 决策
  表逐行携出处。
- 产出的包自身过 S2-8 禁用词自检（双重狗粮）：banned_word_hits 单字
  「等」以合成词豁免口径实现（幂等/等价/等级不违规）。
"""
from __future__ import annotations

from typing import Any, Final

BANNED_WORDS: Final[frozenset[str]] = frozenset(
    {"适当", "合理", "必要时", "等", "大约", "尽量", "若干"}
)

# 「等」的合成词豁免（S2-8 审核判例口径）
_DENG_COMPOUND_NEIGHBORS: Final[frozenset[str]] = frozenset(
    {"幂", "价", "级", "同", "对", "平", "候", "待", "相"}
)


def banned_word_hits(text: str) -> list[str]:
    hits: list[str] = []
    for word in sorted(BANNED_WORDS - {"等"}):
        if word in text and word not in hits:
            hits.append(word)
    for index, char in enumerate(text):
        if char != "等":
            continue
        prev_char = text[index - 1] if index > 0 else ""
        next_char = text[index + 1] if index + 1 < len(text) else ""
        if (
            prev_char not in _DENG_COMPOUND_NEIGHBORS
            and next_char not in _DENG_COMPOUND_NEIGHBORS
            and "等" not in hits
        ):
            hits.append("等")
    return sorted(hits)


def assemble_s1_charter(charter: dict[str, Any]) -> str:
    non_goals = "；".join(str(g) for g in charter["non_goals"])
    return (
        "## S1 Charter\n\n"
        f"**目标**：{charter['goal']}\n\n"
        f"**非目标（NEVER 实现）**：{non_goals}\n\n"
        f"**本包范围**：{charter['scope']}\n"
    )


def assemble_s2_invariants(invariants: list[dict[str, Any]]) -> str:
    lines = [
        f"{index}. [{item['kind']}] {item['rule']}"
        for index, item in enumerate(invariants, start=1)
    ]
    return "## S2 Invariants\n\n" + "\n".join(lines) + "\n"


def assemble_s4_decisions(decisions: list[dict[str, Any]]) -> str:
    rows = [
        f"| {item['id']} | {item['decision']} | {item['source']} |"
        for item in decisions
    ]
    return (
        "## S4 Decision Log\n\n"
        "| 编号 | 决策 | 出处 |\n|---|---|---|\n" + "\n".join(rows) + "\n"
    )
