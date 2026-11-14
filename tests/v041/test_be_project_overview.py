"""BE-01：项目总览聚合端点 `GET /projects/{id}`（蓝本 P14 标注「无专属端点」）。

## 这张卡补的是什么

蓝本 `design_handoff_flint_web/README.md` 的路由表里，P14 项目总览那一行写着
**「无专属端点：topics + jobs + deliverables 组合」**——意思是前端要自己发三次请求
再拼起来。而蓝本自己的铁律第一条是**零计算**：拼装是计算，它不该在前端。

所以本卡把那个组合做成一个端点。

## 四条不肯含糊的地方

1. **越权取他人项目返回 404 而不是 403**。403 等于告诉对方「这个 id 存在，只是不给你看」——
   **状态码本身就泄露了存在性**，还能被用来枚举 id。与 `flint/api/deref.py` 同一条口径。
2. **空态与错误态分清**：项目在、但一个 topic 都没有 → 返回**空数组**，不是 404。
   只有真正未知的 id 才 404。空数组说的是「查过了，没有」，404 说的是「没这个东西」。
3. **只读**：这个端点 NEVER 写库。判据用 SQL 关键字检测作阴性对照。
4. **NEVER 造字段**：返回的每一项都要在库里真有那一列。后端算不出的值不返回、不填假值。
"""
from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path

import asyncpg
import pytest
from fastapi.testclient import TestClient

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from flint.api.project_overview import (
    ProjectOverviewDeps,
    create_project_overview_app,
)
from tests.conftest import TEST_DSN

MODULE = REPO / "flint" / "api" / "project_overview.py"

OWNER = "u-be01"
STRANGER = "u-other"


def _client() -> TestClient:
    return TestClient(create_project_overview_app(ProjectOverviewDeps(dsn=TEST_DSN)))


async def _seed(*, with_children: bool) -> None:
    conn = await asyncpg.connect(TEST_DSN)
    try:
        await conn.execute("DELETE FROM jobs WHERE project_id LIKE 'be01-%'")
        await conn.execute("DELETE FROM deliverables WHERE project_id LIKE 'be01-%'")
        await conn.execute("DELETE FROM projects WHERE project_id LIKE 'be01-%'")
        await conn.execute("DELETE FROM topics WHERE topic_id LIKE 'be01-%'")
        await conn.execute("DELETE FROM topic_seeds WHERE seed_id LIKE 'be01-%'")
        await conn.execute("DELETE FROM origins WHERE origin_id LIKE 'be01-%'")

        for pid, owner in (("be01-mine", OWNER), ("be01-theirs", STRANGER)):
            await conn.execute(
                "INSERT INTO projects (project_id, owner, origin_id, topic_ids, "
                "chosen_topic_id, deliverable_ids, change_log, status, created_at) "
                "VALUES ($1, $2::jsonb, $3, $4::jsonb, $5, $6::jsonb, $7::jsonb, "
                "$8, now())",
                pid, json.dumps({"id": owner, "kind": "user"}), "be01-origin",
                json.dumps(["be01-t1"] if with_children else []), None,
                "[]", "[]", "active")
        if not with_children:
            return
        # 外键链是 origins ← topic_seeds ← topics，**逐层种齐**。
        # 少一层就 `ForeignKeyViolationError`——那不是断言不过，是库没备齐
        # （与 `tests/conftest.py` 里那句「空库缺 12 行 categories」同一种坑）。
        await conn.execute(
            "INSERT INTO origins (origin_id, kind, owner, payload, created_at) "
            "VALUES ($1, $2, $3::jsonb, $4::jsonb, now())",
            "be01-origin", "combo", json.dumps({"id": OWNER, "kind": "user"}), "{}")
        # `topics.seed_id` 有外键指向 `topic_seeds`——先种它，否则插 topic 会
        # `ForeignKeyViolationError`（那不是断言不过，是库没备齐）。
        await conn.execute(
            "INSERT INTO topic_seeds (seed_id, origin_id, keywords, context_text) "
            "VALUES ($1, $2, $3::jsonb, $4)",
            "be01-seed", "be01-origin", json.dumps(["锂电池回收"]), "种子上下文")
        # `why_now` / `keyword_mapping` 是 jsonb，`embedding` 是 NOT NULL 的
        # vector(1024)——三处都照库里的真类型给，NEVER 猜一个短的塞进去。
        await conn.execute(
            "INSERT INTO topics (topic_id, seed_id, one_liner, target_user_tag, "
            "form_factor_tag, why_now, keyword_mapping, embedding) "
            "VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7::jsonb, $8::vector)",
            "be01-t1", "be01-seed", "把热点变成计划书", "独立开发者", "web",
            json.dumps({"text": "现在做正好", "speculative": False}), "{}",
            "[" + ",".join(["0"] * 1024) + "]")
        await conn.execute(
            "INSERT INTO jobs (job_id, kind, project_id, owner_scope, state, progress, "
            "budget, cost_accum, cancel_requested, initiated_by, created_at, updated_at) "
            "VALUES ($1, $2, $3, $4::jsonb, $5, $6, $7, $8, $9, $10, now(), now())",
            "be01-j1", "gate1_analysis", "be01-mine",
            json.dumps({"id": OWNER, "kind": "user"}), "done", 1.0, 0.0, 0.0,
            False, OWNER)
        await conn.execute(
            "INSERT INTO deliverables (deliverable_id, project_id, type, version, "
            "inputs, ledger_version, generation_record_id, stale_reasons, "
            "created_at, reproducible, meta) "
            "VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7, $8::jsonb, now(), $9, $10::jsonb)",
            "be01-d1", "be01-mine", "report", 1, "{}", 1, "be01-gr1", "[]", True, "{}")
    finally:
        await conn.close()


