"""JobKind → handler 分派表（ASM-02）：判别联合的每个成员都必须有一行。

## 这张表要根治什么

`harness/demo_server.py:_enqueue` 认两个 kind，其余直接 `return`。提交一个它不认的
作业，界面上看到的是「排队中」——永远。静默丢弃把失败伪装成等待，是最难查的一类缺陷。

本模块把「哪些 kind 有消费者」变成显式总表：

- **已接线**（`WIREABLE_KINDS`）：调用方注入 handler，缺一个就 `IncompleteDispatchTable`；
- **未接线**（`UnwiredKindReason`）：仓里确实还没有这个 kind 的消费者，表里照样占一行，
  被调到时抛 `JobKindNotWired` 并说明现有代码在哪、缺的是什么；
- **未知 kind**：抛 `UnknownJobKind`，同时把 job 记 failed。

三条路都会落到「作业变成 failed 且有话说」，NEVER 落到「作业一直排队」。

## 覆盖面从判别联合求出

`known_job_kinds()` 用 `typing.get_args` 读两个真契约：`flint/domain/models.py`（运行期
类型）与 `contracts_v04/models_v04.py`（v0.4 冻结件，additive 多三值）。手抄一份清单的
表在契约新增成员时仍是绿的——那正是要避免的。取并集是因为两份契约都在被引用：
`flint/jobs/runner.py` 标注用前者，`flint/i18n/name_display_job.py` 的 `translate` 出自后者。
"""
from __future__ import annotations

import importlib.util
import sys
from collections.abc import Awaitable, Callable, Mapping
from pathlib import Path
from typing import Final, get_args

from flint.domain.models import JSON, JobKind

JobHandler = Callable[[str, JSON], Awaitable[None]]
MarkFailed = Callable[[str, str], Awaitable[None]]

_V04_CONTRACT: Final[Path] = (
    Path(__file__).resolve().parents[2] / "contracts_v04" / "models_v04.py"
)

# 仓里已有 per-job 消费者、由调用方注入的 kind（ASM-03 worker 装配处注入）。
WIREABLE_KINDS: Final[tuple[str, ...]] = (
    "gate1_analysis",     # flint/jobs/gate1.py:run_gate1
    "report",             # flint/jobs/compose.py:run_compose（regenerate 形状另派）
    "proposal",           # flint/jobs/compose.py:run_compose（模板不同，同一 5 步）
    "spec_export",        # flint/jobs/spec_export.py:run_spec_export
    "daily_ingest",       # flint/jobs/ingest.py:run_daily_ingest
    "revalidation",       # flint/jobs/revalidation.py:run_revalidation（BL-07 接的）
    "pricebook_scan",     # flint/jobs/pricebook_scan.py:run_pricebook_scan（BL-08 接的）
    "design_generate",    # flint/jobs/design_generate.py:run_design_generate（DESIGN-01 接的）
    "translate",          # flint/jobs/translate.py:run_translate（SLOT-03 接的）
    "template_solidify",  # flint/jobs/template_solidify.py:run_template_solidify（PERSIST-03 接的）
)

# 仓里**还没有**消费者的 kind：每条指出现有代码在哪、缺的是什么。
# 这不是 TODO 清单，是分派表的一部分——被调到时它负责大声失败。
#
# **`PERSIST-03` 之后这张表空了**（最后一条 `template_solidify` 接上了消费者：
# `flint/jobs/template_solidify.py`）。**空了 NEVER 等于可以删**——
# 它挡的是「提交了一个没人取的作业，界面上看到『排队中』——永远」那种缺陷
# （见本文件开头）。下一个 additive 新增的 kind 在有消费者之前 MUST 先写进这里，
# 判据 `test_the_empty_unwired_table_is_still_a_live_mechanism` 守着这套机制还活着。
UnwiredKindReason: Final[Mapping[str, str]] = {}


