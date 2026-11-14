"""M4-009 acceptance tests: contracts read-only copy.

Acceptance (tasks.json M4-009):
  - pack contracts/ copy byte-identical with source + read-only marking
  - tamper detection via hash manifest
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from flint.spec.contracts_copy import (
    ContractsCopy,
    ContractsCopyError,
    build_contracts_copy,
    render_manifest,
    verify_copy,
)

pytestmark = pytest.mark.compose

CONTRACTS = Path(__file__).resolve().parents[2] / "contracts"


def test_copy_byte_identical_with_source() -> None:
    copy = build_contracts_copy(CONTRACTS)
    assert set(copy.files) == {"models.py", "protocols.py"}
    for name, body in copy.files.items():
        assert body == (CONTRACTS / name).read_bytes(), f"{name} not byte-identical"
    assert "NEVER 修改" in copy.readme and "只读" in copy.readme


def test_manifest_is_sha256_and_verifies_clean() -> None:
    copy = build_contracts_copy(CONTRACTS)
    for name, digest in copy.manifest.items():
        assert digest == hashlib.sha256(copy.files[name]).hexdigest()
    assert verify_copy(copy) == []
    manifest_text = render_manifest(copy)
    assert "models.py" in manifest_text and "protocols.py" in manifest_text


def test_tampered_content_detected() -> None:
    copy = build_contracts_copy(CONTRACTS)
    tampered = ContractsCopy(
        files={**copy.files, "models.py": copy.files["models.py"] + b"# x"},
        manifest=copy.manifest,
        readme=copy.readme,
    )
    problems = verify_copy(tampered)
    assert problems == ["models.py: content drifted from manifest hash"]


def test_missing_and_extra_files_detected() -> None:
    copy = build_contracts_copy(CONTRACTS)
    missing = ContractsCopy(
        files={"protocols.py": copy.files["protocols.py"]},
        manifest=copy.manifest, readme=copy.readme,
    )
    assert any("file missing" in p for p in verify_copy(missing))
    extra = ContractsCopy(
        files={**copy.files, "rogue.py": b"x"},
        manifest=copy.manifest, readme=copy.readme,
    )
    assert any("not in manifest" in p for p in verify_copy(extra))


def test_missing_source_rejected(tmp_path: Path) -> None:
    with pytest.raises(ContractsCopyError, match="models.py"):
        build_contracts_copy(tmp_path)
