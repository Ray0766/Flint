"""OVERVIEW-01：项目总览的交付物只有一份清单——`deliverables` 表那一份（`DEC-063`）。

## 改前是两份，而且对不上

`GET /projects/{id}` 同时回两样东西：

- `deliverable_ids`：`projects` 表里的一列。**建项时写一次，此后组稿与重写都不回写它**；
- `deliverables[]`：现查 `deliverables` 表，带 `version` / `supersedes`。

`docs/blocked/PROJECT-DOES-NOT-LIST-ITS-OWN-DELIVERABLES.md` 实测：库里已有四份交付物，
那一列仍只有一条。读前一样的人（`tools/ui_probe_wb_annotate.py`）看到的清单从不变，
于是得出「项目总览列不出新产出」——而后一样一直是对的。

`DEC-063` 的裁法：总览不再读那一列，真相只有一处。

## 那一列还在

`DEC-063` 原话：**列保留、不再读**——删列是数据删除，属事前必审，那条裁决不授权。
所以本文件有一条专门判「库里那一列原样还在」：端点不读它，与它被清掉，是两件事。
"""
from __future__ import annotations

import ast
import asyncio
import json
from pathlib import Path

import asyncpg
import pytest
from fastapi.testclient import TestClient

from flint.api.project_overview import ProjectOverviewDeps, create_project_overview_app
from tests.conftest import TEST_DSN

REPO = Path(__file__).resolve().parents[2]
MODULE = REPO / "flint" / "api" / "project_overview.py"
PROBE_TOOL = REPO / "tools" / "ui_probe_wb_annotate.py"
SHEET = REPO / "docs" / "blocked" / "PROJECT-DOES-NOT-LIST-ITS-OWN-DELIVERABLES.md"

OWNER = "u-ov01"
PROJECT = "ov01-proj"
# 那一列里故意放一个**库里没有的** id：端点要是还在读它，这个词会出现在响应里。
STALE = "ov01-only-in-the-old-column"


async def _seed() -> None:
    conn = await asyncpg.connect(TEST_DSN)
    try:
        await conn.execute("DELETE FROM deliverables WHERE project_id = $1", PROJECT)
        await conn.execute("DELETE FROM projects WHERE project_id = $1", PROJECT)
        await conn.execute("DELETE FROM origins WHERE origin_id = 'ov01-origin'")
        await conn.execute(
            "INSERT INTO origins (origin_id, kind, owner, payload, created_at) "
            "VALUES ('ov01-origin', 'combo', $1::jsonb, '{}'::jsonb, now())",
            json.dumps({"id": OWNER, "kind": "user"}))
        await conn.execute(
            "INSERT INTO projects (project_id, owner, origin_id, topic_ids, "
            "chosen_topic_id, deliverable_ids, change_log, status, created_at) "
            "VALUES ($1, $2::jsonb, 'ov01-origin', '[]'::jsonb, NULL, $3::jsonb, "
            "'[]'::jsonb, 'active', now())",
            PROJECT, json.dumps({"id": OWNER, "kind": "user"}), json.dumps([STALE]))
        # 两份：第二份是第一份的重写产物（version 2，supersedes 指回第一份）。
        for did, version, supersedes in (
                ("ov01-d1", 1, None), ("ov01-d1-r-job", 2, "ov01-d1")):
            await conn.execute(
                "INSERT INTO deliverables (deliverable_id, project_id, type, version, "
                "supersedes, inputs, ledger_version, generation_record_id, "
                "stale_reasons, created_at, reproducible, meta) "
                "VALUES ($1, $2, 'report', $3, $4, '[]'::jsonb, 1, $5, '[]'::jsonb, "
                "now(), true, '{}'::jsonb)",
                did, PROJECT, version, supersedes, f"gr-{did}")
    finally:
        await conn.close()


async def _column() -> str:
    conn = await asyncpg.connect(TEST_DSN)
    try:
        return str(await conn.fetchval(
            "SELECT deliverable_ids FROM projects WHERE project_id = $1", PROJECT))
    finally:
        await conn.close()


@pytest.fixture
def body() -> dict[str, object]:
    asyncio.run(_seed())
    client = TestClient(create_project_overview_app(ProjectOverviewDeps(dsn=TEST_DSN)))
    response = client.get(f"/projects/{PROJECT}", headers={"x-user-id": OWNER})
    assert response.status_code == 200, response.text
    return dict(response.json())


# ───────────────────────── 一、响应里只剩一份清单


@pytest.mark.compose
def test_the_old_column_is_no_longer_in_the_response(body: dict[str, object]) -> None:
    assert "deliverable_ids" not in body, "总览还在回那一列——清单仍是两份"
    assert STALE not in json.dumps(body, ensure_ascii=False), (
        "只存在于旧列里的那个 id 出现在响应里：端点还在读它")


@pytest.mark.compose
def test_the_one_list_comes_from_the_table_with_version_and_supersedes(
        body: dict[str, object]) -> None:
    listed = body["deliverables"]
    assert isinstance(listed, list)

    assert [d["deliverable_id"] for d in listed] == ["ov01-d1", "ov01-d1-r-job"], (
        "清单要按 version 排——新版本排在它取代的那一份后面")
    assert [d["version"] for d in listed] == [1, 2]
    assert listed[0]["supersedes"] is None
    assert listed[1]["supersedes"] == "ov01-d1", "看不出第二份取代的是哪一份"


# ───────────────────────── 二、那一列还在库里，一个字没动


@pytest.mark.compose
def test_the_column_itself_is_kept_and_untouched(body: dict[str, object]) -> None:
    """`DEC-063`：列保留、不再读。端点 NEVER 顺手把它清掉或改写。"""
    assert json.loads(asyncio.run(_column())) == [STALE]


# ───────────────────────── 三、源码面：两处都不再读它


def _string_constants(path: Path) -> list[str]:
    """源码里除文档串之外的全部字符串常量（SQL、字典键都在这里面）。

    判的是**代码用没用到那个列名**，不是**注释与文档串里提没提**——
    改因说明里会逐字写到它。
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstrings = {
        id(node.body[0].value)
        for node in ast.walk(tree)
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        and node.body and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
    }
    return [
        node.value for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
        and id(node) not in docstrings
    ]


def test_the_endpoint_sql_does_not_select_the_column() -> None:
    constants = _string_constants(MODULE)

    assert any("FROM deliverables" in c for c in constants), "扫描面自证：查表那一句得在"
    assert not [c for c in constants if "deliverable_ids" in c], "总览模块的代码里还有那个列名"


def test_the_probe_reads_the_list_not_the_column() -> None:
    """读的人也要改：`tools/ui_probe_wb_annotate.py` 原先拿那一列当「总览列不列得出新产出」的证据。"""
    constants = _string_constants(PROBE_TOOL)

    assert "deliverables" in constants, "取证脚本没有读总览的那份清单"
    assert not [c for c in constants if "deliverable_ids" in c], "取证脚本还在读那一列"


# ───────────────────────── 四、单据关掉


def test_the_sheet_is_closed_and_names_this_card() -> None:
    text = SHEET.read_text(encoding="utf-8")
    status = next(line for line in text.splitlines() if line.startswith("**状态**"))

    assert "closed" in status and "open" not in status.split("·")[0], status
    assert "OVERVIEW-01" in status
    assert "DEC-063" in status
