"""证伪 claim 构造（M3-025，M2 出口报告遗留 4 收口）。

- refute 检索 doc → (证伪 claim, doc) 对：只有**证伪证据形态**的 doc 才成对
  （标记口径：标题命中证伪标记族，或 meta.refute_evidence 显式为 True——
  负面证据通道 M2-016 的产出面即带标记）；普通 refute 检索结果不构造
  claim（避免把「搜过证伪」误当「有证伪证据」）。
- claim 文案绑定关键词与 doc 标题（对齐判定的断言面自含出处指向）。
- gate1 编排（_judge_payload / _validate_verdict）消费本构造器 → rule A
  输入非空，verdict A 在编排链路可达。
"""
from __future__ import annotations

from typing import Final

from flint.domain.models import Doc

REFUTE_EVIDENCE_MARKERS: Final[tuple[str, ...]] = (
    "retraction", "retracted", "failed replication", "discontinued",
    "shutdown", "archived", "撤稿", "复现失败", "停运", "关停",
)


def is_refute_evidence(doc: Doc) -> bool:
    if doc.meta.get("refute_evidence") is True:
        return True
    title = doc.title.lower()
    return any(marker in title for marker in REFUTE_EVIDENCE_MARKERS)


def build_refute_pairs(
    keywords: list[str], refute_docs: list[Doc]
) -> list[tuple[str, Doc]]:
    subject = "、".join(keywords)
    pairs: list[tuple[str, Doc]] = []
    seen: set[str] = set()  # 多 query 命中同一 doc → 一对（首见去重）
    for doc in refute_docs:
        if doc.doc_id not in seen and is_refute_evidence(doc):
            seen.add(doc.doc_id)
            claim = f"方向「{subject}」存在公开证伪证据：{doc.title}"
            pairs.append((claim, doc))
    return pairs
