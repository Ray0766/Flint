"""DESIGN-01：`design_generate` 没有消费者——「说一句话出一个设计」那一步空着。

## 改前的实况（`flint/jobs/dispatch.py:59` 自己写着）

```python
"design_generate": (
    "flint/design/session.py 的 delta_events / replay_window 是同步纯函数，"
    "仓里还没有 design_generate 作业的消费者。"
),
```

`flint/design/` 十三个模块、七条端点都已装配，**唯独最上游那步空着**：
提交一个 `design_generate` 作业，worker 取到它之后只会抛 `JobKindNotWired`。

## 本卡把三样接上

1. **消费者**：`flint/jobs/design_generate.py` 的 `run_design_generate`，
   经 `worker_main.build_handlers()` 进分派表，并从 `UnwiredKindReason` 移出；
2. **流式**：文字逐块出，复用 `flint/design/session.py#delta_events` 造 `DesignDelta`，
   经既有 `PgJobEventStream` 落库（seq 由库原子取号，**NEVER 由本模块自己数**）；
3. **中断可续**：重跑同一个 job 时先读回已产出的块，**从断点接着写，NEVER 从头重跑**。

## 判据为什么要有「续跑」那一条

「从头重跑」在功能上看起来是对的——最终文字一样。
但它意味着**用户已经读到的那一段会被再推一遍**，SSE 的 Last-Event-ID 补发机制
会把重复的块当成新块；更贵的是它对模型再收一次费。
所以这份验收里那一条断的是**副作用**（provider 被调了几次、seq 有没有回退），
不是最终文字。

## 网络红线

`LLMProvider` 恒由 fixture 注入（`tests/fixtures` 同款），`respx` 护栏断言**零真实出网**。
本卡不打真模型：真跑属运行时的事，判据面恒回放（工单 §5 第 7 条）。
"""
from __future__ import annotations

import inspect
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[2]
DISPATCH = REPO / "flint" / "jobs" / "dispatch.py"
WORKER_MAIN = REPO / "flint" / "jobs" / "worker_main.py"
JOB = REPO / "flint" / "jobs" / "design_generate.py"

NOW = datetime(2026, 8, 8, 2, 30, tzinfo=UTC)


# ───────────────────────── 一、分派表：移出未接线，且覆盖不倒


def test_design_generate_is_no_longer_declared_unwired() -> None:
    from flint.jobs.dispatch import WIREABLE_KINDS, UnwiredKindReason

    assert "design_generate" not in UnwiredKindReason, (
        "它还挂在「仓里没有消费者」名单里"
    )
    assert "design_generate" in WIREABLE_KINDS


def test_the_remaining_unwired_kind_stays_declared() -> None:
    """本卡只接一条。剩下的理由仍然成立，**NEVER 顺手把名单清空**——

    清空之后，「已经接了」与「忘了登记」在表里长得一模一样。

    改前这里写的是 `{"translate", "template_solidify"}`。
    v0.4.1 第 6 批的 `SLOT-03` 把 `translate` 接上了消费者
    （`flint/jobs/translate.py`），所以它离开了这份名单。
    **改的是这条判据而不是那次接线**：名单是「现在还缺谁」的真相，
    它跟着事实走；钉死一个过期的集合，只会让下一次真正的接线被判成错。
    """
    from flint.jobs.dispatch import UnwiredKindReason

    # `PERSIST-03` 把最后一条 `template_solidify` 也接上了消费者，**那张表空了**。
    # 改前这里钉的是 `{"template_solidify"}`——红的是「还剩这一条」这个事实
    # 过去了，不是有人把声明弄丢了（与本判据 docstring 记的上一次同一形状）。
    assert set(UnwiredKindReason) == set()


def test_the_dispatch_table_still_covers_the_whole_union() -> None:
    """acceptance⑤：移出之后分派表仍覆盖判别联合全部成员。"""
    from flint.jobs.dispatch import IncompleteDispatchTable, build_dispatch_table
    from flint.jobs.worker_main import WorkerDeps, build_handlers

    deps = WorkerDeps(
        dsn="postgresql://unused", redis_url="redis://unused",
        repo_root=REPO, profile=_profile(), now=NOW,
    )
    table = build_dispatch_table(build_handlers(deps))

    assert "design_generate" in table
    with pytest.raises(IncompleteDispatchTable):
        # 阴性对照：少一个 kind 必须抛——不抛的话上面那条绿说明不了任何事。
        handlers = dict(build_handlers(deps))
        handlers.pop("design_generate")
        build_dispatch_table(handlers)


