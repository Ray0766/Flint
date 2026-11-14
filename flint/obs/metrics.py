"""进程内指标注册表（M1-040，技术方案 E7 四指标计数器）。

- 计数器：inc(name, labels, value)；时长观测 observe() 同步维护
  {name}_count / {name}_sum 两个衍生键（Prometheus 语义的最小面）。
- /metrics 导出端点归 api 层（M2）；本模块提供注册表与快照，
  演练断言（M1-040）与夜间评测直接读快照。
"""
from __future__ import annotations

from typing import Final

LabelSet = tuple[tuple[str, str], ...]
MetricKey = tuple[str, LabelSet]

REQUIRED_INGEST_METRICS: Final[list[str]] = [
    "ingest_success_total",
    "degraded_sources_total",
    "job_duration_seconds",
    "llm_cost_cny_total",
]

_registry: dict[MetricKey, float] = {}


def _key(name: str, labels: dict[str, str] | None) -> MetricKey:
    label_set: LabelSet = tuple(sorted((labels or {}).items()))
    return (name, label_set)


def inc(name: str, labels: dict[str, str] | None = None, value: float = 1.0) -> None:
    key = _key(name, labels)
    _registry[key] = _registry.get(key, 0.0) + value


def observe(name: str, labels: dict[str, str] | None = None, value: float = 0.0) -> None:
    """Duration/size observation: maintains {name}, {name}_count, {name}_sum."""
    base = _key(name, labels)
    _registry.setdefault(base, 0.0)
    inc(f"{name}_count", labels, 1.0)
    inc(f"{name}_sum", labels, value)


def get_value(name: str, labels: dict[str, str] | None = None) -> float:
    return _registry.get(_key(name, labels), 0.0)


def registry_snapshot() -> dict[MetricKey, float]:
    return dict(_registry)


def reset_metrics() -> None:
    _registry.clear()
