"""DESIGN-29（隔离带·G4）：固化校验器（四判据 + 行号）。

固化管道（DESIGN-28）负责**转换**，本模块负责**判定**。分开的理由：
转换器只知道自己做了什么，判定要看的是**结果长什么样**——一份从别处导入的、
或被手改过的模板，转换器根本没见过它，而它照样要过这道检查。

## 四条判据

1. **插槽完整**：声明的 slots 与 HTML 里实际出现的插槽逐项一致。
   对不上的两种后果都难查：多声明 → 渲染时要一个不存在的值；
   少声明 → `{{block:x}}` 原样渲染给客户看。
2. **无占位残留**：示例数字/示例来源（DESIGN-27 的语法表）不许留。
   留一处，它就跟着模板进生产。
3. **无水印残留**：水印属于样板；印在正式产物上比漏一个示例数字更难解释。
4. **插槽类型与 Block 类型对齐**：`{{block:b-1}}` 指向的必须是一个真实存在的 Block，
   `{{t:key}}` 指向的必须是词条 key。指错的话，渲染期才发现，而那时用户已经在等结果了。

## 每条违规都带行号

「模板不合格」这句话对改的人没有任何帮助。行号 + 原因 + 那一行的原文，
才是他能照着动手的东西。
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from flint.design.mock_syntax import CONCRETE_NUMBER_PATTERN, CONCRETE_SOURCE_PATTERN

SLOT_TOKEN = re.compile(r"\{\{([a-z]+):([a-z0-9_-]+)\}\}", re.IGNORECASE)
WATERMARK = re.compile(r"data-mock-watermark", re.IGNORECASE)


@dataclass(frozen=True)
class ValidationIssue:
    criterion: str
    line: int
    detail: str
    action: str


@dataclass(frozen=True)
class ValidationReport:
    ok: bool
    issues: list[ValidationIssue]


def _lines(html: str) -> list[str]:
    return html.replace("\r\n", "\n").split("\n")


def validate_template(
    html: str,
    *,
    declared_slots: tuple[str, ...],
    known_block_ids: frozenset[str],
    known_text_keys: frozenset[str],
) -> ValidationReport:
    """四条判据全跑完再回结果——NEVER 命中第一条就返回。"""
    issues: list[ValidationIssue] = []
    lines = _lines(html)

    found: list[tuple[str, str, int]] = []
    for index, line in enumerate(lines, start=1):
        for match in SLOT_TOKEN.finditer(line):
            found.append((match.group(1).lower(), match.group(2), index))

    # 判据 1：插槽完整（两个方向都查）
    in_html = {f"{kind}:{name}" for kind, name, _ in found}
    declared = set(declared_slots)
    for missing in sorted(declared - in_html):
        issues.append(
            ValidationIssue(
                criterion="slot_declared_not_used", line=0, detail=missing,
                action="从 slots 里去掉它，或在正文里补上这个插槽——"
                       "渲染时会要一个模板里并不存在的值",
            )
        )
    for undeclared in sorted(in_html - declared):
        line_no = next(
            i for kind, name, i in found if f"{kind}:{name}" == undeclared
        )
        issues.append(
            ValidationIssue(
                criterion="slot_used_not_declared", line=line_no, detail=undeclared,
                action="把它加进 slots——否则没人给它值，{{…}} 会原样渲染给客户看",
            )
        )

    # 判据 2：占位残留（先遮插槽再扫，插槽里的数字不是示例数字）
    for index, line in enumerate(lines, start=1):
        masked = SLOT_TOKEN.sub(lambda m: " " * len(m.group(0)), line)
        for match in CONCRETE_NUMBER_PATTERN.finditer(masked):
            issues.append(
                ValidationIssue(
                    criterion="example_number", line=index, detail=match.group(0),
                    action="换成插槽或占位形态（XX.X%）——"
                           "具体数字会跟着模板进生产，而生产渲染不再看内容",
                )
            )
        for match in CONCRETE_SOURCE_PATTERN.finditer(masked):
            issues.append(
                ValidationIssue(
                    criterion="example_source", line=index, detail=match.group(0),
                    action="换成 [来源待补] 或 SRC-XXXX",
                )
            )

    # 判据 3：水印残留
    for index, line in enumerate(lines, start=1):
        if WATERMARK.search(line):
            issues.append(
                ValidationIssue(
                    criterion="watermark_left", line=index, detail="data-mock-watermark",
                    action="删掉水印属性——水印属于样板，印在正式产物上更难解释",
                )
            )

    # 判据 4：插槽类型与 Block/词条对齐
    for kind, name, line_no in found:
        if kind == "block" and name not in known_block_ids:
            issues.append(
                ValidationIssue(
                    criterion="unknown_block", line=line_no, detail=f"block:{name}",
                    action="指向一个真实存在的 Block——否则渲染期才发现，"
                           "而那时用户已经在等结果了",
                )
            )
        elif kind == "t" and name not in known_text_keys:
            issues.append(
                ValidationIssue(
                    criterion="unknown_text_key", line=line_no, detail=f"t:{name}",
                    action="指向一个真实存在的词条 key",
                )
            )
        elif kind not in {"block", "t"}:
            issues.append(
                ValidationIssue(
                    criterion="unknown_slot_kind", line=line_no, detail=f"{kind}:{name}",
                    action="插槽类型只有 block 与 t 两种",
                )
            )

    return ValidationReport(ok=not issues, issues=issues)


def format_report(report: ValidationReport) -> str:
    """给人看的一行一条：`行号 · 判据 · 原文 → 怎么办`。"""
    if report.ok:
        return "模板校验通过：四条判据全过"
    return "\n".join(
        f"L{issue.line} · {issue.criterion} · {issue.detail} → {issue.action}"
        for issue in report.issues
    )
