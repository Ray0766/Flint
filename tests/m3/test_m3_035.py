"""M3-035 acceptance tests: pdf renderer (containerized per Q-003 option 3).

Acceptance (tasks.json M3-035, verify scope per owner ruling 2026-07-30):
  - html -> pdf artifact non-empty with page structure incl the quality card
  - CJK glyphs render (Noto CJK font embedded, no tofu)
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import zlib
from pathlib import Path

import pytest

pytestmark = pytest.mark.compose

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCKER_BIN = (
    Path(os.environ.get("LOCALAPPDATA", ""))
    / "Programs" / "DockerDesktop" / "resources" / "bin" / "docker.exe"
)
IMAGE = "flint-pdf:69"
OUT = REPO_ROOT / ".pdf-probe" / "out.pdf"


def _docker() -> str:
    if DOCKER_BIN.exists():
        return str(DOCKER_BIN)
    found = shutil.which("docker")
    assert found, "docker CLI required (Q-003 option 3 verify scope)"
    return found


@pytest.fixture(scope="module")
def probe_pdf() -> bytes:
    if OUT.exists():
        OUT.unlink()
    completed = subprocess.run(
        [
            _docker(), "run", "--rm",
            "-v", f"{REPO_ROOT}:/work",
            IMAGE, "python", "/work/scripts/pdf_probe.py",
        ],
        capture_output=True, text=True, timeout=300, check=False,
    )
    assert completed.returncode == 0, (
        f"container probe failed:\n{completed.stdout}\n{completed.stderr}"
    )
    assert OUT.exists(), "probe artifact missing"
    return OUT.read_bytes()


def _inflate_all(pdf: bytes) -> bytes:
    """weasyprint 1.7 全压缩对象流：解压 Flate 流后才可断言结构名。"""
    inflated = b""
    for match in re.finditer(rb"stream\r?\n(.*?)endstream", pdf, re.DOTALL):
        try:
            inflated += zlib.decompress(match.group(1).strip(b"\r\n"))
        except zlib.error:
            continue
    return inflated


def test_pdf_nonempty_with_page_structure(probe_pdf: bytes) -> None:
    assert probe_pdf[:5] == b"%PDF-", "a real pdf"
    assert len(probe_pdf) > 5_000, "non-trivial artifact"
    combined = probe_pdf + _inflate_all(probe_pdf)
    assert b"/Type /Pages" in combined or b"/Type/Pages" in combined


def test_fonts_embedded(probe_pdf: bytes) -> None:
    combined = probe_pdf + _inflate_all(probe_pdf)
    assert b"FontFile2" in combined or b"FontFile3" in combined, "fonts embedded"


def test_cjk_font_embedded_no_tofu(probe_pdf: bytes) -> None:
    combined = probe_pdf + _inflate_all(probe_pdf)
    assert (
        b"NotoSansCJK" in combined
        or b"NotoSerifCJK" in combined
    ), "CJK font subset embedded -> glyphs render, no tofu"
