"""canonical 生成与别名归并 · A3 第三段（M1-019，PDD v0.2 §3.1）。

- 流程：clean()（第一段）→ TermMap.lookup（第二段，zh/alias/en → en 规范形）
  → 未命中原样保留 cleaned 文本。
- lang 判定基于最终 canonical 形态：含 CJK → zh，否则 en——命中映射表的中文词
  归并到英文规范形后 lang=en（入库以 canonical 形态为准，Keyword.lang 语义）。
- embedding 近邻合并候选（§3.1 尾步，τ_dup）依赖 flint.embed（M1-020）与
  Keyword 仓储（M1-021），在 M1-021 的 upsert 路径接入。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from flint.norm.clean import clean
from flint.norm.terms import TermMap


@dataclass(frozen=True)
class CanonicalKeyword:
    canonical: str
    lang: Literal["zh", "en"]
    source: Literal["term_map", "cleaned"]


def _contains_cjk(text: str) -> bool:
    return any(
        0x4E00 <= ord(ch) <= 0x9FFF or 0x3400 <= ord(ch) <= 0x4DBF for ch in text
    )


def canonicalize(raw: str, terms: TermMap) -> CanonicalKeyword:
    cleaned = clean(raw)
    mapped = terms.lookup(cleaned)
    if mapped is not None:
        return CanonicalKeyword(
            canonical=mapped,
            lang="zh" if _contains_cjk(mapped) else "en",
            source="term_map",
        )
    return CanonicalKeyword(
        canonical=cleaned,
        lang="zh" if _contains_cjk(cleaned) else "en",
        source="cleaned",
    )
