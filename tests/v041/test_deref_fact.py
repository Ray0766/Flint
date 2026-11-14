"""FB-04：解引用端点① `GET /facts/{fact_id}` —— fact_id → 事实内容 + 数值 + 出处。

## 为什么要这个端点

报告屏现在把六类 id **原样显给用户**（EYE-03 首跑的截图里，正文中间赫然写着
`fact-demo-vecdb-cost`、`cit-demo-arxiv-2506-06962`）。前端要把 id 换成内容，
后端得先有地方可问。本卡是六个解引用端点的第一个。

## 四条边界

1. **内容 + 数值 + 出处三样都要**，字段名与冻结件 `Fact` **逐字对齐**——
   前端照冻结件的字段名写，改一个名字就等于让它去改代码；
2. **三通道 NEVER 混用**（S2-2）：Fact / PriceCell / ProfileRef 各走各的端点。
   本端点只回 Fact 通道的东西——混进一个 `amount` 或 `field_path`，
   下游就再也说不清某个数字的出处是哪条通道；
3. **`disputed` 照实返回**，NEVER 静默过滤。用户有权看见争议态：
   悄悄滤掉一条有争议的事实，界面上留下的是一句没有异议的结论；
4. **只读 + 越权返 404**。用 404 而不是 403：403 等于告诉对方「这个 id 存在，
   只是不给你看」——**状态码本身就泄露了存在性**。查不到与不该看到，对外必须长得一样。
"""
from __future__ import annotations

import asyncio
import json
import os
import re
from dataclasses import fields
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import asyncpg
import pytest
from fastapi.testclient import TestClient

from contracts.models import Fact
from flint.api.deref import DerefApiDeps, create_deref_app

pytestmark = pytest.mark.compose

REPO = Path(__file__).resolve().parents[2]
DSN = os.environ.get("FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")
NOW = datetime(2026, 8, 4, 12, 0, 0, tzinfo=UTC)
PREFIX = "fb04-"

OWNER = "fb04-user-a"
INTRUDER = "fb04-user-b"


def run(coro: Any) -> Any:
    return asyncio.run(coro)


async def _seed(conn: asyncpg.Connection) -> None:
    async def project(pid: str, owner: str) -> None:
        await conn.execute(
            "INSERT INTO projects (project_id, owner, origin_id, topic_ids, "
            "chosen_topic_id, deliverable_ids, change_log, status, created_at) "
            "VALUES ($1, $2, $3, $4, NULL, $5, $6, 'active', $7)",
            pid, json.dumps({"kind": "user", "id": owner}), f"{pid}-origin",
            json.dumps([]), json.dumps([]), json.dumps([]), NOW,
        )

    async def ledger(lid: str, pid: str, version: int) -> None:
        await conn.execute(
            "INSERT INTO facts_ledgers (ledger_id, project_id, version, parent_version, "
            "derivation_reason, created_from, created_at, actor) "
            "VALUES ($1, $2, $3, $4, 'initial', $5, $6, 'seed')",
            lid, pid, version, None if version == 1 else version - 1,
            json.dumps([]), NOW,
        )

    async def fact(lid: str, fid: str, statement: str, value: Any, unit: str | None,
                   cits: list[str], status: str) -> None:
        await conn.execute(
            "INSERT INTO facts (ledger_id, fact_id, statement, value, unit, citation_ids, "
            "status, origin, created_in_version, source_claim_id, promoted_from) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7, 'injected', 1, NULL, NULL)",
            lid, fid, statement, json.dumps(value), unit, json.dumps(cits), status,
        )

    await project(f"{PREFIX}proj-a", OWNER)
    await project(f"{PREFIX}proj-b", INTRUDER)

    await ledger(f"{PREFIX}led-a1", f"{PREFIX}proj-a", 1)
    await ledger(f"{PREFIX}led-a2", f"{PREFIX}proj-a", 2)
    await ledger(f"{PREFIX}led-b1", f"{PREFIX}proj-b", 1)

    # 同一个 fact_id 在两个版本里内容不同：端点必须回**最新版本**那一份。
    await fact(f"{PREFIX}led-a1", f"{PREFIX}fact-1", "旧版陈述", 11.0, "美元", ["c-1"], "frozen")
    await fact(f"{PREFIX}led-a2", f"{PREFIX}fact-1", "向量库托管月成本", 12.5, "美元",
               ["c-1", "c-2"], "frozen")
    await fact(f"{PREFIX}led-a2", f"{PREFIX}fact-disputed", "推理算力单价", 720, "美元",
               ["c-3"], "disputed")
    await fact(f"{PREFIX}led-b1", f"{PREFIX}fact-other", "别人的事实", 1, None, ["c-9"], "frozen")


