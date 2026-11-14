"""vibe 附加门禁装配（M4-027，技术方案 E3）。

- vibe_pack 导出门禁 = 三与：审11 blocking 零开放 ∧ DagValidator 零
  errors（含 orphans/unreachable 全表面）∧ registry 100%（M4-016 门
  零违规）。任一不过 → 拒，violations 按类别前缀指认
  （review: / dag: / registry:）。
- as_pack_gate 适配 build_zip 的 PackGate 回调面（M4-010 挂钩位消费）。
"""
from __future__ import annotations

from dataclasses import dataclass

from flint.domain.models import DagReport
from flint.registry.gate import RegistryGateResult


@dataclass(frozen=True)
class ExportGateVerdict:
    allowed: bool
    violations: list[str]


def vibe_export_gate(
    blocking_block_ids: list[str],
    dag_report: DagReport,
    registry: RegistryGateResult,
) -> ExportGateVerdict:
    violations: list[str] = []
    for block_id in blocking_block_ids:
        violations.append(f"review: blocking review open on block {block_id}")
    dag_findings = [
        *dag_report.errors,
        *(f"orphan terminal {t}" for t in dag_report.orphans),
        *(f"unreachable {t}" for t in dag_report.unreachable),
    ]
    for finding in dag_findings:
        violations.append(f"dag: {finding}")
    for violation in registry.violations:
        violations.append(f"registry: {violation}")
    return ExportGateVerdict(allowed=not violations, violations=violations)
