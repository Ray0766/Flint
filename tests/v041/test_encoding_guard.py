"""ENV-01：不带 `PYTHONIOENCODING=utf-8` 时，**先说人话，别让人去修没坏的东西**。

## 治的病（第 7 批实测）

不带那个变量跑 `pytest`，**27 条走 subprocess 的判据假红**，报的全是同一句：

```
TypeError: argument of type 'NoneType' is not iterable
```

链条：子进程按 GBK 写中文 → 父进程按 UTF-8 解 → 读取线程抛 `UnicodeDecodeError`
→ `subprocess.run` 回来的 `stdout` 是 `None` → `"xxx" in done.stdout` 炸。

**那句 `TypeError` 与代码坏了长得一模一样。** 不带 **35 红** / 带上 **8 红**——
那 8 条才是真的。差的那 27 条足以让下一个会话相信自己撞上了一片回归。

## 判的是实况，不是那个变量在不在

真正咬人的是**父进程用什么编码解子进程的字节**：

- Linux/CI 上默认就是 UTF-8，没有那个变量也安全——判变量会**误报**；
- 变量设成 `gbk` 也算「在」，而那照样炸。

所以量 `sys.stdout.encoding`。
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

TOOL = REPO / "tools" / "check_encoding_env.py"
CONFTEST = REPO / "tests" / "conftest.py"
WORKER = REPO / "worker.md"
MAKEFILE = REPO / "Makefile"


def _run_pytest_with(env_overrides: dict[str, str | None]) -> subprocess.CompletedProcess[str]:
    """拿一条**真的**跑一次 pytest，环境按需改。

    只收一个最小的用例文件，图的是快——这里要量的是那道闸，不是那条用例。
    """
    env = dict(os.environ)
    for key, value in env_overrides.items():
        if value is None:
            env.pop(key, None)
        else:
            env[key] = value
    return subprocess.run(
        [sys.executable, "-m", "pytest", "tests/v041/test_encoding_guard.py",
         "-q", "--collect-only"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=REPO, env=env, timeout=600, check=False)


# ───────────────────────── 一、这条自检本身


def test_the_hazard_is_measured_from_the_real_encoding() -> None:
    """量 `sys.stdout.encoding`，NEVER 判「那个环境变量在不在」。

    判变量的话，Linux/CI 上会误报，而 `PYTHONIOENCODING=gbk` 会漏报——
    两个方向都错，且都错得很自然。
    """
    from tools.check_encoding_env import hazard, stdout_encoding

    source = TOOL.read_text(encoding="utf-8")
    assert "sys.stdout" in source
    assert 'environ.get("PYTHONIOENCODING")' not in source, "判的是变量而不是实况"

    # 本次会话自己就该是干净的（worker 纪律要求带上那个变量）。
    assert stdout_encoding() in ("utf8", "utf8mb4"), stdout_encoding()
    assert hazard() is None


def test_the_message_says_what_to_do_in_ascii_on_its_first_line() -> None:
    """这条消息要从一个**非 UTF-8 的 stdout** 走出去。

    中文那几段在读者屏上多半是乱码——**乱码里唯一还读得出来的就是那一行命令**。
    把结论放在中文段落末尾的话，真正需要它的那一次，它恰好看不见。
    """
    from tools.check_encoding_env import MESSAGE

    first, second = MESSAGE.splitlines()[:2]
    assert first.isascii() and second.isascii(), (first, second)
    assert "PYTHONIOENCODING=utf-8" in second


def test_the_message_names_the_false_red_so_nobody_goes_fixing_it() -> None:
    """**这条判据的全部意义**：那句 `TypeError` 要被叫出名字。

    只说「请设置环境变量」的话，下一个人设完、红消失了，
    他仍然不知道刚才那 27 条红是假的——下一次不带变量时他会重新怀疑代码。
    """
    from tools.check_encoding_env import MESSAGE

    assert "NoneType" in MESSAGE, "没点名那句假红长什么样"
    assert "27" in MESSAGE and "35" in MESSAGE and "8" in MESSAGE, "没给出实测的数"


# ───────────────────────── 二、闸接在开跑之前


def test_the_gate_runs_before_collection() -> None:
    """放在 `pytest_configure`，不是某一条用例里。

    那 27 条一旦开跑，满屏 `TypeError` 就已经把这句说明淹没了——
    **而它正是用来防止那种误读的**。
    """
    code = CONFTEST.read_text(encoding="utf-8")

    assert "def pytest_configure" in code
    assert "check_encoding_env" in code
    assert code.index("def pytest_configure") < code.index(
        "def pytest_collection_modifyitems")


# ───────────────────────── 三、阴性对照：清掉变量跑一次


def test_without_the_variable_you_get_the_sentence_not_a_wall_of_tracebacks() -> None:
    """**卡上点名的阴性对照**：清掉那个变量真跑一次。

    要拿到的是那句说明，NEVER 是一片 `TypeError`。
    """
    if sys.platform != "win32":
        import pytest

        pytest.skip("非 Windows 上 stdout 本来就是 UTF-8，这道闸对它是空操作")

    done = _run_pytest_with({"PYTHONIOENCODING": None})
    # 两股流都收：`pytest.exit` 把这段写到哪一股，取决于 pytest 的终端写法——
    # 判据 NEVER 挂在那个实现细节上，读者两股都看得到。
    said = (done.stdout or "") + (done.stderr or "")

    assert done.returncode == 1, said[-500:]
    assert "[flint] stdout encoding is" in said, said[-500:]
    assert "PYTHONIOENCODING=utf-8" in said
    # 判的是「**一条判据都没跑起来**」，NEVER 判「输出里没有 TypeError」——
    # 那句人话自己就点名了 `TypeError`（那正是它的作用）。
    # 拿禁词去查，会把说明问题的那句话当成问题本身：本批第十七次同一形状。
    assert "Traceback (most recent call last)" not in said, said[-600:]
    assert "failed" not in said and "passed" not in said, said[-600:]


def test_with_the_variable_the_gate_is_a_no_op() -> None:
    """带上变量就当它不存在——**一道会误伤的闸没人会留着**。"""
    done = _run_pytest_with({"PYTHONIOENCODING": "utf-8"})
    said = (done.stdout or "") + (done.stderr or "")

    assert done.returncode == 0, said[-800:]
    assert "[flint] stdout encoding is" not in said


def test_the_bypass_is_written_down_and_loud() -> None:
    """留一个明写的出口，比让人去注释掉一道闸好——注释掉的闸不会有人再打开。

    但出口本身要在消息里写明，且用它的人得知道自己在放弃什么。
    """
    from tools.check_encoding_env import BYPASS, MESSAGE, hazard_text

    # `MESSAGE` 是模板（`{bypass}` 还没填）；判的要是**读者真会看到的那一段**。
    assert BYPASS in hazard_text("gbk")
    assert "{bypass}" in MESSAGE
    assert "自己分辨" in MESSAGE, "没说清绕过去之后要自己承担什么"

    if sys.platform == "win32":
        done = _run_pytest_with({"PYTHONIOENCODING": None, BYPASS: "1"})
        assert done.returncode == 0, done.stdout[-500:]


# ───────────────────────── 四、一处定义，他处引用


def test_the_discipline_is_written_once_and_referenced() -> None:
    """跑法写进 `worker.md` 的固定纪律段与 `Makefile` 的 `gate`。

    同一条纪律抄两份措辞的话，两份会各自漂移——
    这条判据要求**别处引用它，而不是重抄一遍**。
    """
    worker = WORKER.read_text(encoding="utf-8")
    makefile = MAKEFILE.read_text(encoding="utf-8")

    assert "PYTHONIOENCODING=utf-8" in worker, "worker.md 里没有这条纪律"
    assert "check_encoding_env" in worker or "tools/check_encoding_env.py" in worker, (
        "worker.md 没指向那句人话的出处")
    assert "PYTHONIOENCODING=utf-8" in makefile, "make gate 不带这个变量"
