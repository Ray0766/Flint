"""HOTSPOT-03 验收（后端半）：分析界面读路径**零新计算**。

acceptance（tasks-v04.json#HOTSPOT-03）第一条的后端一侧：
「进入即渲染既有判定与证据概览；无任何新分析调用」。

前端 spy 能证明浏览器没发写请求；但只要后端把一次 GET 做成了「顺手重算一遍」，
用户仍会在每次打开分析界面时付一次钱、并可能看到与上次不同的判定——
**同一个热点、什么都没做、判定却变了**，那会让判定本身失去可引用性。
所以这一半断言的是服务端事实：分析界面用到的两个读端点只读快照、只跑 SELECT、
不触发任何生成通道；判定缺失时是 404 而 NEVER 是一个当场造出来的判定。

一处规格与真件不符已上报（docs/blocked/HOTSPOT-03.md，非阻塞）：卡片 inputs 写的是
`GET /clusters/{id}/verdict(既有)`，真件里判定按 job 键落在 `GET /jobs/{id}/verdict`，
且 contracts 中 Job 无 cluster 字段、jobs 表无 cluster_id ——cluster→判定 的对应关系
当前无持久化真相。本卡按「缺就是缺」处理：对应关系由调用方给出，NEVER 由视图或端点
拼一个 job id 去试（K 组绕行纪律）。
"""
from __future__ import annotations

import ast
import asyncio
import json
from collections.abc import Coroutine
from pathlib import Path
from typing import Any, TypeVar

import httpx
import pytest

from flint.api import views as views_module
from flint.api.views import ViewsApiDeps, create_views_app

REPO_ROOT = Path(__file__).resolve().parents[3]
VIEWS_SRC = REPO_ROOT / "flint" / "api" / "views.py"

WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
VERDICT_CODES = ("A_infeasible", "B_red_ocean", "C_opportunity", "D_insufficient")

VERDICT_PAYLOAD = {
    "verdict": "C_opportunity",
    "all_satisfied": ["C_opportunity"],
    "key_citation_ids": ["cit-1"],
    "rationale_fact_ids": ["fact-1"],
    "competitors": [],
    "constraints_checked": True,
    "gaps": [],
}


class RecordingConn:
    """假连接：记下每一条 SQL，返回罐头行。零真实网络、零真实 PG（S2-7）。"""

    def __init__(self, sql_log: list[str], verdict: bytes | None) -> None:
        self.sql_log = sql_log
        self._verdict = verdict

    async def fetchval(self, sql: str, *args: Any) -> Any:
        self.sql_log.append(sql)
        return self._verdict

    async def fetch(self, sql: str, *args: Any) -> list[dict[str, Any]]:
        self.sql_log.append(sql)
        return [
            {
                "card_id": "card-1", "cluster_id": "c-1",
                "keyword_ids": json.dumps(["k1", "k2"]),
                "flags": json.dumps(["needs_price"]),
                "top_links": json.dumps(["http://l1", "http://l2"]),
            }
        ]

    async def execute(self, sql: str, *args: Any) -> None:
        self.sql_log.append(sql)

    async def close(self) -> None:
        return None


def _is_write_sql(sql: str) -> bool:
    head = sql.strip().split(None, 1)[0].upper()
    return head in {"INSERT", "UPDATE", "DELETE", "TRUNCATE", "MERGE"}


