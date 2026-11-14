"""FB-07：解引用端点④ `GET /charts/{chart_id}` —— 图表数据点 + 每点的出处。

## 零计算是这条端点的正题

冻结件 `ChartSpec.derived_from` 的注释原话是「deliverable_id | fact_ids, **必填不许编**」，
报告正文里的图表说明也写着「数据经 derived_from 反查，**前端零计算**」。
所以这条端点把每个数据点**原样**指回账本里的一条 fact：
`value` 是库里那个 value，不是这里算出来的。

**一旦端点开始求和、取比例、算增长率，那个数字就没有出处了**——它是端点算的，
而端点不进账本、不留痕。图表是报告里最容易偷偷造数的地方，所以这里连一个加号都不写。

## 取不到的点照实说

`derived_from` 里列的 fact 可能不存在、或不属于调用者。**NEVER 静默丢掉**：
少一个点的折线图看起来完全正常，没人看得出它少了一段。所以取不到的进 `unresolved`，
让调用方**知道自己拿到的是残的**。

## ChartSpec 从模板来（现状：一个都还没有，见 trace §3）

`ChartSpec` 只在模板里定义（`assets/templates/*.yaml` 的 `charts:` 段），
而当前四份模板**全部是 `charts: []`**。本卡的端点结构照契约建好，
测试用注入的模板目录造真 spec 来验——NEVER 去改 `assets/` 里的模板凑数据。
"""
from __future__ import annotations

import asyncio
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import asyncpg
import pytest
from fastapi.testclient import TestClient

from flint.api.deref import DerefApiDeps, create_deref_app

pytestmark = pytest.mark.compose

REPO = Path(__file__).resolve().parents[2]
DSN = os.environ.get("FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")
NOW = datetime(2026, 8, 4, tzinfo=UTC)
PREFIX = "fb07-"
OWNER = "fb07-user-a"
INTRUDER = "fb07-user-b"

CHART = f"{PREFIX}chart-cost"
FACT_A = f"{PREFIX}fact-vecdb"
FACT_B = f"{PREFIX}fact-infer"
FACT_GONE = f"{PREFIX}fact-not-there"

TEMPLATE = f"""\
template_id: {PREFIX}tpl
locale: zh-CN
audience: human_reader
sections:
- section_id: budget
  ratio: {{share: 1.0, unit: words, min_words: 10, max_words: 100}}
  check_questions: ["预算是否有出处"]
  charts:
  - chart_id: {CHART}
    chart_type: line
    derived_from: ["{FACT_A}", "{FACT_B}", "{FACT_GONE}"]
"""


def run(coro: Any) -> Any:
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def clean_slate() -> None:
    async def wipe() -> None:
        conn = await asyncpg.connect(DSN)
        try:
            await conn.execute(
                "DELETE FROM facts WHERE ledger_id IN "
                f"(SELECT ledger_id FROM facts_ledgers WHERE project_id LIKE '{PREFIX}%')")
            await conn.execute(f"DELETE FROM facts_ledgers WHERE project_id LIKE '{PREFIX}%'")
            await conn.execute(f"DELETE FROM projects WHERE project_id LIKE '{PREFIX}%'")
            await conn.execute(
                "INSERT INTO projects (project_id, owner, origin_id, topic_ids, "
                "chosen_topic_id, deliverable_ids, change_log, status, created_at) "
                "VALUES ($1, $2, $3, $4, NULL, $5, $6, 'active', $7)",
                f"{PREFIX}proj", json.dumps({"kind": "user", "id": OWNER}),
                f"{PREFIX}origin", json.dumps([]), json.dumps([]), json.dumps([]), NOW)
            await conn.execute(
                "INSERT INTO facts_ledgers (ledger_id, project_id, version, parent_version, "
                "derivation_reason, created_from, created_at, actor) "
                "VALUES ($1, $2, 1, NULL, 'initial', $3, $4, 'seed')",
                f"{PREFIX}led", f"{PREFIX}proj", json.dumps([]), NOW)
            await conn.executemany(
                "INSERT INTO facts (ledger_id, fact_id, statement, value, unit, citation_ids, "
                "status, origin, created_in_version, source_claim_id, promoted_from) "
                "VALUES ($1, $2, $3, $4, $5, $6, 'frozen', 'injected', 1, NULL, NULL)",
                [
                    (f"{PREFIX}led", FACT_A, "向量库托管月成本", json.dumps(12.5), "美元",
                     json.dumps(["c-1"])),
                    (f"{PREFIX}led", FACT_B, "推理算力月成本", json.dumps(720), "美元",
                     json.dumps(["c-2"])),
                ],
            )
        finally:
            await conn.close()

    run(wipe())


@pytest.fixture
def templates(tmp_path: Path) -> Path:
    """注入的模板目录：造一个**真的** ChartSpec，NEVER 去改 assets/ 里的模板凑数据。"""
    (tmp_path / f"{PREFIX}tpl.yaml").write_text(TEMPLATE, encoding="utf-8")
    return tmp_path


def get(templates: Path, chart_id: str, *, user: str | None = OWNER) -> Any:
    app = create_deref_app(DerefApiDeps(dsn=DSN, template_dir=templates))
    headers = {"X-User-Id": user} if user is not None else {}
    return TestClient(app).get(f"/charts/{chart_id}", headers=headers)


# ───────────────────────── acceptance①：数据点 + 每点的出处


def test_each_point_carries_the_fact_it_came_from(templates: Path) -> None:
    """每个数据点都指回账本里的一条 fact——那才是这个数字的出处。"""
    body = get(templates, CHART).json()
    points = {p["fact_id"]: p for p in body["points"]}

    assert set(points) == {FACT_A, FACT_B}
    assert points[FACT_A]["value"] == 12.5
    assert points[FACT_A]["unit"] == "美元"
    assert points[FACT_A]["statement"] == "向量库托管月成本"
    assert points[FACT_A]["citation_ids"] == ["c-1"]
    assert points[FACT_A]["ledger_version"] == 1


