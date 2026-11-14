"""PERSIST-03：`template_solidify` 作业的消费者——**分派表里最后一条未接线的 kind**。

改前这条 kind 挂在 `flint/jobs/dispatch.py` 的 `UnwiredKindReason` 里，
理由写着「`flint/design/solidify.py` 的 `solidify_mock` 是同步函数，
仓里还没有 `template_solidify` 作业的消费者」。

**本模块就是那个消费者**，移走之后 `UnwiredKindReason` **空了**。

## 本模块只做三件事：取参 → 转调 → 发事件

固化的全部语义在 `flint/design/solidify.py#solidify_mock`（剥水印、换插槽、
拒示例残留）与 `flint/design/templates/registry.py#register_template`
（去重、版本、checksum 绑定）里，**本模块一行都不重写**。

重写一份的后果很具体：作业路径与端点路径（`POST /design/templates`）
会长出两套固化口径，而用户从设计台点「固化」与从作业提交固化，
拿到的模板可能不一样——**而两者长得一模一样**。

## 被拒时抛出去，NEVER 吞掉

`SolidifyBlocked` 往上抛，由 `dispatch_job` 记 failed 并带上原文
（`dispatch.py` 的既有口径：先记 failed 再抛，作业状态 NEVER 停在 `queued`）。

吞掉改成「发一个 accepted=False 的事件然后正常结束」的话，作业会变成 `done`——
而**一个 `done` 的作业与一个真的固化成功了的作业在作业列表里长得一模一样**。

## 这条路一次网络都不打

固化是**确定性**的文本变换 + 落库：同一份样板固化两次得到同一个 checksum，
而 checksum 与内容绑定正是「产物可复现」（`S2-2` 第三条铁律）在这一族的落点。
一旦有人把模型塞进这条路，同一份样板会固化出两个版本，
而版本序列会显示「内容改过」——**它没改过**。
"""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from flint.design.solidify import solidify_mock
from flint.domain.models import JSON, Principal


@dataclass
class TemplateSolidifyDeps:
    """注入件。**registry 与 emit 都从外面进来**——本模块 NEVER 自己建存储或通道。"""

    registry: Any
    now: datetime
    #: 发事件（SSE 那一侧的出口）。`solidify_result` 是它唯一会发的那一种。
    emit: Callable[[Any], Awaitable[None]]


class TemplateSolidifyPayloadInvalid(ValueError):
    """payload 缺字段。**点名缺哪一个**，NEVER 用一个默认值把它糊过去。"""


def _require(payload: JSON, key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise TemplateSolidifyPayloadInvalid(
            f"template_solidify 的 payload 缺 {key!r}："
            "固化 NEVER 拿一个默认值顶上——那会固化出一份不是用户要的模板")
    return value


def _owner(payload: JSON) -> Principal:
    raw = payload.get("owner")
    if not isinstance(raw, dict) or not raw.get("id"):
        raise TemplateSolidifyPayloadInvalid(
            "template_solidify 的 payload 缺 'owner'："
            "模板的去重与版本都按 owner 算，认错人会让两个人的版本序列串在一起")
    kind = raw.get("kind", "user")
    return Principal(kind="org" if kind == "org" else "user", id=str(raw["id"]))


async def run_template_solidify(
    job_id: str, payload: JSON, deps: TemplateSolidifyDeps,
) -> None:
    """跑一次固化。转调既有实现，成功发 `solidify_result`，被拒抛出去。"""
    del job_id                      # 事件里不带 job_id：SolidifyResult 没有那个字段
    from contracts_v04.models_v04 import SolidifyResult, TemplateRecord

    # **挪进线程**：worker 在事件循环上跑 handler，而 `registry.append` 换成
    # SQL 实现之后是一次阻塞调用（`flint/db/sync_bridge.py`）。
    # 直接在这里调它会把整条循环停住，桥会当场抛 `BlockingCallOnEventLoop`。
    # `asyncio.to_thread` 是标准库，NEVER 为这一件事引一个新依赖。
    event = await asyncio.to_thread(
        solidify_mock,
        deps.registry,
        mock_html=_require(payload, "mock_html"),
        template_id=_require(payload, "template_id"),
        owner=_owner(payload),
        name=_require(payload, "name"),
        source_deliverable_id=_optional(payload, "source_deliverable_id"),
        now=deps.now,
        model=TemplateRecord,
        event_model=SolidifyResult,
    )
    await deps.emit(event)


def _optional(payload: JSON, key: str) -> str | None:
    value = payload.get(key)
    return value if isinstance(value, str) and value.strip() else None
