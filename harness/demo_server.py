"""一键 demo 后端：合并 views+combo+analysis 三 app（同进程 uvicorn）。

- combo 生成走**免费本地 qwen3.6:35b-a3b**（已验证最优免费档）；Gate① 分析走 **live 真实
  github/arxiv + 本地 qwen**（build_live_deps + 提交即后台跑 run_gate1 + quote_span 钉论文）。
- X-User-Id 注入中间件（demo：前端不发该头 → 注 `demo-user`；NEVER 改端点/契约/前端）。
- CORS 放开供前端跨源取（web/ :3000 与 v0 前端 :3001 同用 allow_origins=["*"]）。
  **零付费、零 key**（key 只从 owner 现有环境读，不设即免费本地；本文件 NEVER 读/写任何
  key）。冻结件不动。
- 挂载面（**只挂既有 app，NEVER 改端点响应形状**）：views + combo + analysis +
  deliverables + categories。deliverables（M3-058：GET /deliverables/{id}、/blocks、
  /render?fmt=）是报告 L0 屏的读契约；categories（M1-022：GET /categories）是 S0 外壳
  大类筛选的读契约——不挂则前端只能硬编码一份大类清单（造假数据），故挂。
  report/proposal 提交端点（flint.api.compose）**挂着且真能跑**（`COMPOSE-01`）。

  这里原先写着「刻意不挂：demo 无 report worker，挂了只会造出永远 queued 的 job」。
  **那句话今天两重是假的**：

  1. 这一族早在 `WIRE-08` 就由 `create_app` 挂上了——demo 这一侧根本没有「挂不挂」
     的选择权，注释描述的是一个已经不存在的装配面；
  2. **report worker 存在**：`harness/run_worker.py` 起 `flint/jobs/worker_main.py#build_worker`，
     `start-demo.ps1` §3b 每次都起它。消费 report 作业的就是它。

  一句变假的注释比没有注释坏：它让「已经能用」被读成「刻意没做」。

  真正缺的那一件是**队列没接**：`create_app(DSN)` 不给 `redis_url` 时
  `_queue_hook(None)` 回 `_unconfigured("analysis")`，于是提交回 503 而不是入队
  （`flint/api/app.py` 的原话：NEVER 让它默默地不入队，那样「队列没配」与
  「worker 没起来」在表上长得一模一样）。本文件因此把 `REDIS_URL` 注进去，
  与 `harness/run_worker.py` 读**同一个环境变量、同一个默认值**——
  各写一份的话，API 推 A 队列而 worker 守 B 队列，作业照样永远 queued。

  组稿走的模型是**免费本地档**（`LocalProvider` → 本机 Ollama），零 key 零付费。
  **flint.api.pack 也 NEVER 挂**：它与 deliverables 都定义了
  `GET /deliverables/{id}/render`，同挂会撞路由；fmt=pack 走 deliverables 既有的
  503 SERVICE_UNAVAILABLE 才是正确行为（E6 姿态：明说不可用）。
"""
from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime
from pathlib import Path

import asyncpg
import httpx
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from flint.api.app import create_app
from flint.domain.models import JSON, JobKind, Principal, UserProfile
from flint.evidence.enrich import pin_verdict_citations
from flint.evidence.search import GithubArxivSearcher
from flint.jobs.gate1 import build_live_deps, run_gate1
from flint.jobs.regenerate_job import RegenerateJobDeps, run_regenerate_job
from harness.demo_model import build_demo_provider

REPO = Path(__file__).resolve().parents[1]
DSN = os.environ.get("FLINT_DEMO_DSN", "postgresql://flint:flint@localhost:55432/flint")
#: 作业队列。**与 `harness/run_worker.py` 读同一个变量、同一个默认值**（`COMPOSE-01`）。
#: 两处各写一份的话，API 会把作业推进 A 队列而 worker 守着 B 队列，
#: 而症状是「作业永远 queued」——与「worker 没起来」在表上长得一模一样。
REDIS_URL = os.environ.get("FLINT_REDIS_URL", "redis://localhost:56379/0")
# demo 的身份：`_InjectUserMiddleware` 在没有 X-User-Id 时注的就是这个 id。
# 它现在**是库里一行真的 users**（AUTH-05 种的），不再是一个凭空的字符串。
DEMO_USER = "demo-user"
DEMO_ORG = "org-demo"


