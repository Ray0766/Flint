"""GAUGE-03 / F-05：把「并发下主唯一」从一句话变成量得到的东西（**单进程**口径）。

## 这张卡在修什么

`tests/v04/graph/test_primary_unique_runtime.py:83` 那条断言**抽掉临界区之后照样绿**
（终检 F-05 实测：加锁版 25 次全绿，把 `_lock_for` 换成 nullcontext 之后仍然 25 次全绿）。
根因不是锁写错了，是那条断言的压力打不到锁：同一份终检用带计数的假锁量过全部 320 次
写入，`max_inside=1`——8 个线程从头到尾没有任何两个同时处在临界区内。默认调度下
8 个节点的清主循环在一个时间片里就跑完了，写入根本撞不上。撞不上的绿证明不了任何
关于那把锁的事。

## 口径收窄：服务端 → 单进程（acceptance④）

GRAPH-06 卡面 acceptance② 原话是「**服务端**并发双写下 primary ≤1 仍成立」。
v0.4 里那个服务端不存在：`migrations/` 全目录 grep `graph_nodes` 零命中（模块 docstring
说的部分唯一索引 `UNIQUE (graph_id) WHERE primary` 因此没有落点），`flint/graph/roles.py`
全仓无生产调用方，`GraphStore` 自述是内存实现。而 `threading.Lock` 只在**一个进程内**
成立，uvicorn 多 worker 进程下它一开始就不构成保证。

所以本文件只声称一件事：**单进程并发写下 I12-1 成立**。跨进程那一半挂在 E2 建
`graph_nodes` 表那张卡上（部分唯一索引），本文件 NEVER 声称守住了它。

## 三条断言各自证明什么（NEVER 用其中一条交另一条的差）

1. `test_the_storm_puts_more_than_one_writer_inside_the_critical_section`
   ——压力真的把两个以上写入方同时送进了临界区（只计数不排他的闸量出 peak ≥2）；
2. `test_the_lock_is_what_collapses_that_overlap_to_one`
   ——同一份压力，闸包住真锁之后 peak 掉回 1：把它们分开的就是那把锁；
3. `test_no_reader_holding_the_lock_ever_sees_two_primaries`
   ——**互斥**成立：遵守同一把锁的读者恒看不到两个主。这一条量的是互斥，不是
   「线程撞上过」，撞上由第 1 条单独证明。终检对旧用例的判词正是「两者是不同的命题」：
   那里的常驻反例探针证明的是「`primary_count` 这把尺子认得出多主」（串行跑也红），
   却被当成了「线程真撞上了」的证据。

第 3 条是本卡交给元测试件去咬的那条：抽掉 `_lock_for` 之后它必红（旧那条做不到这件事）。

## 旧文件保留（acceptance⑤）

`tests/v04/graph/test_primary_unique_runtime.py` 一字未动、不删。它证明的
「尺子认得出多主」仍然有效；它**不**证明「线程撞上过」——后者由本文件第 1 条接手。
"""
from __future__ import annotations

import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from contracts_v04.models_v04 import GraphNode
from flint.graph import roles
from flint.graph.roles import primary_count
from flint.graph.store import GraphStore, add_node
from tests._meta.probe_bites import CountingGate, Replacement, assert_bites, probe

REPO = Path(__file__).resolve().parents[2]
OLD_CASE = REPO / "tests" / "v04" / "graph" / "test_primary_unique_runtime.py"

NOW = datetime(2026, 8, 4, tzinfo=UTC)
GRAPH = "wb-1"
NODE_IDS = [f"n-{i}" for i in range(6)]

# 老主坐在列表**最后**，抢主的四个写入方全部在它之前：写循环按列表序逐个写，
# 于是「立了新主、还没走到老主那一格」这段窗口的长度是写死的（4~5 次停顿），
# 不靠调度器碰运气。互斥在，这段窗口是临界区内部的事，取同一把锁的读者看不到；
# 互斥没了，它就是两个 primary 同时为真、并且**必然**被采到。
SEEDED_PRIMARY = NODE_IDS[-1]
WRITER_IDS = NODE_IDS[:4]

# 每次写 primary 前让出 GIL 的时长。终检量出的 max_inside=1 就是这一步缺席的结果：
# 不拉开，整个临界区在一个时间片里跑完，线程没有机会重叠。
WRITE_PAUSE = 0.005
ROUNDS = 2
SAMPLE_PAUSE = 0.0005


