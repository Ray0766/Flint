"""换行符扫描尺：源码的行尾 MUST 一致，混入 CRLF 判红并指出是哪个文件。

## 这把尺子在守什么

不是「代码风格」。**是别的尺子的视力。**

全仓「先剥注释再判」的尺子共用同一份剥刀
（`web/test-utils/source.ts#codeOnly`，与 `tools/i18n_scan.mjs` 对齐）：

```js
source.split("\\n").map((line) => line.replace(/\\/\\/.*$/, "")).join("\\n")
```

CRLF 之下，`split("\\n")` 切出来的每行**末尾还挂着一个 `\\r`**。
而在 JS 正则里 **`\\r` 是行终止符**：`.` 不匹配它，`$`（无 `m` 标志）要求匹配到
字符串末尾。于是 `//.*$` 在 `\\r` 前就走不下去，**整行注释一条都剥不掉**。

**实测坐实**（`GAUGE-08` 执行时，`web/` 下 35 个 ts/tsx 是 CRLF）：

```
lib/jobClient.ts      CRLF 161 行   注释 13 处   剥掉 0 处
lib/screenClient.ts   CRLF  80 行   注释 26 处   剥掉 0 处
```

后果是**全局的、静默的**：所有「源码里不该出现 X」的判据，
在这些文件上都退化成了「全文里不该出现 X」——
一次表现为假红（`DEF-03` 撞上的那次），而同一条缝在另一个方向上给出**假绿**。

## 为什么判「一致」而不是「一律 LF」

本仓 531 个文件是纯 CRLF（Windows 上的常态），一刀切成 LF 是一次巨大的无关改动，
且会让所有历史比对失效。**这把尺子守的是「剥刀能不能工作」**，
所以它盯的是**剥刀实际扫描的那个面**（`SCANNED_FACES`），别处不管。

混用（同一个文件里既有 CRLF 又有 LF）**一律判红**：那种文件在任何读法下
都会有一半行为异常，且它通常是一次工具事故的痕迹
（`Path.write_text()` 在 Windows 上默认做换行翻译——`DEF-03` 那次就是这么来的）。
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Final

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
SKIP_DIRS: Final[frozenset[str]] = frozenset(
    {"__pycache__", ".venv", "node_modules", ".next", ".git", ".ui-probe"}
)

# **剥刀实际扫描的那个面**。别处的行尾不管——守的是尺子的视力，不是风格。
#
# `web/**/*.ts(x)`：`web/test-utils/source.ts#codeOnly` 与
# `tools/i18n_scan.mjs` / `check_design_constraints.mjs` 都扫这一面。
SCANNED_FACES: Final[tuple[tuple[str, tuple[str, ...]], ...]] = (
    ("web", (".ts", ".tsx")),
)


@dataclass(frozen=True)
class Finding:
    path: str
    kind: str
    detail: str


def classify(raw: bytes) -> str:
    """`lf` / `crlf` / `mixed` / `none`（一行都没有）。"""
    crlf = raw.count(b"\r\n")
    lf = raw.count(b"\n") - crlf
    if crlf and lf:
        return "mixed"
    if crlf:
        return "crlf"
    if lf:
        return "lf"
    return "none"


def files_in_scanned_faces(root: Path) -> list[Path]:
    out: list[Path] = []
    for prefix, suffixes in SCANNED_FACES:
        base = root / prefix
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file() or path.suffix not in suffixes:
                continue
            if any(part in SKIP_DIRS for part in path.parts):
                continue
            out.append(path)
    return out


def audit(root: Path | None = None) -> dict[str, Any]:
    """扫一遍并给出结论。**扫描面为空要说出来**，NEVER 报成「干净」。"""
    root = root or REPO_ROOT
    files = files_in_scanned_faces(root)
    findings: list[Finding] = []
    for path in files:
        shown = path.relative_to(root).as_posix()
        kind = classify(path.read_bytes())
        if kind == "mixed":
            findings.append(Finding(
                shown, "mixed",
                "同一个文件里既有 CRLF 又有 LF——任何读法下都会有一半行为异常，"
                "且它通常是一次工具事故的痕迹（Windows 上 write_text 默认翻译换行）"))
        elif kind == "crlf":
            findings.append(Finding(
                shown, "crlf",
                "CRLF：JS 剥刀 `//.*$` 在 `\\r` 前走不下去，**整行注释一条都剥不掉**——"
                "所有「源码里不该出现 X」的判据在这个文件上都退化成「全文里不该出现 X」"))
    return {
        "schema": "line-endings/1",
        "scanned": len(files),
        "findings": [asdict(f) for f in findings],
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = audit()

    if args.json:
        sys.stdout.write(json.dumps(report, ensure_ascii=False, indent=1))
        return 1 if report["findings"] else 0

    if not report["scanned"]:
        sys.stdout.write("扫描面为空——**这不是「干净」**，是没量到。检查 SCANNED_FACES。\n")
        return 2
    if not report["findings"]:
        sys.stdout.write(f"行尾一致：{report['scanned']} 个文件全是 LF。\n")
        return 0
    sys.stdout.write(
        f"扫了 {report['scanned']} 个文件，{len(report['findings'])} 个的行尾会让剥刀失效：\n")
    for row in report["findings"]:
        sys.stdout.write(f"    · {row['path']}  [{row['kind']}]\n")
    sys.stdout.write(
        "\n剥刀失效 = 那些文件上「源码里不该出现 X」的判据全部退化成"
        "「全文里不该出现 X」。修法：把这些文件的行尾统一成 LF。\n")
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