def _is_regenerate_payload(payload: JSON) -> bool:
    """按 payload **形状**判别 report 类 job 是不是 regenerate（坑二）。

    背景：`flint/api/interventions.py` 的 regenerate 提交的是 `kind="report"`，
    而 compose 新建报告用的**也是** `kind="report"`。两者只能靠 payload 区分：
    regenerate 必带 action ∈ {regenerate_section, regenerate_block}
    且带 deliverable_id / section_id / project_id（见 parse_regenerate_payload）。

    **分不出来 MUST 显式失败，NEVER 静默误派**——compose 将来挂上时，
    静默误派会变成一个极难查的 bug（报告作业被当成重生成跑，或反过来）。
    """
    action = payload.get("action")
    if action not in ("regenerate_section", "regenerate_block"):
        return False
    missing = [k for k in ("deliverable_id", "section_id", "project_id")
               if not isinstance(payload.get(k), str) or not payload.get(k)]
    if missing:
        raise ValueError(
            f"report job 形似 regenerate（action={action!r}）但缺字段 {missing}；"
            "拒绝派发——NEVER 静默误派。"
        )
    return True


async def _enqueue(job_id: str, kind: JobKind, payload: JSON) -> None:
    """demo 早期的作业派发钩子。**今天没有任何地方调它**（`COMPOSE-01` 实查）。

    ## 它现在是什么

    `WIRE-07~10` 把三族搬进 `create_app` 之后，作业提交走的是那边真 arq 缝
    （`_queue_hook(redis_url)`），消费方是 `harness/run_worker.py` 起的
    `flint/jobs/worker_main.py#build_worker`。本函数**不在那条路上**：
    全仓没有一处把它传给 `PgJobRunner(enqueue=...)`。

    留着它而不删：它是 demo 面唯一一处写着「gate1 怎么在本机跑起来」的地方，
    删掉之后那段接线知识没有第二份。**但它的说法必须是真的**——

    下面这句原文是假的、且已改：「其余（compose 新建报告）本 demo 未挂 compose 端点，
    故不应出现」。compose 端点 `WIRE-08` 就挂上了，`COMPOSE-01` 又把队列接通，
    今天 demo 上提交一份报告是**正常路径**，由 run_worker 消费。

    一句变假的注释比没有注释坏：照着它读，会以为「⑦计划书」这一步没做。
    """
    if kind == "report":
        if _is_regenerate_payload(payload):
            await _run_regenerate(job_id, payload)
        else:
            raise ValueError(
                f"收到无法判别的 report job（job_id={job_id}，"
                f"action={payload.get('action')!r}）。"
                "本钩子只认 regenerate 形状；compose 新建报告由 "
                "harness/run_worker.py 那条真队列消费（COMPOSE-01）。"
                "拒绝派发——NEVER 静默误派。"
            )
        return
    if kind != "gate1_analysis":
        return
    now = datetime.now(UTC)
    provider = build_demo_provider()
    searcher = GithubArxivSearcher(
        httpx.Client(timeout=30.0, follow_redirects=True), now,
        per_source=3, resilient=True)
    deps = build_live_deps(DSN, REPO, provider, searcher, now)
    keywords = [str(k) for k in payload.get("keywords", [])]
    locale = str(payload.get("locale", "zh-CN"))

    async def _run() -> None:
        await run_gate1(job_id, keywords, locale, deps)
        await pin_verdict_citations(DSN, job_id, now)

    asyncio.create_task(_run())      # 后台跑；/jobs/{id}/events SSE 报进度


