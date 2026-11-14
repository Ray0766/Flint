"""DESIGN-01：设计台会话的事件构造 + replay 截断（后端半）。

## 一条事件通道（§6-H4）

`design_delta` 与另外六个新 payload 成员复用**同一条** JobEventStream，
NEVER 新开第二条流：第二条流意味着 seq 各排各的，断线重连时两条流的先后无从判断——
用户会看到工具调用出现在它产生的那段文字之前。本模块只**构造事件**，
落库与补发仍走既有 `flint/jobs/events.py`。

## 为什么要截断参数（§9-P3 的当前基线）

基线是 **delta 全量入 replay**：断线重连时把整场对话的每一个碎片都回放一遍。
一场长对话里 delta 占事件总量的绝大部分，全量回放意味着重连那一刻要读回
成千上万条，只为拼出用户**已经看过**的文字。

截断参数不解决这个问题，它**把代价封顶**：重连拿最近 N 条 + 检查点快照。

## ephemeral：真正把写入量降下来的那一半（§9-P3，owner 已采纳，DEF-02）

标了 `ephemeral=True` 的事件**只走内存，NEVER 落 replay 日志**。
位在 `JobEvent` 上而不是 `DesignDelta` 上：决定落不落库的是事件记录，
加在载荷上则 replay 过滤要认识 11 个联合成员。

**代价在检查点上还**：不落日志，重连时唯一还能拿到它的地方就是检查点快照，
所以检查点 MUST 盖住每一个 ephemeral 事件。盖不住时 `resume_text` 直接抛，
NEVER 静默返回短文字——短一截没有任何错误信号，排查会从「模型是不是没生成完」
开始，方向全错。截断上限一并保留：不落库与不封顶两条一起放松，
一个没存检查点的长会话会把内存吃光。

## 截断要说出来

丢了多少条经 `on_truncate` 报给调用方。静默截断会让「回放不全」看起来像
「后端丢了事件」——那是两种完全不同的排查方向。
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

# 回放窗口默认上限：写死的显式值。取「最近这么多条」够拼出用户眼前那一屏，
# 更早的内容在检查点快照里（重连流程 = 快照 + 续流）。
REPLAY_DEFAULT_LIMIT = 200


def delta_events(
    job_id: str,
    fragments: Sequence[str],
    *,
    start_seq: int,
    now: datetime,
    ephemeral: bool = False,
) -> list[Any]:
    """把一串文字片段构造成 `design_delta` 事件（seq 接着已有的排）。

    重排 seq 会让 Last-Event-ID 补发定位错位，用户看到的是错乱的顺序。

    `ephemeral` 默认 False：既有构造点一个字不用改，行为也一个字不变。
    默认 True 的那天，所有既存事件会**悄悄**不再落库，而「没落库」在重连之前
    看不出任何异样。标 True 的调用方 MUST 自己保证检查点盖住它们（见 `fold`）。
    """
    from contracts_v04.models_v04 import DesignDelta, JobEvent

    if any(f == "" for f in fragments):
        raise ValueError(
            "fragment NEVER 为空：一个什么都没带的 delta 只会让前端多渲染一次空"
        )
    events: list[Any] = []
    for offset, fragment in enumerate(fragments, start=1):
        seq = start_seq + offset
        events.append(
            JobEvent(
                job_id=job_id,
                seq=seq,
                ts=now,
                payload=DesignDelta(kind="design_delta", seq=seq, fragment=fragment),
                ephemeral=ephemeral,
            )
        )
    return events


class EphemeralNotCheckpointed(Exception):
    """检查点没盖住某些 ephemeral 事件——那几段文字既不在快照里也不在日志里。"""

    def __init__(self, seqs: Sequence[int]) -> None:
        super().__init__(
            f"检查点停在这些 ephemeral 事件之前，它们的文字会丢：seq {list(seqs)}。"
            "存一个盖住它们的检查点，或者不要标 ephemeral。"
        )
        self.seqs = list(seqs)


@dataclass(frozen=True)
class ResumePoint:
    """检查点快照里与流有关的那两样：已经拼好的文字 + 拼到哪个 seq。"""

    text: str
    seq: int


def persisted_events(events: Sequence[Any]) -> list[Any]:
    """入 replay 日志的那些。标了 `ephemeral` 的不进——它们只走内存。

    顺序原样保留：重排 seq 会让 Last-Event-ID 补发定位错位。
    过滤只看这一位，**NEVER 按 kind 猜**：同一个 kind 两种用法都有，
    一场闲聊的 delta 可以丢，一份正在生成的报告的 delta 丢不得。
    """
    return [e for e in events if not getattr(e, "ephemeral", False)]


def fold(state: ResumePoint, events: Sequence[Any]) -> ResumePoint:
    """把事件的碎片折进检查点状态。**不折就是丢**。

    折的是**全部** delta，不是只折 ephemeral 的：只折一半的话 `state.seq` 会停在
    最后一个 ephemeral 上，而它之前的普通事件已经被折进文字里了——续流按
    `seq > state.seq` 取，那些普通事件会被再拼一遍，重连后多出重复的一段。
    """
    text = state.text
    seq = state.seq
    for event in events:
        if event.seq <= seq:
            continue
        text += event.payload.fragment
        seq = event.seq
    return ResumePoint(text=text, seq=seq)


def unfolded_ephemeral(state: ResumePoint, events: Sequence[Any]) -> list[int]:
    """检查点没盖住的 ephemeral 事件的 seq——**每一个都是一段会丢的文字**。

    普通事件落在检查点之后是正常的（续流会补回来）；把它们也报成问题，
    等于要求每推一条就存一次检查点，那比全量入 replay 还贵。
    """
    return [e.seq for e in events if getattr(e, "ephemeral", False) and e.seq > state.seq]


def resume_text(
    state: ResumePoint,
    events: Sequence[Any],
    *,
    limit: int = REPLAY_DEFAULT_LIMIT,
    on_truncate: Callable[[int], None] | None = None,
) -> str:
    """断线重连后的文字 = 最新检查点快照 + 从当前位置续流。

    续流复用 `replay_window`（截断上限、丢弃报数、seq 过滤只有一份实现——
    两份实现迟早会在某个边界上分叉）。

    守卫只有拿到**全量**事件才看得见丢失：ephemeral 事件不落日志，事后从日志里
    查不出它曾经存在。所以调用方 MUST 在生产侧（手上还有全量）就检查。
    """
    missing = unfolded_ephemeral(state, events)
    if missing:
        raise EphemeralNotCheckpointed(missing)
    window = replay_window(
        persisted_events(events), after_seq=state.seq, limit=limit, on_truncate=on_truncate,
    )
    return state.text + "".join(e.payload.fragment for e in window)


def replay_window(
    events: Sequence[Any],
    *,
    after_seq: int,
    limit: int = REPLAY_DEFAULT_LIMIT,
    on_truncate: Callable[[int], None] | None = None,
) -> list[Any]:
    """按 Last-Event-ID 过滤后，取**最近** limit 条（seq 升序）。

    取最早的 limit 条等于把用户带回对话开头——他要看的是刚才断在哪里。
    """
    if limit <= 0:
        raise ValueError(
            "limit NEVER ≤0：0 不是「不截断」，它是「什么都不回放」"
        )
    fresh = [e for e in events if e.seq > after_seq]
    dropped = max(0, len(fresh) - limit)
    if dropped > 0 and on_truncate is not None:
        on_truncate(dropped)                 # 丢了多少要说出来
    return list(fresh[len(fresh) - min(len(fresh), limit):])
