"""M2-041 acceptance tests: boundary schemas and error body.

Acceptance (tasks.json M2-041):
  - pydantic at the boundary only (domain layer stays pure dataclass,
    zero-pollution asserted over the whole flint package)
  - error body {code, message, detail} with machine-readable code enum (E3)
"""
from __future__ import annotations

import dataclasses
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import BaseModel, ValidationError

from flint.api.schemas import ERROR_CODES, ErrorBody, JobView
from flint.domain.models import Doc, Job, Principal

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_error_codes_are_machine_readable_enum() -> None:
    for named in ("LEDGER_CONFLICT", "EXPORT_BLOCKED", "PERMISSION_DENIED",
                  "BUDGET_EXCEEDED"):
        assert named in ERROR_CODES, f"E3-named code {named} must exist"
    for code in ERROR_CODES:
        assert code == code.upper() and " " not in code, "UPPER_SNAKE machine codes"


def test_error_body_shape_with_optional_detail() -> None:
    plain = ErrorBody(code="PERMISSION_DENIED", message="cancel denied")
    assert plain.model_dump(exclude_none=True) == {
        "code": "PERMISSION_DENIED", "message": "cancel denied",
    }
    rich = ErrorBody(
        code="BUDGET_EXCEEDED", message="over budget",
        detail={"budget": 10.0, "cost_accum": 12.5},
    )
    dumped = rich.model_dump()
    assert dumped["detail"] == {"budget": 10.0, "cost_accum": 12.5}


def test_unknown_error_code_rejected() -> None:
    with pytest.raises(ValidationError):
        ErrorBody(code="SOMETHING_ELSE", message="x")  # type: ignore[arg-type]


def test_job_view_from_domain_roundtrip() -> None:
    job = Job(
        job_id="job-1", kind="gate1_analysis", project_id="p-1",
        owner_scope=Principal(kind="user", id="u-1"), state="judging",
        steps=[], progress=0.5, partial_output_ref="snap-x", budget=10.0,
        cost_accum=1.5, cancel_requested=False, error=None, initiated_by="u-1",
        created_at=datetime(2026, 7, 28, tzinfo=UTC),
        updated_at=datetime(2026, 7, 28, 1, tzinfo=UTC),
    )
    view = JobView.from_domain(job)
    dumped = view.model_dump()
    assert dumped["job_id"] == "job-1"
    assert dumped["state"] == "judging"
    assert dumped["partial_output_ref"] == "snap-x"
    assert dumped["progress"] == 0.5
    assert "owner_scope" not in dumped, "principal internals stay behind the boundary"


def test_pydantic_imports_confined_to_api_package() -> None:
    """S3/E1: pydantic 仅边界——全包扫描，域层与业务层零 pydantic。"""
    offenders = []
    for path in (REPO_ROOT / "flint").rglob("*.py"):
        if "pydantic" in path.read_text(encoding="utf-8"):
            relative = path.relative_to(REPO_ROOT / "flint")
            if relative.parts[0] != "api":
                offenders.append(str(relative))
    assert offenders == [], f"pydantic leaked outside flint/api: {offenders}"


def test_domain_types_stay_plain_dataclasses() -> None:
    for cls in (Doc, Job):
        assert dataclasses.is_dataclass(cls)
        assert not issubclass(cls, BaseModel), "domain must never subclass pydantic"