def _profile() -> Any:
    from flint.domain.models import UserProfile

    fields = {f: None for f in ()}
    del fields
    sig = inspect.signature(UserProfile)
    kwargs: dict[str, Any] = {}
    for name, param in sig.parameters.items():
        if param.default is not inspect.Parameter.empty:
            continue
        kwargs[name] = _blank_for(param.annotation)
    return UserProfile(**kwargs)


def _blank_for(annotation: Any) -> Any:
    text = str(annotation)
    if "list" in text:
        return []
    if "dict" in text or "Mapping" in text:
        return {}
    if "int" in text:
        return 0
    if "float" in text:
        return 0.0
    if "bool" in text:
        return False
    return ""


# ───────────────────────── 二、缺依赖时大声失败


def test_the_handler_says_what_is_missing_and_where_it_comes_from() -> None:
    """照 `_revalidation_handler` 的既有形状：缺依赖 → 抛并写清需要什么、默认出处在哪。

    静默跳过的话，作业会「成功」而什么都没产出——那比失败更难查。
    """
    import asyncio

    from flint.jobs.worker_main import HandlerDepsMissing, WorkerDeps, build_handlers

    deps = WorkerDeps(
        dsn="postgresql://unused", redis_url="redis://unused",
        repo_root=REPO, profile=_profile(), now=NOW,
    )
    handler = build_handlers(deps)["design_generate"]

    with pytest.raises(HandlerDepsMissing) as caught:
        asyncio.run(handler("job-x", {"prompt": "一个卡片"}))

    message = str(caught.value)
    assert "design_generate_deps" in message, "没说清缺的是哪个注入面"
    assert "provider" in message, "没说清需要什么"


# ───────────────────────── 三、流式：逐块出，seq 由库取号


class _FixtureProvider:
    """fixture 回放的 provider。**它记着自己被调了几次**——续跑那条判据要看这个。"""

    def __init__(self, text: str) -> None:
        self.text = text
        self.calls: list[str] = []

    def generate(self, prompt: str, tools: Any = None) -> Any:
        from flint.domain.models import Completion

        self.calls.append(prompt)
        return Completion(text=self.text, tool_calls=[], usage={})

    def generate_structured(self, prompt: str, schema: Any, max_retries: int) -> Any:
        raise AssertionError("设计稿是自由文本，NEVER 走结构化输出那条路")


class _MemoryStream:
    """内存版事件流，接口与 `PgJobEventStream` 逐字相同（append / replay）。

    用它是为了让本文件不依赖库——**但 seq 仍然由「流」取号**，
    与真实现同一条路：那正是本卡 NEVER 自己数 seq 的地方。
    """

    def __init__(self) -> None:
        self.events: list[Any] = []

    async def append(self, job_id: str, payload: Any, ts: datetime) -> Any:
        from flint.domain.models import JobEvent

        seq = max((e.seq for e in self.events if e.job_id == job_id), default=0) + 1
        event = JobEvent(job_id=job_id, seq=seq, ts=ts, payload=payload)
        self.events.append(event)
        return event

    async def replay(self, job_id: str, after_seq: int) -> list[Any]:
        return [e for e in self.events if e.job_id == job_id and e.seq > after_seq]


SAMPLE = (
    "一张纸质卡片：底色走 --surface 并铺 --tex-paper 麻纸噪点，1px --rule 描边、--r-card 圆角、--shadow-sticker 投影、24px 内边距。顶行左边一枚贴纸标签，右边一枚状态记号。标题走 --fs-20/600/--ink，次要行 --fs-14 两行截断。脚注一条 1px 分隔线，下面是等宽数字。"
)