async def _run_regenerate(job_id: str, payload: JSON) -> None:
    """report(regenerate 形状) → run_regenerate_job，后台跑。

    生成走免费本地 qwen（同 combo 口径）；LocalProvider 是**同步**的，
    run_regenerate_job 内部的生成调用因此不能占住事件循环——放后台 task 只是排到同一个
    loop 上并不解决问题，故整个作业经 run_in_threadpool 挪出（与 combo 同款处置）。
    """
    prompt_path = REPO / "prompts" / "section_draft@1.md"
    deps = RegenerateJobDeps(
        dsn=DSN,
        provider=build_demo_provider(),
        prompt_text=prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else "",
        # 逐字照冻结件 UserProfile 字段（demo 无真实档案 → 全空，NEVER 编造涉我信息）
        profile=UserProfile(
            profile_id="demo-profile", owner=Principal(kind="user", id="demo-user"),
            identity={}, research={}, team=[], assets={}, constraints={},
            track_record=[], locale="zh-CN", sensitivity_overrides={},
            updated_at=datetime.now(UTC)),
        template_path=REPO / "assets" / "templates" / "report.yaml",
        now=lambda: datetime.now(UTC),
    )

    def _blocking() -> None:
        # 协程 MUST 在线程内部创建：在主 loop 上先造好再丢进线程跑会绑错事件循环。
        asyncio.run(run_regenerate_job(job_id, payload, deps))

    async def _run() -> None:
        await run_in_threadpool(_blocking)

    asyncio.create_task(_run())


#: FIX-20：这道中间件替人补身份时，在响应上留的记号。
#: **「我现在是谁」这件事从此永远看得见**——`steward` 重起两次都没收口，
#: 正是因为屏上、日志里、响应里没有任何地方说过「你这个请求的身份是补出来的」。
DEMO_IDENTITY_HEADER = b"x-flint-demo-identity"


class _InjectUserMiddleware:
    """纯 ASGI 中间件：前端不发 X-User-Id → 注 demo-user（scope 级，NEVER 碰 body 流；
    避开 BaseHTTPMiddleware 吞 body 的坑）。NEVER 改端点/前端/契约。

    ## FIX-20：它是**网关替身**，而它此前是隐形的

    `web/lib/screenClient.ts` 逐字写着「前端不发身份头……身份该由网关/中间件定，
    NEVER 由前端自己编一个」。所以这道中间件不是权宜之计，它就是 demo 栈里的那个网关。

    **此前的问题不是它存在，是它不说话**：走网络的匿名请求到端点手上时
    已经带着 `demo-user`，于是「匿名回 200」看起来像端点把门开着——
    而进程内实测匿名是 422，带 `stranger` 走网络是 404，
    **两条都证明端点的门是关着的**。

    改后两件事：
    1. `enabled=False` 时**一个头都不补**——那时走真网络的匿名请求就是 422，
       判据打的就是这一态（`tests/v041/test_anon_deref_over_network.py`）；
    2. 补过身份的响应带上 `X-Flint-Demo-Identity: injected`——
       **NEVER 让「这是补出来的身份」这件事只存在于代码里**。

    默认 `enabled=True`：demo 界面每一屏都靠它才取得到数，
    默认关掉等于把灯关了（`FIX-20` 的 trace §4）。
    """

    def __init__(self, app: ASGIApp, enabled: bool = True) -> None:
        self._app = app
        self._enabled = enabled

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        injected = (
            self._enabled
            and scope["type"] == "http"
            and not any(k == b"x-user-id" for k, _ in scope["headers"])
        )
        if injected:
            scope = {**scope, "headers": [*scope["headers"], (b"x-user-id", b"demo-user")]}
            # 补过身份的响应留记号。**NEVER 在没补的时候也留**——
            # 那样这个记号就不再说明任何事。
            async def marked(message: Message) -> None:
                if message["type"] == "http.response.start":
                    message = {
                        **message,
                        "headers": [*message.get("headers", []),
                                    (DEMO_IDENTITY_HEADER, b"injected")],
                    }
                await send(message)

            await self._app(scope, receive, marked)
            return
        await self._app(scope, receive, send)


