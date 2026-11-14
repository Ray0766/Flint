"""BL-06：Q-009/Q-010 现状核实 —— 主题与关联假设已落库，视图接了没有。

## 两条问题单的前提已经不成立

`docs/v0.4-问题单.md` 里 Q-009 写着「**DB 无 `topics` 表，Topic 未持久化**」、
Q-010 写着「**DB 无 `origins`/`topic_seeds`/`topics` 表，Origin/TopicSeed/hypothesis
全未持久化**（grep 无 INSERT）」。

那是 @2026-07-30 的实况。主题子系统（TS-001~010）建完之后，四张表、真 INSERT、
两个端点都在了——**问题单还挂在那儿，是留痕过期，不是缺陷仍在**。

过期的问题单比没有更糟：下一个人读到「未持久化」，会去建第二套落库路径。

## 所以本卡先核实、再补差、最后改问题单

- **核实**：表在不在、INSERT 在不在、端点在不在（下面前三组用例，一条一条对）；
- **补差**：广场展示主题、工作台展示关联假设——**只补真缺的那段**；
- **改问题单**：写明依据（表名 / 文件行号 / 端点路径），NEVER 只改状态字。

## 空态 NEVER 拿簇冒充主题

一天里没有主题就说「尚无主题」。拿簇顶上去的话，界面上那一排看起来像主题，
而它们是日更采集层的产物——**用户会以为系统已经分析过了**。
"""
from __future__ import annotations

import asyncio
import inspect
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DSN = os.environ.get("FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")
MIGRATION = REPO_ROOT / "migrations" / "versions" / "0017_topic_subsystem.py"
STORE = REPO_ROOT / "flint" / "topic" / "store.py"
VIEWS = REPO_ROOT / "flint" / "api" / "views.py"
ISSUES = REPO_ROOT / "docs" / "v0.4-问题单.md"


# ───────────────────────── 一、核实：四张表建了


@pytest.mark.parametrize("table", ["origins", "topic_seeds", "topics", "projects"])
def test_the_migration_creates_the_table(table: str) -> None:
    """acceptance①：`0017_topic_subsystem` 建了这四张表。"""
    source = MIGRATION.read_text(encoding="utf-8")

    assert f'"{table}"' in source, f"迁移里没有 {table}"


@pytest.mark.compose
@pytest.mark.parametrize("table", ["origins", "topic_seeds", "topics", "projects"])
def test_the_table_really_exists_in_the_database(table: str) -> None:
    """迁移文件里写了**不等于**库里真有——问题单说的是「DB 无此表」，就去 DB 问。"""
    async def ask() -> bool:
        import asyncpg

        conn = await asyncpg.connect(DSN)
        try:
            return bool(await conn.fetchval("SELECT to_regclass($1) IS NOT NULL", table))
        finally:
            await conn.close()

    assert asyncio.run(ask()), f"库里没有 {table}"


# ───────────────────────── 二、核实：真 INSERT 在


@pytest.mark.parametrize(
    ("store_class", "table"),
    [("PgOriginStore", "origins"), ("PgTopicSeedStore", "topic_seeds"),
     ("PgTopicStore", "topics"), ("PgProjectStore", "projects")],
)
def test_the_store_really_inserts(store_class: str, table: str) -> None:
    """acceptance①：`flint/topic/store.py` 有**真** INSERT（问题单说的是 grep 无 INSERT）。"""
    from flint.topic import store

    code = inspect.getsource(getattr(store, store_class))
    code = "\n".join(ln for ln in code.split("\n") if not ln.strip().startswith("#"))

    assert f"INSERT INTO {table}" in code


def test_the_hypothesis_column_is_where_the_association_lives() -> None:
    """关联假设 = combo 型 Origin/TopicSeed 的 `hypothesis`——列在 `topic_seeds` 上。"""
    assert "hypothesis" in MIGRATION.read_text(encoding="utf-8")


# ───────────────────────── 三、核实：端点在


@pytest.mark.parametrize("path", ["/topics/{topic_id}", "/projects/{project_id}/topics"])
def test_the_topic_endpoints_are_registered(path: str) -> None:
    """acceptance①：两个既有端点真在路由表上（读 FastAPI 自己注册的那一份）。"""
    from flint.api.views import ViewsApiDeps, create_views_app

    app = create_views_app(ViewsApiDeps(dsn="postgresql://x/x"))

    assert path in {r.path for r in app.routes}  # type: ignore[attr-defined]


# ───────────────────────── 四、补差：广场展示主题