@pytest.fixture
def seeded() -> None:
    asyncio.run(_seed(with_children=True))


@pytest.fixture
def seeded_empty() -> None:
    asyncio.run(_seed(with_children=False))


# ───────────────────────── 一、三个列表一次给全（acceptance①②）


@pytest.mark.compose
def test_the_overview_returns_all_three_lists(seeded: None) -> None:
    """一次请求拿到 topics / jobs / deliverables——前端不再拼三次。"""
    del seeded
    body = _client().get("/projects/be01-mine", headers={"X-User-Id": OWNER}).json()

    assert {"project_id", "topics", "jobs", "deliverables"} <= set(body)
    assert [t["topic_id"] for t in body["topics"]] == ["be01-t1"]
    assert [j["job_id"] for j in body["jobs"]] == ["be01-j1"]
    assert [d["deliverable_id"] for d in body["deliverables"]] == ["be01-d1"]


@pytest.mark.compose
def test_each_item_carries_its_status(seeded: None) -> None:
    """acceptance②：三个列表**各带状态**——没有状态的清单读不出「进行到哪了」。"""
    del seeded
    body = _client().get("/projects/be01-mine", headers={"X-User-Id": OWNER}).json()

    assert body["jobs"][0]["state"] == "done"
    assert body["deliverables"][0]["version"] == 1
    assert body["status"] == "active"


@pytest.mark.compose
def test_the_backend_does_the_joining_not_the_caller(seeded: None) -> None:
    """组合逻辑在后端：topics 是按 `projects.topic_ids` 取出来的，不是让调用方再问一次。"""
    del seeded
    body = _client().get("/projects/be01-mine", headers={"X-User-Id": OWNER}).json()

    assert body["topics"][0]["one_liner"] == "把热点变成计划书"


# ───────────────────────── 二、空态与错误态分清（acceptance④）


@pytest.mark.compose
def test_an_empty_project_returns_empty_lists_not_404(seeded_empty: None) -> None:
    """项目在、但没有任何 topic/job/deliverable → **空数组**，不是 404。

    空数组说的是「查过了，没有」；404 说的是「没这个东西」。
    两者混在一起时，用户看到 404 会以为自己的项目丢了。
    """
    del seeded_empty
    response = _client().get("/projects/be01-mine", headers={"X-User-Id": OWNER})

    assert response.status_code == 200
    body = response.json()
    assert body["topics"] == []
    assert body["jobs"] == []
    assert body["deliverables"] == []


@pytest.mark.compose
def test_a_truly_unknown_project_is_404(seeded: None) -> None:
    del seeded
    response = _client().get("/projects/be01-nope", headers={"X-User-Id": OWNER})

    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"


# ───────────────────────── 三、多租户：越权是 404 不是 403（acceptance③）


@pytest.mark.compose
def test_another_owners_project_is_404_not_403(seeded: None) -> None:
    """**状态码本身就泄露存在性**：403 等于告诉对方「这个 id 存在，只是不给你看」。"""
    del seeded
    response = _client().get("/projects/be01-theirs", headers={"X-User-Id": OWNER})

    assert response.status_code == 404, "越权返回了 403，等于确认了这个 id 存在"


@pytest.mark.compose
def test_the_two_kinds_of_404_are_indistinguishable(seeded: None) -> None:
    """「不存在」与「不该看到」对外**长得一样**——差一个字都能被用来枚举 id。"""
    del seeded
    client = _client()
    unknown = client.get("/projects/be01-nope", headers={"X-User-Id": OWNER})
    forbidden = client.get("/projects/be01-theirs", headers={"X-User-Id": OWNER})

    assert unknown.status_code == forbidden.status_code
    assert unknown.json()["code"] == forbidden.json()["code"]


@pytest.mark.compose
def test_the_owner_still_sees_their_own(seeded: None) -> None:
    """反向：本人照样看得见。见谁都 404 的隔离等于把功能关掉。"""
    del seeded
    response = _client().get("/projects/be01-theirs", headers={"X-User-Id": STRANGER})

    assert response.status_code == 200