def _run(text: str = SAMPLE, stream: Any = None,
         provider: Any = None) -> tuple[Any, Any, Any]:
    import asyncio

    from flint.jobs.design_generate import DesignGenerateDeps, run_design_generate

    prov = provider or _FixtureProvider(text)
    events = stream or _MemoryStream()
    deps = DesignGenerateDeps(provider=prov, events=events, now=lambda: NOW)
    result = asyncio.run(run_design_generate("job-d1", {"prompt": "画个卡片"}, deps))
    return result, prov, events


def test_the_text_comes_out_in_fragments_not_in_one_lump() -> None:
    """流式：逐块出。一整块出的话，前端的「逐块出现」就只是个说法。"""
    result, _, events = _run()

    deltas = [e for e in events.events if e.payload.kind == "design_delta"]
    assert len(deltas) > 1, f"只出了 {len(deltas)} 块"
    assert "".join(d.payload.fragment for d in deltas) == result.text
    # 收尾标记也在：没有它，「推完了」与「推到一半」在日志里长得一模一样。
    assert [e for e in events.events if e.payload.kind == "status"], "没有收尾标记"


def test_no_fragment_is_empty() -> None:
    """`delta_events` 自己就拒空块——一个什么都没带的 delta 只让前端多渲染一次空。"""
    _, _, events = _run()

    for event in events.events:
        if event.payload.kind == "design_delta":
            assert event.payload.fragment != ""


def test_seq_is_monotonic_and_matches_the_payload() -> None:
    """seq 由流取号；载荷里的 seq 与事件的 seq 逐条相等。

    两者对不上时，Last-Event-ID 补发会定位错位——用户看到的是错乱的顺序。
    """
    _, _, events = _run()

    seqs = [e.seq for e in events.events]
    assert seqs == sorted(seqs) and len(set(seqs)) == len(seqs)
    for event in events.events:
        if event.payload.kind == "design_delta":
            assert event.payload.seq == event.seq


def test_the_job_never_counts_seq_by_itself() -> None:
    """源码层：本模块 NEVER 自己维护一个计数器。

    自己数的那一份迟早与库里的对不上，而对不上时**没有任何错误信号**。
    """
    code = JOB.read_text(encoding="utf-8")
    code = re.sub(r'"""[\s\S]*?"""', "", code)
    code = "\n".join(
        ln for ln in code.splitlines() if not ln.lstrip().startswith("#")
    )

    assert "seq += 1" not in code and "seq = seq + 1" not in code


# ───────────────────────── 四、中断可续：NEVER 从头重跑


def test_resuming_picks_up_where_it_stopped() -> None:
    """断线后重跑同一个 job：**已产出的块不再产一遍**。

    断的是副作用而不是最终文字：从头重跑最终文字也一样，
    但用户已经读到的那一段会被再推一遍，模型也会被再收一次费。
    """
    stream = _MemoryStream()
    _, first, _ = _run(stream=stream)
    before = [e.seq for e in stream.events]

    _, second, _ = _run(stream=stream, provider=_FixtureProvider("x"))
    after = [e.seq for e in stream.events]

    assert second.calls == [], "续跑时又调了一次模型——那就是从头重跑"
    assert after == before, f"续跑时又追加了事件：{after} vs {before}"
    assert first.calls != []


def test_resume_reads_back_through_the_shared_replay_window() -> None:
    """续跑读回用的是 `session.replay_window`，NEVER 另写一份取回逻辑。

    两份实现迟早在某个边界上分叉（`session.py` 自己的原话）。
    """
    code = JOB.read_text(encoding="utf-8")

    assert "replay_window" in code, "没复用 session.replay_window"
    assert "delta_events" in code, "没复用 session.delta_events"


