"""DESIGN-01 验收（后端半）：design_delta 走既有事件通道 + replay 截断参数。

acceptance（tasks-v04.json#DESIGN-01）：
① delta 边到边渲染 NEVER 等整回合（前端半验）；
② **replay 截断参数生效**并在 trace 登记 §9-P3 风险。

## 为什么要截断参数

当前基线（P3 未采纳）是 **delta 全量入 replay**：断线重连时把整场对话的每一个碎片
都回放一遍。一场长对话里 delta 占事件总量的绝大部分，全量回放意味着重连那一刻
要读回成千上万条只为了拼出用户**已经看过**的文字。

截断参数（最近 N 条）不解决这个问题，它只是**把代价封顶**：重连拿最近 N 条 + 检查点，
而不是无界地读。真正的解法是 P3 的 ephemeral 位——**owner 已于 v0.4.1 采纳**
（DEF-02），行为面归 `tests/v041/test_delta_ephemeral.py`；原风险登记在
`docs/trace/DESIGN-01.md`。本文件的面不变：**基线（delta 全量入 replay）不被改坏**。

## 一条事件通道

七个新 payload 成员（design_delta 等）复用**同一条**通道（§6-H4），
NEVER 新开第二条事件流：第二条流意味着 seq 各排各的，断线重连时两条流的先后
无从判断，用户会看到工具调用出现在它产生的文字之前。
"""
from __future__ import annotations

import ast
import importlib.util
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
V04 = REPO_ROOT / "contracts_v04" / "models_v04.py"
SESSION_SRC = REPO_ROOT / "flint" / "design" / "session.py"


def _models() -> Any:
    spec = importlib.util.spec_from_file_location("models_v04", V04)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["models_v04"] = module
    spec.loader.exec_module(module)
    return module


M = _models()
NOW = datetime(2026, 8, 3, tzinfo=UTC)

from flint.design.session import (
    REPLAY_DEFAULT_LIMIT,
    delta_events,
    replay_window,
)


def _event(seq: int, fragment: str) -> Any:
    return M.JobEvent(
        job_id="job-1", seq=seq, ts=NOW,
        payload=M.DesignDelta(kind="design_delta", seq=seq, fragment=fragment),
    )


def _stream(n: int) -> list[Any]:
    return [_event(i, f"f{i}") for i in range(1, n + 1)]


# ───────────────────────── delta 走既有通道，形状不走样


def test_delta_events_are_contract_payload_members() -> None:
    """delta 是既有 JobEvent 的 payload 成员，NEVER 是另一种事件对象。"""
    events = delta_events("job-1", ["半導", "体材料", "の新工法"], start_seq=0, now=NOW)

    assert [e.payload.kind for e in events] == ["design_delta"] * 3
    assert [e.payload.fragment for e in events] == ["半導", "体材料", "の新工法"]
    assert [e.seq for e in events] == [1, 2, 3]
    # 用**包路径**导入来做 isinstance：本文件顶部那份 M 是 importlib 按文件路径
    # 单独加载的副本（v04 测试的既有写法），两个加载器下的类对象不是同一个，
    # 拿 M.JobEvent 去 isinstance 永远为假——那条红是判据错了不是实现错了。
    from contracts_v04.models_v04 import JobEvent as ContractJobEvent

    assert all(isinstance(e, ContractJobEvent) for e in events)


def test_seq_continues_from_where_the_stream_left_off() -> None:
    """seq 接着已有的排：重排会让补发定位错位，用户看到的是错乱的顺序。"""
    events = delta_events("job-1", ["a", "b"], start_seq=41, now=NOW)

    assert [e.seq for e in events] == [42, 43]
    assert [e.payload.seq for e in events] == [42, 43]


def test_empty_fragments_are_rejected() -> None:
    """空片段不入流：一个什么都没带的 delta 只会让前端多渲染一次空。"""
    with pytest.raises(ValueError):
        delta_events("job-1", ["a", "", "b"], start_seq=0, now=NOW)


