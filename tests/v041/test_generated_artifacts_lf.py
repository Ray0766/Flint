"""MAC-07：门禁与回放顺手重写的那批入库文件，换行 NEVER 随平台变。

## 那批文件是什么

`harness.replay30`、金标回归、文书回归、试跑包生成、演练七都会把结果落到**入库的**路径上：
`docs/trace/replay30/`、`docs/trace/goldcases/`、`docs/trace/golddocs-doc/`、
`assets/trial_specs/`、`docs/trace/drill7.md`。每跑一遍全量 pytest 或回放，它们就被重写一遍。

## 病在哪

写入用的是 `Path.write_text(text, encoding="utf-8")`，没指定换行。Python 的文本模式
在 Windows 上把 `\\n` 写成 `\\r\\n`，在 POSIX 上原样写。入库那份是 Windows 上生成的（CRLF），
搬到 macOS 之后每跑一遍就有 66 个文件变成「已修改」，而内容一个字没变
（`git diff --ignore-cr-at-eol` 无输出）。真改动混在这 66 个里很难看见。

`harness/m4_regress.py:173` 早就写了 `newline="\\n"`，其余几处没跟上。

## 本文件守两件

1. 这几个写入点都指定 `newline="\\n"`；
2. 入库的那批文件里没有 `\\r\\n`。

第 1 条用 AST 判而不是跑一遍看产物：在 POSIX 上不指定也是 LF，跑出来的产物分不出写没写。
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]

# 门禁或回放会重写入库文件的那几个写入者。
WRITERS = (
    "harness/replay30.py",
    "harness/gate1_regress.py",
    "harness/m3_regress.py",
    "harness/m4_regress.py",
    "harness/drill7.py",
    "fixtures/_generate_trial_specs.py",
)

GENERATED_DIRS = (
    "docs/trace/replay30",
    "docs/trace/goldcases",
    "docs/trace/golddocs-doc",
    "assets/trial_specs",
)
GENERATED_FILES = ("docs/trace/drill7.md",)
TEXT_SUFFIXES = {".md", ".json"}


def _write_text_calls(path: Path) -> list[ast.Call]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        and node.func.attr == "write_text"
    ]


@pytest.mark.parametrize("rel", WRITERS)
def test_the_writer_pins_the_newline(rel: str) -> None:
    calls = _write_text_calls(REPO / rel)
    assert calls, f"{rel} 里一处 write_text 都没有——清单过期了"

    for call in calls:
        newline = next((k.value for k in call.keywords if k.arg == "newline"), None)
        assert isinstance(newline, ast.Constant) and newline.value == "\n", (
            f"{rel}:{call.lineno} 的 write_text 没写 newline=\"\\n\"——"
            "在 Windows 上它会落成 CRLF")


def _generated() -> list[Path]:
    found = [REPO / rel for rel in GENERATED_FILES]
    for rel in GENERATED_DIRS:
        found.extend(
            p for p in sorted((REPO / rel).rglob("*"), key=lambda p: p.as_posix())
            if p.is_file() and p.suffix in TEXT_SUFFIXES)
    return found


def test_the_scan_sees_the_whole_set() -> None:
    """扫描面自证：扫到的文件数对得上——少扫一个目录的话下一条会因为「没看见」而绿。"""
    assert len(_generated()) >= 60, len(_generated())


def test_no_generated_artifact_carries_crlf() -> None:
    dirty = [p.relative_to(REPO).as_posix() for p in _generated() if b"\r\n" in p.read_bytes()]

    assert dirty == [], f"{len(dirty)} 个生成物还是 CRLF：{dirty[:5]}"
