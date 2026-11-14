"""证据源降级（M2-050，技术方案 E6 行 2）。

- 单证据源不可用 → 换备源（同维度 fetcher 列表按序尝试，首个成功即用）；
- 维度全灭 → DimensionOutage：该维度覆盖不达标（映射为「计划 query 未全
  执行」的 CoverageResult），按 §2.2 C 档必要条件落 D，并产出报告盲区声明
  （质量卡 blind_spots 进账面，M2-048 消费）。
- 捕获面 = 源层三异常族（限频/取数失败/结构漂移）；其余异常原样上抛
  （不吞编程错误）。
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from flint.competitor.coverage import CoverageResult
from flint.domain.models import Doc
from flint.sources.errors import ParseDrift, RateLimitedError, SourceFetchError

DimensionFetcher = Callable[[], list[Doc]]


@dataclass(frozen=True)
class DimensionOutage:
    dimension: str
    attempted_sources: list[str]
    blind_spot: str


@dataclass
class FallbackResult:
    docs: list[Doc] = field(default_factory=list)
    used_source: str | None = None
    failed_sources: list[str] = field(default_factory=list)
    outage: DimensionOutage | None = None


def fetch_dimension_with_fallback(
    dimension: str, fetchers: list[tuple[str, DimensionFetcher]]
) -> FallbackResult:
    result = FallbackResult()
    for source_id, fetch in fetchers:
        try:
            result.docs = fetch()
        except (RateLimitedError, SourceFetchError, ParseDrift):
            result.failed_sources.append(source_id)
            continue
        result.used_source = source_id
        return result
    attempted = list(result.failed_sources)
    result.outage = DimensionOutage(
        dimension=dimension,
        attempted_sources=attempted,
        blind_spot=(
            f"盲区：{dimension} 维度证据源全部不可用"
            f"（已尝试 {'、'.join(attempted)}），该维度覆盖不达标"
        ),
    )
    return result


def outage_coverage(outage: DimensionOutage) -> CoverageResult:
    """维度停摆 → 覆盖不达标（计划 query 无法全执行的口径，M2-036 消费）。"""
    return CoverageResult(
        covered=False,
        reason="queries_pending",
        pending_queries=[
            f"{outage.dimension}:{source}" for source in outage.attempted_sources
        ],
    )
