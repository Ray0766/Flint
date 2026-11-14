"""正文裸数字 needs_review 软扫描（FE-CORE-008，owner 裁 B）。

了结 v0.4-问题单登记的「正文裸数字不被 validate_channels 检出」观察。

- **软标非硬拒**：扫段落 TextSpan 文本里带单位的可疑数字，命中即置该 block
  `needs_review=True` + `review_severity="advisory"`（走现成 Block 字段，L0 已渲染），
  并回报触发 token 供复核 UI。**NEVER 进 validate_channels hard violations、NEVER
  触发 DraftViolation**——纯软标、不阻塞生成。
- **初始单位集 = %、万、亿、$**（后续可扩，扩时改本正则并登记）。确切正则见下 `UNIT_NUMBER_RE`。
- **启发式**：带单位数字出现在 prose text span = 本应走 Fact/PriceCell 通道、而非裸正文，
  故标出复核。**NEVER 与账本做模糊值匹配**（易碎）。
- **不经手结构化单元**：只扫 ParagraphContent 的 TextSpan(kind=="text")；表格 FactCell/
  PriceCell、其余块型不由本扫描经手（它们走 validate_channels 硬门）。
- functional：返回新 Block（dataclasses.replace），NEVER 就地改输入。
"""
from __future__ import annotations

import re
from dataclasses import replace

from flint.domain.models import Block

# 带单位可疑数字（初始单位集 %、万、亿、$）。日期/序号/计数（个/节/项/v2 无单位）
# 不匹配——数字必须紧邻上述四种单位之一才命中。
UNIT_NUMBER_RE = re.compile(
    r"\$\s?\d[\d,]*(?:\.\d+)?"          # $ 前缀金额，如 $3000 / $ 3,000.50
    r"|\d+(?:\.\d+)?\s?%"               # 百分比，如 40% / 12.5 %
    r"|\d+(?:\.\d+)?\s?(?:万|亿)"       # 万 / 亿，如 500万 / 12.5亿
)


def scan_block_naked_numbers(block: Block) -> list[str]:
    """回该 block 段落正文里命中的带单位数字 token（去重、保序）；非段落回 []。"""
    content = block.content
    if content.kind != "paragraph":
        return []
    tokens: list[str] = []
    for span in content.spans:
        if span.kind != "text":
            continue
        for match in UNIT_NUMBER_RE.findall(span.text):
            token = match if isinstance(match, str) else match[0]
            if token and token not in tokens:
                tokens.append(token)
    return tokens


def mark_naked_numbers(
    blocks: list[Block],
) -> tuple[list[Block], dict[str, list[str]]]:
    """软标：命中 → needs_review=True + severity=advisory；回 (标注后 blocks, 报告
    block_id→触发 token)。NEVER 硬拒、NEVER 改动 fact_ids/内容。review_reason 保持
    None（冻结 ReviewReason 三枚举无裸数字项，NEVER 误用；具体 token 走报告）。"""
    out: list[Block] = []
    report: dict[str, list[str]] = {}
    for block in blocks:
        tokens = scan_block_naked_numbers(block)
        if tokens:
            report[block.block_id] = tokens
            out.append(replace(block, needs_review=True, review_severity="advisory"))
        else:
            out.append(block)
    return out, report
