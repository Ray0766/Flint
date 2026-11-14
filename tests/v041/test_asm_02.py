"""ASM-02：JobKind → handler 分派表（覆盖判别联合全部成员）。

缺陷背景：全仓没有一处把 `JobKind` 的每个成员都映到一个消费者。demo 的
`harness/demo_server.py:_enqueue` 只认 `gate1_analysis` 与 `report`，其余 kind 直接
`return`——用户提交后作业永远停在 queued，界面上看不出任何错误。本卡把「哪些 kind 有
消费者、哪些没有」变成**代码里的显式总表**，并让未知/未接线两种情况都大声失败。

覆盖面 NEVER 手抄：由 `typing.get_args` 从两个真契约文件求出（`flint/domain/models.py`
是运行期类型，`contracts_v04/models_v04.py` 是 v0.4 冻结件，后者 additive 多三值）。
手抄的清单不会跟着契约变——契约加一个 kind，手抄的表还是绿的。
"""
from __future__ import annotations

import ast
import asyncio
import importlib.util
import inspect
import sys
from pathlib import Path
from typing import get_args

import pytest

from flint.domain.models import JSON
from flint.jobs.dispatch import (
    WIREABLE_KINDS,
    IncompleteDispatchTable,
    JobKindNotWired,
    UnknownJobKind,
    UnwiredKindReason,
    build_dispatch_table,
    known_job_kinds,
    validate_dispatch_coverage,
)

REPO = Path(__file__).resolve().parents[2]