class _GatedNode:
    """真节点的代理：写 `primary` 前先停 `pause` 秒；读不停（观察线程要采得够密）。

    停顿只加在测试这一侧的代理上，`flint/graph/roles.py` 一字未动——被测的是真件。
    """

    def __init__(self, node: Any, pause: float) -> None:
        object.__setattr__(self, "_node", node)
        object.__setattr__(self, "_pause", pause)

    def __getattr__(self, name: str) -> Any:
        return getattr(object.__getattribute__(self, "_node"), name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name == "primary":
            time.sleep(object.__getattribute__(self, "_pause"))
        setattr(object.__getattribute__(self, "_node"), name, value)


class _SlowStore(GraphStore):
    """`nodes()` 返回代理，把临界区从「一个时间片」拉成一段可观测的时间。"""

    def nodes(self, graph_id: str) -> list[Any]:
        return [_GatedNode(node, WRITE_PAUSE) for node in super().nodes(graph_id)]


def _store() -> _SlowStore:
    """六个节点，主先坐在最后一个上（窗口长度由此写死）。"""
    store = _SlowStore()
    for nid in NODE_IDS:
        add_node(
            store, graph_id=GRAPH, node_id=nid, source_kind="cluster",
            source_id=f"c-{nid}", label=nid, position=(0.0, 0.0), now=NOW,
            model=GraphNode,
        )
    roles.set_node_role(store, graph_id=GRAPH, node_id=SEEDED_PRIMARY, role="primary")
    return store


def _storm(store: GraphStore, *, rounds: int = ROUNDS) -> None:
    """四个写入方各占一个线程，在同一屏障上对齐后同时抢主。"""
    barrier = threading.Barrier(len(WRITER_IDS))

    def writer(nid: str) -> None:
        barrier.wait()
        for _ in range(rounds):
            roles.set_node_role(store, graph_id=GRAPH, node_id=nid, role="primary")

    threads = [threading.Thread(target=writer, args=(nid,)) for nid in WRITER_IDS]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30.0)
    alive = [t.name for t in threads if t.is_alive()]
    assert alive == [], f"写入线程没跑完就超时了：{alive}"


STORM_CALLS = len(WRITER_IDS) * ROUNDS
HANDOVER_ROUNDS = 2
HANDOVER_CALLS = HANDOVER_ROUNDS * 2


def _lone_handover(store: GraphStore, *, rounds: int = HANDOVER_ROUNDS) -> None:
    """一个写入方做「主从最后一格交回第一格」——窗口长度写死，不靠调度器碰运气。

    `_storm` 里四个写入方互相把对方刚立的主清掉，撕裂窗口有多长由线程唤醒次序决定，
    换台机器就换个数（实测同一份压力有时一次都不出现）。**把红压在那种窗口上，
    这条元测试就成了下一个 F-05**。所以再走一段独占写入：老主坐在列表最后一格，
    新主在第一格——写循环按列表序逐个写，于是「立了新主、还没走到老主那一格」
    这段窗口恒等于 4 次停顿（20 毫秒），与调度无关。

    这一段与并发不冲突：观察线程全程在跑，它与写入方之间的互斥正是本条要量的东西。
    """
    for _ in range(rounds):
        roles.set_node_role(store, graph_id=GRAPH, node_id=SEEDED_PRIMARY, role="primary")
        roles.set_node_role(store, graph_id=GRAPH, node_id=NODE_IDS[0], role="primary")


