"""M1-006 acceptance tests: structlog JSON logging (E7).

Acceptance (tasks.json M1-006):
  - every emitted log line is valid JSON carrying request_id / job_id
"""
from __future__ import annotations

import io
import json
from typing import Any

from flint.obs import bind_log_context, clear_log_context, configure_logging, get_logger


def emit_and_parse(buffer: io.StringIO) -> list[dict[str, Any]]:
    raw_lines = [ln for ln in buffer.getvalue().splitlines() if ln.strip()]
    parsed = [json.loads(ln) for ln in raw_lines]
    assert parsed, "no log lines captured"
    return parsed


def test_log_line_is_json_with_bound_ids() -> None:
    buf = io.StringIO()
    configure_logging(stream=buf)
    clear_log_context()
    bind_log_context(request_id="req-42", job_id="job-7", project_id="p-1")
    get_logger("flint.test").info("ingest_started", source="weibo")
    lines = emit_and_parse(buf)
    line = lines[-1]
    assert line["request_id"] == "req-42"
    assert line["job_id"] == "job-7"
    assert line["project_id"] == "p-1"
    assert line["event"] == "ingest_started"
    assert line["source"] == "weibo"


def test_unbound_context_still_carries_correlation_keys() -> None:
    """Acceptance says ANY log line carries request_id/job_id — including logs
    emitted before any binding happened (startup, background loops)."""
    buf = io.StringIO()
    configure_logging(stream=buf)
    clear_log_context()
    get_logger("flint.test").warning("startup_probe")
    line = emit_and_parse(buf)[-1]
    assert "request_id" in line
    assert "job_id" in line
    assert line["request_id"] is None
    assert line["job_id"] is None


def test_every_line_valid_json_across_levels() -> None:
    buf = io.StringIO()
    configure_logging(stream=buf)
    clear_log_context()
    bind_log_context(request_id="r", job_id="j")
    log = get_logger("flint.test")
    log.info("a")
    log.warning("b", extra_field=1)
    log.error("c", nested={"k": "v"})
    lines = emit_and_parse(buf)
    assert len(lines) == 3
    for line in lines:
        assert line["request_id"] == "r"
        assert line["job_id"] == "j"
        assert "timestamp" in line
        assert "level" in line


def test_clear_context_drops_previous_binding() -> None:
    buf = io.StringIO()
    configure_logging(stream=buf)
    clear_log_context()
    bind_log_context(request_id="stale", job_id="stale")
    clear_log_context()
    get_logger("flint.test").info("after_clear")
    line = emit_and_parse(buf)[-1]
    assert line["request_id"] is None
    assert line["job_id"] is None