def _load_v04_contract() -> object:
    spec = importlib.util.spec_from_file_location(
        "models_v04_asm02", REPO / "contracts_v04" / "models_v04.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["models_v04_asm02"] = module
    spec.loader.exec_module(module)
    return module


def _kinds_from_real_contracts() -> set[str]:
    from flint.domain import models as domain_models
    v04 = _load_v04_contract()
    return set(get_args(domain_models.JobKind)) | set(get_args(v04.JobKind))  # type: ignore[attr-defined]


async def _noop(_job_id: str, _payload: JSON) -> None:
    return None


def _full_handlers() -> dict[str, object]:
    return {kind: _noop for kind in WIREABLE_KINDS}


class _Recorder:
    def __init__(self) -> None:
        self.failed: list[tuple[str, str]] = []

    async def __call__(self, job_id: str, error: str) -> None:
        self.failed.append((job_id, error))


# ── acceptance ①：覆盖面由 get_args 从真件求出，NEVER 手抄 ──────────────

def test_known_kinds_equal_the_union_of_both_real_contracts() -> None:
    assert known_job_kinds() == _kinds_from_real_contracts()


def test_known_kinds_are_derived_by_get_args_not_a_literal_list() -> None:
    """AST 面：模块里真的调了 `get_args`，而不是抄了一份字符串清单。"""
    from flint.jobs import dispatch

    tree = ast.parse(inspect.getsource(dispatch))
    called = {
        node.func.id for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert "get_args" in called, "覆盖面不是从判别联合求出的"


def test_every_contract_kind_has_a_row_in_the_table() -> None:
    table = build_dispatch_table(_full_handlers())  # type: ignore[arg-type]
    assert set(table) == _kinds_from_real_contracts()
    assert len(table) == 10, f"契约现有 10 个 kind，表里 {len(table)} 行"


# ── acceptance ②：缺任一成员即红，且报错点名缺哪个 ──────────────────────

def test_missing_wireable_handler_is_red_and_names_it() -> None:
    handlers = _full_handlers()
    handlers.pop("report")
    with pytest.raises(IncompleteDispatchTable) as err:
        build_dispatch_table(handlers)  # type: ignore[arg-type]
    assert "report" in str(err.value), f"报错没点名缺哪个：{err.value}"


def test_empty_handlers_names_every_missing_kind() -> None:
    with pytest.raises(IncompleteDispatchTable) as err:
        build_dispatch_table({})
    msg = str(err.value)
    for kind in WIREABLE_KINDS:
        assert kind in msg, f"报错漏点名 {kind}：{msg}"


def test_a_new_contract_member_nobody_declared_is_red_and_named() -> None:
    """契约将来加一个 kind 而没人声明它 → 覆盖校验红并点名（这条就是防手抄的闸）。"""
    known = _kinds_from_real_contracts() | {"brand_new_kind"}
    with pytest.raises(IncompleteDispatchTable) as err:
        validate_dispatch_coverage(declared=_kinds_from_real_contracts(), known=known)
    assert "brand_new_kind" in str(err.value)


def test_coverage_passes_when_everything_is_declared() -> None:
    known = _kinds_from_real_contracts()
    validate_dispatch_coverage(declared=known, known=known)


def test_typo_in_a_handler_key_is_rejected_and_named() -> None:
    handlers = _full_handlers()
    handlers["gate1_analysiss"] = _noop
    with pytest.raises(IncompleteDispatchTable) as err:
        build_dispatch_table(handlers)  # type: ignore[arg-type]
    assert "gate1_analysiss" in str(err.value)


# ── acceptance ③：未知 kind → 抛错 + job 记 failed，NEVER 静默丢弃 ──────

def test_unknown_kind_raises_and_marks_the_job_failed() -> None:
    from flint.jobs.dispatch import dispatch_job

    table = build_dispatch_table(_full_handlers())  # type: ignore[arg-type]
    recorder = _Recorder()
    with pytest.raises(UnknownJobKind) as err:
        asyncio.run(dispatch_job(
            "job-1", "no_such_kind", {}, table=table, mark_failed=recorder,
        ))
    assert "no_such_kind" in str(err.value)
    assert recorder.failed and recorder.failed[0][0] == "job-1", (
        "未知 kind 被静默丢弃——用户会看到作业永远排队"
    )
    assert "no_such_kind" in recorder.failed[0][1]


def test_unknown_kind_never_reaches_any_handler() -> None:
    seen: list[str] = []

    async def _spy(job_id: str, _payload: JSON) -> None:
        seen.append(job_id)

    table = build_dispatch_table({k: _spy for k in WIREABLE_KINDS})  # type: ignore[arg-type]
    with pytest.raises(UnknownJobKind):
        asyncio.run(_dispatch(table, "job-2", "no_such_kind"))
    assert seen == []


async def _dispatch(table: object, job_id: str, kind: str) -> None:
    from flint.jobs.dispatch import dispatch_job

    async def _sink(_j: str, _e: str) -> None:
        return None

    await dispatch_job(job_id, kind, {}, table=table, mark_failed=_sink)  # type: ignore[arg-type]


# ── 已接线 / 未接线两条路 ────────────────────────────────────────────

def test_wired_handler_receives_job_id_and_payload() -> None:
    from flint.jobs.dispatch import dispatch_job

    seen: list[tuple[str, JSON]] = []

    async def _spy(job_id: str, payload: JSON) -> None:
        seen.append((job_id, payload))

    handlers = _full_handlers()
    handlers["report"] = _spy
    table = build_dispatch_table(handlers)  # type: ignore[arg-type]
    recorder = _Recorder()
    asyncio.run(dispatch_job(
        "job-3", "report", {"project_id": "p-1"}, table=table, mark_failed=recorder,
    ))
    assert seen == [("job-3", {"project_id": "p-1"})]
    assert recorder.failed == [], "成功的作业不该被记 failed"


def test_unwired_kind_raises_with_a_reason_and_marks_failed() -> None:
    """未接线的 kind：显式抛错并说明「消费者在哪儿还没有」，NEVER 静默排队。"""
    # 例子取**当下仍未接线**的那一族里的第一个，而不是写死某个 kind：
    # BL-07/BL-08 各接走一个（revalidation / pricebook_scan）之后，写死的例子
    # 会随接线进度变红——而那种红说的是「例子过期了」，不是「大声失败坏了」。
    # `PERSIST-03` 把最后一条也接走了，**那张表现在是空的**。
    # 「取当下仍未接线的第一个」这个写法本来就是为了不被接线进度带红，
    # 而它没预料到表会被清空（`min({})` 当场抛 ValueError）。
    # 改成造一条**本判据自己的**未接线声明：量的是「大声失败」这套机制还活着，
    # 而那与「今天恰好还剩几条没接」本来就是两件事。
    from flint.jobs.dispatch import _not_wired, dispatch_job
    unwired_example = "some_future_kind"
    table = {
        **build_dispatch_table(_full_handlers()),  # type: ignore[arg-type]
        unwired_example: _not_wired(
            unwired_example, "仓里还没有它的消费者。"),
    }
    recorder = _Recorder()
    with pytest.raises(JobKindNotWired) as err:
        asyncio.run(dispatch_job(
            "job-4", unwired_example, {}, table=table, mark_failed=recorder,
        ))
    msg = str(err.value)
    assert unwired_example in msg
    assert len(msg) > len(unwired_example) + 10, f"未接线报错没给出理由：{msg}"
    assert recorder.failed and recorder.failed[0][0] == "job-4"


def test_every_unwired_kind_carries_a_concrete_reason() -> None:
    """未接线清单不是一句「以后再说」：每条都要指出现有代码在哪、缺的是什么。"""
    declared = set(WIREABLE_KINDS) | set(UnwiredKindReason)
    assert declared == _kinds_from_real_contracts()
    for kind, reason in UnwiredKindReason.items():
        assert len(reason) >= 20, f"{kind} 的未接线理由太短：{reason}"
        assert ".py" in reason, f"{kind} 的未接线理由没指向具体文件：{reason}"


def test_handler_failure_marks_failed_and_reraises() -> None:
    """handler 自己炸了也要记 failed——否则作业同样停在半路没人知道。"""
    from flint.jobs.dispatch import dispatch_job

    async def _boom(_job_id: str, _payload: JSON) -> None:
        raise RuntimeError("下游炸了")

    handlers = _full_handlers()
    handlers["daily_ingest"] = _boom
    table = build_dispatch_table(handlers)  # type: ignore[arg-type]
    recorder = _Recorder()
    with pytest.raises(RuntimeError, match="下游炸了"):
        asyncio.run(dispatch_job(
            "job-5", "daily_ingest", {}, table=table, mark_failed=recorder,
        ))
    assert recorder.failed and recorder.failed[0][0] == "job-5"
    assert "下游炸了" in recorder.failed[0][1]
