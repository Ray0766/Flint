"""contracts 只读副本打包（M4-009，技术方案 E3）。

- 副本 = 源 contracts/ 逐字节读取（不重排不转码）；hash 清单 sha256；
  README 携只读标注（S2-1 措辞：唯一真相 / NEVER 修改）。
- verify_copy = 篡改检测：重算 hash 对照清单，缺文件/多文件/内容漂移
  逐项指认。
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

COPY_FILES = ("models.py", "protocols.py")

README = (
    "# contracts/ 只读副本\n\n"
    "本目录是冻结件唯一真相的打包副本：NEVER 修改；实现 MUST 与其类型"
    "逐字一致；类型不够用 → 停止实现，按 S9 写问题单。\n"
    "完整性以 MANIFEST.sha256 为准（逐文件 sha256）。\n"
)


class ContractsCopyError(Exception):
    pass


@dataclass(frozen=True)
class ContractsCopy:
    files: dict[str, bytes]
    manifest: dict[str, str]
    readme: str


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def build_contracts_copy(source_dir: Path) -> ContractsCopy:
    files: dict[str, bytes] = {}
    for name in COPY_FILES:
        path = source_dir / name
        if not path.is_file():
            raise ContractsCopyError(f"frozen source missing: {path}")
        files[name] = path.read_bytes()
    return ContractsCopy(
        files=files,
        manifest={name: _sha256(body) for name, body in files.items()},
        readme=README,
    )


def verify_copy(copy: ContractsCopy) -> list[str]:
    problems: list[str] = []
    for name in copy.manifest:
        if name not in copy.files:
            problems.append(f"{name}: listed in manifest but file missing")
    for name, body in copy.files.items():
        expected = copy.manifest.get(name)
        if expected is None:
            problems.append(f"{name}: file present but not in manifest")
        elif _sha256(body) != expected:
            problems.append(f"{name}: content drifted from manifest hash")
    return problems


def render_manifest(copy: ContractsCopy) -> str:
    lines = [f"{digest}  {name}" for name, digest in sorted(copy.manifest.items())]
    return "\n".join(lines) + "\n"
