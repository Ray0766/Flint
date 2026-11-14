"""不变量回归族并册（M3-064，技术方案 E9 点名 + 通道执行器 + 谓词等价）。

- 单命令回归入口：E9 三点名测试 + 三通道互斥全册 + Python/SQL 保护谓词
  等价——任一破 → exit 1 且指认破处（pytest 节点名即指认）。
运行：python -m eval.invariants
"""
from __future__ import annotations

import subprocess
import sys
from typing import Final

INVARIANT_NODES: Final[list[str]] = [
    "tests/m3/test_m3_006.py::test_partial_never_promoted",
    "tests/m3/test_m3_028.py::test_protected_block_never_rewritten",
    "tests/m3/test_m3_051.py::test_verdict_shift_requires_rerun",
    "tests/m3/test_m3_016.py",
    "tests/m3/test_m3_064.py::test_protection_predicate_python_sql_equivalence",
]


def main(node_ids: list[str] | None = None) -> int:
    nodes = node_ids if node_ids is not None else INVARIANT_NODES
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-rf", *nodes],
        check=False,
    )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
