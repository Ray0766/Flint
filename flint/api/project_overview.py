"""BE-01：项目总览聚合端点 `GET /projects/{project_id}`。

## 补的是蓝本自己标出来的那个洞

`design_handoff_flint_web/README.md` 的路由表里，P14 项目总览那一行写着
**「无专属端点：topics + jobs + deliverables 组合」**——前端要自己发三次请求再拼。
而同一份 README 的铁律第一条是**零计算**：拼装是计算，它不该在前端。

所以这里把那个组合做成一个端点：一次请求，三个列表，各带状态。

## 越权返回 404 而不是 403

403 等于告诉对方「这个 id 存在，只是不给你看」——**状态码本身就泄露了存在性**，
还能被用来枚举 id。「查不到」与「不该看到」对外**长得一样**，
连错误码都一样（与 `flint/api/deref.py` 同一条口径）。

## 空态与错误态分清

项目在、但一个 topic 都没有 → 返回**空数组**，不是 404。
空数组说的是「查过了，没有」；404 说的是「没这个东西」。
混在一起时，用户看到 404 会以为自己的项目丢了。

## 只读，且 NEVER 造字段

本模块只有 `SELECT`。返回的每一项都是库里真有的列——
**后端算不出的值不返回、不填假值**：前端最想要的「完成度 60%」这类数，
后端算不出（没有总量、没有权重口径），给一个就是编。

## 交付物只有一份清单（`OVERVIEW-01` / `DEC-063`）

`projects` 表里另有一列同名的旧清单：建项时写一次，此后组稿与重写都不回写。
它与下面现查的那份清单对不上（单 `PROJECT-DOES-NOT-LIST-ITS-OWN-DELIVERABLES`）。
本模块**不读那一列**：交付物只认 `deliverables` 表，带 `version` / `supersedes`。
那一列留在库里没有删——删列是数据删除，`DEC-063` 不授权。

## 按 owner 过滤放在 SQL 里

不是取回来再判。取回来再判的写法，哪天有人删掉那两行 Python 判断，
数据已经出库了（同 `deref.py#_FACT_SQL` 的既有做法）。
项目过了门也**不代表它下面每条作业都归你**，所以 jobs 那一条另带一层 owner 过滤。
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import asyncpg
from fastapi import FastAPI, Header
from fastapi.responses import JSONResponse, Response

from flint.api.schemas import ErrorBody, ErrorCode

# 项目本体 + 归属一次判掉：owner 不符时**与不存在同一个结果**（都是 row is None）。
_PROJECT_SQL = """
SELECT project_id, owner, origin_id, topic_ids, chosen_topic_id,
       status, created_at
FROM projects
WHERE project_id = $1
  AND owner ->> 'kind' = 'user'
  AND owner ->> 'id' = $2
"""

_TOPICS_SQL = """
SELECT topic_id, seed_id, one_liner, target_user_tag, form_factor_tag, why_now
FROM topics
WHERE topic_id = ANY($1::text[])
ORDER BY topic_id
"""

# 作业另带一层 owner 过滤：项目归你，不代表它下面每条作业都归你。
_JOBS_SQL = """
SELECT job_id, kind, state, cancel_requested, error, initiated_by,
       created_at, updated_at
FROM jobs
WHERE project_id = $1
  AND owner_scope ->> 'kind' = 'user'
  AND owner_scope ->> 'id' = $2
ORDER BY created_at, job_id
"""

_DELIVERABLES_SQL = """
SELECT deliverable_id, type, version, supersedes, ledger_version,
       stale_reasons, reproducible, created_at
FROM deliverables
WHERE project_id = $1
ORDER BY version, deliverable_id
"""


@dataclass
class ProjectOverviewDeps:
    dsn: str


def _error(status: int, code: ErrorCode, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content=ErrorBody(code=code, message=message).model_dump(exclude_none=True),
    )


# 这几列在库里是 `jsonb`，asyncpg 取回来是**字符串**。逐个列名写死解码，
# NEVER 「看着像 JSON 就解」——那会把一个正好以 `[` 开头的正文字段解坏。
_JSONB_COLUMNS = frozenset({
    "owner", "owner_scope", "topic_ids", "stale_reasons",
    "change_log", "inputs", "meta", "progress", "budget", "cost_accum",
    "keyword_mapping", "why_now",
})


def _row(record: asyncpg.Record) -> dict[str, Any]:
    """行 → 可 JSON 化的字典。**只搬列，不加工**。

    时间戳转 ISO 字符串是序列化，不是计算；`jsonb` 列解回对象同理。
    NEVER 在这里合成任何库里没有的键。
    """
    out: dict[str, Any] = {}
    for key, value in dict(record).items():
        if hasattr(value, "isoformat"):
            out[key] = value.isoformat()
        elif key in _JSONB_COLUMNS and isinstance(value, str):
            out[key] = json.loads(value)
        else:
            out[key] = value
    return out


def create_project_overview_app(deps: ProjectOverviewDeps) -> FastAPI:
    app = FastAPI(title="Flint project overview (BE-01)")

    @app.get("/projects/{project_id}")
    async def project_overview(project_id: str, x_user_id: str = Header()) -> Response:
        conn = await asyncpg.connect(deps.dsn)
        try:
            project = await conn.fetchrow(_PROJECT_SQL, project_id, x_user_id)
            if project is None:
                # 「不存在」与「不该看到」走同一条出口：差一个字都能被用来枚举 id。
                return _error(404, "NOT_FOUND", f"unknown project: {project_id}")
            # `topic_ids` 是 jsonb，取回来是字符串——直接当列表用会把它按字符切开。
            raw_ids = project["topic_ids"]
            topic_ids = [
                str(x) for x in (json.loads(raw_ids) if isinstance(raw_ids, str)
                                 else (raw_ids or []))
            ]
            topics = await conn.fetch(_TOPICS_SQL, topic_ids)
            jobs = await conn.fetch(_JOBS_SQL, project_id, x_user_id)
            deliverables = await conn.fetch(_DELIVERABLES_SQL, project_id)
        finally:
            await conn.close()

        body = _row(project)
        # 三个列表**恒存在**：没有内容时是空数组，不是缺这个键、更不是 404。
        body["topics"] = [_row(r) for r in topics]
        body["jobs"] = [_row(r) for r in jobs]
        body["deliverables"] = [_row(r) for r in deliverables]
        return JSONResponse(status_code=200, content=body)

    return app