@pytest.fixture(autouse=True)
def clean_slate() -> None:
    async def wipe() -> None:
        conn = await asyncpg.connect(DSN)
        try:
            await conn.execute(
                "DELETE FROM facts WHERE ledger_id IN "
                f"(SELECT ledger_id FROM facts_ledgers WHERE project_id LIKE '{PREFIX}%')"
            )
            await conn.execute(f"DELETE FROM facts_ledgers WHERE project_id LIKE '{PREFIX}%'")
            await conn.execute(f"DELETE FROM projects WHERE project_id LIKE '{PREFIX}%'")
            await _seed(conn)
        finally:
            await conn.close()

    run(wipe())


def client() -> TestClient:
    return TestClient(create_deref_app(DerefApiDeps(dsn=DSN)))


def get(fact_id: str, *, user: str = OWNER) -> Any:
    return client().get(f"/facts/{fact_id}", headers={"X-User-Id": user})


# ───────────────────────── acceptance①：内容 + 数值 + 出处


def test_the_fact_body_carries_content_value_and_provenance() -> None:
    """三样都要：陈述（内容）、value+unit（数值）、citation_ids（出处）。"""
    body = get(f"{PREFIX}fact-1").json()

    assert body["statement"] == "向量库托管月成本"
    assert body["value"] == 12.5
    assert body["unit"] == "美元"
    assert body["citation_ids"] == ["c-1", "c-2"]


def test_the_field_names_match_the_frozen_contract_verbatim() -> None:
    """字段名与冻结件 `Fact` 逐字对齐——一个都不能少、一个都不能改名。

    前端照冻结件的字段名写；这里换个名字，就等于让前端去改代码，
    而那份改动没有任何地方记着它为什么发生。
    """
    body = get(f"{PREFIX}fact-1").json()
    frozen = {f.name for f in fields(Fact)}

    assert frozen <= set(body), f"少了冻结件字段：{sorted(frozen - set(body))}"
    assert body["fact_id"] == f"{PREFIX}fact-1"
    assert body["origin"] == "injected"
    assert body["created_in_version"] == 1
    assert body["source_claim_id"] is None
    assert body["promoted_from"] is None


def test_the_latest_ledger_version_wins_and_says_which_one() -> None:
    """同一 fact_id 在多版本里成行：回最新那一份，并**说清是哪一版**。

    不说版本的话，两个人拿着同一个 fact_id 看到不同数字，谁都不知道差在哪。
    """
    body = get(f"{PREFIX}fact-1").json()

    assert body["statement"] != "旧版陈述"
    assert body["ledger_version"] == 2
    assert body["project_id"] == f"{PREFIX}proj-a"


# ───────────────────────── acceptance②：三通道不混


def test_the_price_and_profile_channels_never_leak_in() -> None:
    """本端点只回 Fact 通道的东西（S2-2）。

    混进一个 `amount` 或 `field_path`，下游就再也说不清某个数字的出处是哪条通道——
    而「数字必有出处且三通道互不混用」是这套系统的三条铁律之一。
    """
    body = get(f"{PREFIX}fact-1").json()
    from contracts.models import PriceCell, ProfileRef

    fact_names = {f.name for f in fields(Fact)}
    foreign = ({f.name for f in fields(PriceCell)} | {f.name for f in fields(ProfileRef)})
    leaked = (foreign - fact_names) & set(body)

    assert leaked == set(), f"另外两条通道的字段漏进来了：{sorted(leaked)}"
    assert body["channel"] == "fact", "响应要自报通道，省得下游靠字段猜"


