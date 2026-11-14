"""SignalFlag 判定：novelty / momentum / revival（M1-031，PDD v0.2 §3.3 / A4）。

三规则，阈值全部配置化（验收硬条款），直接喂 why now：
- novelty：first_seen 距今 <= novelty_days（§3.3 初值 7 天）；
- momentum：当日 norm - 基线 norm >= momentum_delta；基线 = 距今 >=
  momentum_window_days 的最近一条（无基线不判，避免新簇误报升温）；
- revival：当日发生 dormant -> active（血缘④ RevivalEvent 输入）。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from flint.domain.models import SignalFlag


@dataclass(frozen=True)
class SignalConfig:
    novelty_days: int = 7
    momentum_window_days: int = 7
    momentum_delta: float = 20.0


def detect_signals(
    first_seen: date,
    revived_today: bool,
    norm_series: list[tuple[date, float]],
    today: date,
    config: SignalConfig,
) -> list[SignalFlag]:
    flags: list[SignalFlag] = []

    if (today - first_seen).days <= config.novelty_days:
        flags.append("novelty")

    today_norm = next((v for d, v in norm_series if d == today), None)
    cutoff = today - timedelta(days=config.momentum_window_days)
    baseline_candidates = [(d, v) for d, v in norm_series if d <= cutoff]
    if today_norm is not None and baseline_candidates:
        _, baseline = max(baseline_candidates, key=lambda item: item[0])
        if today_norm - baseline >= config.momentum_delta:
            flags.append("momentum")

    if revived_today:
        flags.append("revival")

    return flags
