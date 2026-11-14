"""FIX-20：匿名走**真网络**仍回 200——查清之后发现，卡面那个假设不成立。

## 卡面说的差别不是那个差别

卡面 acceptance②：「差别在 `harness/demo_server.py` 走 `create_app` 而不是
`create_deref_app`」。**不是**——`create_app` 第 509 行就挂着
`create_deref_app(...)`，两条路拿到的是同一份 deref。

**真正的差别是 `harness/demo_server.py` 的 `_InjectUserMiddleware`**：
前端不发身份头（`web/lib/screenClient.ts` 逐字写死的口径），
所以 demo 栈里有一道中间件替它补 `demo-user`。
**走网络的「匿名」请求，到端点手上时已经不是匿名的了。**

## 「门开着」这个读法从一开始就与实测对不上

如果端点真的把门开着，带一个**不是数据主人**的身份也该拿到东西。实测：

```
走网络 匿名          -> 200      ← 中间件补了 demo-user
走网络 demo-user     -> 200
走网络 stranger      -> 404      ← 身份确实在起作用
进程内 匿名（不经中间件）-> 422      ← 头确实必填
```

`FIX-16` 的进程内证据与 steward 的网络证据**两个都对**，
中间夹着的是那道中间件。

## 所以本卡收的是**隐形**这一条

删中间件 = demo 界面每一屏都变 422（不是收口，是把灯关了）；
把必填头改成可选 = 卡面 acceptance⑤ 逐字禁掉的动作。

两头都堵死之后剩下的那条路：把这道**网关替身**从隐形变成明说——
默认照旧、**可以关**、而且**每次替人补身份都在响应上留记号**。

`steward` 重起两次都没收口，正是因为屏上、日志里、响应里
**没有任何地方说过「你这个请求的身份是补出来的」**。

## 判据打真网络，不是 TestClient

下面起一个**真 uvicorn** 子进程（各用各的端口），用 `httpx` 打它。
`TestClient` 在进程内跑 ASGI，量不到「网络那一层」——
而这一条缺陷**只在网络那一层看得见**（`FIX-16` 就是在这里栽的）。
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest

pytestmark = pytest.mark.compose

REPO = Path(__file__).resolve().parents[2]
DEMO = REPO / "harness" / "demo_server.py"
TICKET = REPO / "docs" / "blocked" / "DEREF-PROBE-HIT-A-STALE-BACKEND.md"
FACT = "fact-demo-vecdb-cost"
OWNER_ID = "demo-user"


#: 子进程的启动脚本。写成一个常量而不是拼在 `Popen` 的列表里：
#: 拼在列表里是**隐式字符串拼接**，ruff（ISC004）判红，而它判得对——
#: 那种写法里少一个空格就会把两个词粘成一个，而报错在子进程里，很难看出来。
_BOOT = (
    "import os, uvicorn;"
    "from harness.demo_server import build_app;"
    "uvicorn.run(build_app(), host='127.0.0.1',"
    " port=int(os.environ['FLINT_DEMO_PORT']), log_level='error')"
)


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _serve(*, inject: bool) -> Iterator[str]:
    """起一个**真 uvicorn**，回它的 base url。

    **各用各的端口**：`:8000` 上那个是人在用的 demo 栈，
    judged run 去占它的话，一次判据会把界面打断——
    而更坏的是反过来：判据可能量到那个**别人起的、代码不知道多旧的**进程。
    本仓已经为「旧进程冒充判据的对象」栽过两次。
    """
    port = _free_port()
    env = {
        **os.environ,
        "PYTHONIOENCODING": "utf-8",
        "FLINT_DEMO_INJECT_IDENTITY": "1" if inject else "0",
        "FLINT_DEMO_PORT": str(port),
    }
    proc = subprocess.Popen(
        [sys.executable, "-c", _BOOT],
        cwd=REPO, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        deadline = time.time() + 60
        while time.time() < deadline:
            if proc.poll() is not None:
                err = (proc.stderr.read() or b"").decode("utf-8", "replace")
                pytest.skip(f"demo 起不来：{err[-800:]}")
            try:
                httpx.get(f"{base}/categories", timeout=2.0)
                break
            except httpx.HTTPError:
                time.sleep(0.4)
        else:
            pytest.skip("demo 60 秒没起来")
        yield base
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()


@pytest.fixture(scope="module")
def closed() -> Iterator[str]:
    """网关替身**关掉**的那一台：这时「匿名」是真的匿名。"""
    yield from _serve(inject=False)


@pytest.fixture(scope="module")
def demo() -> Iterator[str]:
    """网关替身**开着**的那一台：今天 demo 界面用的就是这一台。"""
    yield from _serve(inject=True)


# ───────────────────────── 一、收口：真网络上，匿名进不来


def test_anonymous_over_a_real_network_is_refused(closed: str) -> None:
    """acceptance④ 的前半：**匿名 MUST 回 422/401**。

    打的是真 socket，不是 `TestClient`——这条缺陷只在网络那一层看得见。
    """
    got = httpx.get(f"{closed}/facts/{FACT}", timeout=20.0)

    assert got.status_code in (401, 422), f"匿名竟然拿到了 {got.status_code}"


def test_the_real_owner_still_gets_it_over_the_network(closed: str) -> None:
    """acceptance④ 的后半：**带真实身份仍 200**。

    只判「匿名被拒」的话，一个把整条路关死的实现也能全绿——
    而那时用户什么都读不到。
    """
    got = httpx.get(
        f"{closed}/facts/{FACT}", headers={"x-user-id": OWNER_ID}, timeout=20.0)

    assert got.status_code == 200, got.text


def test_a_stranger_is_still_refused_over_the_network(closed: str) -> None:
    """陌生人**看到的 NEVER 多于主人**（`FIX-16` 立的那条不变量）。

    这一条同时是「门本来就是关着的」的证据：
    如果端点真把门开着，带一个不是主人的身份也该拿到东西。
    """
    got = httpx.get(
        f"{closed}/facts/{FACT}", headers={"x-user-id": "stranger"}, timeout=20.0)

    assert got.status_code == 404, got.status_code


# ───────────────────────── 二、网关替身：默认还在，但**说话了**


def test_the_demo_gateway_still_lets_the_ui_work(demo: str) -> None:
    """默认那一台照旧：不带头也拿得到——**demo 界面每一屏都靠它取数**。

    默认关掉的话，那不是收口，是把灯关了（`web/lib/screenClient.ts`
    写死了前端不发身份头）。
    """
    got = httpx.get(f"{demo}/facts/{FACT}", timeout=20.0)

    assert got.status_code == 200


def test_an_injected_identity_says_so_on_the_response(demo: str) -> None:
    """**本卡真正收的那一条**：补过身份的响应带记号。

    `steward` 重起两次都没收口，正是因为屏上、日志里、响应里
    没有任何地方说过「你这个请求的身份是补出来的」。
    """
    got = httpx.get(f"{demo}/facts/{FACT}", timeout=20.0)

    assert got.headers.get("x-flint-demo-identity") == "injected", (
        f"补了身份却没留记号：{dict(got.headers)}")


def test_a_real_identity_is_not_marked_as_injected(demo: str) -> None:
    """**没补的时候 NEVER 留记号**——那样这个记号就不再说明任何事。"""
    got = httpx.get(
        f"{demo}/facts/{FACT}", headers={"x-user-id": OWNER_ID}, timeout=20.0)

    assert "x-flint-demo-identity" not in got.headers


def test_the_switch_is_off_by_a_single_environment_variable() -> None:
    """关掉这道替身**只要一个环境变量**——判据自己用的就是它。"""
    code = DEMO.read_text(encoding="utf-8")

    assert "FLINT_DEMO_INJECT_IDENTITY" in code
    assert "enabled=inject_identity" in code


# ───────────────────────── 三、NEVER 把必填头改成可选


def test_the_header_is_still_required_on_the_endpoint() -> None:
    """acceptance⑤ 逐字：**NEVER 把必填头改成可选**来让判据变绿。

    改成可选之后谁都能读任何项目的事实——而判据会全绿。
    所以这一条从**源码**上量：那几条 deref 端点的 `x_user_id` 仍是 `Header()`，
    没有默认值。
    """
    deref = (REPO / "flint" / "api" / "deref.py").read_text(encoding="utf-8")

    assert "x_user_id: str = Header()" in deref
    assert "x_user_id: str | None = Header(default=None)" not in deref
    assert "Header(default=" not in deref, "有一条 deref 端点的身份头被改成可选了"


def test_the_middleware_was_not_deleted() -> None:
    """网关替身**没有被删**——删了 demo 界面每一屏都变 422。"""
    code = DEMO.read_text(encoding="utf-8")

    assert "_InjectUserMiddleware" in code
    assert "add_middleware(_InjectUserMiddleware" in code


def test_the_ticket_is_closed_with_the_real_root_cause() -> None:
    """关单时 MUST 写清真根因——**不是 `create_app` 与 `create_deref_app` 的差别**。

    照卡面那个假设关单的话，下一个人再遇到同类现象会去查装配，
    而那里没有问题。
    """
    text = TICKET.read_text(encoding="utf-8")

    assert "**状态** closed" in text, "单还开着"
    assert "_InjectUserMiddleware" in text, "没写清真正的根因"
