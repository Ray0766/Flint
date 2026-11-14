"""vibe_pack 内容读取口（BE-02）+ 三与门的输入类型（M4-028，技术方案 E3）。

## ROUTE-01：出件那条路已经搬走

本模块原来还注册 `GET /deliverables/{id}/render?fmt=pack|markdown`——
与 `deliverables.py` **同一条路径**。两个 app 各自独立时互不干扰，
并成一个应用后先挂的先匹配、后挂的静默失效。

owner 裁决 `deliverables.py` 赢，出件面收敛到那一条。
**门禁不是被删掉而是搬过去了**：`GateInputs` 这个类型仍在本模块
（**同一份真相**，赢家 import 它），三与判定 `vibe_export_gate` 在赢家的
`fmt=pack` 分支里跑，拒绝仍是 409 EXPORT_BLOCKED 带 violations 分类。

**单文件 CLAUDE.md 预览（`fmt=markdown`）随那条路一起没了**：
赢家的 `fmt=markdown` 是 Block 树渲染，两种 markdown 一条路径上放不下。
内容仍可读——走下面的 `/pack`（逐章给，且不算导出）。
要把带门禁的单文件预览接回来需要一个新的 fmt 值，那是 owner 的口径决定。

## BE-02：`GET /deliverables/{id}/pack` —— 读内容，不是导出

蓝本路由表 P12 那一行写着「内容端点未接（pack 装配仅离线）」：
vibe_pack 查看器拿不到内容，因为装配只在离线跑、没有读的口。本卡补那个口。

**读内容与导出是两条路，不能合并**：

| | `/render?fmt=pack`（`deliverables.py`） | `/pack`（本模块） |
|---|---|---|
| 干什么 | 出件 | 看内容 |
| 过导出门禁 | **是**（审11：预览与出件同门） | **否**——看内容不是导出 |
| 现场装配 | 由注入的 builder 出 bundle | **只读已有产物** |
| 没有产物 | 走 builder | 回「尚未生成」态 |

**读的那条路 NEVER 调装配器**：装配要跑门禁、算副本哈希、过 S2-8 自检。
放进一个 GET 里的话，一次刷新页面就跑一遍，而且装出来的与导出那份
可能不是同一份（两次装配之间源变了）。

**产物不存在回「尚未生成」而不是 404**：404 说的是「没这个交付物」，
而这里交付物是在的，只是 pack 还没装。混在一起时用户会以为交付物丢了。

**冻结件副本只给清单与哈希，不给内容**：副本是二进制、动辄几十 KB，
塞进 JSON 里既没人看也拖慢每次打开。要看内容走导出那条路（zip 里有）。
"""
from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from fastapi import FastAPI, Header
from fastapi.responses import JSONResponse, Response

from flint.api.schemas import ErrorBody, ErrorCode
from flint.domain.models import DagReport
from flint.registry.gate import RegistryGateResult
from flint.spec.pack_zip import PackBundle


@dataclass(frozen=True)
class GateInputs:
    blocking_block_ids: list[str]
    dag_report: DagReport
    registry: RegistryGateResult


PackBuilder = Callable[[str], Awaitable[PackBundle]]
GateInputsFetcher = Callable[[str], Awaitable[GateInputs]]
# BE-02：读内容那条路要的两件事，都由调用方注入——
# 本层不认识库表，也不该认识（同 `deref.py` 把归属判定放在注入点的做法）。
PackOwnerFetcher = Callable[[str], Awaitable[str | None]]   # None = 这个交付物不存在
PackReadyFetcher = Callable[[str], Awaitable[bool]]         # False = pack 还没装


@dataclass
class PackApiDeps:
    dsn: str
    bundle_builder: PackBuilder
    gate_inputs: GateInputsFetcher
    # 两项默认 `None`：既有装配点（M4-028）一个字不用改，
    # 不注入时读内容那条路直接 404——**NEVER 在没有归属判定时把内容交出去**。
    pack_owner: PackOwnerFetcher | None = None
    pack_ready: PackReadyFetcher | None = None


# 章头形如 `## S1 Charter`。**从 markdown 里数出来**，NEVER 写死九个字符串：
# 写死的话，装配少了一章这里照样报九章，而读的人以为拿到的是全本。
_CHAPTER_HEAD = re.compile(r"^## (S\d+) ", re.MULTILINE)


