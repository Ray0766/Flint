"""通用归档保护（H-3）：防同名覆盖丢证据。

所有 trail/产出写入共用此函数——写前若目标已存在且内容不同，先把旧内容备份
到非撞名的 `.bak-N`（N 递增，永不覆盖已有备份），再写新内容；内容相同则幂等
写、不备份。这是通用机制（非单次换目录绕过）：任何后续对已存在证据文件的
覆写都会先自动留档旧证据。
"""
from __future__ import annotations

from pathlib import Path


def archive_write(
    path: Path, text: str, *, encoding: str = "utf-8"
) -> Path | None:
    """写 text 到 path，防同名覆盖丢证据。

    - path 不存在 → 直接写，返回 None；
    - path 存在且内容相同 → 幂等写（内容不变），返回 None；
    - path 存在且内容不同 → 先把旧内容备份到首个未占用的 `{path}.bak-N`
      （N 从 1 递增，永不覆盖已有备份），再写新内容，返回备份路径。
    """
    backup: Path | None = None
    new_bytes = text.encode(encoding)
    if path.exists():
        old_bytes = path.read_bytes()
        if old_bytes != new_bytes:
            n = 1
            while True:
                candidate = path.with_name(f"{path.name}.bak-{n}")
                if not candidate.exists():
                    break
                n += 1
            candidate.write_bytes(old_bytes)
            backup = candidate
    path.write_text(text, encoding=encoding)
    return backup
