"""H-3 通用归档保护：写前若目标已存在且内容不同，先把旧内容备份到非撞名的
.bak-N（永不覆盖已有备份），再写新内容——**防同名覆盖丢证据**（不是单次换
目录绕过，是所有 trail 写入共用的通用机制）。内容相同则幂等写、不备份。
"""
from __future__ import annotations

from pathlib import Path

from flint.testing.archive import archive_write


def test_backs_up_on_content_change(tmp_path: Path) -> None:
    p = tmp_path / "trail.json"
    p.write_text("v1", encoding="utf-8")
    backup = archive_write(p, "v2")
    assert p.read_text(encoding="utf-8") == "v2"
    assert backup is not None
    assert backup.read_text(encoding="utf-8") == "v1"  # 旧证据保住


def test_second_change_does_not_clobber_first_backup(tmp_path: Path) -> None:
    p = tmp_path / "trail.json"
    p.write_text("v1", encoding="utf-8")
    b1 = archive_write(p, "v2")
    b2 = archive_write(p, "v3")
    assert b1 is not None and b2 is not None and b1 != b2
    # 两份旧证据都在，前一个备份未被覆盖
    assert b1.read_text(encoding="utf-8") == "v1"
    assert b2.read_text(encoding="utf-8") == "v2"
    assert p.read_text(encoding="utf-8") == "v3"


def test_idempotent_same_content_no_backup(tmp_path: Path) -> None:
    p = tmp_path / "t.json"
    p.write_text("same", encoding="utf-8")
    backup = archive_write(p, "same")
    assert backup is None  # 内容相同不备份
    assert p.read_text(encoding="utf-8") == "same"


def test_new_file_no_backup(tmp_path: Path) -> None:
    p = tmp_path / "new.json"
    backup = archive_write(p, "content")
    assert backup is None
    assert p.read_text(encoding="utf-8") == "content"
