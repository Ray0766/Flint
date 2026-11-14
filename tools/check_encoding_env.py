"""ENV-01：跑测试之前先看一眼**父进程按什么编码读子进程的输出**。

## 治的病（第 7 批实测）

不带 `PYTHONIOENCODING=utf-8` 跑 `pytest`，**27 条走 subprocess 的判据会假红**，
报的全是同一句：

```
TypeError: argument of type 'NoneType' is not iterable
```

链条是这样的：子进程（尺子脚本）按 Windows 默认的 GBK 往 stdout 写中文 →
`subprocess` 的读取线程按 UTF-8 解 → `UnicodeDecodeError` 在那个线程里抛出 →
`subprocess.run` 回来的 `stdout` 是 **`None`** → 判据里 `"xxx" in done.stdout` 炸。

**那句 `TypeError` 与代码坏了长得一模一样。** 第 7 批实测：
不带 **35 红**，带上 **8 红**——那 8 条才是真的。

## 为什么判的是「实际编码」而不是「那个环境变量在不在」

真正咬人的是**父进程用什么编码解子进程的字节**。环境变量只是设定它的一种办法：

- Linux/CI 上默认就是 UTF-8，没有这个变量也一样安全——判变量在不在会**误报**；
- 反过来，变量设成 `gbk` 也算「在」，而那照样炸。

所以这里量 `sys.stdout.encoding`，那是它真实的样子。

用法：

    python tools/check_encoding_env.py     # 有隐患时 exit 1 并说明怎么跑
"""
from __future__ import annotations

import os
import sys

#: 想绕过去时设它。**留一个明写的出口**比让人去注释掉一道闸好：
#: 注释掉的那道闸不会有人再打开。
BYPASS = "FLINT_ALLOW_NON_UTF8_STDOUT"

# 第一行是 **ASCII**，而且是那句「怎么办」。
#
# 理由很实际：这条消息本身要从一个非 UTF-8 的 stdout 走出去，
# 中文那几段在读者屏上多半是乱码——**而乱码里唯一还读得出来的就是这一行**。
# 把结论放在中文段落末尾的话，真正需要它的那次，它恰好看不见。
MESSAGE = """\
[flint] stdout encoding is {encoding}, not UTF-8.
[flint] Run:  PYTHONIOENCODING=utf-8 pytest -q

本机的标准输出编码是 {encoding}，不是 UTF-8。

**这样跑下去，27 条走 subprocess 的判据会假红**，报的全是同一句
`TypeError: argument of type 'NoneType' is not iterable`——
那不是回归：子进程按 {encoding} 写中文，父进程按 UTF-8 解，读取线程抛
UnicodeDecodeError，于是 `subprocess.run` 回来的 stdout 是 None。

第 7 批实测：不带 35 红 / 带上 8 红，**那 8 条才是真的**。

正确跑法（Windows / Git Bash 都一样）：

    PYTHONIOENCODING=utf-8 pytest -q

PowerShell：

    $env:PYTHONIOENCODING = 'utf-8'; pytest -q

真要在非 UTF-8 下跑，设 {bypass}=1——**那时红的那几十条要自己分辨**。\
"""


def stdout_encoding() -> str:
    """父进程解子进程输出用的编码。取不到时按最坏情况算。"""
    name = getattr(sys.stdout, "encoding", None) or ""
    return name.lower().replace("-", "").replace("_", "") or "unknown"


def hazard_text(encoding: str) -> str:
    """填好的那段人话。**判据要判读者真会看到的东西**，不是模板本身。"""
    return MESSAGE.format(encoding=encoding or "未知", bypass=BYPASS)


def hazard() -> str | None:
    """有隐患时回一句**人话**，没有时回 None。"""
    if os.environ.get(BYPASS):
        return None
    encoding = stdout_encoding()
    if encoding in ("utf8", "utf8mb4"):
        return None
    return hazard_text(encoding)


def main() -> int:
    problem = hazard()
    if problem is None:
        print(f"标准输出编码 = {stdout_encoding()}，没有这一类隐患。")
        return 0
    print(problem)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
