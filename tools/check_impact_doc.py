"""MIGRATE-05/06/07 共用的登记类文档校验器。

三张卡共用一个校验器（NEVER 写三个）：
  MIGRATE-05: --require-sections screens,i18n-hardcode,known-issues
  MIGRATE-06: --require-refs 12
  MIGRATE-07: --require-sections currency,defer

## --require-sections
小节锚点写在标题里：`## screens — 缺屏清单`。要求该小节存在**且正文非空**——
只留标题不写内容，是登记类文档最容易的失守方式。

## --require-refs N
「逐场景 id 引用」这条要求，光数个数没用（写 12 个假 id 也能过）。
所以这里额外做**存在性核实**：文档里反引号包起来的 id 逐个回 `harness/` 与 `assets/`
里找，找不到即红。登记文档引用的场景 id 必须是真跑得到的那些。

用法：python tools/check_impact_doc.py <doc.md> [--require-sections a,b] [--require-refs N]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SEARCH_DIRS = ("harness", "assets")
REF_RE = re.compile(r"`([a-z][a-z0-9_.\-]{3,})`")


def sections(text: str) -> dict[str, list[str]]:
    """`## <token> …` → 该小节正文行。"""
    out: dict[str, list[str]] = {}
    key: str | None = None
    for line in text.replace("\r\n", "\n").split("\n"):
        match = re.match(r"^##\s+(\S+)", line)
        if match:
            key = match.group(1)
            out[key] = []
        elif key is not None:
            out[key].append(line)
    return out


def repo_corpus() -> str:
    parts: list[str] = []
    for name in SEARCH_DIRS:
        root = REPO_ROOT / name
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.suffix in {".py", ".json", ".yaml", ".yml"} and path.is_file():
                try:
                    parts.append(path.read_text(encoding="utf-8"))
                except (UnicodeDecodeError, OSError):
                    continue
    return "\n".join(parts)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="登记类文档校验器")
    parser.add_argument("path")
    parser.add_argument("--require-sections", default="")
    parser.add_argument("--require-refs", type=int, default=0)
    args = parser.parse_args(argv[1:])

    path = Path(args.path)
    if not path.exists():
        print(f"文档不存在：{path}", file=sys.stderr)
        return 1
    text = path.read_text(encoding="utf-8")
    blocks = sections(text)
    problems: list[str] = []

    wanted = [s.strip() for s in args.require_sections.split(",") if s.strip()]
    for name in wanted:
        if name not in blocks:
            problems.append(f"缺小节 `## {name} …`")
        elif not "\n".join(blocks[name]).strip():
            problems.append(f"小节 `## {name}` 是空的（只有标题不算登记）")

    refs: list[str] = []
    if args.require_refs:
        refs = sorted(set(REF_RE.findall(text)))
        if len(refs) < args.require_refs:
            problems.append(f"引用 id 只有 {len(refs)} 个，少于要求的 {args.require_refs}：{refs}")
        corpus = repo_corpus()
        missing = [r for r in refs if r not in corpus]
        if missing:
            problems.append(
                f"这些 id 在 {'/'.join(SEARCH_DIRS)} 里找不到：{missing}"
                "（登记文档 NEVER 引用不存在的场景）"
            )

    if problems:
        print(f"{path.name} 校验不通过（{len(problems)} 项）：", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1
    detail = f"小节齐全 {wanted}" if wanted else ""
    if args.require_refs:
        detail += f"{'；' if detail else ''}{len(refs)} 个引用 id 均在仓库中可查"
    print(f"{path.name} 校验通过：{detail}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
