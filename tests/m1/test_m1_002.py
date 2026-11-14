"""M1-002 acceptance tests: Docker Compose dev environment.

Acceptance (tasks.json M1-002):
  - after compose up, CREATE EXTENSION vector succeeds in postgres
  - redis answers PING with PONG
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.compose

REPO_ROOT = Path(__file__).resolve().parents[2]

_FALLBACK_DOCKER = (
    Path.home() / "AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe"
)


def docker_exe() -> str:
    found = shutil.which("docker")
    if found:
        return found
    if _FALLBACK_DOCKER.is_file():
        return str(_FALLBACK_DOCKER)
    raise RuntimeError("docker CLI not found; compose environment cannot be verified")


def compose(*args: str, timeout: float = 600.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [docker_exe(), "compose", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


@pytest.fixture(scope="module")
def stack() -> None:
    """Bring the dev stack up once for this module; idempotent re-entry."""
    result = compose("up", "-d", "--wait", "postgres", "redis")
    assert result.returncode == 0, f"compose up failed:\n{result.stdout}\n{result.stderr}"


def test_compose_defines_expected_services() -> None:
    result = compose("config", "--services")
    assert result.returncode == 0, result.stderr
    services = set(result.stdout.split())
    assert {"postgres", "redis", "api", "worker"} <= services


def test_create_extension_vector_succeeds(stack: None) -> None:
    created = compose(
        "exec", "-T", "postgres",
        "psql", "-U", "flint", "-d", "flint",
        "-c", "CREATE EXTENSION IF NOT EXISTS vector;",
    )
    assert created.returncode == 0, created.stderr

    probe = compose(
        "exec", "-T", "postgres",
        "psql", "-U", "flint", "-d", "flint", "-tA",
        "-c", "SELECT extname FROM pg_extension WHERE extname = 'vector';",
    )
    assert probe.returncode == 0, probe.stderr
    assert probe.stdout.strip() == "vector"

    # the type actually works, not just registers
    vec = compose(
        "exec", "-T", "postgres",
        "psql", "-U", "flint", "-d", "flint", "-tA",
        "-c", "SELECT '[1,2,3]'::vector;",
    )
    assert vec.returncode == 0, vec.stderr
    assert vec.stdout.strip() == "[1,2,3]"


def test_redis_ping_pong(stack: None) -> None:
    result = compose("exec", "-T", "redis", "redis-cli", "PING")
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "PONG"
