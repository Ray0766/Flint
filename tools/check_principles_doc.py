"""PRIN-01 校验器：docs/PRINCIPLES-v04.md 与工单 §3 一致、且七条四段齐全。

acceptance（tasks-v04.json#PRIN-01）：
  ① 七条各含 规则 / 反例 / 校验点 / 违反时 四段，逐条断言四段齐全；
  ② 与工单 §3 正文逐字一致（哈希比对）。

## §3 正文的边界（DEC-001）

工单 §3 整节 = 从 `## §3 ` 标题行起，到**下一个** `## ` 同级标题前为止，
去掉末尾的分隔线 `---` 与首尾空行。落盘文档就是这一整节（含标题行），
所以两处可以直接做整体哈希，不需要「文档里挑一段再比」那种模糊口径。

## 为什么哈希前要归一行尾

Windows 上编辑器可能把落盘文档写成 CRLF，而工单是 LF；不归一的话，
两份内容完全相同也会哈希不等 —— 那是假红，会逼着人去「修」一个本来就对的文件。
两侧走**同一个**归一（CRLF/CR → LF，去尾部空白），归一后仍是逐字节比对。

用法：python tools/check_principles_doc.py docs/PRINCIPLES-v04.md
退出码 0 = 通过；1 = 不通过（逐条打印原因）。
"""
from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKORDER = REPO_ROOT / "WORKORDER-v04.md"
SECTION_HEADING = "## §3 "
EXPECTED_COUNT = 7                      # 工单 §3 标题即「七条」
PRINCIPLE_RE = re.compile(r"^### PRINCIPLES#(\S+)\s*(.*)$")
REQUIRED_PARTS = ("规则", "反例", "校验点", "违反时")


def normalize(text: str) -> str:
    """行尾归一 + 去尾部空白。两侧同一处理，归一后仍是逐字节比对。"""
    return text.replace("\r\n", "\n").replace("\r", "\n").rstrip()


def extract_section(markdown: str) -> str | None:
    """取工单 §3 整节：标题行 → 下一个 `## ` 前，去掉末尾 `---`。"""
    lines = normalize(markdown).split("\n")
    start = next((i for i, ln in enumerate(lines) if ln.startswith(SECTION_HEADING)), None)
    if start is None:
        return None
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if lines[i].startswith("## "):
            end = i
            break
    body = lines[start:end]
    while body and not body[-1].strip():
        body.pop()
    if body and body[-1].strip() == "---":
        body.pop()
    return normalize("\n".join(body))


def split_principles(section: str) -> list[tuple[str, list[str]]]:
    """切成 [(编号, 该条的行), ...]。"""
    blocks: list[tuple[str, list[str]]] = []
    current: list[str] | None = None
    for line in section.split("\n"):
        match = PRINCIPLE_RE.match(line)
        if match:
            current = []
            blocks.append((match.group(1), current))
        elif current is not None:
            current.append(line)
    return blocks


def check_parts(pid: str, body: list[str]) -> list[str]:
    """四段齐全且非空。段落形态：`- **规则**：<正文>`。"""
    problems: list[str] = []
    for part in REQUIRED_PARTS:
        marker = f"- **{part}**："
        hit = next((ln for ln in body if ln.startswith(marker)), None)
        if hit is None:
            problems.append(f"PRINCIPLES#{pid}：缺「{part}」段")
        elif not hit[len(marker):].strip():
            problems.append(f"PRINCIPLES#{pid}：「{part}」段是空的")
    return problems


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(f"用法：python {Path(__file__).name} docs/PRINCIPLES-v04.md", file=sys.stderr)
        return 2
    doc_path = Path(argv[1])
    problems: list[str] = []

    if not WORKORDER.exists():
        print(f"找不到工单：{WORKORDER}", file=sys.stderr)
        return 1
    section = extract_section(WORKORDER.read_text(encoding="utf-8"))
    if section is None:
        print(f"工单里找不到以「{SECTION_HEADING}」开头的小节", file=sys.stderr)
        return 1

    if not doc_path.exists():
        print(f"落盘文档不存在：{doc_path}", file=sys.stderr)
        return 1
    doc = normalize(doc_path.read_text(encoding="utf-8"))

    # ② 逐字一致（哈希比对）
    doc_hash = hashlib.sha256(doc.encode("utf-8")).hexdigest()
    src_hash = hashlib.sha256(section.encode("utf-8")).hexdigest()
    if doc_hash != src_hash:
        problems.append(
            f"与工单 §3 正文不一致：文档 sha256={doc_hash[:16]}… 工单 sha256={src_hash[:16]}…"
        )
        doc_lines, src_lines = doc.split("\n"), section.split("\n")
        for i in range(max(len(doc_lines), len(src_lines))):
            left = doc_lines[i] if i < len(doc_lines) else "<文档到此结束>"
            right = src_lines[i] if i < len(src_lines) else "<工单到此结束>"
            if left != right:
                problems.append(f"  首个差异在第 {i + 1} 行：\n    文档：{left}\n    工单：{right}")
                break

    # ① 七条 × 四段
    blocks = split_principles(doc)
    if len(blocks) != EXPECTED_COUNT:
        ids = ", ".join(pid for pid, _ in blocks) or "（一条都没有）"
        problems.append(f"应有 {EXPECTED_COUNT} 条原则，实际 {len(blocks)} 条：{ids}")
    src_ids = [pid for pid, _ in split_principles(section)]
    doc_ids = [pid for pid, _ in blocks]
    if doc_ids != src_ids:
        problems.append(f"原则编号与工单不一致：文档 {doc_ids} ≠ 工单 {src_ids}")
    for pid, body in blocks:
        problems += check_parts(pid, body)

    if problems:
        print(f"PRIN-01 校验不通过（{len(problems)} 项）：", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1
    print(f"PRIN-01 校验通过：{len(blocks)} 条原则 × {len(REQUIRED_PARTS)} 段齐全；"
          f"与工单 §3 逐字一致 sha256={doc_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
