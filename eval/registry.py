"""registry 评测（M4-018，技术方案 E9：四态回放全景）。

- 四态：存在 / 不存在 / 不可用 / 替换——全部走录制回放（零联网），
  期望由 fixtures/_generate_registry.py 构造数据携带。
- 通过率 100% 语义收紧：**全部存在 且 锁版成功**（full_pass）——
  仅 pass_rate==1.0 不够，锁不上（无稳定版）同样不算过。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from flint.domain.models import GapHint, PackageStatus
from flint.registry.batch import BatchReport, Ecosystem, validate_batch
from flint.registry.lock import LockEntry, LockError, lock_versions
from flint.registry.pypi import check_pypi
from flint.registry.replace import Replacement, resolve_replacement
from flint.testing.replay import HttpReplay, fixture_path

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
DAY = date(2026, 7, 28)


@dataclass(frozen=True)
class RegistryEvalRow:
    name: str
    ok: bool
    detail: str


@dataclass(frozen=True)
class RegistryEvalReport:
    rows: list[RegistryEvalRow]
    all_ok: bool


def full_pass(report: BatchReport, locks: list[LockEntry]) -> bool:
    locked = {entry.package for entry in locks}
    return (
        report.available
        and report.pass_rate == 1.0
        and all(i.package in locked for i in report.items)
    )


def run_registry_eval() -> RegistryEvalReport:
    rows: list[RegistryEvalRow] = []
    fixture = fixture_path(FIXTURES, "registry_pypi", DAY)
    with HttpReplay(fixture, "replay") as replay:
        client = replay.client()

        def check(package: str, ecosystem: Ecosystem) -> PackageStatus:
            return check_pypi(client, package)

        exists = check_pypi(client, "httpx")
        rows.append(RegistryEvalRow(
            name="exists", ok=exists.exists and exists.latest_stable == "0.28.1",
            detail=f"latest_stable={exists.latest_stable}",
        ))

        missing = check_pypi(client, "flint-no-such-package")
        rows.append(RegistryEvalRow(
            name="missing", ok=not missing.exists and missing.reason is not None,
            detail=str(missing.reason),
        ))

        down = validate_batch(check, [("flint-broken-registry", "pypi")])
        rows.append(RegistryEvalRow(
            name="unavailable",
            ok=not down.available and down.missing == [],
            detail="available=False, not counted missing",
        ))

        replaced = resolve_replacement(missing, [exists])
        rows.append(RegistryEvalRow(
            name="replaced",
            ok=isinstance(replaced, Replacement)
            and replaced.status.replaced_with == "httpx",
            detail=replaced.marker if isinstance(replaced, Replacement) else "gap",
        ))

        no_candidate = resolve_replacement(missing, [])
        rows.append(RegistryEvalRow(
            name="replaced-no-candidate",
            ok=isinstance(no_candidate, GapHint),
            detail="GapHint, never guesses",
        ))

        clean = validate_batch(check, [("httpx", "pypi")])
        try:
            locks = lock_versions(
                [i.status for i in clean.items if i.status is not None], {}
            )
            rows.append(RegistryEvalRow(
                name="full-pass-semantics",
                ok=full_pass(clean, locks) and not full_pass(down, []),
                detail="all exist AND all locked; unavailable never full-pass",
            ))
        except LockError as err:
            rows.append(RegistryEvalRow(
                name="full-pass-semantics", ok=False, detail=str(err),
            ))

    return RegistryEvalReport(rows=rows, all_ok=all(r.ok for r in rows))
