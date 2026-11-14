"""MIGRATE-03 校验器：前端功能说明 v2 的屏数、六类新屏、i18n key 总表与定名标记。

acceptance（tasks-v04.json#MIGRATE-03）：
  ① 新增六类屏（设置/卡片广场/图书馆/图谱/设计台/外链查看）逐屏含状态呈现规则；
  ② 2.2 与 F 组定名方案成文并标 owner_review。

屏的识别口径：`### <编号> <屏名>` 形式的三级标题（编号形如 2.1 / 2.13）。
`--min-screens` 由调用方给（卡上是 16）。

用法：python tools/check_fe_doc.py docs/前端功能说明-v2.md --min-screens 16
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

SCREEN_RE = re.compile(r"^###\s+(\d+\.\d+)\s+(.+)$")
# 六类新屏：识别关键词 → 人读名（关键词出现在屏名里即算命中）
NEW_SCREENS = {
    "语言": "语言/地区设置",
    "卡片广场": "热点卡片广场",
    "图书馆": "收藏图书馆",
    "图谱": "热点工作台·图谱",
    # 工单 §2-J4 里这一屏叫「AI 设计工作台」——关键词取「设计工作台」而不是卡上的简称
    # 「设计台」，否则会去匹配一个文档里并不存在的名字（首轮就是这么红的）。
    "设计工作台": "AI 设计工作台",
    "外链": "外链只读查看页",
}
STATE_RULES_MARK = "状态呈现规则"
I18N_TABLE_MARK = "i18n key 总表"
OWNER_REVIEW_MARK = "owner_review: true"
NAMING_MARKS = ("证据卡面板", "/workbench")


def screens(text: str) -> list[tuple[str, str, list[str]]]:
    """[(编号, 屏名, 该屏正文行)]。"""
    out: list[tuple[str, str, list[str]]] = []
    body: list[str] | None = None
    for line in text.replace("\r\n", "\n").split("\n"):
        match = SCREEN_RE.match(line)
        if match:
            body = []
            out.append((match.group(1), match.group(2).strip(), body))
        elif body is not None:
            if line.startswith("## "):        # 出了「逐界面」大节
                body = None
            else:
                body.append(line)
    return out


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="前端功能说明 v2 校验器")
    parser.add_argument("path")
    parser.add_argument("--min-screens", type=int, required=True)
    args = parser.parse_args(argv[1:])

    path = Path(args.path)
    if not path.exists():
        print(f"文档不存在：{path}", file=sys.stderr)
        return 1
    text = path.read_text(encoding="utf-8")
    found = screens(text)
    problems: list[str] = []

    if len(found) < args.min_screens:
        names = ", ".join(f"{n} {t}" for n, t, _ in found)
        problems.append(f"屏数 {len(found)} < 要求的 {args.min_screens}：{names}")

    # ① 六类新屏各自在列，且各自带状态呈现规则
    for keyword, label in NEW_SCREENS.items():
        hit = next(((n, t, b) for n, t, b in found if keyword in t), None)
        if hit is None:
            problems.append(f"缺新屏：{label}（屏名里应含「{keyword}」）")
            continue
        number, title, body = hit
        if STATE_RULES_MARK not in "\n".join(body):
            problems.append(f"新屏 {number} {title} 缺「{STATE_RULES_MARK}」")

    # ② i18n key 总表
    if I18N_TABLE_MARK not in text:
        problems.append(f"缺「{I18N_TABLE_MARK}」")

    # ③ 2.2 与 F 组定名方案 + owner_review 标记
    if OWNER_REVIEW_MARK not in text:
        problems.append(f"定名方案未标 `{OWNER_REVIEW_MARK}`——偏离清单处 MUST 标出待 owner 复核")
    for mark in NAMING_MARKS:
        if mark not in text:
            problems.append(f"定名方案缺要素：{mark}")

    if problems:
        print(f"MIGRATE-03 校验不通过（{len(problems)} 项）：", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1
    print(
        f"MIGRATE-03 校验通过：{len(found)} 屏（≥{args.min_screens}）；"
        f"六类新屏各带{STATE_RULES_MARK}；{I18N_TABLE_MARK}在列；定名方案已标 owner_review"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
