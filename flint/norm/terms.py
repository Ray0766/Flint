"""中英术语映射表加载器（M1-018，A3 第二段，PDD v0.2 §3.1）。

- 资产：assets/term-map.yaml（version + terms[]，每条 zh/en/aliases）。
- 键空间 = zh + en + aliases，装载时全部过 A3 第一段 clean() 归一，
  全局唯一性校验（跨条目撞键 = 加载失败，杜绝歧义映射）。
- lookup 输入同样先 clean()；返回 en 规范形（en 查 en 恒等命中）。
- 命中率统计钩子：hits/misses 计数 + stats() 快照，供入库前观测
  映射覆盖率（验收硬条款）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from flint.norm.clean import clean


class TermMapError(Exception):
    """Raised when the term-map yaml fails schema validation."""


@dataclass
class TermMap:
    _mapping: dict[str, str]
    size: int
    hits: int = 0
    misses: int = 0
    _lookups: int = field(default=0, init=False)

    def lookup(self, raw: str) -> str | None:
        key = clean(raw)
        self._lookups += 1
        result = self._mapping.get(key)
        if result is None:
            self.misses += 1
        else:
            self.hits += 1
        return result

    def stats(self) -> dict[str, float]:
        rate = (self.hits / self._lookups) if self._lookups else 0.0
        return {
            "hits": self.hits,
            "misses": self.misses,
            "lookups": self._lookups,
            "hit_rate": rate,
        }


def _require_str(entry: dict[str, Any], key: str, index: int) -> str:
    value = entry.get(key)
    if not isinstance(value, str) or not value.strip():
        raise TermMapError(f"terms[{index}]: field {key!r} missing or empty")
    return value


def load_term_map(path: Path) -> TermMap:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("terms"), list):
        raise TermMapError("term map must be a mapping with a 'terms' list")
    mapping: dict[str, str] = {}
    count = 0
    for i, entry in enumerate(payload["terms"]):
        if not isinstance(entry, dict):
            raise TermMapError(f"terms[{i}]: entry must be a mapping")
        zh = _require_str(entry, "zh", i)
        en = _require_str(entry, "en", i)
        aliases = entry.get("aliases", [])
        if not isinstance(aliases, list) or not all(isinstance(a, str) for a in aliases):
            raise TermMapError(f"terms[{i}]: aliases must be a list of strings")
        canonical = clean(en)
        for key_raw in [zh, en, *aliases]:
            key = clean(key_raw)
            if not key:
                raise TermMapError(f"terms[{i}]: key {key_raw!r} normalizes to empty")
            existing = mapping.get(key)
            if existing is not None and existing != canonical:
                raise TermMapError(
                    f"terms[{i}]: duplicate key {key!r} maps to both "
                    f"{existing!r} and {canonical!r}"
                )
            if existing == canonical and key_raw == zh:
                raise TermMapError(f"terms[{i}]: duplicate zh entry {key!r}")
            mapping[key] = canonical
        count += 1
    return TermMap(_mapping=mapping, size=count)
