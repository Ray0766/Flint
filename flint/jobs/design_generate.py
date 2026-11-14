"""`design_generate` 作业的消费者——「说一句话出一个设计」那一步。

> 本模块由 **v0.4.1 第 5 批的 `DESIGN-01`** 建（`docs/steward/tasks-v041-b5.json`）。
> 首行**刻意不写那个卡号**：`DESIGN-01` 在 v0.4 已经属于另一张卡
> （对话面板 + SSE 流式渲染，outputs 是 `web/design/chat-panel/` 与 `flint/design/session.py`），
> 而 `tools/check_outputs_declared.py` 按首行的卡号去查那张卡的 outputs——
> 写上去它会把本文件报成「v0.4 的 DESIGN-01 少声明了一个产物」，而那句话是假的。
> 号撞车这件事已立单：`docs/blocked/CARD-ID-COLLISION-DESIGN-01.md`。

## 改前

`flint/design/` 十三个模块、七条端点都已装配，**唯独最上游那步空着**：
`flint/jobs/dispatch.py` 自己写着「仓里还没有 `design_generate` 作业的消费者」，
提交这类作业，worker 取到之后只会抛 `JobKindNotWired`。

## 三件事，各自复用现成的那一份

| 要做的 | 复用谁 | 为什么 NEVER 自己写一份 |
|---|---|---|
| 造 `design_delta` 事件 | `flint/design/session.py#delta_events` | 它已经守着「空 fragment 直接拒」与 seq 接排 |
| 取回已产出的块 | `flint/design/session.py#replay_window` | 两份取回逻辑迟早在某个边界上分叉（那个模块自己的原话） |
| 落库并取号 | 注入的 `JobEventStream`（生产是 `PgJobEventStream`） | seq 由库原子取号；**本模块自己数的那一份对不上时没有任何错误信号** |

## 中断可续：**NEVER 从头重跑**

跑之前先 `replay` 一次，分三种情况：

1. **已经收尾**（日志里有 `status=done`）→ **一次模型都不调**，一个事件都不追加；
2. **推到一半**（有 delta 没有收尾）→ 调一次模型拿全稿，**只推还没推过的那一段**；
3. **全新**（什么都没有）→ 从头推。

第 2 种为什么还要调一次模型：本模块**手上没有上一次的全稿**（delta 落的是碎片，
拼起来只是「已经推出去的那一段」）。要接着往下写就得知道整段是什么。
但**已经推给用户的那几块 NEVER 再推一遍**——那才是「从头重跑」真正的害处：
SSE 的 Last-Event-ID 会把重复的块当成新块，用户屏上会多出一段。

**收尾标记不能省**。没有它，「推完了」与「推到一半」在日志里长得一模一样，
第 1 种情况就只能靠猜文字长度来判——而本模块拿不到「设计稿应该多长」这个数，
猜出来的那个数会在某一天把半份稿子当成全稿。

## 网络

模型调用恒经注入的 `LLMProvider`（`contracts/protocols.py:100`）。
本模块不 import 任何 HTTP 客户端：自己发的那一条会绕过所有 respx 护栏，
而 CI 恒不联网（S2-7）。运行时用哪个模型是**注入方**的事。
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from flint.design.session import delta_events, replay_window
from flint.domain.models import StatusChanged

# 一块多长。太碎会把一次生成压成上百条事件（每条一次库写），太整则「逐块出现」名存实亡。
# 取值理由：素材那份设计稿的一句话约 20~40 字，一块一句读起来是连续的。
FRAGMENT_SIZE = 24


class LLMProviderLike(Protocol):
    """只用到 `generate`。设计稿是自由文本，NEVER 走 `generate_structured`——

    那条路是给 verdict 那类结构化输出的，它会把一份设计稿硬塞进一个 schema。
    """

    def generate(self, prompt: str, tools: Any) -> Any: ...


class JobEventStreamLike(Protocol):
    """`PgJobEventStream` 的那两个方法。注入而不是直接 import，测试才好回放。"""

    async def append(self, job_id: str, payload: Any, ts: datetime) -> Any: ...

    async def replay(self, job_id: str, after_seq: int) -> list[Any]: ...


@dataclass
class DesignGenerateDeps:
    provider: LLMProviderLike
    events: JobEventStreamLike
    now: Callable[[], datetime]
    #: 库连接串。`DESIGN-STATE`：**收尾要把 `jobs.state` 也推到 `done`**。
    #:
    #: 改前这个 dataclass 里**没有任何库句柄**——那正是这一族当初只写事件流的
    #: 结构原因：手上没有连接，那一半就写不了。
    #: 于是「作业跑完没有」有了两个真相：事件流说 `done`，`jobs.state` 停在 `queued`
    #: （`SMOKE-01` 2026-08-11 实测：192 个片段的设计稿产出了，屏上转圈不停）。
    #:
    #: `None` = **这一路没有库**（离线判据用）：那时只写事件流，
    #: 且**照实不推 `jobs.state`**——NEVER 假装推过了。
    dsn: str | None = None


@dataclass
class DesignGenerateReport:
    job_id: str
    text: str
    fragments: int
    #: 从第几个 seq 接着写的。0 = 全新开始。
    resumed_from: int
    #: 这一趟有没有调模型。已经收尾的作业恒 False。
    called_model: bool


def _chunks(text: str, size: int) -> list[str]:
    """切块。空块不产出——`delta_events` 会直接拒，那道拒绝是对的。"""
    return [text[i:i + size] for i in range(0, len(text), size) if text[i:i + size]]


def _kind_of(event: Any) -> str:
    kind: str = getattr(event.payload, "kind", "")
    return kind


def _is_done(events: list[Any]) -> bool:
    return any(
        _kind_of(e) == "status" and getattr(e.payload, "state", "") == "done"
        for e in events
    )


async def run_design_generate(
    job_id: str, payload: dict[str, Any], deps: DesignGenerateDeps,
) -> DesignGenerateReport:
    """跑一次设计生成。已经跑过的部分**不再跑一遍**。"""
    prompt = str(payload.get("prompt", ""))
    if not prompt:
        raise ValueError(
            f"作业 {job_id} 没有 prompt：一句话都没有的「说一句话出一个设计」"
            "只会让模型自由发挥，而产出的东西没有任何人要求过"
        )

    # ── 先看断点。**这一步在发请求之前**：已经收尾的作业一次模型都不该再调。
    history = list(await deps.events.replay(job_id, 0))
    deltas = [e for e in history if _kind_of(e) == "design_delta"]
    # 取回走 `replay_window`（与 SSE 补发同一条路），NEVER 另写一份过滤。
    window = replay_window(deltas, after_seq=0, limit=max(1, len(deltas))) if deltas else []
    produced = "".join(e.payload.fragment for e in window)
    resumed_from = window[-1].seq if window else 0

    if _is_done(history):
        return DesignGenerateReport(
            job_id=job_id, text=produced, fragments=len(deltas),
            resumed_from=resumed_from, called_model=False,
        )

    completion = deps.provider.generate(prompt, None)
    full = str(completion.text)
    if not full.startswith(produced):
        # 模型这一趟给的稿子与已经推出去的那一段对不上。**照实抛**——
        # 悄悄接上去会让用户读到一段前后不接的文字，而屏上没有任何异常信号。
        raise ValueError(
            f"作业 {job_id} 续跑失败：模型这一趟的稿子与已推出的 "
            f"{len(produced)} 字对不上。NEVER 把两段拼起来充数"
        )

    now = deps.now()
    pending = _chunks(full[len(produced):], FRAGMENT_SIZE)
    # seq 由**流**取号：这里只给 `start_seq` 一个起点，事件落库时由流定号，
    # 两者对不上就是 bug——判据逐条比对 `payload.seq == event.seq`。
    for event in delta_events(job_id, pending, start_seq=resumed_from, now=now):
        await deps.events.append(job_id, event.payload, now)
    # 收尾标记：没有它，「推完了」与「推到一半」在日志里长得一模一样。
    #
    # `DESIGN-STATE`：这一句**只写了两个记号里的一个**。
    # 另一个（`jobs.state`）由 `_finish` 补上，走的是与 compose / gate1
    # **同一个** `flint/jobs/state.py#enter_state`——
    # NEVER 在这里另写一套推进状态的代码（owner 逐字：
    # 两套推进器会让「作业跑完没有」再长出第三个真相）。
    await _finish(deps, job_id, now)

    return DesignGenerateReport(
        job_id=job_id, text=full, fragments=len(deltas) + len(pending),
        resumed_from=resumed_from, called_model=True,
    )


async def load_design_session(
    job_id: str, events: JobEventStreamLike,
) -> tuple[Any, list[Any]] | None:
    """给 `GET /design/sessions/{job_id}/replay` 的取数件（`design.py` 的 `SessionLoader`）。

    回 `(ResumePoint, events)`。**检查点从零起**：本仓还没有设计会话的检查点存储，
    所以快照是空的、全部文字都从事件里续出来——`resume_text` 正好是这么算的
    （`state.text + 续流`）。

    这样接的代价说清楚：事件多到超过 `REPLAY_DEFAULT_LIMIT` 时会被截断，
    而截断多少 `replay_window` 会报出来。真检查点建成之后，把这里的 `ResumePoint("", 0)`
    换成最新快照即可，**调用方一行都不用改**。

    一条 delta 都没有 → 回 `None`：那是「没有这个会话」，
    与「有会话但还没产出」是两件事，NEVER 拿一个空文本冒充后者。
    """
    from flint.design.session import ResumePoint

    history = list(await events.replay(job_id, 0))
    # **只交出 delta**：同一个 job 的日志里还有状态事件（收尾标记就是一条），
    # 而 `resume_text` 会对每一条取 `.payload.fragment`——把状态事件也交出去，
    # 那一行会当场 AttributeError。会话的事件流说的是**设计文字**这一条流。
    stream = [e for e in history if _kind_of(e) == "design_delta"]
    if not stream:
        return None
    return ResumePoint(text="", seq=0), stream


async def _finish(deps: DesignGenerateDeps, job_id: str, now: datetime) -> None:
    """把 `jobs.state` 推到 `done`——**与 compose / gate1 同一条路**。

    `enter_state` 幂等（已经是 `done` 就什么都不做），所以续跑重复调它是安全的。

    `dsn is None` 时**照实什么都不做**：那一路没有库，
    NEVER 假装推过了——假装的话，离线判据会以为这一半被覆盖到了。
    """
    if deps.dsn is None:
        # 这一路**没有库**：只写事件流那一半，并且**照实不推 `jobs.state`**。
        # **NEVER 假装推过了**——假装的话，离线判据会以为这一半被覆盖到了，
        # 而真栈上它其实没跑。
        #
        # 这个分支本身就是本卡要治的病的形状：`DesignGenerateDeps` 改前
        # 没有任何库句柄，于是那一半写不了，「作业跑完没有」就有了两个答案。
        await deps.events.append(
            job_id, StatusChanged(kind="status", state="done"), now)
        return
    import asyncpg

    from flint.jobs.state import enter_state

    conn = await asyncpg.connect(deps.dsn)
    try:
        await enter_state(conn, deps.events, job_id, "done", now)
    finally:
        await conn.close()