@pytest.fixture
def sql_log(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    log: list[str] = []

    async def fake_connect(dsn: str) -> RecordingConn:
        return RecordingConn(log, json.dumps(VERDICT_PAYLOAD).encode())

    monkeypatch.setattr(views_module.asyncpg, "connect", fake_connect)
    return log


@pytest.fixture
def sql_log_no_verdict(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    log: list[str] = []

    async def fake_connect(dsn: str) -> RecordingConn:
        return RecordingConn(log, None)

    monkeypatch.setattr(views_module.asyncpg, "connect", fake_connect)
    return log


T = TypeVar("T")


def run(coro: Coroutine[Any, Any, T]) -> T:
    """同步驱动一次协程（仓库既有惯例：tests/fe_views 同款，无 asyncio_mode 依赖）。"""
    return asyncio.run(coro)


def _app() -> Any:
    return create_views_app(ViewsApiDeps(dsn="postgresql://unused/none"))


async def _get(app: Any, path: str) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        return await client.get(path)


def _routes(app: Any) -> dict[str, set[str]]:
    table: dict[str, set[str]] = {}
    for route in app.routes:
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None)
        if path is None or methods is None:
            continue
        table.setdefault(path, set()).update(methods)
    return table


def test_analysis_read_endpoints_are_get_only() -> None:
    """分析界面用到的两个读端点存在且只读——一个写方法都不挂。"""
    table = _routes(_app())
    for path in ("/clusters/{cluster_id}/evidence-cards", "/jobs/{job_id}/verdict"):
        assert path in table, f"分析界面依赖的读端点缺失：{path}"
        assert not (table[path] & WRITE_METHODS), f"{path} 挂了写方法：{table[path]}"


def test_views_app_registers_zero_write_routes() -> None:
    """整张读端点表零写路由：打开分析界面这条链路上没有任何可写入口。"""
    table = _routes(_app())
    offenders = {p: m & WRITE_METHODS for p, m in table.items() if m & WRITE_METHODS}
    assert offenders == {}, f"读端点表出现写路由：{offenders}"


def test_verdict_read_runs_select_only(sql_log: list[str]) -> None:
    """读既有判定只跑 SELECT：零 INSERT/UPDATE/DELETE，且 SQL 真的跑过（非空转）。"""
    response = run(_get(_app(), "/jobs/job-1/verdict"))

    assert response.status_code == 200
    assert response.json()["verdict"]["verdict"] == "C_opportunity"
    assert len(sql_log) >= 1
    assert [s for s in sql_log if _is_write_sql(s)] == []


def test_evidence_overview_read_runs_select_only(sql_log: list[str]) -> None:
    """读证据概览同样只跑 SELECT——概览是查出来的，不是当场算出来的。"""
    response = run(_get(_app(), "/clusters/c-1/evidence-cards"))

    assert response.status_code == 200
    assert response.json()["evidence_cards"][0]["card_id"] == "card-1"
    assert len(sql_log) >= 1
    assert [s for s in sql_log if _is_write_sql(s)] == []


def test_write_sql_detector_catches_writes() -> None:
    """阴性对照：写语句检查器认得出写语句。

    否则「全是 SELECT」这条断言可能只是因为检查器谁都不认——一把见谁都放行的尺子。
    """
    assert _is_write_sql("INSERT INTO snapshots VALUES (1)")
    assert _is_write_sql("  update jobs SET state = 'done'")
    assert _is_write_sql("DELETE FROM clusters")
    assert not _is_write_sql("SELECT payload FROM snapshots WHERE snapshot_id = $1")


def test_missing_verdict_is_404_never_a_fabricated_one(
    sql_log_no_verdict: list[str],
) -> None:
    """没有既有判定就是 404：NEVER 当场造一个（哪怕造的是 D_insufficient）。"""
    response = run(_get(_app(), "/jobs/job-未判/verdict"))

    assert response.status_code == 404
    body = response.text
    for code in VERDICT_CODES:
        assert code not in body, f"404 响应里出现了判定值 {code}"
    assert [s for s in sql_log_no_verdict if _is_write_sql(s)] == []


def test_read_module_imports_no_generation_channel() -> None:
    """静态断言：读端点模块不接生成通道（Gate 引擎 / LLM / 作业下发）。

    「零新计算」若只在运行时验，改天有人在端点里补一句「查不到就跑一次」也照样绿；
    这条从 import 面上断它——生成通道根本不在这个模块的可达范围内。
    """
    tree = ast.parse(VIEWS_SRC.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)

    forbidden = ("anthropic", "flint.gate", "flint.jobs", "flint.llm", "flint.compose")
    hits = [m for m in imported for f in forbidden if m == f or m.startswith(f + ".")]
    assert hits == [], f"读端点模块接上了生成通道：{hits}"