def build_app(inject_identity: bool | None = None) -> FastAPI:
    """demo 栈的后端 = **`WIRE-01` 装配后的那个 app** + demo 才有的四族。

    改前：这里各屏各造一个 `create_*_app` 再 `include_router`，共七族。
    那份清单与 `flint/api/app.py` 各写各的——**两个真相**，
    而「哪些挂了」这件事要有人记着，正是 51 条藏一整批的原因。

    改后：`create_app(DSN)` 一次拿到 42 条，再把 demo **独有**的四族加上去。
    这四族在可部署应用里此刻还挂不上（`WIRE-07~10` 正在接），而 demo 先有。

    **AUTH-05：那只假手已经退役。** 这里原本是 `lambda _u, _o: "owner"`——
    谁问都答 owner，在 demo 里被称作「明知故犯的口径」，在可部署应用里是安全洞。
    现在三处都换成了 `flint/authz` 的真解析器（查 `memberships`）。
    demo 的身份数据由 `seed_demo_identity()` 种，NEVER 用常量顶替。

    加的时候走**同一个装配器**（`_Assembler`），所以撞车照样 raise，
    NEVER 因为「这是 demo」就少一道闸。
    """
    if inject_identity is None:
        # `FLINT_DEMO_INJECT_IDENTITY=0` 关掉网关替身。默认开——见中间件 docstring。
        inject_identity = os.environ.get("FLINT_DEMO_INJECT_IDENTITY", "1") != "0"
    # `redis_url` 是**作业队列的缝**：不给的话 `_queue_hook(None)` 回
    # `_unconfigured("analysis")`，任何组稿提交都是 503，而 demo 面上
    # 「⑦计划书」那一步会被读成功能没做（`COMPOSE-01` 实测到的就是这一幕）。
    #
    # `combo_provider` / `combo_model` 是**模型的缝**（`WIRE-10` 留的，
    # `COMBO-WIRE-01` 接上）。改前这里不传，于是 `POST /projects/combo` 在
    # **所有**部署上都是 503——owner 在工作台屏上按「按你选的卡建项」
    # 撞见的就是那一幕（`docs/blocked/COMBO-FAMILY-HAS-NO-PROVIDER-ANYWHERE.md`）。
    # 那条缝本身**留着**：不传 provider 时照旧 503 并点名 combo（阴性对照在
    # `tests/v041/test_combo_wire.py`），因为「没配模型」与「模型说没有」是两件相反的事。
    #
    # 模型口径与组稿那一族**同一处定义**（`harness/local_model.py`）：
    # 各造一份的话，「combo 用的是哪个模型」会有两个答案，
    # 而两个答案在屏上、在日志里长得一模一样。
    #
    # `NARROW-04`：provider 改由 `harness/demo_model.py` 按 `FLINT_DEMO_PROVIDER` 选
    # （不设 = 照旧本地）；模型名取 provider 自己的 `.model`，换了厂商也只有一个答案。
    combo_provider = build_demo_provider()
    app = create_app(DSN, redis_url=REDIS_URL,
                     combo_provider=combo_provider, combo_model=combo_provider.model)
    app.title = "flint-demo"
    # FIX-20：网关替身默认开着（demo 界面靠它取数），但**可以关**——
    # 关掉之后走真网络的匿名请求就是端点自己的答复（422）。
    # 环境变量而不是命令行参数：这一条要能在判据起的那个子进程里设。
    app.add_middleware(_InjectUserMiddleware, enabled=inject_identity)
    app.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

    # `WIRE-07~10` 之后 demo **一族都不再自己挂**——四族全在 `create_app` 里。
    # 所以这里不再需要装配器。撞车守卫仍由 `flint/api/app.py` 的 `_Assembler` 把着，
    # 阴性对照搬去了 `tests/v041/test_demo_stack_wired.py`
    # （`test_the_collision_guard_still_bites_where_the_assembler_lives`）。
    #
    # demo 与可部署应用现在的差别只剩两条中间件：注 demo 身份、放开 CORS。
    # combo 族**已由 `create_app` 挂上**（`WIRE-10`）——这里不再造第二份。
    # 它的 provider 由上面那一发 `create_app(combo_provider=…)` 注进去
    # （`COMBO-WIRE-01`）；不注的那一态照旧是「一调用即 503 并点名 combo」。
    # `WIRE-07~09` 之后，需要 runner 与解析器的三族（analysis / compose /
    # interventions）都由 `create_app` 自己装配——demo 这一侧不再造 runner。
    # `_enqueue`（那条 `asyncio.create_task` 的后台派发）**今天一处都没接**——
    # 全仓没有把它传给任何 `PgJobRunner(enqueue=...)`（`COMPOSE-01` 实查）。
    # 作业提交端点走的是 `create_app(redis_url=REDIS_URL)` 里那条真 arq 缝，
    # 消费方是 `harness/run_worker.py`。
    # analysis 族**已由 `create_app` 挂上**（`WIRE-07`）——这里不再造第二份。
    # 造了就是两个真相，而 `_Assembler` 会当场以 RouteConflictError 拦下来
    # （它拦得对：并进一个应用后必有一个永远收不到请求）。
    # views / deliverables / categories / deref 四族**已由 create_app 挂上**，
    # 这里不再各造一份：造两份就有两个真相，而它们的 deps 逐字相同（只有 dsn）。
    # M3-058 的口径不变：`pack_builder`/`pack_gate` 不注入 → `fmt=pack` 走既有
    # 503 SERVICE_UNAVAILABLE（E6 姿态：明说不可用），NEVER 伪装成可用。
    # 干预层：interventions 与 compose **两族今天都挂着**
    # （原注释写的「compose 不挂」是 `WIRE-08` 之前的裁决，已过期）。
    # 四端点：lock / regenerate / evidence / disputes。
    # aligner 吃 LLM 且 CitationAligner.align 是**同步**的 —— 已在
    # flint/intervene/inject.py 用 run_in_threadpool 挪出事件循环，
    # 回归测试 tests/harness/test_inject_nonblocking.py 证明单次最长停顿 < 阈值。
    # interventions 族**已由 `create_app` 挂上**（`WIRE-09`）——这里不再造第二份。
    # demo 想用真模型跑对齐时，把 provider 从 `create_app(aligner_provider=...)`
    # 那条缝注进去即可；不注就是「一调用即 503 并点名 interventions」。
    # 四族此刻**一族都不再由 demo 独有**（`WIRE-07~10` 全接通）。
    # 装配器留着：下一次真有 demo 独有的族时，加回来的地方是确定的。
    return app


