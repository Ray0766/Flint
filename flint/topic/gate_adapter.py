"""TS-006：Topic → keywords 适配器（Gate 集成最小改法，owner #8）。

chosen Topic → 派生 keywords → 照原样喂 run_gate1（内核逐字不变、仍 keyword-unit）。
关联假设 = 人类判断，NEVER 喂 gate（gate 只认证据、不判假设对错）。
"""
from __future__ import annotations

from flint.domain.models import Topic, TopicSeed


def topic_to_keywords(topic: Topic, seed: TopicSeed | None = None) -> list[str]:
    """从 Topic.keyword_mapping 派生 gate keywords（键 + 值扁平、去重保序）。

    mapping 为空时回退 seed.keywords；两者皆空 → []。hypothesis NEVER 参与（#8）。
    """
    ordered: list[str] = []
    seen: set[str] = set()
    for key, expansions in topic.keyword_mapping.items():
        for word in [key, *expansions]:
            text = str(word).strip()
            if text and text not in seen:
                seen.add(text)
                ordered.append(text)
    if ordered:
        return ordered
    if seed is not None:
        for word in seed.keywords:
            text = word.strip()
            if text and text not in seen:
                seen.add(text)
                ordered.append(text)
    return ordered
