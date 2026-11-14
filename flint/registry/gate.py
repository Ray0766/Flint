"""registry 不可用 → 整包禁导出（M4-016，技术方案 E6 行）。

- ai_executor：available=False → S3 章 GapHint + 禁导出违规（质量门
  registry=100% **不可降级**——不可用时 NEVER 出包）；missing 包同为
  禁导出违规（替换流程 M4-014 解决后方可放行），但不产不可用 GapHint。
- human_reader：registry 门不适用（人类模板无锁版清单），恒放行
  ——受众分叉断言。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from flint.domain.models import GapHint
from flint.registry.batch import BatchReport


@dataclass(frozen=True)
class RegistryGateResult:
    violations: list[str]
    gap: GapHint | None


def registry_pack_gate(
    report: BatchReport,
    audience: Literal["human_reader", "ai_executor"],
) -> RegistryGateResult:
    if audience == "human_reader":
        return RegistryGateResult(violations=[], gap=None)
    violations: list[str] = []
    gap: GapHint | None = None
    if not report.available:
        down = [i.package for i in report.items if i.state == "unavailable"]
        violations.append(
            f"registry: validation unavailable for {down} — pack export "
            "banned (quality gate registry=100%, no degradation)"
        )
        gap = GapHint(
            missing_what=(
                f"S3 锁版清单未完成校验：registry 通道对 {down} 不可用"
                "（不可用 ≠ 不存在，不走替换）"
            ),
            cause="missing_data",
            suggested_sources=[
                "重跑 registry 批校验（通道恢复后）",
                "检查网络/镜像源配置",
            ],
            action="search",
        )
    for package in report.missing:
        violations.append(
            f"registry: {package} does not exist — resolve via replacement "
            "(M4-014) before export"
        )
    return RegistryGateResult(violations=violations, gap=gap)