async def seed_demo_identity(dsn: str = DSN) -> None:
    """种 demo 的身份数据：一个用户、一个组织、一条 membership。幂等。

    **NEVER 用常量角色顶替**（那正是 `AUTH-05` 退役掉的那只手）。
    demo 里绝大多数资源是**个人归属**（`owner_scope.kind == "user"`），
    那条路根本不问角色；这条 membership 是给 org 归属的资源准备的——
    没有它，任何 org 归属的东西在 demo 上都会被真解析器如实拒掉。
    """
    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute(
            "INSERT INTO users (user_id, email, display_name, created_at) "
            "VALUES ($1, $2, $3, now()) ON CONFLICT (user_id) DO NOTHING",
            DEMO_USER, f"{DEMO_USER}@flint.invalid", "Demo 用户")
        await conn.execute(
            "INSERT INTO orgs (org_id, name, created_at) "
            "VALUES ($1, $2, now()) ON CONFLICT (org_id) DO NOTHING",
            DEMO_ORG, "Demo 组织")
        await conn.execute(
            "INSERT INTO memberships (user_id, org_id, role) VALUES ($1, $2, 'owner') "
            "ON CONFLICT (user_id, org_id) DO UPDATE SET role = EXCLUDED.role",
            DEMO_USER, DEMO_ORG)
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(seed_demo_identity())
    uvicorn.run(build_app(), host="127.0.0.1", port=8000, log_level="info")