def split_chapters(claude_md: str) -> list[dict[str, str]]:
    """CLAUDE.md 合卷 → 逐章。切不出章就返回空表，**NEVER 把整篇当成一章**。"""
    marks = list(_CHAPTER_HEAD.finditer(claude_md))
    out: list[dict[str, str]] = []
    for index, match in enumerate(marks):
        end = marks[index + 1].start() if index + 1 < len(marks) else len(claude_md)
        out.append({"id": match.group(1), "body": claude_md[match.start():end].strip()})
    return out


def pack_content_json(deliverable_id: str, bundle: PackBundle | None) -> dict[str, Any]:
    """产物 → 响应体。`bundle is None` = 尚未生成（**不是 404**）。

    NEVER 造字段：每一项都来自 `PackBundle` / `ContractsCopy` 的真字段。
    也 NEVER 合成「完整度 8/9 章」这类分值——章节数是**计数**不是分值，
    把它除以 9 是前端的事，而这里连那个分母都不给（少一章是内容问题，
    不是「完成度 89%」）。
    """
    if bundle is None:
        return {
            "deliverable_id": deliverable_id,
            "status": "not_generated",
            "chapters": [],
            "human_digest": None,
            "tasks": [],
            "contracts": [],
        }
    try:
        tasks = list(json.loads(bundle.tasks_json).get("tasks", []))
    except (ValueError, AttributeError):
        # 任务清单读不动时给空表**并不掩盖**——status 仍是 generated，
        # 章节照给。硬把整个响应变成 404 会把能看的那部分也一起藏掉。
        tasks = []
    return {
        "deliverable_id": deliverable_id,
        "status": "generated",
        "chapters": split_chapters(bundle.claude_md),
        # Human Digest 是**监工视图**（`pack_assemble` 原话「NEVER 并入 markdown」）。
        # 带上这个标记，否则前端会把它和九章一起喂进上下文。
        "human_digest": {"body": bundle.human_digest, "for_ai_context": False},
        "tasks": tasks,
        "contracts": [
            {"name": name, "sha256": bundle.contracts.manifest.get(name, "")}
            for name in sorted(bundle.contracts.files)
        ],
    }


def _error(status: int, code: ErrorCode, message: str,
           detail: dict[str, object] | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content=ErrorBody(
            code=code, message=message, detail=detail
        ).model_dump(exclude_none=True),
    )


def create_pack_app(deps: PackApiDeps) -> FastAPI:
    app = FastAPI(title="flint-pack-api")

    # ROUTE-01：这里原来还注册着 `GET /deliverables/{id}/render`
    # （`?fmt=pack|markdown`），与 `deliverables.py:97` **抢同一条路径**。
    # FastAPI 对重复注册不报错，先挂的先匹配——两个模块并进一个应用后，
    # 行为由挂载顺序决定，而顺序是文件里两行的先后。
    #
    # owner 裁决 `deliverables.py` 赢（它管五种 fmt；反过来选会让另外四种
    # 全部落到只认 pack 的处理函数）。**这里删的是路由，不是门禁**：
    # 那道三与门（M4-027）连同它的 409 姿态一起搬进了赢家
    # （`DeliverableApiDeps.pack_gate_inputs`），并非丢掉。
    #
    # 留着不挂只会把静默遮蔽换成死代码：下一个人把它挂上去，冲突原样回来。
    # `deps.gate_inputs` 仍在 deps 上——装配点一个字不用改，
    # 且它就是赢家那道门要的同一份输入（**同一个类型，不是两份真相**）。

    @app.get("/deliverables/{deliverable_id}/pack")
    async def pack_content(deliverable_id: str, x_user_id: str = Header()) -> Response:
        """读 vibe_pack 内容（BE-02）。**不过导出门禁、不现场装配。**"""
        if deps.pack_owner is None or deps.pack_ready is None:
            # 没注入归属判定就不给内容：那时任何人都能读任何 pack。
            # 「查不到」与「不该看到」在这里也走同一条出口。
            return _error(404, "NOT_FOUND", f"unknown deliverable: {deliverable_id}")
        owner = await deps.pack_owner(deliverable_id)
        if owner is None or owner != x_user_id:
            # 越权与不存在**同一个出口、同一个错误码**：403 等于告诉对方
            # 「这个 id 存在，只是不给你看」——状态码本身就泄露了存在性。
            return _error(404, "NOT_FOUND", f"unknown deliverable: {deliverable_id}")
        bundle = (
            await deps.bundle_builder(deliverable_id)
            if await deps.pack_ready(deliverable_id) else None
        )
        return JSONResponse(
            status_code=200, content=pack_content_json(deliverable_id, bundle))

    return app
