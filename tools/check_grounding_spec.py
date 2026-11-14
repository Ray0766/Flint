"""MIGRATE-01 校验器：接地增强(a) 规格 v04 的完整性与真件对账。

acceptance（tasks-v04.json#MIGRATE-01）：
  ① 规格含三条 v04 增补：校验输入=原文字段、译文禁入比对、译文引用可展开原文；
  ② 含 event 文本/日期一致性判据的伪码与错误类型 `GroundingOnTranslationError`。

## 这个校验器为什么要连 contracts/ 一起查

规格文档最容易的失守方式不是缺段落，是**引用了不存在的类型名**——读起来严丝合缝，
落地时才发现冻结件里没这个东西。所以除了查段落齐全，还查文档引用的冻结件符号
（WhyNowEvidence / Citation / CitationAligner / Alignment）在 `contracts/` 里真的存在。
`contracts/` 只读，本校验器只读不写。

`GroundingOnTranslationError` 是 v04 **新**错误类型，尚未落地实现，
故只查它在规格里被定义与被伪码引用，NEVER 去 contracts/ 找它——找不到是正常的。

用法：python tools/check_grounding_spec.py docs/grounding_spec_v04.md
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = REPO_ROOT / "contracts"

# 三条 v04 增补：锚点 → 该条 MUST 出现的关键词（防「标题写了、正文空转」）
REQUIRED_ADDITIONS = {
    "A1": ("校验输入", ("原文", "PRINCIPLES#B10")),
    "A2": ("译文禁入比对", ("NEVER", "PRINCIPLES#B10")),
    "A3": ("译文引用可展开原文", ("展开", "PRINCIPLES#B9")),
}
PSEUDOCODE_SECTION = "## B"
ERROR_SECTION = "## C"
ERROR_NAME = "GroundingOnTranslationError"
# 伪码 MUST 同时覆盖「文本」与「日期」两条判据，并在译文入参时抛错
PSEUDOCODE_TOKENS = ("event", "event_date", ERROR_NAME)
# §0 里那个自称「冻结件里的相关真件」的代码块——块内出现的每个类型名都要在 contracts/ 里真实存在。
# 扫这个块而不是扫固定名单：固定名单里全是已存在的名字，那条分支永远打不到 = 死代码，
# 而真正要防的是「规格里编了一个冻结件没有的类型」。
CONTRACT_QUOTE_SECTION = "## 0"
CAMEL_CASE = re.compile(r"\b([A-Z][A-Za-z0-9]{2,})\b")
# v04 新类型：本轮才引入，contracts/ 里理应没有，故不参与存在性断言。
V04_NEW_TYPES = frozenset({
    "GroundingOnTranslationError", "GroundingResult", "TranslatedText",
})
# 非类型的大写词（判据/字面量），同样不参与存在性断言。
NOT_A_TYPE = frozenset({"Literal", "None", "PRINCIPLES", "WORKORDER"})


def sections(text: str) -> dict[str, list[str]]:
    """按 `## ` / `### ` 标题切块，键是标题行的首个 token（## B / ### A1）。"""
    out: dict[str, list[str]] = {}
    key: str | None = None
    for line in text.replace("\r\n", "\n").split("\n"):
        match = re.match(r"^(#{2,3})\s+(\S+)", line)
        if match:
            key = f"{match.group(1)} {match.group(2)}"
            out[key] = []
        elif key is not None:
            out[key].append(line)
    return out


def fenced_blocks(lines: list[str]) -> list[str]:
    blocks: list[str] = []
    current: list[str] | None = None
    for line in lines:
        if line.startswith("```"):
            if current is None:
                current = []
            else:
                blocks.append("\n".join(current))
                current = None
        elif current is not None:
            current.append(line)
    return blocks


def quoted_contract_types(blocks: dict[str, list[str]]) -> list[str]:
    """§0 冻结件引用块里出现的类型名（去掉 v04 新类型与非类型词）。"""
    if CONTRACT_QUOTE_SECTION not in blocks:
        return []
    code = "\n".join(fenced_blocks(blocks[CONTRACT_QUOTE_SECTION]))
    names = {n for n in CAMEL_CASE.findall(code)}
    return sorted(names - V04_NEW_TYPES - NOT_A_TYPE)


def missing_from_contracts(names: list[str]) -> list[str]:
    text = "".join(
        p.read_text(encoding="utf-8") for p in sorted(CONTRACTS.glob("*.py"))
    )
    return [n for n in names if not re.search(rf"\b{n}\b", text)]


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(f"用法：python {Path(__file__).name} docs/grounding_spec_v04.md", file=sys.stderr)
        return 2
    path = Path(argv[1])
    if not path.exists():
        print(f"规格文档不存在：{path}", file=sys.stderr)
        return 1

    text = path.read_text(encoding="utf-8")
    blocks = sections(text)
    problems: list[str] = []

    # ① 三条 v04 增补
    for aid, (label, tokens) in REQUIRED_ADDITIONS.items():
        key = f"### {aid}"
        if key not in blocks:
            problems.append(f"缺增补条 {aid}（{label}）：找不到 `{key} …` 小节")
            continue
        body = "\n".join(blocks[key]).strip()
        if not body:
            problems.append(f"增补条 {aid}（{label}）小节是空的")
            continue
        for token in tokens:
            if token not in body:
                problems.append(f"增补条 {aid}（{label}）正文缺关键内容：{token}")

    # ② 伪码 + 错误类型
    if PSEUDOCODE_SECTION not in blocks:
        problems.append(f"缺伪码小节 `{PSEUDOCODE_SECTION} …`")
    else:
        code = "\n".join(fenced_blocks(blocks[PSEUDOCODE_SECTION]))
        if not code.strip():
            problems.append("伪码小节里没有代码块（``` 围栏）")
        for token in PSEUDOCODE_TOKENS:
            if token not in code:
                problems.append(f"伪码缺判据要素：{token}")

    if ERROR_SECTION not in blocks:
        problems.append(f"缺错误类型小节 `{ERROR_SECTION} …`")
    else:
        body = "\n".join(blocks[ERROR_SECTION])
        if ERROR_NAME not in body:
            problems.append(f"错误类型小节没有定义 {ERROR_NAME}")
        if "何时抛" not in body:
            problems.append("错误类型小节缺「何时抛」——只给类名不给触发条件等于没规定")

    # ③ §0 自称引自冻结件的类型名，MUST 在 contracts/ 里真实存在
    referenced = quoted_contract_types(blocks)
    if not referenced:
        problems.append(f"`{CONTRACT_QUOTE_SECTION} …` 里没有引用任何冻结件类型（规格要挂在真件上）")
    missing = missing_from_contracts(referenced)
    if missing:
        problems.append(
            f"规格自称引自冻结件、但 contracts/ 里没有这些类型：{missing}"
            "（新类型属 v04 增量，NEVER 混进「冻结件真件」块）"
        )

    if problems:
        print(f"MIGRATE-01 校验不通过（{len(problems)} 项）：", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1
    print(
        f"MIGRATE-01 校验通过：三条增补齐全（{'/'.join(REQUIRED_ADDITIONS)}）；"
        f"伪码含 {'/'.join(PSEUDOCODE_TOKENS)}；{ERROR_NAME} 已定义；"
        f"引用的冻结件符号 {referenced} 均在 contracts/ 中"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
