"""MAC-01：`start-demo.sh` / `stop-demo.sh` —— `start-demo.ps1` 的 POSIX 对应物。

## 为什么要有这两个脚本

开发机从 Windows 换到 macOS（owner 2026-11-14）。`start-demo.ps1` 整份是 PowerShell：
开新窗口用 `Start-Process powershell`，查重用 `Win32_Process`，这两样在 macOS 上都没有。

## 判据是静态检查

本卡在 Windows 主机上写成，**macOS 实机一次都没跑过**。所以这份验收判的是脚本文本
（外加 `bash -n` 语法检查）——它能挡住的是「换平台时最容易错的那几样」：

1. CRLF 行尾（`#!/usr/bin/env bash\\r` 在 macOS 上报的是 `bad interpreter`，
   屏上看不出是行尾的事）；
2. 只有 bash 4 才有的语法（macOS 自带的是 bash 3.2）；
3. 与 ps1 **环境变量名对不上**（先例：少设 `FLINT_API_BASE` → 报告路由恒 500）；
4. 起脚本与停脚本用了不同的进程标记（起得来、关不掉）；
5. 停下来问人（无人值守时那就是挂住）。

**它挡不住的**：脚本在真机上跑起来之后的任何行为。那一步要在 macOS 上实跑才算数。

## 模型端点这一条为什么单列

owner 2026-11-14 裁决：本地模型那条路先不做。于是 POSIX 脚本 NEVER 探测、
NEVER 拉取本地模型，模型端点只从环境透传——脚本里出现端口 11434 或模型名，
就说明有人把 ps1 的那一段照抄过来了。
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
START = REPO / "start-demo.sh"
STOP = REPO / "stop-demo.sh"
PS1 = REPO / "start-demo.ps1"
SETUP_DOC = REPO / "docs" / "macOS-安装.md"
README = REPO / "README.md"

BOTH = pytest.mark.parametrize("script", [START, STOP], ids=["start", "stop"])

#: 模型端点的两个变量：ps1 里写死成本机 Ollama，POSIX 脚本里只许透传。
MODEL_VARS = frozenset({"FLINT_LOCAL_BASE_URL", "FLINT_FREE_TIER_MODEL"})


def _code(path: Path) -> str:
    """剥掉注释行再判——注释里会逐字写着「不能那样写」的那种写法。"""
    return "\n".join(
        line for line in path.read_text(encoding="utf-8").splitlines()
        if not line.lstrip().startswith("#")
    )


# ───────────────────────── 一、文件本身在 macOS 上能被执行


@BOTH
def test_bash_shebang(script: Path) -> None:
    first = script.read_text(encoding="utf-8").splitlines()[0]

    assert first == "#!/usr/bin/env bash", f"{script.name} 首行不是 bash shebang：{first!r}"


@BOTH
def test_lf_only(script: Path) -> None:
    """本仓 CRLF 与 LF 混用（`.gitattributes` 关掉了换行转换），这两个脚本 MUST 是 LF。"""
    assert b"\r" not in script.read_bytes(), f"{script.name} 里有 CR：macOS 上会 bad interpreter"


@BOTH
def test_parses(script: Path) -> None:
    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("本机没有 bash")
    probe = subprocess.run([bash, "--version"], capture_output=True, check=False)
    if probe.returncode != 0:
        pytest.skip("PATH 里的 bash 起不来（Windows 上可能是没装发行版的 WSL 启动器）")

    done = subprocess.run(
        [bash, "-n", script.name], cwd=REPO,
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )

    assert done.returncode == 0, done.stdout + done.stderr


@BOTH
def test_no_bash4_only_syntax(script: Path) -> None:
    """macOS 自带 bash 3.2：关联数组、`mapfile`、大小写展开、`&>>`、`|&` 它都不认。"""
    code = _code(script)

    for pattern, name in (
        (r"\bdeclare\s+-A\b", "declare -A"),
        (r"\b(mapfile|readarray)\b", "mapfile / readarray"),
        (r"\$\{[A-Za-z_][A-Za-z0-9_]*(,,|\^\^)", "${x,,} / ${x^^}"),
        (r"&>>", "&>>"),
        (r"\|&", "|&"),
    ):
        assert not re.search(pattern, code), f"{script.name} 用了 bash 4 才有的 {name}"


@BOTH
def test_executable_bit_is_in_the_index(script: Path) -> None:
    """Windows 文件系统没有可执行位，只能记在 git 索引里；漏了它，macOS 上是 permission denied。"""
    git = shutil.which("git")
    if git is None or not (REPO / ".git").exists():
        pytest.skip("不是 git 检出，查不了索引里的文件模式")

    done = subprocess.run(
        [git, "ls-files", "-s", "--", script.name], cwd=REPO,
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )

    assert done.stdout.startswith("100755 "), (
        f"{script.name} 在索引里不是 100755：{done.stdout.strip()!r}"
    )


# ───────────────────────── 二、不写死任何一台机器


@BOTH
def test_no_hardcoded_machine_paths(script: Path) -> None:
    code = _code(script)

    for needle in ("/Users/", "/home/", "/opt/homebrew", "C:\\", "C:/"):
        assert needle not in code, f"{script.name} 里写死了一条本机路径：{needle}"
    assert "BASH_SOURCE" in code, "项目根没有从脚本自身位置推出来"


# ───────────────────────── 三、与 ps1 逐项对得上


def test_same_environment_names_as_the_ps1() -> None:
    """ps1 给子进程设的每个变量，POSIX 脚本都要设——模型端点那两个除外（见第四节）。"""
    ps1_names = set(re.findall(r"\$env:([A-Z][A-Z0-9_]*)\s*=", _code(PS1)))
    assert ps1_names, "从 ps1 里一个变量都没读出来——是这条判据的正则坏了，不是脚本对上了"
    code = _code(START)

    missing = sorted(
        name for name in ps1_names - MODEL_VARS
        if not re.search(rf"\b{name}=", code)
    )

    assert not missing, f"start-demo.sh 没有设这些 ps1 设了的变量：{missing}"


def test_same_ports_as_the_ps1() -> None:
    start, stop = _code(START), _code(STOP)

    for port in ("55432", "56379", "8000", "3000"):
        assert port in start, f"start-demo.sh 里没有端口 {port}"
    for port in ("8000", "3000"):
        assert port in stop, f"stop-demo.sh 不管端口 {port}"


def test_start_and_stop_agree_on_the_process_markers() -> None:
    """worker 没有监听端口，只能按命令行标记认人：两边标记不同，就关不掉自己起的那个。"""
    start, stop = _code(START), _code(STOP)

    assert "harness.demo_server" in start
    for marker in ("harness.run_worker",):
        assert marker in start, f"start-demo.sh 没起 {marker}"
        assert marker.replace(".", r"\.") in stop or marker in stop, (
            f"stop-demo.sh 不认 {marker}"
        )


# ───────────────────────── 四、模型端点只透传


def test_the_model_endpoint_is_passed_through_not_hardwired() -> None:
    code = _code(START)

    for needle in ("11434", "ollama", "qwen"):
        assert needle not in code.lower(), f"start-demo.sh 里出现了本地模型那一段的 {needle!r}"
    for name in sorted(MODEL_VARS):
        assert not re.search(rf"\b{name}=", code), f"start-demo.sh 给 {name} 赋了值（只许透传）"
        assert name in code, f"start-demo.sh 没有报告 {name} 配没配"


@BOTH
def test_never_touches_a_key(script: Path) -> None:
    """脚本 NEVER 读写、NEVER 打印密钥：既不点名任何密钥变量，也不开 xtrace。"""
    code = _code(script)

    assert "API_KEY" not in code, f"{script.name} 点名了一个密钥变量"
    assert not re.search(r"\bset\s+-[a-wyz]*x", code), f"{script.name} 开了 xtrace"


# ───────────────────────── 五、不卡人，也不装作成功


@BOTH
def test_never_blocks_on_read(script: Path) -> None:
    code = _code(script)

    assert not re.search(r"(?m)(^|[;|&(]\s*|\bwhile\s+|\bdo\s+)\s*read\b", code), (
        f"{script.name} 会停下来读标准输入"
    )


def test_it_fails_loudly_when_docker_is_absent() -> None:
    code = _code(START)
    block = code[code.index("Docker 引擎未就绪"):code.index("Docker 引擎就绪")]

    assert "手动步骤" in block, "轮询不到引擎时没给手动步骤"
    assert "docker info" in block, "手动步骤里没给可执行的那一条"
    assert re.search(r"fail\s+\"Docker 引擎不可用", block), "轮询不到引擎却没有失败"
    assert re.search(r"fail\(\)\s*\{[^}]*exit 1", code), "fail 不是以非零码退出"


# ───────────────────────── 六、停脚本只停自己起的，且不删数据


def test_stop_keeps_the_data_volume() -> None:
    code = _code(STOP)

    assert "docker compose stop" in code
    assert not re.search(r"compose\s+down", code), "down 会连数据卷一起处置，这里只许 stop"


def test_stop_never_kills_by_process_name() -> None:
    """按 `python` / `node` 这种进程名停，会连别人的进程一起杀。"""
    code = _code(STOP)

    assert "killall" not in code
    assert not re.search(r"pkill\s+(-[A-Za-z0-9]+\s+)*(python|node|npm)\b", code)
    assert "kill -9" not in code and "-KILL" not in code, "先礼后兵：这里只发 TERM"


def test_runtime_files_are_ignored() -> None:
    """PID 与日志落在 `.run/`，那是本机运行态，NEVER 进仓。"""
    assert ".run" in _code(START)
    ignored = (REPO / ".gitignore").read_text(encoding="utf-8").splitlines()

    assert ".run/" in ignored


# ───────────────────────── 七、文档指得到脚本


def test_the_setup_doc_names_both_scripts() -> None:
    text = SETUP_DOC.read_text(encoding="utf-8")

    for needle in ("start-demo.sh", "stop-demo.sh", "requirements.lock", "tests/v041/test_start_demo_sh.py"):
        assert needle in text, f"docs/macOS-安装.md 没提 {needle}"


def test_the_readme_points_at_the_license_and_the_setup_doc() -> None:
    text = README.read_text(encoding="utf-8")

    assert "AGPL-3.0" in text
    assert "docs/macOS-安装.md" in text
    assert "start-demo.ps1" in text and "start-demo.sh" in text
