"""M1-001 acceptance tests: repo skeleton + frozen contracts in flint/domain.

Acceptance (tasks.json M1-001):
  - mypy --strict flint/domain zero errors  (enforced by verify_cmd stage 1)
  - ruff check whole repo passes            (enforced by verify_cmd stage 2)
This file guards the semantic core behind those gates: the frozen contract
files are copied verbatim into flint/domain (S2-1: contracts are the single
source of truth and are never modified), the package is importable, and the
S3 directory skeleton exists.
"""
from __future__ import annotations

import importlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = REPO_ROOT / "contracts"
DOMAIN = REPO_ROOT / "flint" / "domain"

# S3 directory tree: packages under flint/ and top-level dirs.
FLINT_PACKAGES = [
    "domain", "obs", "sources", "norm", "cluster", "lineage",
    "retrieval", "gate", "ledger", "compose", "jobs", "api",
]
FLINT_MODULES = ["config.py", "embed.py", "heat.py", "signals.py", "cards.py"]
TOP_DIRS = ["tests", "fixtures", "assets", "migrations", "prompts", "docs", "web"]


def test_models_frozen_verbatim() -> None:
    """flint/domain/models.py is a byte-identical copy of contracts/models.py."""
    src = (CONTRACTS / "models.py").read_bytes()
    dst = (DOMAIN / "models.py").read_bytes()
    assert src == dst, "flint/domain/models.py deviates from frozen contracts/models.py"


def test_protocols_frozen_except_package_import() -> None:
    """flint/domain/protocols.py matches contracts/protocols.py line-for-line,
    with exactly one permitted mechanical difference: the top-level
    'from models import (' becomes a package-relative 'from .models import ('.
    Everything else (types, signatures, docstrings) is verbatim frozen."""
    src_lines = (CONTRACTS / "protocols.py").read_text(encoding="utf-8").splitlines()
    dst_lines = (DOMAIN / "protocols.py").read_text(encoding="utf-8").splitlines()
    assert len(src_lines) == len(dst_lines), "line count differs from frozen contract"
    diffs = [
        (i, s, d) for i, (s, d) in enumerate(zip(src_lines, dst_lines)) if s != d
    ]
    assert len(diffs) == 1, f"expected exactly 1 differing line, got {len(diffs)}: {diffs}"
    _, src_line, dst_line = diffs[0]
    assert src_line == "from models import ("
    assert dst_line == "from .models import ("


def test_domain_models_importable() -> None:
    m = importlib.import_module("flint.domain.models")
    for symbol in [
        "Keyword", "Cluster", "HeatPoint", "EvidenceCard", "Origin", "Topic",
        "Doc", "Citation", "Claim", "Fact", "FactsLedger", "LedgerVersionConflict",
        "Block", "Deliverable", "VerdictResult", "Job", "JobEvent", "TaskSpec",
        "UserProfile", "PriceEntry", "QualityCard", "Project", "TrendItem",
    ]:
        assert hasattr(m, symbol), f"models.{symbol} missing"


def test_domain_protocols_importable() -> None:
    p = importlib.import_module("flint.domain.protocols")
    for symbol in [
        "TrendSource", "PaperSource", "QueryBuilder", "RelevanceJudge",
        "EvidenceScorer", "CitationAligner", "LLMProvider", "JobRunner",
        "JobEventStream", "Analyzer", "ReportComposer", "SpecExporter",
        "RegistryValidator", "DagValidator", "InterventionService",
        "Revalidator", "LedgerStore", "SnapshotStore", "Renderer",
    ]:
        assert hasattr(p, symbol), f"protocols.{symbol} missing"


def test_repo_skeleton_packages() -> None:
    for pkg in FLINT_PACKAGES:
        init = REPO_ROOT / "flint" / pkg / "__init__.py"
        assert init.is_file(), f"flint/{pkg}/__init__.py missing"
    for mod in FLINT_MODULES:
        assert (REPO_ROOT / "flint" / mod).is_file(), f"flint/{mod} missing"
    assert (REPO_ROOT / "flint" / "__init__.py").is_file()
    assert (REPO_ROOT / "flint" / "py.typed").is_file(), "py.typed marker missing"


def test_repo_skeleton_top_dirs() -> None:
    for d in TOP_DIRS:
        assert (REPO_ROOT / d).is_dir(), f"top-level dir {d}/ missing"


def test_toolchain_config_present() -> None:
    """pyproject.toml pins the toolchain contract: mypy strict + 3.11 semantics."""
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'python_version = "3.11"' in pyproject
    assert "strict = true" in pyproject
