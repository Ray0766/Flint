"""可观测性：structlog JSON 日志（M1-006，技术方案 E7）。

- 全量 JSON 输出；上下文经 contextvars 绑定 request_id / job_id / project_id / principal。
- 不变量：任何日志行都是合法 JSON，且始终携带 request_id / job_id 键
  （未绑定时值为 null），使采集侧无需条件解析。
- 指标端点与 OTel 不在本模块范围（E7：v1 不上 OTel，job_events 即业务 trace）。
"""
from __future__ import annotations

import io
from typing import Any, TextIO, cast

import structlog

_CORRELATION_KEYS = ("request_id", "job_id")


def _ensure_correlation_keys(
    _logger: structlog.typing.WrappedLogger,
    _method_name: str,
    event_dict: structlog.typing.EventDict,
) -> structlog.typing.EventDict:
    for key in _CORRELATION_KEYS:
        event_dict.setdefault(key, None)
    return event_dict


def configure_logging(stream: TextIO | io.StringIO | None = None) -> None:
    """Configure process-wide structlog JSON output. `stream` is injectable so
    tests can capture and parse emitted lines; None keeps stdout."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            _ensure_correlation_keys,
            structlog.processors.JSONRenderer(ensure_ascii=False),
        ],
        logger_factory=structlog.PrintLoggerFactory(file=stream),
        cache_logger_on_first_use=False,
    )


def get_logger(name: str) -> structlog.typing.FilteringBoundLogger:
    return cast(structlog.typing.FilteringBoundLogger, structlog.get_logger(name))


def bind_log_context(**values: Any) -> None:
    """Bind correlation fields (request_id / job_id / project_id / principal)
    onto the contextvars context shared by all loggers in this task."""
    structlog.contextvars.bind_contextvars(**values)


def clear_log_context() -> None:
    structlog.contextvars.clear_contextvars()
