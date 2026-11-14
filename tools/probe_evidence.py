"""`.ui-probe/` 取证产物不在本机时的统一口径（`MAC-06`）。

`.ui-probe/` 是本机运行产物，不进仓。判据读它之前先过这里：

- 锚点不在——这台机器没跑过这份取证——**skip**，写明缺什么、怎么补；
- 锚点在——取证跑过——什么都不做，缺哪一张照旧由调用方判红。

锚点取「这份取证跑过就一定会有」的那个目录或报告文件。开工前拍的历史对照
（只存在于原来那台机器上）以那份文件本身为锚点，`how` 里写明它重跑不出来。

判据：`tests/v041/test_probe_evidence_guard.py`。
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

# 历史对照那一类共用的一句：它们是改动之前拍的，改动已经发生，拍不回来。
ONLY_ON_THE_ORIGINAL_MACHINE = "这是开工前拍的历史对照，重跑取证造不出来，只在原来那台机器的 .ui-probe/ 里"


def require_probe_evidence(anchor: Path, how: str) -> None:
    """锚点不在就 skip；在就返回，后面的断言照旧生效。"""
    if anchor.exists():
        return
    try:
        shown = anchor.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        shown = anchor.as_posix()
    pytest.skip(
        f"本机没跑过这份取证：缺 {shown}（.ui-probe/ 不进仓）。怎么补：{how}。NEVER 当它通过")
