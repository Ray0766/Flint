"""registry 批量校验器（M4-015，技术方案 E5 / S2-6）。

- S3 tech_choices 全清单批校验 → BatchReport（逐包状态 + 通过率）。
- 三态严格分离：exists / missing（404，可走替换）/ **unavailable**
  （通道不可用）——任一包不可用即整批 available=False（S2-6：registry
  校验不可用时 NEVER 引入新依赖；不可用 ≠ 不存在，不计入 missing）。
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from flint.domain.models import PackageStatus
from flint.registry.pypi import RegistryUnavailable

Ecosystem = Literal["pypi", "npm", "crates"]
CheckFn = Callable[[str, Ecosystem], PackageStatus]


@dataclass(frozen=True)
class BatchItem:
    package: str
    ecosystem: Ecosystem
    state: Literal["exists", "missing", "unavailable"]
    status: PackageStatus | None
    detail: str | None


@dataclass(frozen=True)
class BatchReport:
    items: list[BatchItem]
    total: int
    existing: int
    missing: list[str]
    pass_rate: float
    available: bool


def validate_batch(
    check: CheckFn, requests: list[tuple[str, Ecosystem]]
) -> BatchReport:
    items: list[BatchItem] = []
    available = True
    for package, ecosystem in requests:
        try:
            status = check(package, ecosystem)
        except RegistryUnavailable as err:
            available = False
            items.append(
                BatchItem(
                    package=package, ecosystem=ecosystem,
                    state="unavailable", status=None, detail=str(err),
                )
            )
            continue
        items.append(
            BatchItem(
                package=package, ecosystem=ecosystem,
                state="exists" if status.exists else "missing",
                status=status, detail=status.reason,
            )
        )
    existing = sum(1 for i in items if i.state == "exists")
    missing = [i.package for i in items if i.state == "missing"]
    total = len(items)
    return BatchReport(
        items=items,
        total=total,
        existing=existing,
        missing=missing,
        pass_rate=existing / total if total else 0.0,
        available=available,
    )