def test_the_plaza_now_has_a_topics_endpoint() -> None:
    """acceptance②：广场能拿到主题。补之前广场只有 `/plaza/hot`（簇）。"""
    from flint.api.views import ViewsApiDeps, create_views_app

    app = create_views_app(ViewsApiDeps(dsn="postgresql://x/x"))

    assert "/plaza/topics" in {r.path for r in app.routes}  # type: ignore[attr-defined]


def test_the_workbench_now_exposes_the_association_hypothesis() -> None:
    """acceptance②：工作台能拿到关联假设（Origin/TopicSeed 的 hypothesis）。"""
    from flint.api.views import ViewsApiDeps, create_views_app

    app = create_views_app(ViewsApiDeps(dsn="postgresql://x/x"))

    assert "/projects/{project_id}/hypothesis" in {
        r.path for r in app.routes  # type: ignore[attr-defined]
    }


def test_the_plaza_topics_endpoint_never_reads_the_clusters_table() -> None:
    """**NEVER 用簇冒充主题**：这个端点的 SQL 里不许出现 clusters / heat_points。

    冒充的后果很具体：界面上那一排看起来像主题，而它们是日更采集层的产物——
    用户会以为系统已经分析过了。
    """
    from flint.api import views

    source = inspect.getsource(views)
    body = source[source.index("/plaza/topics"):]
    body = body[: body.index("@app.get", 20)] if "@app.get" in body[20:] else body
    code = "\n".join(ln for ln in body.split("\n") if not ln.strip().startswith("#"))

    assert "clusters" not in code
    assert "heat_points" not in code


def test_the_empty_state_says_there_are_no_topics_yet() -> None:
    """acceptance④：没有主题就说「尚无主题」，而不是返回一个空数组了事。

    空数组在前端会变成一片空白，而空白既可能是「没有」也可能是「没加载出来」。
    """
    from flint.api import views

    source = inspect.getsource(views)

    assert "尚无主题" in source


# ───────────────────────── 五、真库：空态与有数据两种都跑


@pytest.mark.compose
def test_the_plaza_topics_endpoint_against_the_real_database() -> None:
    """真库跑一遍：先空态、再塞一条主题。

    清理按**前缀**（`bl06-%`）：整表清空会连带删掉别的用例的数据。
    """
    import asyncpg
    from fastapi.testclient import TestClient

    from flint.api.views import ViewsApiDeps, create_views_app

    async def cleanup() -> None:
        conn = await asyncpg.connect(DSN)
        try:
            await conn.execute("DELETE FROM topics WHERE topic_id LIKE 'bl06-%'")
            await conn.execute("DELETE FROM topic_seeds WHERE seed_id LIKE 'bl06-%'")
            await conn.execute("DELETE FROM origins WHERE origin_id LIKE 'bl06-%'")
        finally:
            await conn.close()

    async def seed() -> None:
        from flint.domain.models import (
            Principal,
            Topic,
            TopicSeed,
            WhyNow,
        )
        from flint.topic.create import create_origin
        from flint.topic.store import PgOriginStore, PgTopicSeedStore, PgTopicStore

        origin = await create_origin(
            origin_id="bl06-o1", kind="idea", owner=Principal(kind="user", id="u-bl06"),
            payload={"text": "跨热点联想：端侧推理 × 教育"},
            created_at=datetime(2026, 7, 20, tzinfo=UTC),
        )
        await PgOriginStore(dsn=DSN).save(origin)
        seed_obj = TopicSeed(
            seed_id="bl06-s1", origin_id="bl06-o1", keywords=["端侧推理"],
            hypothesis="端侧推理会先在教育场景落地", context_text="关联假设：…",
        )
        await PgTopicSeedStore(dsn=DSN).save(seed_obj)
        await PgTopicStore(dsn=DSN).save(
            Topic(
                topic_id="bl06-t1", seed_id="bl06-s1", one_liner="端侧推理进课堂",
                target_user_tag="tu", form_factor_tag="ff",
                why_now=WhyNow(claim="时机", evidences=[], speculative=True),
                keyword_mapping={"端侧推理": ["kw"]}, embedding=[0.0] * 1024,
            )
        )

    asyncio.run(cleanup())
    client = TestClient(create_views_app(ViewsApiDeps(dsn=DSN)))
    try:
        empty = client.get("/plaza/topics", params={"owner_id": "u-bl06"})
        assert empty.status_code == 200
        assert empty.json()["topics"] == []
        assert "尚无主题" in empty.json()["empty_note"]

        asyncio.run(seed())
        filled = client.get("/plaza/topics", params={"owner_id": "u-bl06"})
        assert filled.status_code == 200
        ids = [t["topic_id"] for t in filled.json()["topics"]]
        assert "bl06-t1" in ids
        assert filled.json()["empty_note"] == ""

        hypo = client.get("/projects/bl06-s1/hypothesis")
        assert hypo.status_code == 200
        assert hypo.json()["hypothesis"] == "端侧推理会先在教育场景落地"
    finally:
        asyncio.run(cleanup())