def test_the_storm_puts_more_than_one_writer_inside_the_critical_section(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """acceptance①：用计数版闸量出临界区并发峰值 ≥2。

    闸只计数、不排他——排他的闸量出来的峰值恒为 1，那是锁的定义，不是压力的证据。
    这一条要回答的是终检那句「并发双写在这个测试的压力下根本没有发生过」：
    先证明新压力真的让写入方在同一段临界区里重叠了，后面关于锁的话才有分母。
    """
    store = _store()                       # 先建库再打补丁：播种那次不进计数
    gate = CountingGate()
    monkeypatch.setattr(roles, "_lock_for", gate)
    _storm(store)

    assert gate.calls == STORM_CALLS, (
        f"闸被调用 {gate.calls} 次，期望 {STORM_CALLS} 次"
        "（四个写入方 × 两轮）——对不上说明替换没生效，下面的峰值就是假的"
    )
    assert gate.peak >= 2, (
        f"临界区并发峰值 {gate.peak}：写入方从未同时进过临界区，"
        "这份压力与终检量到 max_inside=1 的旧压力是同一种摆设"
    )


def test_the_lock_is_what_collapses_that_overlap_to_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """同一份压力，闸包住真锁之后峰值掉回 1：把写入方分开的就是 `_lock_for`。

    上一条与这一条是一对：**能重叠**（去掉锁）与**没重叠**（留着锁）来自同一个 `_storm`，
    唯一变量是那把锁。少了任何一条，另一条都可以用「压力太弱」解释掉。
    """
    store = _store()
    gate = CountingGate(inner=roles._lock_for)
    monkeypatch.setattr(roles, "_lock_for", gate)
    _storm(store)

    assert gate.calls == STORM_CALLS
    assert gate.peak == 1, f"真锁在位却量出并发峰值 {gate.peak}：互斥没有成立"
    assert primary_count(store, graph_id=GRAPH) == 1


def test_no_reader_holding_the_lock_ever_sees_two_primaries() -> None:
    """acceptance③ 咬的就是这一条：互斥成立 —— 取同一把锁的读者恒看不到两个主。

    为什么读者也要取锁：写循环按列表序逐个写，「立了新主、还没走到老主那一格」这一瞬
    两个 primary 都为真。这一瞬是临界区**内部**的事，取同一把锁的读者看不到它；不取锁
    的读者看得到——而「被外人看得到」正是这条不变量被破坏的样子。抽掉 `_lock_for`，
    写入方与观察方同时失去互斥，这条断言必红（`test_removing_the_lock_...` 守着）。

    它量的是互斥，**不是**「两个线程撞上过」；撞上由 `test_the_storm_...` 单独证明。

    压力分两段：`_storm` 是四个写入方互抢（真并发，但撕裂窗口长短随调度），
    `_lone_handover` 的窗口长度写死。**红由后一段保证**——把保证压在前一段那种
    随机窗口上，这条元测试自己就成了下一个 F-05。
    """
    store = _store()
    samples: list[int] = []
    stop = threading.Event()

    def observer() -> None:
        while not stop.is_set():
            with roles._lock_for(store):
                samples.append(primary_count(store, graph_id=GRAPH))
            time.sleep(SAMPLE_PAUSE)

    watcher = threading.Thread(target=observer, daemon=True)
    watcher.start()
    try:
        _storm(store)
        _lone_handover(store)
    finally:
        stop.set()
        watcher.join(timeout=10.0)

    assert samples, "观察线程一次都没采到样本：这条断言什么都没量到"
    assert max(samples) <= 1, (
        f"取锁的读者看到了 {max(samples)} 个主（{len(samples)} 次采样）：I12-1 被破坏"
    )
    assert primary_count(store, graph_id=GRAPH) == 1


def test_removing_the_lock_makes_the_guarded_case_red() -> None:
    """acceptance②③：把 `_lock_for` 换成不排他的替换件之后，上一条必须红。

    这正是旧用例做不到的那件事——终检把它换成 nullcontext 打了 25 次，25 次全绿。
    """
    report = probe(
        Replacement(
            module="flint.graph.roles",
            attr="_lock_for",
            build=lambda: CountingGate(),  # 只计数、不排他 = 临界区消失
            why="把 store 级互斥抽掉，其余逻辑一字不动",
        ),
        [test_no_reader_holding_the_lock_ever_sees_two_primaries],
    )

    assert report.bit, report.explain()
    # 下界 = 播种 1 次 + storm STORM_CALLS 次 + 交接 HANDOVER_CALLS 次；观察线程每采一次样
    # 也走一次 `_lock_for`，采样次数随机，故只钉下界。这一条钉的是「补丁真的被走到了」。
    floor = 1 + STORM_CALLS + HANDOVER_CALLS
    assert report.replacement_calls >= floor, (
        f"替换件只被调用 {report.replacement_calls} 次，写入方那 {floor} 次都没走到它"
    )


def _equivalent_lock_for(store: Any) -> Any:
    """与真件语义相同的替换件：换了个壳，互斥一点没少。"""
    with _EQUIVALENT_GUARD:
        return _EQUIVALENT_LOCKS.setdefault(id(store), threading.Lock())


_EQUIVALENT_LOCKS: dict[int, threading.Lock] = {}
_EQUIVALENT_GUARD = threading.Lock()


def test_probe_bites_goes_red_when_the_replacement_changes_nothing() -> None:
    """元测试件的阴性对照：替换后仍绿 → 元测试件自己必须红。

    没有这一条，`assert_bites` 可能是一句「我看什么都挺好」——那正是它要防的东西。
    """
    with pytest.raises(AssertionError, match="替换之后仍然是绿的"):
        assert_bites(
            Replacement(
                module="flint.graph.roles",
                attr="_lock_for",
                build=lambda: _equivalent_lock_for,
                why="构造用：语义等同的替换件，互斥仍在",
            ),
            [test_no_reader_holding_the_lock_ever_sees_two_primaries],
        )


_MARKER = {"patched": False}


def _case_red_only_while_patched() -> None:
    """构造用：它的红与那把锁无关，只与「补丁装没装上」有关。"""
    assert not _MARKER["patched"], "构造用的红：与被替换的机制无关"


def _build_never_called_replacement() -> Any:
    """装载时打标记，装上去的那个替换件本身 NEVER 被调用。"""
    _MARKER["patched"] = True

    def unused(store: Any) -> Any:  # pragma: no cover - 立在那里就是不被调用
        raise AssertionError("这个替换件不该被调用")

    return unused


def test_probe_bites_refuses_a_conclusion_built_on_an_uncalled_replacement() -> None:
    """红了、但替换件一次都没被调用 → 结论是假的，元测试件必须拒绝它。

    这是终检 F-05 里单独验过的那一步（「monkeypatch 自证生效：`_lock_for` 被调用 320 次」）：
    补丁装上了、被测代码根本没走那条路、测试因为别的原因红了——三件事凑在一起，
    「抽掉机制后必红」这个结论就什么都没证明。
    """
    _MARKER["patched"] = False
    try:
        with pytest.raises(AssertionError, match="一次都没被调用"):
            assert_bites(
                Replacement(
                    module="flint.graph.roles",
                    attr="naive_set_primary_unsafe",
                    build=_build_never_called_replacement,
                    why="构造用：装得上、走不到",
                ),
                [_case_red_only_while_patched],
            )
    finally:
        _MARKER["patched"] = False


def _always_red() -> None:
    raise AssertionError("构造用：替换之前就是红的")


def test_probe_bites_refuses_a_case_that_was_already_red() -> None:
    """替换**之前**就红的用例，替换之后的红说明不了任何事。"""
    with pytest.raises(AssertionError, match="替换之前就是红的"):
        assert_bites(
            Replacement(
                module="flint.graph.roles",
                attr="_lock_for",
                build=lambda: CountingGate(),
                why="构造用",
            ),
            [_always_red],
        )


def test_probe_bites_refuses_a_target_that_does_not_exist() -> None:
    """打歪的补丁 NEVER 悄悄通过：目标不存在就当场说出来。"""
    with pytest.raises(AssertionError, match="没有属性"):
        assert_bites(
            Replacement(
                module="flint.graph.roles",
                attr="_lock_for_typo",
                build=lambda: CountingGate(),
                why="构造用：打歪的补丁",
            ),
            [test_no_reader_holding_the_lock_ever_sees_two_primaries],
        )


def test_the_old_runtime_case_is_kept_intact() -> None:
    """acceptance⑤：旧文件保留不删。

    它证明的「`primary_count` 这把尺子认得出多主」仍然有效，删掉就把那份证据也删了。
    它不证明「线程撞上过」——本文件第一条接手的正是这一半（trace 里逐句记了两者的分工）。
    """
    assert OLD_CASE.exists(), f"旧用例被删了：{OLD_CASE}"
    text = OLD_CASE.read_text(encoding="utf-8")
    for name in (
        "def test_primary_stays_unique_under_concurrent_writes",
        "def test_the_concurrency_check_can_actually_fail",
        "naive_set_primary_unsafe",
    ):
        assert name in text, f"旧用例里找不到 {name}"
