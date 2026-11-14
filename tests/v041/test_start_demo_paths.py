"""FIX-07：一键启动脚本的 Docker 路径写死，本机走不通。

## 现象

`start-demo.ps1` 把 Docker Desktop 写死成

    C:\\Program Files\\Docker\\Docker\\Docker Desktop.exe

而本机是**用户级安装**（`%LOCALAPPDATA%\\Programs\\DockerDesktop\\`）。
于是 `Test-Path` 恒 false → 脚本掉进 `Read-Host` 等人敲回车，
**无人值守时那就是挂住**——而挂住在屏上与「Docker 起得慢」长得一模一样，
没人知道该去敲那个回车。

## 修法

1. **候选路径逐个探测**：至少覆盖 `Program Files` 与 `LOCALAPPDATA` 两处；
2. **从 `docker` CLI 的实际位置反推**——这一条最准：CLI 能找到就说明装过；
3. 全都找不到 → **明说找不到并给手动步骤**，NEVER 用 `Read-Host` 卡住。

## 判据是静态检查

起一次 Docker 要几分钟，且它在 CI 里根本不在（S2-7）。
所以这份验收判的是**脚本文本**：不含写死的绝对安装路径、候选清单覆盖两处、
且那条等待分支不再挂人。
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "start-demo.ps1"


def _source() -> str:
    return SCRIPT.read_text(encoding="utf-8-sig")


def _code_only() -> str:
    """剥掉注释再判。

    本文件的注释里逐字写着那条被修掉的写死路径（说明为什么不能那样写）——
    不剥的话，判据会把**解释问题的那句话**当成问题本身。
    这一形状本仓栽过多次（`docs/blocked/SCANNERS-DO-NOT-STRIP-COMMENTS.md`）。
    """
    return "\n".join(
        line for line in _source().splitlines() if not line.lstrip().startswith("#")
    )


# ───────────────────────── 一、不含写死的绝对安装路径


def test_no_hardcoded_install_path() -> None:
    code = _code_only()

    assert not re.search(r'"[A-Za-z]:\\\\?Program Files', code), (
        "脚本里还写死着一条绝对安装路径"
    )
    assert "Docker\\Docker\\Docker Desktop.exe" not in code or "$env:" in code


def test_the_candidates_cover_both_install_locations() -> None:
    """卡面 acceptance③：候选清单**至少覆盖 Program Files 与 LOCALAPPDATA 两处**。

    只覆盖一处的话，另一种装法的机器上脚本照样走不通——
    而它失败的样子仍然是「找不到」，看不出是候选清单漏了。
    """
    code = _code_only()

    assert "$env:LOCALAPPDATA" in code, "候选里没有用户级安装那一处"
    assert "$env:ProgramFiles" in code, "候选里没有 Program Files 那一处"


def test_the_cli_location_is_used_to_infer_the_desktop_app() -> None:
    """从 `docker` CLI 的实际位置反推——**这一条最准**：CLI 能找到就说明装过。"""
    code = _code_only()

    assert "Get-Command docker" in code, "没有从 CLI 反推"
    assert "Split-Path" in code


# ───────────────────────── 二、找不到时明说，NEVER 卡住


def test_the_wait_branch_never_blocks_on_read_host() -> None:
    """`Read-Host` 在无人值守时就是挂住。

    挂住与「Docker 起得慢」在屏上长得一模一样——**没人知道该去敲那个回车**。
    """
    code = _code_only()
    block = code[code.index("Docker 引擎未就绪"):code.index("Docker 引擎就绪")]

    assert "Read-Host" not in block, "Docker 那段还会停下来等人敲回车"


def test_it_says_what_to_do_by_hand() -> None:
    """找不到时**给手动步骤**——只说「找不到」等于把人留在原地。"""
    code = _code_only()

    assert "手动" in code
    assert "docker info" in code, "手动步骤里没给可执行的那一条"


def test_it_still_fails_loudly_when_docker_is_absent() -> None:
    """不卡住 ≠ 装作成功。等不到引擎就**照实失败**。"""
    code = _code_only()

    assert re.search(r"throw\s+\"Docker 引擎不可用", code), "等不到引擎却没有失败"


# ───────────────────────── 三、别处的 Read-Host 不在本卡范围内（说清楚）


def test_the_remaining_read_hosts_are_the_ollama_ones() -> None:
    """脚本里还有 `Read-Host`，但它们在 **Ollama** 那一段。

    本卡只治 Docker 那一处（卡面写的就是它）。**把剩下的也列出来**——
    「改完了」与「只改了一半」NEVER 长得一样。
    Ollama 那两处要不要一起改，留给 owner：它们问的是「要不要现在拉模型」，
    那是**真的需要人回答**的问题，与 Docker 那条「等它起来」不同。
    """
    lines = [
        line.strip() for line in _source().splitlines()
        if "Read-Host" in line and not line.lstrip().startswith("#")
    ]

    assert lines, "一处 Read-Host 都没有了——那就来这里删掉这条判据"
    for line in lines:
        assert "Ollama" in line or "ollama" in line, (
            f"这一处 Read-Host 不在 Ollama 段里，本卡漏了它：{line}"
        )


# ───────────────────────── 四、脚本本身仍然是可解析的 PowerShell


def test_the_script_still_parses() -> None:
    """改完之后它得还能跑。**语法错的脚本与「Docker 没装」在屏上也长得一样。**"""
    import shutil
    import subprocess

    import pytest

    powershell = shutil.which("powershell")
    if powershell is None:
        pytest.skip("本机没有 powershell")

    # `[ref]$errors` 要求那个变量**先存在**——不先声明的话，
    # PowerShell 报的是 `NonExistingVariableReference`，
    # 而那句话说的是**这条检查命令自己写错了**，不是脚本有语法错。
    # 两者混起来会让人去改一个没病的脚本。
    # 拼成一条再传：在 list 字面量里靠相邻字符串隐式拼接会被 ruff 判 ISC004
    # ——它挡的是「本想写两个参数，少打了一个逗号」那种，**它挡得对**。
    command = (
        "$errs = $null; "
        "$null = [System.Management.Automation.Language.Parser]::ParseFile("
        f"'{SCRIPT}', [ref]$null, [ref]$errs); "
        "if ($errs -and $errs.Count) { $errs | ForEach-Object { $_.Message }; exit 1 }"
    )
    done = subprocess.run(
        [powershell, "-NoProfile", "-Command", command],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )

    assert done.returncode == 0, done.stdout + done.stderr
