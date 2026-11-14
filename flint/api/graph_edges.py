"""GRAPH-07：连线落盘端点（`POST /workbenches/{id}/edges`）。

## 服务端这一道是独立的一道

前端那一半只能保证「正常用界面的人不会建出空假设边」。curl 一发、或者哪天多一个
批量导入入口，空假设边就进库了——而一条没有假设的边说不出两端为什么被连起来：
它在画布上是一根线，在生成时是一条**没有理由的关联**，会被当成用户的判断写进文书。

## 校验只有一份（§6-H8）

边上的假设与 combo 的关联假设是同一个东西。本层因此**不写**任何
`if not hypothesis.strip()`，而是照常走 `add_edge`（它 import 的是 combo 的
`_require_str`），再把共享校验器抛出的 `OriginValidationError` 映射成
422 `EMPTY_HYPOTHESIS`。两份实现就是两种口径，用户会遇到
「在 combo 里能提交、在图谱里被拒」这种事。

## 两种拒绝不共用一个码

空假设与悬空边都返回 422，但码不同：前者要把光标送回假设输入框，
后者是接线错了（前端不该发出这种请求）。共用一个码的话，前端只能弹一句通用报错，
而用户不知道该改什么。
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from functools import partial
from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from flint.api.errors import origin_validation_error
from flint.api.schemas import ErrorBody, ErrorCode
from flint.graph.store import GraphStoreLike, add_edge
from flint.topic.create import OriginValidationError


@dataclass
class GraphEdgeDeps:
    store: GraphStoreLike
    now: Callable[[], datetime]
    edge_model: Any


class EdgeIn(BaseModel):
    edge_id: str
    from_node_id: str
    to_node_id: str
    hypothesis: str = ""      # 缺字段与空字符串走同一条路：NEVER 当成「没填就算没有」


def _error(status: int, code: ErrorCode, message: str) -> JSONResponse:
    body = ErrorBody(code=code, message=message, detail=None)
    return JSONResponse(status_code=status, content=body.model_dump(exclude_none=True))


def create_graph_edge_app(deps: GraphEdgeDeps) -> FastAPI:
    app = FastAPI(title="flint-graph-edges-api")

    @app.post("/workbenches/{graph_id}/edges")
    async def create_edge(graph_id: str, payload: EdgeIn) -> Response:
        try:
            # **同步 store 挪出事件循环**（`PERSIST-01` 立的护栏）。
            # `PERSIST-02` 把图换成 SQL 件时给 `workbenches.py` 包了这一层，
            # **漏了这一个**——那时这条路上的 store 还是内存件，包不包都跑得动。
            # 换成 `PgGraphStore` 之后它每一次都抛 `BlockingCallOnEventLoop`，
            # 而那道护栏是对的：它拦的是「在事件循环上阻塞住整个进程」。
            edge = await run_in_threadpool(partial(
                add_edge,
                deps.store, graph_id=graph_id, edge_id=payload.edge_id,
                from_node_id=payload.from_node_id, to_node_id=payload.to_node_id,
                hypothesis=payload.hypothesis, now=deps.now(),
                model=deps.edge_model,
            ))
        except OriginValidationError as err:       # H8 共享校验器说的话
            # FIX-10：映射**只有一处**（`flint/api/errors.py`）。
            # 这一条的答复没变（422 EMPTY_HYPOTHESIS），变的是它**从哪来**——
            # 各写一个 except 分支的后果是下一条端点会照着最近的那个抄，
            # 而它抄到哪一个取决于作者先看到哪一份。
            return origin_validation_error(err)
        except ValueError as err:                  # 悬空边：两端必须都在
            return _error(422, "VALIDATION_FAILED", str(err))
        return JSONResponse(
            status_code=201,
            content={
                "edge_id": edge.edge_id, "graph_id": edge.graph_id,
                "from_node_id": edge.from_node_id, "to_node_id": edge.to_node_id,
                "hypothesis": edge.hypothesis,
            },
        )

    return app
