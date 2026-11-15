"""PERSIST-01：把 asyncpg 的异步调用接到**同步**的 store 接口上。

## 为什么需要这个东西

三族的 store 接口是**同步**的：

```
FavoriteStore.get / put / drop / all        （flint/fav/store.py）
ShareLinkStore.get / put / for_owner        （flint/api/share.py）
PrefsStore.get / put                        （flint/profile/prefs.py）
```

而本仓**只有 asyncpg 一个 Postgres 驱动**（`requirements.lock` 里没有 psycopg，
本批 rules 写死 NEVER 新增依赖）。两者之间必须有一座桥。

## 为什么不把 store 接口改成 async

改 `async` 会一路传染到 `flint/fav/store.py` · `stale.py` · `batch.py` ·
`flint/api/favorites.py`，**然后传染到 `tests/v04/fav/` 下那些已经 verified 的判据**——
而 `DEC-021` / `worker.md` §9.2 写死：v0.4 已 verified 的判据 NEVER 再改。
为了让实现更顺手去改判据，正是那条纪律要挡住的动作。

所以：**store 接口一字不动，桥在下面**。

## 这座桥怎么搭：一条专用事件循环线程

`asyncio.run()` 每次都建一条新的事件循环。asyncpg 的连接**绑定在建它的循环上**，
所以那条路走不通（连接池会跨循环失效）。这里起一条守护线程，
里面跑一条长活的事件循环，同步侧用 `run_coroutine_threadsafe(...).result()` 等它。

## `.result()` 会阻塞调用它的那条线程——所以调用点 MUST 是同步处理函数

这是本模块唯一需要小心的一件事，写在这里而不是散在三个 store 里：

- FastAPI 的 `async def` 处理函数跑在**事件循环线程**上。
  在那里 `.result()` 会把整条循环停住——**所有并发请求一起卡**，
  而症状是「服务偶尔很慢」，没有任何一条错误日志。
- FastAPI 的 `def`（同步）处理函数跑在**它自己的线程池**里。
  在那里阻塞只影响这一个请求，那正是线程池存在的意义。

所以 `run_sync` **主动检测**自己是不是在一条正在运行的事件循环上被调用，
是就当场抛错。**NEVER 让它悄悄地慢下去**：一个响亮的错误可以在第一次跑判据时
就被发现，而一条被停住的事件循环要等到有并发的那天才现形，
那天没人会想到是这里。

异步侧要用这三个 store 时，走 `starlette.concurrency.run_in_threadpool`
把整段同步调用挪到线程池——`flint/api/share.py` 的外链只读那条路正是这么接的。
"""
from __future__ import annotations

import asyncio
import threading
from collections.abc import Coroutine
from typing import Any

_lock = threading.Lock()
_loop: asyncio.AbstractEventLoop | None = None


class BlockingCallOnEventLoop(RuntimeError):
    """在事件循环线程上调用了同步桥。见模块 docstring 最后一节。"""


def _ensure_loop() -> asyncio.AbstractEventLoop:
    """取那条专用循环，没有就起一条。**进程内只起一条**。

    双重检查：第一次判断在锁外（热路径上不必每次都抢锁），
    确认要建时再进锁里判第二次——否则两个线程会各建一条循环，
    而 asyncpg 的连接绑在建它的那条上，第二条循环上的连接会莫名其妙地失效。
    """
    global _loop
    if _loop is not None:
        return _loop
    with _lock:
        if _loop is None:
            loop = asyncio.new_event_loop()
            thread = threading.Thread(
                target=loop.run_forever, name="flint-sync-bridge", daemon=True)
            thread.start()
            _loop = loop
    assert _loop is not None
    return _loop


def run_sync[T](coro: Coroutine[Any, Any, T]) -> T:
    """在专用循环上跑一个协程，**阻塞当前线程**直到它出结果。

    在事件循环线程上调用会抛 `BlockingCallOnEventLoop`——那不是保守，
    那是把一个查不出来的性能事故换成一条一眼看得见的错误。
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass
    else:
        coro.close()          # 不关的话解释器会补一句 "coroutine was never awaited"
        raise BlockingCallOnEventLoop(
            "run_sync 在事件循环线程上被调用：这会把整条循环停住。"
            "把调用点改成同步处理函数（FastAPI 会用线程池跑它），"
            "或用 starlette.concurrency.run_in_threadpool 包住整段同步调用。"
        )
    return asyncio.run_coroutine_threadsafe(coro, _ensure_loop()).result()
