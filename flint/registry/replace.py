"""替换标记 [replaced]（M4-014，冻结协议 RegistryValidator E1 口径）。

- 不存在包 + 已校验存在的候选 → 替换建议：PackageStatus 携 replaced_with
  + S3 pin 行携 `[replaced: 原因]` 标注。
- 无候选（或候选全不存在）→ GapHint（cause=missing_data，
  action=ask_user）——NEVER 猜包名。
"""
from __future__ import annotations

from dataclasses import dataclass

from flint.domain.models import GapHint, PackageStatus


class ReplaceError(Exception):
    pass


@dataclass(frozen=True)
class Replacement:
    status: PackageStatus  # exists=False + replaced_with 已填
    substitute: PackageStatus
    marker: str


def resolve_replacement(
    missing: PackageStatus, candidates: list[PackageStatus]
) -> Replacement | GapHint:
    if missing.exists:
        raise ReplaceError(
            f"{missing.package}: replacement is for nonexistent packages only"
        )
    for candidate in candidates:
        if candidate.exists and candidate.ecosystem == missing.ecosystem:
            reason = missing.reason or "not found"
            return Replacement(
                status=PackageStatus(
                    package=missing.package, ecosystem=missing.ecosystem,
                    exists=False, latest_stable=None,
                    replaced_with=candidate.package, reason=reason,
                ),
                substitute=candidate,
                marker=f"[replaced: {missing.package} → {candidate.package}"
                f"（{reason}）]",
            )
    return GapHint(
        missing_what=(
            f"依赖 {missing.package}（{missing.ecosystem}）不存在且无已校验"
            "替换候选——不猜包名"
        ),
        cause="missing_data",
        suggested_sources=[
            "提供替换包名（将经 registry 校验后进 S3）",
            "移除该依赖并调整对应任务卡",
        ],
        action="ask_user",
    )


def pin_line(replacement: Replacement) -> str:
    substitute = replacement.substitute
    version = substitute.latest_stable or "unpinned"
    return f"- {substitute.package} {version} {replacement.marker}"