def test_the_spec_fields_come_through_verbatim(templates: Path) -> None:
    """`ChartSpec` 三字段逐字：`chart_id` / `chart_type` / `derived_from`。"""
    body = get(templates, CHART).json()

    assert body["chart_id"] == CHART
    assert body["chart_type"] == "line"
    assert body["derived_from"] == [FACT_A, FACT_B, FACT_GONE]
    assert body["channel"] == "chart"


# ───────────────────────── acceptance②：零计算


def test_the_values_are_exactly_what_the_ledger_stores(templates: Path) -> None:
    """每个点的 value 与库里那条逐值相等——端点没有动过任何一个数字。"""
    body = get(templates, CHART).json()

    async def stored() -> dict[str, Any]:
        conn = await asyncpg.connect(DSN)
        try:
            rows = await conn.fetch(
                "SELECT fact_id, value FROM facts WHERE ledger_id = $1", f"{PREFIX}led")
        finally:
            await conn.close()
        return {r["fact_id"]: json.loads(r["value"]) for r in rows}

    truth = run(stored())
    for point in body["points"]:
        assert point["value"] == truth[point["fact_id"]]


def test_no_aggregate_is_computed(templates: Path) -> None:
    """响应里 NEVER 出现求和/均值/比例/增长率这类派生值。

    图表是报告里最容易偷偷造数的地方：一个「合计 732.5」看起来天经地义，
    而它没有出处——它是端点算的，端点不进账本、不留痕。
    """
    body = get(templates, CHART).json()
    banned = ("total", "sum", "avg", "average", "mean", "growth", "pct", "percent",
              "ratio", "delta", "trend")

    leaked = [k for k in body if any(b in k.lower() for b in banned)]
    assert leaked == [], f"出现了派生值字段：{leaked}"
    assert body["computed"] is False, "响应要自报「零计算」"


def test_the_endpoint_source_does_no_arithmetic_on_values(templates: Path) -> None:
    """源码面：图表那段里没有对 value 做算术。

    与字段面那条互补——字段名可以起得人畜无害，算术却藏不住。
    """
    source = (REPO / "flint" / "api" / "deref.py").read_text(encoding="utf-8")
    code = re.sub(r'"""[\s\S]*?"""', "", source)
    start = code.find("def chart_json")
    assert start > 0, "找不到 chart_json"
    segment = code[start:code.find("\ndef ", start + 1)]

    assert not re.search(r'\["value"\]\s*[-+*/]', segment), "对 value 做了算术"
    assert "sum(" not in segment and "mean(" not in segment


# ───────────────────────── 取不到的点照实说


def test_a_fact_that_cannot_be_resolved_is_listed_not_dropped(templates: Path) -> None:
    """`derived_from` 里取不到的 fact 进 `unresolved`，NEVER 静默丢掉。

    少一个点的折线图看起来完全正常，没人看得出它少了一段。
    """
    body = get(templates, CHART).json()

    assert body["unresolved"] == [FACT_GONE]
    assert body["complete"] is False
    assert len(body["points"]) == 2


def test_a_fully_resolved_chart_says_so(templates: Path, tmp_path: Path) -> None:
    """正例：全部取到时 `complete: true` 且 `unresolved` 为空。"""
    good = tmp_path / "good"
    good.mkdir()
    (good / "t.yaml").write_text(
        TEMPLATE.replace(f', "{FACT_GONE}"', "").replace(f"{CHART}", f"{CHART}-ok"),
        encoding="utf-8")

    body = get(good, f"{CHART}-ok").json()

    assert body["unresolved"] == []
    assert body["complete"] is True
    assert len(body["points"]) == 2


# ───────────────────────── acceptance③：多租户 + 只读


def test_another_owner_sees_no_points_at_all(templates: Path) -> None:
    """越权调用者一个点都取不到——fact 是按归属过滤的（与 FB-04 同一条 SQL 口径）。

    而且**取不到的照实列进 unresolved**：他拿到的是一张空图，不是一张看起来正常的图。
    """
    body = get(templates, CHART, user=INTRUDER).json()

    assert body["points"] == []
    assert set(body["unresolved"]) == {FACT_A, FACT_B, FACT_GONE}
    assert body["complete"] is False


def test_identity_is_required(templates: Path) -> None:
    assert get(templates, CHART, user=None).status_code == 422


def test_an_unknown_chart_is_404(templates: Path) -> None:
    assert get(templates, f"{PREFIX}chart-nope").status_code == 404


def test_the_endpoint_module_never_writes() -> None:
    from tests.v041.test_deref_fact import _write_statements

    source = (REPO / "flint" / "api" / "deref.py").read_text(encoding="utf-8")
    assert _write_statements(source) == []


def test_the_shipped_templates_define_no_chart_yet() -> None:
    """现状钉住：`assets/templates/` 四份模板**一个 chart 都没定义**。

    这条不是在庆祝空白，是在**登记**：本端点今天没有真数据可回。
    哪天模板里真加了 chart，这条会红，提醒那时的人来这里补一条真数据的验收。
    """
    import yaml

    defined = []
    for path in sorted((REPO / "assets" / "templates").glob("*.yaml")):
        for section in yaml.safe_load(path.read_text(encoding="utf-8"))["sections"]:
            defined += [c["chart_id"] for c in section.get("charts", [])]

    assert defined == [], f"模板里已经有 chart 了，本卡的「无真数据」登记要更新：{defined}"
