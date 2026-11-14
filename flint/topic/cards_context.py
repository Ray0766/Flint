"""BL-02：`{cards}` 强接地上下文——把被引卡的真实内容与日期喂进提示词。

## 为什么单独一个模块

`generate_topic(..., cards_context: str = "")` 的参数早就在，`{cards}` 占位也在
提示词里，缺的一直是**谁来拼这个串**。此前只有 harness（`topic_caliber.py` /
`featb_payoff.py`）各拼各的，生产路径一路默认空串——**空串与没接线长得一模一样**：
模型照常生成、校验器照常判，只是它手上从来没有卡的真实内容。

拼串放这里而不是放 API 层：API 层拿到的是 DB 行，编排器拿到的是串，
中间这一步是纯函数，纯函数才能不带库地测。

## 接不到卡 NEVER 用空串继续

`build_cards_context([])` 抛 `NoUsableEvidenceCards`，由上层决定怎么答复。
静默继续等于把「没有证据」写成「有证据但模型没引」——两者的处置完全不同：
前者该拒绝生成，后者该看模型。

## 日期从 card_id 里读

`evidence_cards` 表**没有 day 列**，日期编码在 card_id 上（`card-YYYYMMDD-{cluster}`，
见 `flint/jobs/ingest.py`）。解不出就留空，**NEVER 拿今天顶上**——那会让模型
把今天写成事件发生日，而日期幻觉正是接地校验第一条要挡的东西。
"""
from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Final

# card-YYYYMMDD-{cluster_id}
_CARD_ID_DAY: Final[re.Pattern[str]] = re.compile(r"^card-(\d{8})-")


class NoUsableEvidenceCards(Exception):
    """一张能用的证据卡都没有——上层 MUST 显式处置，NEVER 拿空串继续生成。"""

    def __init__(self) -> None:
        super().__init__(
            "无可用证据卡：{cards} 强接地拿不到任何卡内容。"
            "空串会让提示词那一句「以下是被引卡的真实内容」后面跟着一片空白，"
            "强接地退化为无接地。"
        )


@dataclass(frozen=True)
class CardFacts:
    """一张被引卡喂给模型的那几样：id、关键词原文、日期。"""

    card_id: str
    texts: list[str]
    day: date | None


def card_day_from_id(card_id: str) -> date | None:
    """从 `card-YYYYMMDD-…` 里读日期。读不出返回 `None`。

    读不出**不抛**：一张 id 形状不同的卡不该让整批生成失败，
    它只是少一个日期锚点（那一行会显示空日期）。
    """
    match = _CARD_ID_DAY.match(card_id)
    if match is None:
        return None
    try:
        return date.fromisoformat(
            f"{match.group(1)[:4]}-{match.group(1)[4:6]}-{match.group(1)[6:]}"
        )
    except ValueError:
        return None


def build_cards_context(cards: Sequence[CardFacts]) -> str:
    """拼 `{cards}` 占位的内容。一张卡一行，顺序照给定的来。

    格式与 harness 既有的两处拼法同源（`harness/topic_caliber.py#_cards_context`、
    `flint/evidence/enrich.py#enriched_cards_context`）：
    `{card_id} = 「{内容}」（日期 {YYYY-MM-DD}）`。

    顺序照给定的来——顺序变了，模型引的「第一张卡」就不是同一张。
    """
    if not cards:
        raise NoUsableEvidenceCards
    lines: list[str] = []
    for card in cards:
        day = card.day.isoformat() if card.day is not None else ""
        if card.texts:
            body = "；".join(card.texts)
        else:
            # 只有 id 的空壳会让模型以为那张卡内容为空，进而放开手编——
            # 而真相是这一侧没读到。明写出来，两种情况才分得开。
            body = "（内容缺失——未读到卡内容，NEVER 据此编造）"
        lines.append(f"{card.card_id} = 「{body}」（日期 {day}）")
    return "\n".join(lines)