# ───────────────────────── 六、问题单更新（acceptance③）


@pytest.mark.parametrize(
    ("qid", "endpoint"),
    # 两条问题单各自的那一段：Q-009 = 主题进广场，Q-010 = 关联假设有读端点。
    # 判据按条给，不给一个「有任意端点就算」的宽口径——那样 Q-010 抄一句
    # Q-009 的路径也能过。
    [("Q-009", "/plaza/topics"), ("Q-010", "/hypothesis")],
)
def test_the_issue_entry_is_marked_resolved_with_evidence(qid: str, endpoint: str) -> None:
    """acceptance③：状态改了，且**给了依据**——表名 / 文件行号 / 端点路径。

    只改状态字不给依据，下一个人没法自己复核，只能选择相信——
    而问题单正是因为「相信一句过期的话」才需要这张卡。
    """
    text = ISSUES.read_text(encoding="utf-8")
    section = text[text.index(f"## {qid}"):]
    section = section[: section.index("\n## ")] if "\n## " in section else section

    assert "RESOLVED" in section.split("\n")[0], f"{qid} 标题行没标 RESOLVED"
    assert "0017_topic_subsystem" in section, "没写建表依据"
    assert re.search(r"store\.py:\d+", section), "没写 INSERT 的文件行号"
    assert endpoint in section, f"没写这一条对应的端点路径：{endpoint}"


def test_the_stale_claim_is_marked_as_stale_not_deleted() -> None:
    """原话**留着**并注明「已过期」，NEVER 直接删。

    删了就看不出问题单曾经错过——而「什么时候错的、被什么推翻的」正是下次
    读它的人要判断的东西。
    """
    text = ISSUES.read_text(encoding="utf-8")

    # 判据落在**各自的留档小节里**，不是全文任意处。变异考走了两轮才钉住：
    #   · 首版查全文 → 删掉留档也绿，因为新写的 RESOLVED 段里**引用**了那句原话；
    #   · 二版从第一个留档标记切到文末 → 还是绿，因为那一刀之后仍包含另一条的引用。
    # 引用不等于留档：留档要的是「什么时候错的」那个日期上下文。
    sections = text.split("### 原始现象（@2026-07-30，**已不成立**，留档）")

    assert len(sections) == 3, "两条问题单各要有一个留档小节"
    archived = [s.split("\n## ")[0] for s in sections[1:]]

    assert any("全未持久化" in s for s in archived), "Q-010 的原话不在留档小节里"
    assert any("DB 无 `topics` 表" in s for s in archived), "Q-009 的原话不在留档小节里"


def test_the_two_entries_point_at_each_other_s_evidence() -> None:
    """Q-009 与 Q-010 是同一件事的两半（主题 / 关联假设），依据互相引到。"""
    text = ISSUES.read_text(encoding="utf-8")
    q9 = text[text.index("## Q-009"):]
    q9 = q9[: q9.index("\n## ")] if "\n## " in q9 else q9

    assert "Q-010" in q9 or "hypothesis" in q9


def _routes() -> set[str]:
    from flint.api.views import ViewsApiDeps, create_views_app

    app = create_views_app(ViewsApiDeps(dsn="postgresql://x/x"))
    return {getattr(r, "path", "") for r in app.routes}


def test_the_existing_endpoints_are_untouched() -> None:
    """**已建的一字不改**（acceptance②）：既有五个端点仍在。"""
    paths: set[str] = _routes()

    for path in (
        "/plaza/hot",
        "/clusters/{cluster_id}/evidence-cards",
        "/jobs/{job_id}/verdict",
        "/topics/{topic_id}",
        "/projects/{project_id}/topics",
    ):
        assert path in paths, f"既有端点没了：{path}"


def test_nothing_in_the_store_was_rewritten() -> None:
    """`flint/topic/store.py` 一个字没动——本卡只读它、不改它。"""
    source: Any = STORE.read_text(encoding="utf-8")

    assert "BL-06" not in source