class UnknownJobKind(ValueError):
    """收到分派表里没有的 kind。NEVER 静默丢弃——静默丢弃 = 作业永远排队。"""


class JobKindNotWired(NotImplementedError):
    """kind 在契约里，但仓里还没有它的消费者。带理由抛出，NEVER 假装跑过。"""


class IncompleteDispatchTable(ValueError):
    """分派表没盖住判别联合的全部成员（或有拼错的 key）。报错点名缺/多哪个。"""


def _v04_job_kinds() -> tuple[str, ...]:
    spec = importlib.util.spec_from_file_location("flint_models_v04", _V04_CONTRACT)
    if spec is None or spec.loader is None:      # 契约文件缺失 = 装配前提不成立
        raise FileNotFoundError(f"找不到 v0.4 冻结件：{_V04_CONTRACT}")
    module = sys.modules.get("flint_models_v04")
    if module is None:
        module = importlib.util.module_from_spec(spec)
        sys.modules["flint_models_v04"] = module
        spec.loader.exec_module(module)
    return tuple(str(k) for k in get_args(module.JobKind))


def known_job_kinds() -> frozenset[str]:
    """判别联合全部成员（两份真契约的并集，get_args 求出，NEVER 手抄）。"""
    return frozenset(str(k) for k in get_args(JobKind)) | frozenset(_v04_job_kinds())


def validate_dispatch_coverage(*, declared: set[str], known: set[str]) -> None:
    """declared 必须盖住 known，且不含 known 之外的 key。违反即抛并点名。"""
    missing = sorted(known - declared)
    extra = sorted(declared - known)
    if missing or extra:
        parts: list[str] = []
        if missing:
            parts.append(f"分派表缺这些 kind：{', '.join(missing)}")
        if extra:
            parts.append(
                f"分派表有判别联合之外的 key（拼错了？）：{', '.join(extra)}"
            )
        raise IncompleteDispatchTable("；".join(parts))


def _not_wired(kind: str, reason: str) -> JobHandler:
    async def handler(job_id: str, _payload: JSON) -> None:
        raise JobKindNotWired(
            f"作业 {job_id} 的 kind={kind} 在契约里，但仓里还没有它的消费者。{reason}"
        )

    return handler


def build_dispatch_table(
    handlers: Mapping[str, JobHandler],
) -> Mapping[str, JobHandler]:
    """把注入的 handler 与未接线声明合成总表；盖不住判别联合就抛。

    handlers 必须**恰好**覆盖 WIREABLE_KINDS：少一个是漏接线，多一个是 key 拼错——
    两种都抛 IncompleteDispatchTable 并点名。
    """
    known = set(known_job_kinds())
    declared = set(handlers) | set(UnwiredKindReason)
    validate_dispatch_coverage(declared=declared, known=known)
    table: dict[str, JobHandler] = {
        kind: _not_wired(kind, reason)
        for kind, reason in UnwiredKindReason.items()
    }
    table.update(handlers)
    return table


async def dispatch_job(
    job_id: str,
    kind: str,
    payload: JSON,
    *,
    table: Mapping[str, JobHandler],
    mark_failed: MarkFailed,
) -> None:
    """按 kind 派发。未知 kind / handler 抛错 → 先把 job 记 failed，再把错抛上去。

    先记 failed 再抛：抛出去之后 worker 侧怎么处理是它的事，但**作业状态必须已经
    离开 queued**——用户看到的是「失败并有原因」，NEVER 是「永远排队」。
    """
    handler = table.get(kind)
    if handler is None:
        error = (
            f"未知 job kind：{kind!r}（分派表里没有这一行）。"
            f"已知成员：{', '.join(sorted(table))}"
        )
        await mark_failed(job_id, error)
        raise UnknownJobKind(error)
    try:
        await handler(job_id, payload)
    except Exception as err:
        await mark_failed(job_id, f"{type(err).__name__}: {err}")
        raise
