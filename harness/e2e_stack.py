"""E2E-01：端到端用的**装配后的应用**——`create_app` 加上它现在挂不上的两族。

## 为什么不能直接用 `flint/api/app.py#create_app`

主链路的第一步是**提交**（`POST /projects/{id}/analysis` 与
`POST /projects/{id}/report`），而这两条分别属 `analysis` 与 `compose` 两族——
它们在可部署应用里**挂不上**：缺 `role_resolver`（本仓还没有 `users` / `memberships`
两张表，做不出一个诚实的角色解析）与作业 `runner` 的装配面。
`create_app` 把这件事登记成 `UNWIRED_FAMILIES`，请求打过去回
`503 FAMILY_NOT_CONFIGURED` 并点名是哪一族——**那是对的行为**，
在鉴权补上之前 NEVER 用 `lambda: "owner"` 把它糊过去。

## 那这里为什么可以

因为这里是**端到端夹具**，不是可部署面：

- `lambda _u, _o: "owner"` 在这里是**明知故犯的口径**（与 `harness/demo_server.py`
  同一条），写在夹具里；在可部署应用里它是安全洞；
- 它只在 `pytest` 与本机 e2e 里被调用，NEVER 被任何部署脚本引用。

**差多少要有判据看着**：`extra_families()` 声明本模块比可部署应用多出来的那两族，
`tests/v041/test_e2e_full_stack.py` 判**等值**——多一族要有人来确认它是不是
也该进可部署应用，少一族说明鉴权补上了、这里该跟着收。

## 与 `harness/demo_server.py` 的关系

demo 栈多出来的是 `combo` / `analysis` / `interventions` 三族，**没有 `compose`**
（`demo_server` 那条注释：「owner 裁决：interventions 挂、compose 不挂」），
而且它的作业派发是 `asyncio.create_task` 直接跑，**不经 arq**。
所以 demo 栈跑不了「提交报告 → 入队 → worker 消费」这条链——本模块补的正是这一段，
NEVER 去改 demo 栈的那条 owner 裁决。
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from fastapi import FastAPI

from flint.api.app import create_app
from flint.authz import build_role_resolver
from flint.domain.models import JSON, JobKind
from flint.jobs.runner import PgJobRunner


def extra_families() -> tuple[str, ...]:
    """本模块比可部署应用多出来的族。判据判**等值**，见模块 docstring。

    `WIRE-07` 让 `analysis` 进了可部署应用，`WIRE-08` 让 `compose` 也进了——
    **现在这里一族都不多**。等值判据每次变红都是在提醒「又接通了一族」，
    红得对。这个空元组也意味着：本模块此刻只剩「把提交面按夹具口径配一遍」这一件事，
    哪天连那个也不需要了，它就该整个退休。
    """
    return ()


@dataclass
class E2EStackConfig:
    dsn: str
    user_id: str
    now: Callable[[], datetime]
    enqueue: Callable[[str, JobKind, JSON], Any]
    job_ids: Callable[[], str]
    topic_keywords_for: Callable[..., Any]
    # 队列缝（`WIRE-07`）：`create_app` 现在自己挂 analysis，入队走它那一侧。
    # 不给 → 提交回 503 点名 analysis，NEVER 默默不入队。
    redis_url: str | None = None
    queue_name: str | None = None


def build_runner(cfg: E2EStackConfig) -> PgJobRunner:
    """作业提交面。`enqueue` 从外面注入——**推真 arq 还是别的，由调用方决定**，
    本模块 NEVER 自己造一个队列连接。"""
    return PgJobRunner(
        dsn=cfg.dsn,
        role_resolver=build_role_resolver(cfg.dsn),   # AUTH-05：真解析器
        id_factory=cfg.job_ids,
        now=cfg.now,
        enqueue=cfg.enqueue,
    )


def build_e2e_app(cfg: E2EStackConfig) -> FastAPI:
    """**现在它就是 `create_app`。**

    `WIRE-07` 与 `WIRE-08` 之后，提交那两族（analysis / compose）都进了可部署应用，
    本模块**一族都不再补**——`extra_families()` 返回空元组，判据判等值。

    没有把这个函数删掉，是因为端到端那份判据要的是「打的是**装配后的那个**应用」，
    而这条口子留着，下一次再有「可部署应用挂不上、夹具先有」的族时，
    加回来的地方是确定的。它此刻的价值就是**那句空元组**：
    **NEVER 让夹具悄悄比线上多一族。**
    """
    return create_app(cfg.dsn, cfg.redis_url, cfg.queue_name)