# ───────────────────────── acceptance③：争议态照实返回


def test_a_disputed_fact_is_returned_with_its_marker_not_filtered_out() -> None:
    """`status=="disputed"` 照实返回并带标记，NEVER 静默过滤。

    悄悄滤掉一条有争议的事实，界面上留下的是一句**没有异议的结论**——
    那比显示争议本身危险得多。
    """
    response = get(f"{PREFIX}fact-disputed")
    body = response.json()

    assert response.status_code == 200
    assert body["status"] == "disputed"
    assert body["disputed"] is True
    assert body["statement"] == "推理算力单价"


def test_a_frozen_fact_is_not_marked_disputed() -> None:
    """正例：没争议的事实不带争议标记（否则上一条等于恒真）。"""
    assert get(f"{PREFIX}fact-1").json()["disputed"] is False


# ───────────────────────── acceptance④：越权 404、只读


def test_another_owners_fact_is_404_not_403() -> None:
    """越权取他人 fact → **404**。

    403 等于告诉对方「这个 id 存在，只是不给你看」——**状态码本身泄露了存在性**。
    """
    response = get(f"{PREFIX}fact-1", user=INTRUDER)

    assert response.status_code == 404
    assert "fb04-fact-1" not in response.text or "NOT_FOUND" in response.text


def test_an_unknown_fact_looks_exactly_like_someone_elses() -> None:
    """查不到与不该看到，对外必须长得一样——否则 404 也能被用来枚举 id。"""
    unknown = get(f"{PREFIX}fact-does-not-exist")
    forbidden = get(f"{PREFIX}fact-1", user=INTRUDER)

    assert unknown.status_code == forbidden.status_code == 404
    assert unknown.json()["code"] == forbidden.json()["code"]


def test_the_owner_still_sees_their_own_fact() -> None:
    """正例：本人取自己的 fact 是 200（否则上面两条可以靠「一律 404」满足）。"""
    assert get(f"{PREFIX}fact-other", user=INTRUDER).status_code == 200


def test_identity_is_required() -> None:
    """不带 `X-User-Id` 直接拒——匿名可读等于没有多租户。"""
    assert client().get(f"/facts/{PREFIX}fact-1").status_code == 422


# ───────────────────────── 只读检测器（acceptance④ 后半）


WRITE_SQL = re.compile(r"\b(INSERT\s+INTO|UPDATE\s+\w+\s+SET|DELETE\s+FROM|TRUNCATE)\b",
                       re.IGNORECASE)


def _write_statements(source: str) -> list[str]:
    """剥掉注释与 docstring 之后，找写库语句。

    剥注释是必须的：这个模块的 docstring 里逐字写着「NEVER INSERT INTO …」
    （在说明它为什么只读），扫原文会把「解释它」当成「干了它」。
    本批第四次撞上同一类问题（GAUGE-06 / FB-01 / FB-02）。
    """
    code = re.sub(r'"""[\s\S]*?"""', "", source)
    code = re.sub(r"#.*", "", code)
    return WRITE_SQL.findall(code)


def test_the_endpoint_module_never_writes() -> None:
    """本端点 NEVER 写库。"""
    source = (REPO / "flint" / "api" / "deref.py").read_text(encoding="utf-8")

    assert _write_statements(source) == []


def test_the_write_detector_is_not_vacuous() -> None:
    """阴性对照：检测器对真写库语句必须报出来。

    没有这一条，上一条可能只是因为这把尺子什么都认不出——那种绿什么都没证明。
    """
    assert _write_statements('x = "INSERT INTO facts VALUES (1)"')
    assert _write_statements("y = 'DELETE FROM facts WHERE 1=1'")
    assert _write_statements('z = "UPDATE facts SET statement = 1"')
    assert _write_statements('ok = "SELECT * FROM facts"') == []