@pytest.mark.compose
def test_the_jobs_list_is_filtered_by_owner_too(seeded: None) -> None:
    """作业也按 owner 过滤：项目过了门，不代表它下面每条作业都归你。"""
    async def add_foreign_job() -> None:
        conn = await asyncpg.connect(TEST_DSN)
        try:
            await conn.execute(
                "INSERT INTO jobs (job_id, kind, project_id, owner_scope, state, "
                "progress, budget, cost_accum, cancel_requested, initiated_by, "
                "created_at, updated_at) VALUES ($1, $2, $3, $4::jsonb, $5, $6, "
                "$7, $8, $9, $10, now(), now())",
                "be01-j-foreign", "gate1_analysis", "be01-mine",
                json.dumps({"id": STRANGER, "kind": "user"}), "queued",
                0.0, 0.0, 0.0, False, STRANGER)
        finally:
            await conn.close()

    del seeded
    asyncio.run(add_foreign_job())
    body = _client().get("/projects/be01-mine", headers={"X-User-Id": OWNER}).json()

    assert [j["job_id"] for j in body["jobs"]] == ["be01-j1"]


def test_identity_is_required() -> None:
    """没带身份直接 422——匿名读别人的项目总览是最容易被忘掉的那条门。"""
    response = _client().get("/projects/be01-mine")

    assert response.status_code == 422


# ───────────────────────── 四、只读（acceptance③）


def test_the_module_never_writes() -> None:
    """阴性对照：模块里 NEVER 出现写库语句。

    判在**去掉注释与文档串之后**的源码上：注释里解释「本端点只读」不算写库。
    """
    import ast

    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    literals = [
        node.value for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]
    docstrings = {ast.get_docstring(n) for n in ast.walk(tree)
                  if isinstance(n, ast.Module | ast.ClassDef | ast.FunctionDef
                                | ast.AsyncFunctionDef)}
    sql = " ".join(s for s in literals if s not in docstrings)

    for verb in ("INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE"):
        assert not re.search(rf"\b{verb}\b", sql, re.IGNORECASE), f"模块里有 {verb}"


def test_the_module_only_uses_select() -> None:
    """正向：它确实在查库（不是一个什么都不做的空壳）。"""
    source = MODULE.read_text(encoding="utf-8")

    assert "SELECT" in source
    assert "fetch" in source


# ───────────────────────── 五、NEVER 造字段（acceptance⑤）


@pytest.mark.compose
def test_every_returned_key_exists_in_the_database(seeded: None) -> None:
    """返回的每个字段都要在库里真有那一列——**后端算不出的值不返回、不填假值**。"""
    async def columns(table: str) -> set[str]:
        conn = await asyncpg.connect(TEST_DSN)
        try:
            rows = await conn.fetch(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = $1", table)
        finally:
            await conn.close()
        return {r["column_name"] for r in rows}

    del seeded
    body = _client().get("/projects/be01-mine", headers={"X-User-Id": OWNER}).json()

    for key, table in (("topics", "topics"), ("jobs", "jobs"),
                       ("deliverables", "deliverables")):
        available = asyncio.run(columns(table))
        for item in body[key]:
            invented = set(item) - available
            assert invented == set(), f"{key} 里造了库里没有的字段：{invented}"


@pytest.mark.compose
def test_jsonb_columns_come_back_as_objects_not_strings(seeded: None) -> None:
    """`jsonb` 列要解回**对象**，NEVER 原样交出 asyncpg 给的那串字符串。

    不解的话，前端拿到的 `stale_reasons` 是 `"[]"` 这个**字符串**，
    `.length` 是 2、`.map` 直接炸——而后端这边看起来一切正常
    （变异考⑭ 实测：关掉解码，十四条判据全绿）。
    """
    del seeded
    body = _client().get("/projects/be01-mine", headers={"X-User-Id": OWNER}).json()

    assert isinstance(body["owner"], dict), f"owner 没解开：{body['owner']!r}"
    assert isinstance(body["topic_ids"], list)
    assert isinstance(body["deliverables"][0]["stale_reasons"], list)
    assert isinstance(body["topics"][0]["why_now"], dict)


@pytest.mark.compose
def test_no_synthesised_progress_number(seeded: None) -> None:
    """**零计算**（蓝本铁律）：NEVER 合成「完成度 60%」这种前端最想要、后端算不出的数。"""
    del seeded
    body = _client().get("/projects/be01-mine", headers={"X-User-Id": OWNER}).json()
    flat = json.dumps(body, ensure_ascii=False)

    for invented in ("percent", "completion", "progress_pct", "score", "health"):
        assert invented not in flat, f"合成了一个算不出的字段：{invented}"
