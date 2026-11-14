"""MIGRATE-02 校验器：技术方案 v1.2-delta 的八节完整性与真件对账。

acceptance（tasks-v04.json#MIGRATE-02）：
  ① 八节各有增量条目；E2 七新表、E6 三新降级行逐条在列；
  ② 校验器断言八节标题齐全且引用 §4 类型名。

## 「引用 §4 类型名」怎么才算真断言

只查「文档里出现了某几个类型名」是自我安慰——名单写死在校验器里，文档抄一遍就绿。
这里反过来做：把文档里出现的所有 CamelCase 类型名收集起来，逐个回 `WORKORDER-v04.md#4`
与 `contracts/` 核实**确实定义过**。于是「编一个 §4 里没有的类型名」会被抓——
那才是这条断言要防的事。

用法：python tools/check_techplan_delta.py docs/技术方案-v1.2-delta.md
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKORDER = REPO_ROOT / "WORKORDER-v04.md"
CONTRACTS = REPO_ROOT / "contracts"

REQUIRED_SECTIONS = {
    "E2": "存储设计",
    "E3": "API 契约",
    "E4": "作业编排",
    "E5": "LLM 调用层",
    "E6": "故障降级矩阵",
    "E9": "测试策略",
    "E10": "前端架构",
    "E12": "fixture",
}
# E2 七张新表（WORKORDER#2-J2 逐字）
E2_NEW_TABLES = (
    "source_registry", "workbench_graphs", "graph_nodes", "graph_edges",
    "favorites", "template_registry", "share_links",
)
# E6 三条新降级行（按触发条件识别）
E6_NEW_ROWS = ("翻译服务不可用", "单区源全灭", "模板注册表不可用")

# 类型名候选：CamelCase —— **必须含小写字母**。
# 这一条把 API/JSON/SSE 这类缩写与 E10/I12/K1 这类章节号自然排除在外：
# 它们不是类型名，把它们当类型去核实只会制造假红，逼人去「修」一个本来就对的地方。
CAMEL_CASE = re.compile(r"\b([A-Z][A-Za-z0-9]*[a-z][A-Za-z0-9]*)\b")
# 含小写但确实不是类型的词：技术栈与产品名。
NOT_A_TYPE = frozenset({
    "PostgreSQL", "Redis", "Postgres", "Literal", "None", "Optional",
    "Flint", "Markdown", "Python", "TypeScript",
})


def sections(text: str) -> dict[str, list[str]]:
    """按 `## E<n> ` 切块，键为 E 编号。"""
    out: dict[str, list[str]] = {}
    key: str | None = None
    for line in text.replace("\r\n", "\n").split("\n"):
        match = re.match(r"^##\s+(E\d+)\b", line)
        if match:
            key = match.group(1)
            out[key] = []
        elif key is not None:
            out[key].append(line)
    return out


def known_type_names() -> tuple[set[str], str]:
    """(§4 与 contracts/ 里**定义过**的类型名, 工单全文)。

    工单全文一并返回：像 `Translator`（§5-A7 / §7-K4 点名、由 I18N-03 定义）这类
    尚未落到 §4 的协议名，出现在工单里就算合法词汇。写错的名字仍然会被抓——
    笔误既不在 §4、也不在 contracts、更不会出现在工单正文里。
    """
    workorder = WORKORDER.read_text(encoding="utf-8")
    names = set(re.findall(r"^\s*class\s+([A-Z]\w+)", workorder, re.MULTILINE))
    names |= set(re.findall(r"\b([A-Z][A-Za-z0-9]{2,})\s*=\s*Literal", workorder))
    contracts = "".join(p.read_text(encoding="utf-8") for p in sorted(CONTRACTS.glob("*.py")))
    names |= set(re.findall(r"^\s*class\s+([A-Z]\w+)", contracts, re.MULTILINE))
    names |= set(re.findall(r"\b([A-Z][A-Za-z0-9]{2,})\s*=\s*Literal", contracts))
    return names, workorder


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(f"用法：python {Path(__file__).name} docs/技术方案-v1.2-delta.md", file=sys.stderr)
        return 2
    path = Path(argv[1])
    if not path.exists():
        print(f"增量文档不存在：{path}", file=sys.stderr)
        return 1

    text = path.read_text(encoding="utf-8")
    blocks = sections(text)
    problems: list[str] = []

    # ① 八节齐全且各有条目
    for eid, label in REQUIRED_SECTIONS.items():
        if eid not in blocks:
            problems.append(f"缺 {eid}（{label}）小节")
            continue
        body = [ln for ln in blocks[eid] if ln.strip()]
        bullets = [ln for ln in body if ln.lstrip().startswith(("-", "|", "1."))]
        if not bullets:
            problems.append(f"{eid}（{label}）没有增量条目（既无列表也无表格行）")

    # ② E2 七新表逐条在列
    e2 = "\n".join(blocks.get("E2", []))
    for table in E2_NEW_TABLES:
        if table not in e2:
            problems.append(f"E2 缺新表：{table}")

    # ③ E6 三新降级行逐条在列
    e6 = "\n".join(blocks.get("E6", []))
    for row in E6_NEW_ROWS:
        if row not in e6:
            problems.append(f"E6 缺降级行：{row}")

    # ④ 引用 §4 类型名，且引用的每个类型名都真实定义过
    known, workorder_text = known_type_names()
    used = {n for n in CAMEL_CASE.findall(text)} - NOT_A_TYPE
    referenced = sorted(used & known)
    invented = sorted(n for n in used - known if not re.search(rf"\b{n}\b", workorder_text))
    if not referenced:
        problems.append("全文没有引用任何 §4 类型名（八节增量要挂在 §4 的类型上）")
    if invented:
        problems.append(
            f"引用了 §4 与 contracts/ 都没有定义的类型名：{invented}"
            "（要么是笔误，要么是凭空造的类型）"
        )

    if problems:
        print(f"MIGRATE-02 校验不通过（{len(problems)} 项）：", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1
    print(
        f"MIGRATE-02 校验通过：八节齐全（{'/'.join(REQUIRED_SECTIONS)}）；"
        f"E2 七新表在列；E6 三新降级行在列；引用 §4/contracts 类型名 {len(referenced)} 个："
        f"{referenced}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
