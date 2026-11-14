"""DEF-02：`design_delta` 的 ephemeral 语义（§9-P3，owner 已采纳）。

## 采纳前后差在哪

采纳前（DESIGN-01 基线）：delta **全量入 replay**。一场长对话里 delta 占事件总量的
绝大部分，断线重连要读回成千上万条，只为拼出用户**已经看过**的文字。
截断参数把代价封顶，但没有消掉写入量。

采纳后（本卡）：事件可以标 `ephemeral=True` —— **只走内存，NEVER 落 replay 日志**。
换来写入量下降，代价是断线重连拿不到它们。

## 代价要还，还的地方是检查点

ephemeral 的碎片不落日志，重连时唯一还能拿到它的地方是**检查点快照**。
所以本卡的主约束是一句话：**检查点必须盖住每一个 ephemeral 事件**。

盖不住会发生什么很具体：重连后的文字比不断线时**短一截**，而短的那截没有任何
错误信号——用户看到的是一段莫名其妙断掉的话。所以盖不住时直接抛
（`EphemeralNotCheckpointed`），NEVER 静默返回短文字。

## 位在事件上，不在载荷上

`ephemeral` 加在 `JobEvent` 上，不加在 `DesignDelta` 上。理由：**决定落不落库的是
事件记录，不是载荷内容**——加在载荷上，replay 过滤就得认识 11 个联合成员，
每新增一个成员都要回来改一次过滤逻辑。

## 走 additive 通道

字段只进 `contracts_v04/models_v04.py`（新字段带默认值），冻结件
`flint/domain/models.py` **一字不动**——那也意味着落库那一侧（`flint/jobs/events.py`
用的是冻结件的 `JobEvent`）本卡接不上，如实登记在 trace §8。
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from flint.design.session import (
    REPLAY_DEFAULT_LIMIT,
    EphemeralNotCheckpointed,
    ResumePoint,
    delta_events,
    fold,
    persisted_events,
    replay_window,
    resume_text,
    unfolded_ephemeral,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
V04 = REPO_ROOT / "contracts_v04" / "models_v04.py"
FROZEN = REPO_ROOT / "flint" / "domain" / "models.py"
NOW = datetime(2026, 8, 4, 12, 0, tzinfo=UTC)


def _models() -> Any:
    spec = importlib.util.spec_from_file_location("models_v04_def02", V04)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["models_v04_def02"] = module
    spec.loader.exec_module(module)
    return module


M = _models()

FRAGMENTS = ["从", "前", "有", "座", "山"]


def _stream(*, ephemeral: bool = False) -> list[Any]:
    return delta_events("job-1", FRAGMENTS, start_seq=0, now=NOW, ephemeral=ephemeral)


# ───────────────────────── 位加在哪、加在谁的副本上


def test_the_bit_is_on_the_event_not_on_the_payload() -> None:
    """`ephemeral` 在 `JobEvent` 上，`DesignDelta` 上没有。

    决定落不落库的是**事件记录**，不是载荷内容。加在载荷上，replay 过滤就得
    认识 11 个联合成员，每新增一个成员都要回来改一次过滤——而过滤逻辑
    与「这条载荷是什么」本来无关。
    """
    event = M.JobEvent(
        job_id="j", seq=1, ts=NOW,
        payload=M.DesignDelta(kind="design_delta", seq=1, fragment="x"),
    )

    assert hasattr(event, "ephemeral")
    assert not hasattr(M.DesignDelta("design_delta", 1, "x"), "ephemeral")


def test_the_default_is_false_so_every_old_call_site_is_unchanged() -> None:
    """默认 False：既有构造点一个字不用改，行为也一个字不变。

    默认 True 的那天，所有既存事件会**悄悄**不再落库——而「没落库」在重连之前
    看不出任何异样。
    """
    assert M.JobEvent(job_id="j", seq=1, ts=NOW, payload=None).ephemeral is False
    assert all(e.ephemeral is False for e in _stream())


def test_the_frozen_contract_is_untouched() -> None:
    """冻结件 `flint/domain/models.py` **一字不动**——加字段只走 additive 副本。

    这条不是形式主义：`flint/jobs/events.py` 落库用的正是冻结件那个 `JobEvent`，
    冻结件一动，落库那侧就跟着动，而那超出本卡的面（trace §8 登记）。
    """
    frozen_src = FROZEN.read_text(encoding="utf-8")
    start = frozen_src.index("class JobEvent")
    assert "ephemeral" not in frozen_src[start:start + 400]


def test_check_frozen_additive_passes_on_both_files() -> None:
    """acceptance①：additive 双通过（models 与 protocols 各一次）。"""
    for base, v04 in (
        ("flint/domain/models.py", "contracts_v04/models_v04.py"),
        ("contracts/protocols.py", "contracts_v04/protocols_v04.py"),
    ):
        done = subprocess.run(
            [sys.executable, "tools/check_frozen_additive.py", base, v04],
            cwd=REPO_ROOT, capture_output=True, text=True, encoding="utf-8", check=False,
        )
        assert done.returncode == 0, f"{v04}\n{done.stdout}\n{done.stderr}"


# ───────────────────────── 不入 replay 日志


def test_an_ephemeral_event_never_enters_the_replay_log() -> None:
    """acceptance①正题：标了 ephemeral 的一条都不落。"""
    assert persisted_events(_stream(ephemeral=True)) == []


def test_a_plain_event_is_persisted_unchanged() -> None:
    """阴性对照：没标的照常全落，**连顺序都不动**。"""
    events = _stream()

    assert persisted_events(events) == events


def test_the_mark_is_explicit_never_inferred_from_the_kind() -> None:
    """按 `kind == "design_delta"` 猜是错的：**没标的 design_delta 照常入日志**。

    按 kind 猜等于把「这类事件通常不重要」写死进过滤器。真实场景里同一个 kind
    两种用法都有：一场闲聊的 delta 可以丢，一份正在生成的报告的 delta 丢不得。
    """
    events = _stream()
    assert all(e.payload.kind == "design_delta" for e in events)

    assert persisted_events(events) == events


def test_a_mixed_stream_keeps_only_the_unmarked_ones() -> None:
    """混流：标的滤掉、没标的原样留下，seq **NEVER 重排**。

    重排 seq 会让 Last-Event-ID 补发定位错位——用户看到的是错乱的顺序。
    """
    plain = delta_events("job-1", ["a", "b"], start_seq=0, now=NOW)
    marked = delta_events("job-1", ["c"], start_seq=2, now=NOW, ephemeral=True)
    tail = delta_events("job-1", ["d"], start_seq=3, now=NOW)

    kept = persisted_events([*plain, *marked, *tail])

    assert [e.seq for e in kept] == [1, 2, 4]
    assert [e.payload.fragment for e in kept] == ["a", "b", "d"]


# ───────────────────────── 代价还在检查点上


def test_folding_moves_the_fragments_into_the_snapshot() -> None:
    """`fold` 把碎片折进检查点状态：文字接上、seq 推到最后一条。"""
    state = fold(ResumePoint(text="", seq=0), _stream(ephemeral=True))

    assert state.text == "从前有座山"
    assert state.seq == 5


def test_folding_covers_both_kinds_never_only_the_ephemeral_ones() -> None:
    """折的是**全部** delta，不是只折 ephemeral 的。

    只折 ephemeral 的那天，`state.seq` 会停在最后一个 ephemeral 上，而它之前的
    普通事件已经被折进文字里了——续流按 `seq > state.seq` 取，那些普通事件
    会被**再拼一遍**。重连后的文字里会多出重复的一段。
    """
    plain = delta_events("job-1", ["a"], start_seq=0, now=NOW)
    marked = delta_events("job-1", ["b"], start_seq=1, now=NOW, ephemeral=True)

    state = fold(ResumePoint(text="", seq=0), [*plain, *marked])

    assert (state.text, state.seq) == ("ab", 2)


def test_an_ephemeral_event_past_the_checkpoint_is_named() -> None:
    """检查点没盖住的 ephemeral 事件要**逐个点名**——每一个都是一段会丢的文字。"""
    events = _stream(ephemeral=True)
    covered = ResumePoint(text="从前", seq=2)

    assert unfolded_ephemeral(covered, events) == [3, 4, 5]


def test_a_covered_stream_reports_nothing() -> None:
    """盖住了就是空清单（阴性对照）。"""
    events = _stream(ephemeral=True)

    assert unfolded_ephemeral(fold(ResumePoint("", 0), events), events) == []


def test_a_persisted_event_past_the_checkpoint_is_not_a_problem() -> None:
    """普通事件在检查点之后是**正常**的——续流会把它们补回来。

    把它们也报成问题，等于要求每推一条就存一次检查点，那比全量入 replay 还贵。
    """
    assert unfolded_ephemeral(ResumePoint("", 0), _stream()) == []


# ───────────────────────── 重连：快照 + 续流，终态一致


def test_the_text_after_a_reconnect_equals_the_uninterrupted_one() -> None:
    """acceptance②主证：**重连后终态与不断线一致**。

    不断线 = 把每个碎片按到达顺序拼起来。
    重连   = 最新检查点快照 + 从当前位置续流（既有「快照+续传」流程）。
    """
    plain = delta_events("job-1", ["从", "前"], start_seq=0, now=NOW)
    marked = delta_events("job-1", ["有", "座"], start_seq=2, now=NOW, ephemeral=True)
    tail = delta_events("job-1", ["山"], start_seq=4, now=NOW)
    all_events = [*plain, *marked, *tail]

    uninterrupted = "".join(e.payload.fragment for e in all_events)

    # 生产侧：推到第 4 条时存了检查点（盖住了两条 ephemeral）
    checkpoint = fold(ResumePoint("", 0), all_events[:4])
    # 消费侧：断线重连只拿得到检查点 + 日志里剩下的
    reconnected = resume_text(checkpoint, persisted_events(all_events))

    assert reconnected == uninterrupted == "从前有座山"


def test_dropping_without_folding_would_lose_text() -> None:
    """反证：**不折就是丢**。这一条证明 `fold` 不是装饰。

    检查点停在 ephemeral 之前 → 那两段文字既不在快照里、也不在日志里。
    此时 NEVER 静默返回短文字：短一截没有任何错误信号，用户看到的是
    一段莫名其妙断掉的话，而排查会从「模型是不是没生成完」开始——方向全错。
    """
    plain = delta_events("job-1", ["从", "前"], start_seq=0, now=NOW)
    marked = delta_events("job-1", ["有", "座"], start_seq=2, now=NOW, ephemeral=True)
    tail = delta_events("job-1", ["山"], start_seq=4, now=NOW)
    all_events = [*plain, *marked, *tail]

    stale = fold(ResumePoint("", 0), plain)          # 检查点没盖住 ephemeral

    with pytest.raises(EphemeralNotCheckpointed) as err:
        resume_text(stale, all_events)

    assert "3" in str(err.value) and "4" in str(err.value), "要点名是哪几条丢了"


def test_the_guard_needs_the_full_stream_not_the_persisted_one() -> None:
    """守卫只有拿到**全量**事件才看得见丢失——只拿日志那份是看不见的。

    这正是这条缝阴险的地方：ephemeral 事件不落日志，事后从日志里
    **查不出它曾经存在**。所以本条把「传日志那份 → 静默放行」钉成现状：
    调用方 MUST 在生产侧（手上还有全量）就检查。
    """
    plain = delta_events("job-1", ["从", "前"], start_seq=0, now=NOW)
    marked = delta_events("job-1", ["有"], start_seq=2, now=NOW, ephemeral=True)
    stale = fold(ResumePoint("", 0), plain)

    assert resume_text(stale, persisted_events([*plain, *marked])) == "从前"


def test_resume_reuses_the_existing_replay_window() -> None:
    """acceptance②：**复用**既有「快照+续传」，NEVER 另起一条路。

    另起一条意味着截断上限、丢弃报数、seq 过滤各有一份实现，
    而两份实现迟早会在某个边界上分叉。
    """
    calls: list[int] = []
    events = delta_events("job-1", [str(i) for i in range(10)], start_seq=0, now=NOW)

    text = resume_text(ResumePoint("", 3), events, limit=4, on_truncate=calls.append)

    assert text == "6789", "只取最近 4 条（replay_window 的口径）"
    assert calls == [3], "丢了几条要说出来——静默截断会被读成后端丢事件"


def test_resume_from_an_empty_snapshot_is_the_whole_stream() -> None:
    """没有检查点（seq=0）就是从头拼——首次连接与重连走的是同一条路。"""
    assert resume_text(ResumePoint("", 0), _stream()) == "从前有座山"


# ───────────────────────── acceptance③：非 ephemeral 的 replay 行为一字不变


def test_replay_window_is_byte_identical_for_a_plain_stream() -> None:
    """阴性对照：全是普通事件时，过一遍 `persisted_events` 与不过**完全一样**。

    「新功能只在打了标的路径上生效」是本卡对既有行为的全部承诺。
    """
    events = _stream()

    before = replay_window(events, after_seq=1, limit=3)
    after = replay_window(persisted_events(events), after_seq=1, limit=3)

    assert before == after
    assert [e.seq for e in after] == [3, 4, 5]


def test_the_truncation_report_still_fires_unchanged() -> None:
    """截断报数的口径没动（DESIGN-01 的既有断言在本卡之后仍然成立）。"""
    dropped: list[int] = []
    events = delta_events("job-1", [str(i) for i in range(10)], start_seq=0, now=NOW)

    replay_window(persisted_events(events), after_seq=0, limit=2, on_truncate=dropped.append)

    assert dropped == [8]


def test_zero_limit_is_still_rejected() -> None:
    """`limit=0` 仍然是拒绝——本卡没有借着加功能松掉既有的门。"""
    with pytest.raises(ValueError):
        replay_window(persisted_events(_stream()), after_seq=0, limit=0)


def test_the_default_limit_is_the_same_number() -> None:
    """默认上限还是那个数：ephemeral 不是「可以不要截断了」的理由。

    两条一起放松（不落库 + 不封顶）时，一个没存检查点的长会话会把内存吃光。
    """
    assert REPLAY_DEFAULT_LIMIT == 200


# ───────────────────────── 一条通道


def test_ephemeral_does_not_open_a_second_stream() -> None:
    """§6-H4：ephemeral 事件仍走**同一条**通道，NEVER 新开第二条流。

    第二条流意味着 seq 各排各的，断线重连时两条流的先后无从判断——
    用户会看到工具调用出现在它产生的那段文字之前。
    """
    import inspect

    from flint.design import session

    source = inspect.getsource(session)
    code = "\n".join(
        line for line in source.split("\n") if not line.lstrip().startswith("#")
    )
    for forbidden in ("second_stream", "EphemeralStream", "ephemeral_seq"):
        assert forbidden not in code, f"另起了一条流：{forbidden}"

    mixed = [
        *delta_events("job-1", ["a"], start_seq=0, now=NOW),
        *delta_events("job-1", ["b"], start_seq=1, now=NOW, ephemeral=True),
        *delta_events("job-1", ["c"], start_seq=2, now=NOW),
    ]
    assert [e.seq for e in mixed] == [1, 2, 3], "两类事件在同一条 seq 上排队"
