"""private 证据导出标注（M3-038，审5 / 冻结件 Doc docstring）。

- access=="private"：引用条目强制携带「引自用户提供材料，外部不可核验」
  标注，且链接不出导出件（url 抑制——产品内可点开原文段落，导出面断链）。
"""
from __future__ import annotations

from typing import Final

from flint.domain.models import Doc

PRIVATE_MARK: Final[str] = "（引自用户提供材料，外部不可核验）"


def citation_line(doc: Doc) -> str:
    if doc.access == "private":
        return f"- {doc.title}{PRIVATE_MARK}"
    return f"- {doc.title} <{doc.url}>"


def citation_section(docs: list[Doc]) -> str:
    return "## 引用\n\n" + "\n".join(citation_line(d) for d in docs) + "\n"
