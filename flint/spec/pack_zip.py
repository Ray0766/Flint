"""zip 完整包导出（M4-010，技术方案 E3 三件 + M3-039/058 挂钩位收线）。

- zip 布局：CLAUDE.md（vibe_pack S1~S9 合卷）+ tasks.json（机读同步）
  + contracts/ 副本（models/protocols/README/MANIFEST）——E3 三件；
  HUMAN_DIGEST.md 随包侧载（监工视图，不在 CLAUDE.md 内）。
- 门禁挂钩位：PackGate 回调（M4-030 接 DagValidator/registry 实调），
  违规 → PackExportBlocked，NEVER 出残包；contracts 副本完整性
  （verify_copy）是内建门，先于回调执行。
"""
from __future__ import annotations

import io
import zipfile
from collections.abc import Callable
from dataclasses import dataclass

from flint.spec.contracts_copy import ContractsCopy, render_manifest, verify_copy


@dataclass(frozen=True)
class PackBundle:
    claude_md: str
    human_digest: str
    tasks_json: str
    contracts: ContractsCopy


PackGate = Callable[[PackBundle], list[str]]


class PackExportBlocked(Exception):
    def __init__(self, violations: list[str]) -> None:
        super().__init__("; ".join(violations))
        self.violations = violations


def build_zip(bundle: PackBundle, gate: PackGate | None = None) -> bytes:
    integrity = verify_copy(bundle.contracts)
    if integrity:
        raise PackExportBlocked([f"contracts copy: {p}" for p in integrity])
    if gate is not None:
        violations = gate(bundle)
        if violations:
            raise PackExportBlocked(violations)

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("CLAUDE.md", bundle.claude_md)
        archive.writestr("tasks.json", bundle.tasks_json)
        archive.writestr("HUMAN_DIGEST.md", bundle.human_digest)
        for name, body in bundle.contracts.files.items():
            archive.writestr(f"contracts/{name}", body)
        archive.writestr("contracts/README.md", bundle.contracts.readme)
        archive.writestr(
            "contracts/MANIFEST.sha256", render_manifest(bundle.contracts)
        )
    return buffer.getvalue()
