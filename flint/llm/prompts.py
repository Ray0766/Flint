"""prompt 版本库（M2-004，技术方案 E5：文件即版本 + 内容 hash）。

- 命名：prompts/{name}@{n}.md；prompt_version = "{name}@{n}#{sha256 前 12 位}"，
  写入 GenerationRecord.prompt_version。
- 不可变约定：改 prompt = 新文件（{name}@{n+1}.md），旧版永存；
  prompts/prompts.lock.json 记录全部文件 hash——就地改动或未登记新文件
  经 verify_lock 检出（CI 守门），enforce_lock 加载路径直接拒绝。
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

LOCK_FILE = "prompts.lock.json"


class PromptDriftError(Exception):
    def __init__(self, name: str) -> None:
        super().__init__(
            f"prompt {name!r} drifted from prompts.lock.json — "
            "in-place edits are forbidden; add a new @n+1 file instead"
        )


@dataclass(frozen=True)
class PromptVersion:
    name: str
    text: str
    version: str  # "{name}#{hash12}"


def _hash12(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def _read_lock(directory: Path) -> dict[str, str]:
    lock_path = directory / LOCK_FILE
    if not lock_path.exists():
        return {}
    data: dict[str, str] = json.loads(lock_path.read_text(encoding="utf-8"))
    return data


def update_lock(directory: Path) -> dict[str, str]:
    lock = {
        p.stem: _hash12(p.read_text(encoding="utf-8"))
        for p in sorted(directory.glob("*.md"))
    }
    (directory / LOCK_FILE).write_text(
        json.dumps(lock, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return lock


def verify_lock(directory: Path) -> list[str]:
    """Returns drifted prompt names: hash mismatch OR file missing from lock
    OR lock entry without file. Empty list = clean."""
    lock = _read_lock(directory)
    current = {
        p.stem: _hash12(p.read_text(encoding="utf-8"))
        for p in sorted(directory.glob("*.md"))
    }
    drifted = [name for name, digest in current.items() if lock.get(name) != digest]
    drifted += [name for name in lock if name not in current]
    return sorted(set(drifted))


def load_prompt(directory: Path, name: str, enforce_lock: bool = False) -> PromptVersion:
    path = directory / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"prompt file missing: {path}")
    text = path.read_text(encoding="utf-8")
    digest = _hash12(text)
    if enforce_lock:
        lock = _read_lock(directory)
        if lock.get(name) != digest:
            raise PromptDriftError(name)
    return PromptVersion(name=name, text=text, version=f"{name}#{digest}")
