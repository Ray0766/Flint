"""样板占位语法的**唯一真相**（DESIGN-27 定表，DESIGN-28 复用）。

四条模式写在 `web/design/mock-identity/mock-syntax.json`，前端（渲染/导出闸门）
与后端（固化管道）**读同一份**。

为什么不各写一份：前端拦住的示例数字与后端拦住的必须是同一批。两份表分叉时，
一个数字能过固化却在导出时被拒（或者更糟——反过来），而两边各有一半的道理。

为什么表放在 `web/` 而不是 `flint/`：它诞生于前端闸门（DESIGN-27），
挪过来只会让 DESIGN-27 的既有断言全部改路径。位置不重要，**只有一份**才重要。
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

SYNTAX_PATH = (
    Path(__file__).resolve().parents[2]
    / "web" / "design" / "mock-identity" / "mock-syntax.json"
)


@lru_cache(maxsize=1)
def _syntax() -> dict[str, str]:
    raw = json.loads(SYNTAX_PATH.read_text(encoding="utf-8"))
    return {k: str(v) for k, v in raw.items()}


def _compile(key: str) -> re.Pattern[str]:
    return re.compile(_syntax()[key])


CONCRETE_NUMBER_PATTERN = _compile("concreteNumber")
CONCRETE_SOURCE_PATTERN = _compile("concreteSource")
PLACEHOLDER_NUMBER_PATTERN = _compile("placeholderNumber")
PLACEHOLDER_SOURCE_PATTERN = _compile("placeholderSource")
