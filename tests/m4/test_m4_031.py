"""M4-031 acceptance tests: pack integrity eval.

Acceptance (tasks.json M4-031):
  - zip three pieces present + contracts hash manifest passes + tasks.json
    and S5 single-source check
  - pack CLAUDE.md passes the S2-8 self-check
"""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from eval.pack_integrity import run_pack_integrity_eval
from flint.domain.models import TaskSpec
from flint.spec.contracts_copy import build_contracts_copy
from flint.spec.pack_zip import PackBundle, build_zip
from flint.spec.tasks_json import export_tasks_json
from flint.spec.vibe_s5 import build_s5

pytestmark = pytest.mark.compose

CONTRACTS = Path(__file__).resolve().parents[2] / "contracts"


def bundle(claude_prefix: str = "## S1 Charter\n\n目标一\n\n") -> PackBundle:
    tasks = [TaskSpec(
        task_id="T-1", title="任务一", inputs=["repo-skeleton"],
        outputs=["mod.T-1"], acceptance=["验收一"], depends_on=[],
        milestone="M1", estimate_days=None, estimate_cycles=1.0,
        oneshot=True, verify_cmd="pytest tests/test_T-1.py -q",
        context_refs=["contracts/models.py#TaskSpec"], review_gate=False,
    )]
    chapter = build_s5(tasks)
    return PackBundle(
        claude_md=claude_prefix + chapter.markdown,
        human_digest="监工视图。",
        tasks_json=export_tasks_json(chapter),
        contracts=build_contracts_copy(CONTRACTS),
    )


def tamper(zip_bytes: bytes, name: str, new_body: bytes) -> bytes:
    buffer = io.BytesIO()
    with (
        zipfile.ZipFile(io.BytesIO(zip_bytes)) as src,
        zipfile.ZipFile(buffer, "w") as dst,
    ):
        for info in src.namelist():
            body = new_body if info == name else src.read(info)
            dst.writestr(info, body)
    return buffer.getvalue()


def test_clean_pack_all_four_faces_green() -> None:
    report = run_pack_integrity_eval(build_zip(bundle()))
    assert [r.name for r in report.rows] == [
        "three-pieces", "contracts-hash", "single-source", "s2-8",
    ]
    assert report.all_ok, [r for r in report.rows if not r.ok]


def test_tampered_contract_caught_post_build() -> None:
    tampered = tamper(
        build_zip(bundle()), "contracts/models.py", b"# tampered"
    )
    report = run_pack_integrity_eval(tampered)
    row = next(r for r in report.rows if r.name == "contracts-hash")
    assert row.ok is False and "models.py" in row.detail
    assert report.all_ok is False


def test_source_divergence_caught() -> None:
    payload = build_zip(bundle())
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        claude_md = archive.read("CLAUDE.md").decode("utf-8")
    edited = claude_md.replace("| T-1 |", "| T-9 |")
    report = run_pack_integrity_eval(
        tamper(payload, "CLAUDE.md", edited.encode("utf-8"))
    )
    row = next(r for r in report.rows if r.name == "single-source")
    assert row.ok is False


def test_banned_word_in_pack_caught() -> None:
    dirty = tamper(
        build_zip(bundle()), "HUMAN_DIGEST.md", b"x"
    )
    with zipfile.ZipFile(io.BytesIO(dirty)) as archive:
        claude_md = archive.read("CLAUDE.md").decode("utf-8")
    poisoned = tamper(
        dirty, "CLAUDE.md",
        (claude_md + "\n阈值取合理值。\n").encode("utf-8"),
    )
    report = run_pack_integrity_eval(poisoned)
    row = next(r for r in report.rows if r.name == "s2-8")
    assert row.ok is False and "合理" in row.detail
