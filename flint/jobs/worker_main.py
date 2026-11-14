"""arq worker 进程装配（ASM-03）：让提交的作业真的有人跑。

## 缺陷背景

`flint/jobs/runner.py` 的 `EnqueueHook` 从 M1-033 起就是可注入的，但全仓没有一处把它
接到真队列，也没有任何进程消费组稿作业（`harness/demo_seed_report.py:6` 自述 demo 的
enqueue 只接 `gate1_analysis`）。于是提交一份报告 → 作业进 jobs 表 → 永远 queued。

本模块补的就是这一段：`build_enqueue_hook` 把提交推进 arq 队列，`build_worker` 起一个
消费它的 worker，派发经 ASM-02 的 `flint/jobs/dispatch.py` 总表。

## 不新写 runner，不新增依赖

`flint/jobs/runner.py` 一字未改（它本来就可注入）；各 kind 的执行体全是既有 `run_*`
入口。arq 0.28.0 / redis 5.3.1 已在 `requirements.lock`。

## 缺 deps 就抛，NEVER 静默

`gate1_analysis` 需要真 searcher、`daily_ingest` 需要 source/embedder、`spec_export`
需要包清单——这些由调用方注入。没注入时 handler 抛 `HandlerDepsMissing` 并点名要注入
什么，作业随即被记 failed。静默跳过等于把作业留在队列里假装在跑。

## 红线

模块层 NEVER 造 http 客户端、NEVER 读 key。真实 provider / searcher 一律由调用方注入，
CI 注入的是录制回放（S2-7）。
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, cast

import asyncpg
from arq import func
from arq.connections import ArqRedis, RedisSettings
from arq.worker import Worker

from flint.domain.models import JSON, JobFailedEvent, JobKind, UserProfile
from flint.domain.protocols import LLMProvider
from flint.jobs.compose import run_compose
from flint.jobs.compose_deps import build_production_compose_deps
from flint.jobs.design_generate import DesignGenerateDeps, run_design_generate
from flint.jobs.dispatch import JobHandler, build_dispatch_table, dispatch_job
from flint.jobs.events import PgJobEventStream
from flint.jobs.gate1 import Gate1Deps, run_gate1
from flint.jobs.ingest import IngestDeps, run_daily_ingest
from flint.jobs.pricebook_scan import PricebookScanDeps, run_pricebook_scan
from flint.jobs.regenerate_job import RegenerateJobDeps, run_regenerate_job
from flint.jobs.regenerate_worker import parse_regenerate_payload
from flint.jobs.revalidation import RevalidationDeps, run_revalidation
from flint.jobs.spec_export import SpecExportDeps, run_spec_export
from flint.jobs.state import enter_state
from flint.jobs.template_solidify import TemplateSolidifyDeps, run_template_solidify
from flint.jobs.translate import TranslateDeps, run_translate
from flint.llm.prompts import load_prompt

if TYPE_CHECKING:                                    # arq 的类型面只在检查期需要
    from arq.typing import WorkerCoroutine

ARQ_TASK_NAME: Final[str] = "flint_run_job"
DEFAULT_QUEUE_NAME: Final[str] = "arq:flint"
_REGENERATE_ACTIONS: Final[frozenset[str]] = frozenset(
    {"regenerate_section", "regenerate_block"}
)


class HandlerDepsMissing(RuntimeError):
    """某个 kind 的执行体缺注入件。报错点名要注入什么，NEVER 静默跳过。"""


@dataclass
class WorkerDeps:
    """worker 进程的注入面。真实 provider / searcher 一律从外面进来。"""

    dsn: str
    redis_url: str
    repo_root: Path
    profile: UserProfile
    now: datetime
    compose_provider: LLMProvider | None = None
    aligner_provider: LLMProvider | None = None
    report_template: str = "generic.yaml"
    proposal_template: str = "generic.yaml"
    gate1_deps: Gate1Deps | None = None
    ingest_deps: IngestDeps | None = None
    spec_export_deps: SpecExportDeps | None = None
    revalidation_deps: RevalidationDeps | None = None      # BL-07
    pricebook_scan_deps: PricebookScanDeps | None = None    # BL-08
    design_generate_deps: DesignGenerateDeps | None = None  # DESIGN-01
    translate_deps: TranslateDeps | None = None             # SLOT-03
    template_solidify_deps: TemplateSolidifyDeps | None = None   # PERSIST-03


def _payload_str(payload: JSON, key: str) -> str | None:
    value = payload.get(key)
    return value if isinstance(value, str) and value else None


def _template_name(payload: JSON, default: str) -> str:
    template_id = _payload_str(payload, "template_id")
    return f"{template_id}.yaml" if template_id else default


def _is_regenerate(payload: JSON) -> bool:
    """按 payload 形状判别 report 类作业是不是 regenerate。

    `flint/api/interventions.py` 的 regenerate 与 compose 新建报告用的都是
    `kind="report"`，只能靠 payload 区分。形似 regenerate 却缺字段的 → 让
    `parse_regenerate_payload` 抛（KeyError），NEVER 静默误派成新建报告。
    """
    action = payload.get("action")
    if action not in _REGENERATE_ACTIONS:
        return False
    parse_regenerate_payload(dict(payload))
    return True


def _compose_handler(deps: WorkerDeps, *, default_template: str) -> JobHandler:
    async def handler(job_id: str, payload: JSON) -> None:
        if _is_regenerate(payload):
            await _run_regenerate(deps, job_id, payload)
            return
        project_id = _payload_str(payload, "project_id")
        if project_id is None:
            raise HandlerDepsMissing(
                f"作业 {job_id} 的 payload 缺 project_id——组稿无从下手。"
            )
        sources = [
            s for s in (
                _payload_str(payload, "analysis_id"),
                _payload_str(payload, "report_id"),
            ) if s is not None
        ]
        compose_deps = build_production_compose_deps(
            dsn=deps.dsn, repo_root=deps.repo_root, profile=deps.profile,
            now=deps.now, provider=deps.compose_provider,
            template_name=_template_name(payload, default_template),
            aligner_provider=deps.aligner_provider,
        )
        await run_compose(
            job_id=job_id, project_id=project_id,
            source_deliverable_ids=sources, deps=compose_deps,
        )

    return handler


async def _run_regenerate(deps: WorkerDeps, job_id: str, payload: JSON) -> None:
    if deps.compose_provider is None:
        raise HandlerDepsMissing(
            f"作业 {job_id} 是 regenerate，但 WorkerDeps.compose_provider 没注入。"
        )
    prompt_text = load_prompt(
        deps.repo_root / "prompts", "section_draft@1", enforce_lock=True
    ).text
    await run_regenerate_job(job_id, dict(payload), RegenerateJobDeps(
        dsn=deps.dsn, provider=deps.compose_provider, prompt_text=prompt_text,
        profile=deps.profile,
        template_path=deps.repo_root / "assets" / "templates" / deps.report_template,
        now=lambda: deps.now,
    ))


def _gate1_handler(deps: WorkerDeps) -> JobHandler:
    async def handler(job_id: str, payload: JSON) -> None:
        if deps.gate1_deps is None:
            raise HandlerDepsMissing(
                f"作业 {job_id} 是 gate1_analysis，但 WorkerDeps.gate1_deps 没注入"
                "（需要 provider + searcher；CI 注入录制回放，NEVER 真实检索）。"
            )
        keywords = [str(k) for k in payload.get("keywords", [])]
        locale = str(payload.get("locale", "zh-CN"))
        # `PERSIST-04`：`topic_id` 是判定→热点那条关系的**唯一来源**。
        # payload 里有而这里不取的话，链路在这一行静静地断掉——
        # 表照样建着、判据照样绿，而屏上一个字都不会变。
        raw_topic = payload.get("topic_id")
        topic_id = str(raw_topic) if isinstance(raw_topic, str) and raw_topic else None
        await run_gate1(
            job_id, keywords, locale, deps.gate1_deps, topic_id=topic_id)

    return handler


def _daily_ingest_handler(deps: WorkerDeps) -> JobHandler:
    async def handler(job_id: str, payload: JSON) -> None:
        if deps.ingest_deps is None:
            raise HandlerDepsMissing(
                f"作业 {job_id} 是 daily_ingest，但 WorkerDeps.ingest_deps 没注入"
                "（需要 open_source + embedder + terms + categories_path）。"
            )
        day_text = _payload_str(payload, "day")
        if day_text is None:
            raise HandlerDepsMissing(f"作业 {job_id} 的 payload 缺 day。")
        from datetime import date
        await run_daily_ingest(job_id, date.fromisoformat(day_text), deps.ingest_deps)

    return handler


def _spec_export_handler(deps: WorkerDeps) -> JobHandler:
    async def handler(job_id: str, payload: JSON) -> None:
        if deps.spec_export_deps is None:
            raise HandlerDepsMissing(
                f"作业 {job_id} 是 spec_export，但 WorkerDeps.spec_export_deps 没注入"
                "（需要 packages + check + external_inputs）。"
            )
        spec_set_id = _payload_str(payload, "spec_set_id")
        if spec_set_id is None:
            raise HandlerDepsMissing(f"作业 {job_id} 的 payload 缺 spec_set_id。")
        await run_spec_export(job_id, spec_set_id, deps.spec_export_deps)

    return handler


def _revalidation_handler(deps: WorkerDeps) -> JobHandler:
    """BL-07：消费扫描器塞进队列的 revalidation 作业。

    此前这些作业**没人取**——「到期复核」在系统里看起来「有」，实际一次都没跑过。
    判定件由 `RevalidationDeps.revalidator` 注入（默认出处 = 既有 Revalidator），
    本处理器 NEVER 自己判 stale。
    """
    async def handler(job_id: str, payload: JSON) -> None:
        if deps.revalidation_deps is None:
            raise HandlerDepsMissing(
                f"作业 {job_id} 是 revalidation，但 WorkerDeps.revalidation_deps 没注入"
                "（需要 revalidator：默认出处 flint/revalidate/report.py#build_report，"
                "它要 Gate1Deps 的 provider + searcher）。"
            )
        await run_revalidation(job_id, payload, deps.revalidation_deps)

    return handler


def _pricebook_scan_handler(deps: WorkerDeps) -> JobHandler:
    """BL-08：扫全表标时效。**只读价目表**——改价是另一条路径。"""
    async def handler(job_id: str, payload: JSON) -> None:
        scan_deps = deps.pricebook_scan_deps or PricebookScanDeps(
            dsn=deps.dsn, now=deps.now, today=deps.now.date(),
        )
        await run_pricebook_scan(job_id, payload, scan_deps)

    return handler


def build_handlers(deps: WorkerDeps) -> dict[str, JobHandler]:
    """可接线 kind 的执行体。缺注入件的在**被调用时**点名抛错。"""
    return {
        "gate1_analysis": _gate1_handler(deps),
        "report": _compose_handler(deps, default_template=deps.report_template),
        "proposal": _compose_handler(deps, default_template=deps.proposal_template),
        "spec_export": _spec_export_handler(deps),
        "daily_ingest": _daily_ingest_handler(deps),
        "revalidation": _revalidation_handler(deps),
        "pricebook_scan": _pricebook_scan_handler(deps),
        "design_generate": _design_generate_handler(deps),
        "translate": _translate_handler(deps),
        "template_solidify": _template_solidify_handler(deps),
    }


def _template_solidify_handler(deps: WorkerDeps) -> JobHandler:
    """PERSIST-03：消费 `template_solidify` 作业——**分派表里最后一条未接线的 kind**。

    改前这条挂在 `UnwiredKindReason` 里，理由是「`solidify_mock` 是同步函数，
    仓里还没有消费者」。真正缺的不是异步包装，是 `templates` 表
    （`DEC-048`）——没有表的话固化出来的模板落不了地，
    而作业会「成功」结束，用户回列表里什么都看不到。

    **缺注入件时点名抛错，NEVER 假装跑过**（与另外两个 handler 同一形状）：
    假装跑过的后果是作业变成 `done` 而模板一个都没落库，
    且没有任何一条错误可查。
    """
    async def handler(job_id: str, payload: JSON) -> None:
        if deps.template_solidify_deps is None:
            raise HandlerDepsMissing(
                f"作业 {job_id} 是 template_solidify，但 WorkerDeps."
                "template_solidify_deps 没注入（需要 registry："
                "flint/design/templates/pgregistry.py#PgTemplateRegistry；"
                "emit：SolidifyResult 的出口；now）。"
            )
        await run_template_solidify(job_id, dict(payload), deps.template_solidify_deps)

    return handler


def _translate_handler(deps: WorkerDeps) -> JobHandler:
    """SLOT-03：消费 `translate` 作业（name_display 派生）。

    改前这条 kind 挂在 `UnwiredKindReason` 里——提交了也没人取。

    **取源与落盘由注入方给**：冻结件在 `canonical_name` 那一行写着
    「与 `name_native` 的关系由 REGION-04 命名规则成文」，而 `name_display`
    全库没有落点。两件都不是 worker 能替产品决定的，所以没配就大声缺——
    猜一段原文去翻，屏上会出现一个语义正确、指向错误的译名，
    而它与译对了长得一模一样。
    """
    async def handler(job_id: str, payload: JSON) -> None:
        if deps.translate_deps is None:
            raise HandlerDepsMissing(
                f"作业 {job_id} 是 translate，但 WorkerDeps.translate_deps 没注入"
                "（需要 load_target / save_target 两个端口："
                "取哪一段原文见 contracts_v04#Cluster.canonical_name 的 REGION-04 注记；"
                "name_display 今天全库没有落点，落盘面待定。"
                "另需 translator：flint/i18n/translator.py#Translator；cache；now）。"
            )
        await run_translate(job_id, dict(payload), deps.translate_deps)

    return handler


def _design_generate_handler(deps: WorkerDeps) -> JobHandler:
    """DESIGN-01：消费「说一句话出一个设计」那类作业。

    改前这条 kind 挂在 `UnwiredKindReason` 里——提交了也没人取，
    worker 取到只会抛 `JobKindNotWired`。

    产物件由 `DesignGenerateDeps` 注入（provider 恒从外面进来：
    运行时是本机免费档模型，判据面是 fixture 回放），本处理器 NEVER 自己建 provider。
    """
    async def handler(job_id: str, payload: JSON) -> None:
        if deps.design_generate_deps is None:
            raise HandlerDepsMissing(
                f"作业 {job_id} 是 design_generate，但 WorkerDeps.design_generate_deps "
                "没注入（需要 provider：contracts/protocols.py#LLMProvider；"
                "events：默认出处 flint/jobs/events.py#PgJobEventStream；now）。"
            )
        await run_design_generate(job_id, dict(payload), deps.design_generate_deps)

    return handler


def build_dispatch_table_for(deps: WorkerDeps) -> Mapping[str, JobHandler]:
    """装配期就能查出的缺件在这里抛（compose_provider 是组稿的硬前提）。"""
    if deps.compose_provider is None:
        raise HandlerDepsMissing(
            "WorkerDeps.compose_provider 没注入：report / proposal 两个 kind 都要它"
            "（免费档 LocalProvider / 录制回放 provider 均可）。"
        )
    return build_dispatch_table(build_handlers(deps))


def make_mark_failed(
    dsn: str, *, now: Callable[[], datetime] | None = None,
) -> Callable[[str, str], Any]:
    """把作业记 failed、落 error 文本，**并让订阅的那一头收得到**。

    ## 改前只改库（`UIR-02`）

    这里原来是一句直接把 `jobs` 那一行的状态改成 `failed` 的 UPDATE，不写事件流。
    作业屏订阅的是事件流：它收到过 `drafting`，之后什么都收不到，屏上一直是「在写」，
    而库里早就 `failed` 了（单 `SIX-FAMILIES-ADVANCE-STATE-WITHOUT-AN-EVENT`，
    2026-11-14 在真栈上见到）。

    ## 现在

    - `error` 文本照旧落库；
    - 状态经 `flint/jobs/state.py#enter_state` 推到 `failed`——那一处真相，库与事件流一起写；
    - 推之前先追加一条带原因的 `failed` 事件：订阅的屏按到达顺序读，最后一条必须是终态。

    已经 `done` / `cancelled` 的作业一个字不动（与改前那句 `WHERE … NOT IN` 同一条口径）。
    已经 `failed` 的只补 `error`、NEVER 再说一遍：重写作业自己会写失败事件（`REGEN-EVT-01`），
    随后异常抛到这里，再写一遍屏上就是两条一样的「失败」。
    没有这一行作业就什么都不写：事件流的外键指着 `jobs`，硬写会抛，而抛了会盖掉原来那个错。
    """
    clock = now if now is not None else (lambda: datetime.now(UTC))
    events = PgJobEventStream(dsn=dsn)

    async def mark_failed(job_id: str, error: str) -> None:
        conn = await asyncpg.connect(dsn)
        try:
            previous: str | None = await conn.fetchval(
                "SELECT state FROM jobs WHERE job_id = $1", job_id)
            if previous is None or previous in ("done", "cancelled"):
                return
            await conn.execute(
                "UPDATE jobs SET error = $2, updated_at = $3 WHERE job_id = $1",
                job_id, error, clock(),
            )
            if previous == "failed":
                return
            await events.append(
                job_id, JobFailedEvent(kind="failed", reason=error), ts=clock())
            await enter_state(conn, events, job_id, "failed", clock())
        finally:
            await conn.close()

    return mark_failed


def build_enqueue_hook(
    pool: ArqRedis, *, queue_name: str = DEFAULT_QUEUE_NAME,
) -> Callable[[str, JobKind, JSON], Any]:
    """`flint/jobs/runner.py` 的 EnqueueHook 实现：把提交推进真 arq 队列。

    `_job_id` 用作业自身的 id：同一作业重复提交在队列层就被去重，NEVER 跑两遍。
    """
    async def enqueue(job_id: str, kind: JobKind, payload: JSON) -> None:
        await pool.enqueue_job(
            ARQ_TASK_NAME, job_id, kind, dict(payload),
            _job_id=f"arq-{job_id}", _queue_name=queue_name,
        )

    return enqueue


def build_worker(
    deps: WorkerDeps, *, queue_name: str = DEFAULT_QUEUE_NAME, burst: bool = False,
    cron_jobs: Any = None,
) -> Worker:
    """起一个消费 flint 作业的 arq worker。burst=True 跑空队列即退出（测试口径）。"""
    table = build_dispatch_table_for(deps)
    mark_failed = make_mark_failed(deps.dsn)

    async def task(ctx: dict[Any, Any], *args: Any, **_kwargs: Any) -> None:
        job_id, kind, payload = args[0], args[1], args[2]
        await dispatch_job(
            job_id, kind, payload, table=table, mark_failed=mark_failed,
        )

    # arq 的 WorkerCoroutine 是带 `__qualname__` 的 Protocol；普通函数在运行期满足它，
    # 但 mypy 不把 Callable 类型算作该 Protocol 的实现，故显式 cast。
    return Worker(
        functions=[func(cast("WorkerCoroutine", task), name=ARQ_TASK_NAME)],
        queue_name=queue_name,
        redis_settings=RedisSettings.from_dsn(deps.redis_url),
        burst=burst,
        cron_jobs=cron_jobs,
        max_tries=1,          # 续跑由 job_steps 断点负责，NEVER 靠 arq 盲重试
    )
    # handle_signals 留 arq 默认（True）：它的 _add_signal_handler 已吞掉 Windows 的
    # NotImplementedError，而关掉它会让 Worker.close() 走 signal.SIGUSR1——那个信号
    # Windows 没有（arq 0.28 的 POSIX 假设），dev 机上一关就炸。
