"""包完整性评测（M4-031，技术方案 E3）。

- 四面：三件齐（E3 布局）/ contracts hash 清单核对（逐文件 sha256 重算
  对 MANIFEST）/ tasks.json 与 CLAUDE.md S5 表同源（id 集互证）/
  包内 CLAUDE.md 过 S2-8 自检（banned_word_hits 零命中）。
- 输入是 zip 字节（出件后验收面，不信任构建路径）。
"""
from __future__ import annotations

import hashlib
import io
import json
import zipfile
from dataclasses import dataclass

from flint.compose.vibe_core import banned_word_hits

REQUIRED_NAMES = frozenset({
    "CLAUDE.md", "tasks.json", "HUMAN_DIGEST.md",
    "contracts/models.py", "contracts/protocols.py",
    "contracts/README.md", "contracts/MANIFEST.sha256",
})


@dataclass(frozen=True)
class PackIntegrityRow:
    name: str
    ok: bool
    detail: str


@dataclass(frozen=True)
class PackIntegrityReport:
    rows: list[PackIntegrityRow]
    all_ok: bool


def run_pack_integrity_eval(zip_bytes: bytes) -> PackIntegrityReport:
    rows: list[PackIntegrityRow] = []
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        names = set(archive.namelist())
        missing = REQUIRED_NAMES - names
        rows.append(PackIntegrityRow(
            name="three-pieces",
            ok=not missing,
            detail=f"missing={sorted(missing)}" if missing else "complete",
        ))

        manifest_ok = True
        manifest_detail = "all hashes match"
        try:
            manifest_lines = (
                archive.read("contracts/MANIFEST.sha256")
                .decode("utf-8").strip().splitlines()
            )
            for line in manifest_lines:
                digest, _, filename = line.partition("  ")
                body = archive.read(f"contracts/{filename}")
                if hashlib.sha256(body).hexdigest() != digest:
                    manifest_ok = False
                    manifest_detail = f"hash mismatch: {filename}"
                    break
        except KeyError as err:
            manifest_ok = False
            manifest_detail = f"missing member: {err}"
        rows.append(PackIntegrityRow(
            name="contracts-hash", ok=manifest_ok, detail=manifest_detail,
        ))

        claude_md = archive.read("CLAUDE.md").decode("utf-8")
        source_ok = True
        source_detail = "table ids == payload ids"
        try:
            data = json.loads(archive.read("tasks.json").decode("utf-8"))
            payload_ids = [str(t["task_id"]) for t in data["tasks"]]
            # 同源校验对象是 S5 章的表——S6/S7 表同样携任务行，只截
            # S5 章区间（章头到下一章头）
            s5_start = claude_md.find("## S5 ")
            s5_end = claude_md.find("\n## ", s5_start + 1)
            s5_body = claude_md[s5_start:s5_end if s5_end != -1 else None]
            table_ids = [
                line.split("|")[1].strip()
                for line in s5_body.splitlines()
                if line.startswith("| ")
                and not line.startswith("| task_id")
                and any(
                    line.split("|")[1].strip() == pid for pid in payload_ids
                )
            ]
            if table_ids != payload_ids:
                source_ok = False
                source_detail = (
                    f"diverged: table={table_ids} payload={payload_ids}"
                )
            if "dag_report" not in data:
                source_ok = False
                source_detail = "dag_report missing"
        except (KeyError, json.JSONDecodeError) as err:
            source_ok = False
            source_detail = f"tasks.json unreadable: {err}"
        rows.append(PackIntegrityRow(
            name="single-source", ok=source_ok, detail=source_detail,
        ))

        hits = banned_word_hits(claude_md)
        rows.append(PackIntegrityRow(
            name="s2-8",
            ok=not hits,
            detail=f"hits={hits}" if hits else "zero hits",
        ))

    return PackIntegrityReport(rows=rows, all_ok=all(r.ok for r in rows))
