"""LLM 幂等判别缓存（M2-006，技术方案 E5）。

- 只缓存判别类（相关性判定/簇命名一类幂等调用），键 = 内容 hash；
  命中不再调用（hits/misses 计数可断言）。
- 生成类调用绕过缓存直算，不入计数——生成不幂等，缓存即污染。
- 返回深拷贝副本：调用方改自己的结果不脏缓存。
"""
from __future__ import annotations

import copy
import hashlib
from collections.abc import Callable

from flint.domain.models import JSON
from flint.llm.router import CallClass


class LLMJudgmentCache:
    def __init__(self) -> None:
        self._store: dict[str, JSON] = {}
        self.hits = 0
        self.misses = 0

    def cached(
        self, call_class: CallClass, key_material: str, compute: Callable[[], JSON]
    ) -> JSON:
        if call_class != "judgment":
            return compute()
        key = hashlib.sha256(key_material.encode("utf-8")).hexdigest()
        if key in self._store:
            self.hits += 1
            return copy.deepcopy(self._store[key])
        self.misses += 1
        result = compute()
        self._store[key] = copy.deepcopy(result)
        return copy.deepcopy(result)