def test_a_partial_run_resumes_from_the_last_fragment() -> None:
    """只产出了一半就断：续跑要从**下一块**接着写，而不是从第一块。"""
    import asyncio

    from flint.jobs.design_generate import DesignGenerateDeps, run_design_generate

    text = SAMPLE
    stream = _MemoryStream()
    provider = _FixtureProvider(text)
    deps = DesignGenerateDeps(provider=provider, events=stream, now=lambda: NOW)

    # 先跑一遍拿到全量，再把事件截掉一半模拟「推到一半断了」。
    asyncio.run(run_design_generate("job-d2", {"prompt": "画个卡片"}, deps))
    # 只留前一半的 delta，收尾标记一并去掉——那正是「推到一半断了」的形状。
    full = [e for e in stream.events
            if e.job_id == "job-d2" and e.payload.kind == "design_delta"]
    keep = full[: len(full) // 2]
    # 拷一份再塞回去：直接塞 `keep` 本身的话，第二趟的 append 会把它一起改掉，
    # 下面那条断言就会拿**续跑之后**的最后一条去比断点——绿得毫无意义。
    stream.events = list(keep)
    break_at = keep[-1].seq
    produced_before = "".join(e.payload.fragment for e in keep)

    provider2 = _FixtureProvider(text)
    deps2 = DesignGenerateDeps(provider=provider2, events=stream, now=lambda: NOW)
    result = asyncio.run(run_design_generate("job-d2", {"prompt": "画个卡片"}, deps2))

    got = "".join(
        e.payload.fragment for e in stream.events
        if e.job_id == "job-d2" and e.payload.kind == "design_delta"
    )
    assert got == text, f"续跑后拼出来的不是原文：{got!r}"
    assert got.startswith(produced_before), "续跑把已产出的那一段改写了"
    assert result.resumed_from == break_at, "没从断点接上"


# ───────────────────────── 五、网络红线：零真实出网


def test_the_job_opens_no_socket_of_its_own() -> None:
    """本模块 NEVER 自己发网络请求：模型调用恒经注入的 `LLMProvider`。

    自己发的那一条绕过所有 respx 护栏，而 CI 恒不联网（S2-7）。
    """
    code = JOB.read_text(encoding="utf-8")

    for tell in ("httpx.", "requests.", "urllib", "aiohttp", "socket."):
        assert tell not in code, f"{tell} 出现在作业里——模型调用只走注入的 provider"


def test_the_whole_run_makes_zero_real_requests() -> None:
    """respx 护栏：整条链路跑一遍，真实出网 0 次。"""
    respx = pytest.importorskip("respx")

    with respx.mock(assert_all_called=False) as router:
        _run()
        assert len(router.calls) == 0, f"跑出了真实请求：{[c.request.url for c in router.calls]}"


# ───────────────────────── 六、写得进去也读得回来

def test_the_event_store_knows_how_to_read_a_design_delta_back() -> None:
    """`design_delta` 必须在载荷表里。

    不在的话，块**写得进去、读不回来**——`_deserialize` 会在 replay 时抛
    「unknown job event payload kind」，而那正是断线重连要走的那条路。
    """
    from contracts_v04.models_v04 import DesignDelta
    from flint.jobs.events import _PAYLOAD_TYPES, _deserialize, _serialize

    assert "design_delta" in _PAYLOAD_TYPES
    payload = DesignDelta(kind="design_delta", seq=3, fragment="一段")
    assert _deserialize(_serialize(payload)) == payload


def test_the_replay_endpoint_can_now_load_a_session() -> None:
    """acceptance④：断线后 `GET /design/sessions/{job_id}/replay` 取回已产出的块。

    改前 `flint/api/app.py` 给那条端点注的是 `load_session=None`，
    于是它**一律回 404「unknown session」**——断线重连拿不回任何东西。
    """
    import asyncio

    from flint.design.session import resume_text
    from flint.jobs.design_generate import load_design_session

    _, _, stream = _run()
    loaded = asyncio.run(load_design_session("job-d1", stream))

    assert loaded is not None, "有块却回了「没有这个会话」"
    state, events = loaded
    assert resume_text(state, list(events)) == SAMPLE


def test_a_session_with_no_deltas_is_absent_not_empty() -> None:
    """一条 delta 都没有 → 「没有这个会话」，NEVER 拿一个空文本冒充「有会话但还没产出」。"""
    import asyncio

    from flint.jobs.design_generate import load_design_session

    assert asyncio.run(load_design_session("job-none", _MemoryStream())) is None


def test_the_app_no_longer_pins_the_loader_to_none() -> None:
    from pathlib import Path as _P

    app = (_P(REPO) / "flint" / "api" / "app.py").read_text(encoding="utf-8")

    assert "load_session=None" not in app, "那条端点还被钉死成恒 404"
    assert "_design_session_loader" in app
