"""通用元测试件：把「抽掉这个机制之后，守着它的测试必须红」变成一条可执行断言。

## 为什么要有这个文件（终检 F-05）

`tests/v04/graph/test_primary_unique_runtime.py:83` 声称守住了「并发下主唯一」。
终检把 `flint/graph/roles.py:_lock_for` 换成 `nullcontext`（临界区消失，其余逻辑
一字不动）之后又打了 25 次——**25 次全绿**。那条断言连穿了该卡的 verify 与
self_review，绿的原因和它声称的原因不是同一个。

终检由此给出的通用判据（steward 反馈②）：

> 凡断言「并发 / 竞态 / 幂等 / 加锁 / 事务」守着某个不变量的测试，MUST 同时配一条
> 元测试：把那道保护措施抽掉后，该断言必须变红。抽法优先 monkeypatch（零源码改动），
> 红了再还原。**没有这条元测试的并发断言，默认按「未验证」看待。**

本文件是那条判据的执行件。用法：

```python
assert_bites(
    Replacement(module="flint.graph.roles", attr="_lock_for",
                build=lambda: CountingGate(), why="把 store 级互斥抽掉"),
    [test_no_reader_holding_the_lock_ever_sees_two_primaries],
)
```

## 四道检查，缺一道结论就是假的

1. **目标存在**——`module.attr` 找不到就当场失败。打歪的补丁什么都没换掉，而它
   造成的「红」会被读成「机制起作用了」。
2. **替换之前是绿的**——本来就红的用例，替换之后的红说明不了任何事。
3. **替换之后全红**——有一条活下来，就点名说出是哪一条。这是本件的正题。
4. **替换件真的被调用过**——终检对自己的 monkeypatch 单独验了这一步
   （「`_lock_for` 被调用 320 次（期望 8 线程 × 40 轮 = 320）→ monkeypatch 生效」）。
   补丁装上了、被测代码根本没走那条路、测试因为别的原因红了——三件事凑在一起，
   「抽掉机制后必红」这个结论就什么都没证明。

## 反例探针不能替代它

`roles.py:naive_set_primary_unsafe` 那种常驻反例探针证明的是「尺子认得出坏结果」
（它串行跑也红）；本件证明的是「这个测试打得到那道保护措施」。**两者是不同的命题，
NEVER 用前者交后者的差**——F-05 就是这么漏过去的。
"""
from __future__ import annotations

import importlib
import threading
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass
from typing import Any

Case = Callable[[], None]


@dataclass(frozen=True)
class Replacement:
    """被测机制的替换件。

    `build` 每次装载前调用一次，返回真正被 setattr 上去的那个对象；把它做成工厂
    而不是现成对象，是为了让每次探测拿到干净的计数器与锁表。
    `why` 只进报告，用来在失败信息里说清「抽掉的到底是什么」。
    """

    module: str
    attr: str
    build: Callable[[], Any]
    why: str

    def target(self) -> str:
        return f"{self.module}.{self.attr}"


@dataclass(frozen=True)
class BiteReport:
    """一次探测的全部事实。`bit` 为真 = 四道检查全过。"""

    replacement: Replacement
    checked: tuple[str, ...]
    already_red: tuple[str, ...]
    survivors: tuple[str, ...]
    replacement_calls: int

    @property
    def bit(self) -> bool:
        return (
            not self.already_red
            and not self.survivors
            and self.replacement_calls > 0
            and bool(self.checked)
        )

    def explain(self) -> str:
        head = f"抽掉 {self.replacement.target()}（{self.replacement.why}）之后："
        if not self.checked:
            return f"{head}一条被守的测试都没给——这次探测什么都没量"
        if self.already_red:
            return (
                f"{head}这些测试**替换之前就是红的**：{list(self.already_red)}。"
                "本来就红的用例，替换之后的红说明不了任何事，先把它们修绿"
            )
        if self.survivors:
            return (
                f"{head}这些测试**替换之后仍然是绿的**：{list(self.survivors)}。"
                "它们没有守住自己声称守住的那个机制——机制没了，它们照样报绿"
            )
        if self.replacement_calls == 0:
            return (
                f"{head}测试确实红了，但替换件**一次都没被调用**。"
                "被测代码没走到那条路，这次的红与被抽掉的机制无关，结论作废"
            )
        return (
            f"{head}{list(self.checked)} 全部变红，替换件被调用 "
            f"{self.replacement_calls} 次"
        )


class CountingGate:
    """当 `_lock_for` 这类「取锁」函数用的计数闸，同时是最常用的一种替换件。

    - `inner=None`：只计数、**不排他**。此时 `peak` 量的是「压力真的让几个线程
      同时进了临界区」——排他的闸量出来的峰值恒为 1，那是锁的定义，不是压力的证据。
    - `inner=真件`：计数 + 排他。此时 `peak` 恒为 1 才说明那把锁在起作用。

    终检对旧用例做的就是前一种测量：320 次写入，`max_inside=1`，两个线程从头到尾
    没有同时进过临界区。
    """

    def __init__(self, inner: Callable[[Any], Any] | None = None) -> None:
        self._inner = inner
        self._guard = threading.Lock()
        self._inside = 0
        self.peak = 0
        self.calls = 0

    @contextmanager
    def __call__(self, target: Any) -> Iterator[None]:
        holder = self._inner(target) if self._inner is not None else nullcontext()
        with holder:
            with self._guard:      # 只护计数器本身：护得再久就成了第二把锁
                self.calls += 1
                self._inside += 1
                self.peak = max(self.peak, self._inside)
            try:
                yield
            finally:
                with self._guard:
                    self._inside -= 1


def _name(case: Case) -> str:
    return getattr(case, "__name__", repr(case))


def _runs_red(case: Case) -> bool:
    """跑一次，红了返回 True。红 = 抛出任何 `Exception`（断言失败只是其中一种）。"""
    try:
        case()
    except Exception:  # noqa: BLE001 — 红就是红：断言失败、KeyError、超时抛错一律算
        return True
    return False


def probe(replacement: Replacement, guarded: Sequence[Case]) -> BiteReport:
    """装上替换件跑一遍被守的测试，把四道检查的事实全部记进报告。

    只判不抛（目标不存在除外——那是用法错，不是测量结果）。要断言请用 `assert_bites`。
    """
    module = importlib.import_module(replacement.module)
    if not hasattr(module, replacement.attr):
        raise AssertionError(
            f"{replacement.module} 没有属性 {replacement.attr}：这个补丁打歪了，"
            "它什么都没换掉，而它造成的红会被读成「机制起作用了」"
        )

    checked = tuple(_name(case) for case in guarded)
    already_red = tuple(_name(case) for case in guarded if _runs_red(case))
    if already_red:
        return BiteReport(replacement, checked, already_red, (), 0)

    calls = [0]
    built = replacement.build()

    def counted(*args: Any, **kwargs: Any) -> Any:
        calls[0] += 1
        return built(*args, **kwargs)

    original = getattr(module, replacement.attr)
    setattr(module, replacement.attr, counted)
    try:
        survivors = tuple(_name(case) for case in guarded if not _runs_red(case))
    finally:
        setattr(module, replacement.attr, original)

    return BiteReport(replacement, checked, (), survivors, calls[0])


def assert_bites(replacement: Replacement, guarded: Sequence[Case]) -> None:
    """`probe` 的断言版：四道检查任一不过就抛，失败信息里写明是哪一道。"""
    report = probe(replacement, guarded)
    if not report.bit:
        raise AssertionError(report.explain())
