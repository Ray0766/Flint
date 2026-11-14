"""任务一次通过率 Z 线（M4-032，PDD v0.3.1 §7 / S4 Open Question）。

- Z 线值**配置化且初值未定**（owner 待定，S4 登记走问题单通道——
  CLAUDE.md 正文 NEVER 自行改）：FLINT_Z_LINE 环境变量或显式入参；
  未定线 → verdict="report_only"（只报告不判定，NEVER 代 owner 画线）。
- oneshot 口径：任务首个 verify 即绿为一次通过（返工后通过不计）。
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal


class ZLineConfigError(Exception):
    pass


@dataclass(frozen=True)
class PassRateReport:
    total: int
    oneshot_passes: int
    rate: float
    z_line: float | None
    verdict: Literal["pass", "fail", "report_only"]


def z_line_from_env(env: dict[str, str] | None = None) -> float | None:
    raw = (env if env is not None else dict(os.environ)).get("FLINT_Z_LINE")
    if raw is None or raw == "":
        return None
    try:
        value = float(raw)
    except ValueError as err:
        raise ZLineConfigError(f"FLINT_Z_LINE not a number: {raw!r}") from err
    if not 0.0 <= value <= 1.0:
        raise ZLineConfigError(f"FLINT_Z_LINE out of [0,1]: {value}")
    return value


def pass_rate_report(
    outcomes: list[tuple[str, bool]], z_line: float | None = None
) -> PassRateReport:
    total = len(outcomes)
    passes = sum(1 for _task_id, oneshot in outcomes if oneshot)
    rate = passes / total if total else 0.0
    if z_line is None:
        verdict: Literal["pass", "fail", "report_only"] = "report_only"
    else:
        verdict = "pass" if rate >= z_line else "fail"
    return PassRateReport(
        total=total, oneshot_passes=passes, rate=rate,
        z_line=z_line, verdict=verdict,
    )
