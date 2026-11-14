"""版本锁定联动（M4-013，S2-6：版本 MUST 锁死写入 lock 文件）。

- 只锁校验通过（exists=True）的包；不存在/未校验包进锁 = 编程错误即拒。
- 请求版本与 latest_stable 冲突 → 以锁版（请求版本）为准 + note 提示位
  （NEVER 静默升级——锁死语义优先，升级是人的决定）。
- 未指定请求版本 → 锁 latest_stable；连 latest_stable 都无 → 拒
  （无稳定版不可锁）。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from flint.domain.models import PackageStatus


class LockError(Exception):
    pass


@dataclass(frozen=True)
class LockEntry:
    package: str
    ecosystem: Literal["pypi", "npm", "crates"]
    locked_version: str
    note: str | None


def lock_versions(
    statuses: list[PackageStatus], requested: dict[str, str]
) -> list[LockEntry]:
    entries: list[LockEntry] = []
    for status in statuses:
        if not status.exists:
            raise LockError(
                f"{status.package}: nonexistent package cannot be locked"
            )
        wanted = requested.get(status.package)
        if wanted is None:
            if status.latest_stable is None:
                raise LockError(
                    f"{status.package}: no stable version to lock"
                )
            entries.append(
                LockEntry(
                    package=status.package, ecosystem=status.ecosystem,
                    locked_version=status.latest_stable, note=None,
                )
            )
            continue
        note = None
        if status.latest_stable is not None and status.latest_stable != wanted:
            note = (
                f"latest_stable={status.latest_stable} differs; "
                "lock wins (upgrade is an owner decision)"
            )
        entries.append(
            LockEntry(
                package=status.package, ecosystem=status.ecosystem,
                locked_version=wanted, note=note,
            )
        )
    return entries


def render_lock(entries: list[LockEntry]) -> str:
    lines = ["# 包内 lock 清单（版本钉死，S2-6）"]
    for entry in sorted(entries, key=lambda e: (e.ecosystem, e.package)):
        suffix = f"  # {entry.note}" if entry.note else ""
        lines.append(
            f"{entry.ecosystem}: {entry.package}=={entry.locked_version}{suffix}"
        )
    return "\n".join(lines) + "\n"
