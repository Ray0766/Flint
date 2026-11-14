"""TS-010：POST /projects/combo 端点 + analysis topic_keywords_for 接线。

combo 端到端（后端编排，前端 combo 入口的落点）：建 Origin（TS-002 校验）→ 派生
TopicSeed → orchestrate_combo（TS-009：生成 N 主题→[C1] 差异约束→建 Project）→ 持久化
origin/seed/topics/records/project → 返 {project_id, topic_ids, degraded}。

provider 注入（模型无关）：offline/合成 fixture 测；真机 qwen3.6 = 资源触点（TS-011
harness 授权跑，NEVER 在端点默认触发）。`make_topic_keywords_resolver` 供 analysis app
接 topic_id → 真实 Topic → keywords（run_gate1 内核不变）。
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime

from fastapi import FastAPI, Header
from fastapi.responses import JSONResponse, Response
from starlette.concurrency import run_in_threadpool

from flint.api.errors import origin_validation_error
from flint.api.schemas import (
    ComboCreateRequest,
    ComboCreateResponse,
    ErrorBody,
    ErrorCode,
)
from flint.compose.deliverable import PgDeliverableStore
from flint.domain.models import Principal
from flint.domain.protocols import LLMProvider
from flint.embed import EmbeddingService
from flint.topic.cards_context import NoUsableEvidenceCards, build_cards_context
from flint.topic.create import (
    OriginValidationError,
    PgCardCatalog,
    create_origin,
    origin_to_seed,
)
from flint.topic.gate_adapter import topic_to_keywords
from flint.topic.orchestrate import orchestrate_combo
from flint.topic.store import (
    PgOriginStore,
    PgProjectStore,
    PgTopicSeedStore,
    PgTopicStore,
)


@dataclass
class ComboApiDeps:
    dsn: str
    provider: LLMProvider
    embed_service: EmbeddingService
    model: str
    id_factory: Callable[[], str]        # 唯一 base id（无隐藏 uuid，可复现）
    now: Callable[[], datetime]
    target: int = 6


def _error(status: int, code: ErrorCode, message: str) -> JSONResponse:
    body = ErrorBody(code=code, message=message, detail=None)
    return JSONResponse(status_code=status, content=body.model_dump(exclude_none=True))


def make_topic_keywords_resolver(
    dsn: str,
) -> Callable[[str], Awaitable[list[str]]]:
    """analysis app 的 topic_keywords_for：topic_id → 真实 Topic → keywords。"""

    async def resolve(topic_id: str) -> list[str]:
        topic = await PgTopicStore(dsn=dsn).load(topic_id)
        return topic_to_keywords(topic)

    return resolve


def create_combo_app(deps: ComboApiDeps) -> FastAPI:
    app = FastAPI(title="flint-combo-api")

    @app.post("/projects/combo")
    async def combo(body: ComboCreateRequest, x_user_id: str = Header()) -> Response:
        owner = Principal(kind="user", id=x_user_id)
        catalog = PgCardCatalog(dsn=deps.dsn)
        base = deps.id_factory()
        origin_id, seed_id = f"origin-{base}", f"seed-{base}"
        project_id, job_id = f"proj-{base}", f"job-{base}"
        now = deps.now()
        try:
            origin = await create_origin(
                origin_id=origin_id, kind="combo", owner=owner,
                payload={"card_ids": body.card_ids, "hypothesis": body.hypothesis},
                created_at=now, catalog=catalog,
            )
        except OriginValidationError as err:
            # FIX-10：映射**只有一处**（`flint/api/errors.py`）。
            # 改前这里一律回 400 VALIDATION_FAILED，而 graph_edges 对**同一个校验器
            # 抛的同一句话**回 422 EMPTY_HYPOTHESIS——同一件事两个答复，
            # 前端要为它写两套分支，而写着写着必然漏掉一条。
            return origin_validation_error(err)
        seed = await origin_to_seed(seed_id=seed_id, origin=origin, catalog=catalog)
        # BL-02：@2 的 {cards} 强接地——把被引卡的真实内容与日期喂进提示词。
        # 此前这里什么都不传，生产路径上 {cards} 一直被替换成空串，
        # 而空串与没接线在结果上长得一模一样（模型照常生成、校验器照常判）。
        try:
            cards_context = build_cards_context(await catalog.contents_of(body.card_ids))
        except NoUsableEvidenceCards as err:
            # 接不到卡 NEVER 静默继续：那等于把「没有证据」写成「有证据但模型没引」，
            # 而两者的处置完全不同——前者该拒绝生成，后者该看模型。
            return _error(422, "VALIDATION_FAILED", str(err))
        await PgOriginStore(dsn=deps.dsn).save(origin)
        await PgTopicSeedStore(dsn=deps.dsn).save(seed)

        counter = {"n": 0}

        def topic_ids() -> tuple[str, str]:
            counter["n"] += 1
            return (f"topic-{base}-{counter['n']}", f"gr-{base}-{counter['n']}")

        # orchestrate_combo 是同步纯计算，内部调同步 LLMProvider（~秒级/更长）。
        # 挪出事件循环（线程池）——NEVER 在 async handler 内裸跑，否则憋死并发请求。
        result = await run_in_threadpool(
            orchestrate_combo,
            deps.provider, seed, deps.embed_service, id_factory=topic_ids,
            allowed_citation_ids=body.card_ids, model=deps.model, job_id=job_id,
            ts=now, project_id=project_id, owner=owner, target=deps.target,
            cards_context=cards_context,
        )
        topic_store = PgTopicStore(dsn=deps.dsn)
        for topic in result.topics:
            await topic_store.save(topic)
        record_store = PgDeliverableStore(dsn=deps.dsn)
        for record in result.records:  # #4 可复现留痕（interim GenerationRecord 借用）
            await record_store.save_generation_record(record)
        await PgProjectStore(dsn=deps.dsn).save(result.project)
        return JSONResponse(
            ComboCreateResponse(
                project_id=project_id,
                topic_ids=result.project.topic_ids,
                degraded=result.outcome.degraded,
            ).model_dump()
        )

    return app