def test_session_module_never_opens_a_second_stream() -> None:
    """§6-H4：不新开第二条事件流。

    第二条流意味着 seq 各排各的，断线重连时两条流的先后无从判断——
    用户会看到工具调用出现在它产生的那段文字之前。
    """
    tree = ast.parse(SESSION_SRC.read_text(encoding="utf-8"))
    classes = [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
    assert [c for c in classes if "Stream" in c or "EventBus" in c] == []
    source = SESSION_SRC.read_text(encoding="utf-8")
    for forbidden in ("CREATE TABLE", "INSERT INTO job_events", "asyncpg"):
        assert forbidden not in source


# ───────────────────────── replay 截断参数（acceptance ②）


def test_replay_window_returns_the_latest_n_not_the_first_n() -> None:
    """截断取的是**最近** N 条：取最早的 N 条等于把用户带回对话开头。"""
    window = replay_window(_stream(500), after_seq=0, limit=10)

    assert len(window) == 10
    assert [e.seq for e in window] == list(range(491, 501))


def test_replay_window_still_honours_after_seq() -> None:
    """截断不吃掉 Last-Event-ID：先按 after_seq 过滤，再取最近 N 条。"""
    window = replay_window(_stream(100), after_seq=95, limit=10)

    assert [e.seq for e in window] == [96, 97, 98, 99, 100]


def test_replay_window_keeps_order_ascending() -> None:
    """回放顺序恒为 seq 升序：倒序回放会让文字反着拼出来。"""
    window = replay_window(_stream(50), after_seq=0, limit=5)

    assert [e.seq for e in window] == sorted(e.seq for e in window)


def test_replay_window_default_limit_is_explicit() -> None:
    """默认上限是一个写死的显式值，且默认路径确实截断（不是无界）。"""
    assert REPLAY_DEFAULT_LIMIT > 0
    window = replay_window(_stream(REPLAY_DEFAULT_LIMIT + 20), after_seq=0)

    assert len(window) == REPLAY_DEFAULT_LIMIT


def test_replay_window_reports_what_it_dropped() -> None:
    """丢了多少要说出来：静默截断会让「回放不全」看起来像「后端丢了事件」。"""
    window = replay_window(_stream(300), after_seq=0, limit=10, on_truncate=None)
    dropped: list[int] = []
    replay_window(_stream(300), after_seq=0, limit=10, on_truncate=dropped.append)

    assert len(window) == 10
    assert dropped == [290]


def test_replay_window_zero_limit_is_rejected() -> None:
    """limit=0 不是「不截断」，它是「什么都不回放」——拒绝，NEVER 静默当成无界。"""
    with pytest.raises(ValueError):
        replay_window(_stream(10), after_seq=0, limit=0)


def test_p3_option_landed_on_the_event_not_on_the_payload() -> None:
    """P3 的 ephemeral 位 owner **已采纳**（v0.4.1 DEF-02），但它没落在这里。

    改这一条的原因：本条原先断的是「P3 未采纳，本轮 NEVER 实现」——
    采纳之后那句话就不再是真的，留着它等于让尺子替一个已经不成立的现状站岗。

    改成断**落点**：位加在 `JobEvent` 上，`DesignDelta` 仍是三个字段。
    这条约束仍然要守——加在载荷上，replay 过滤就得认识 11 个联合成员，
    每新增一个成员都要回来改一次过滤逻辑。

    行为面（不入 replay 日志 / 重连终态一致 / 非 ephemeral 一字不变）
    归 `tests/v041/test_delta_ephemeral.py`：DESIGN-01 的面是**基线不被改坏**。
    """
    assert not hasattr(M.DesignDelta("design_delta", 1, "x"), "ephemeral")
    assert M.JobEvent(job_id="j", seq=1, ts=NOW, payload=None).ephemeral is False

    tree = ast.parse(SESSION_SRC.read_text(encoding="utf-8"))
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    names |= {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    names |= {
        a.arg
        for f in ast.walk(tree)
        if isinstance(f, ast.FunctionDef)
        for a in [*f.args.args, *f.args.kwonlyargs]
    }
    # 采纳后这个名字**必须**出现：不出现说明那半个功能没接上，
    # 而「契约有字段、实现不认它」比两边都没有更难查。
    assert "ephemeral" in names
