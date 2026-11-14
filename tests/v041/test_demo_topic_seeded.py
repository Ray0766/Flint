"""SEED-01：demo 库种一条主题（`DEC-041`），取证样例从占位串换成它。

## 改前

`harness/fe_smoke.py` 扫 `/topics/[id]` 用的是 `tp-placeholder`，
`GET /topics/{id}` 回带 `code` 的 404——**那是 `TS-007` 要的正确行为**。
红的是取证样例，不是那一屏（与 `DEC-037` 同一形状）。
`CONSOLE_BASELINE` 因此给这一屏留了 1 条 404 额度。

## 开工时查到的实况：库里已经有六条**真**主题

单据立单时写的是「库里一条 `topics` 行都没有」。**那句话现在不成立了**：
`topic-demo14bf9d94b0-1 … -9` 共 6 条，模型产出，各带 2 条 `why_now` 证据。

那为什么还种夹具？**取证样例要的是可复现。**
那六条是一次过去的运行留下的痕迹，没有任何脚本能把它们重造出来——
demo 库重建一次，样例 id 又变成死链，而那正是这张卡要终结的失败。

所以本卡种一条**脚本自己造、随时能撤**的，并且判据同时钉住
**那六条真主题一个字节都没被碰过**。

## 判据打的是测试库，不是 demo 库

种子脚本的 `dsn` 可注入。demo 库是**给人看的**那一份，
判据往里写会与 owner 正在看的那一屏抢数据；而两个库共用一个 PG 实例，
一次写死的地址就能把 demo 抹掉（本仓已经咬过六次）。
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[2]
SMOKE = REPO / "harness" / "fe_smoke.py"
SWEEP = REPO / "tests" / "v041" / "test_mobile_sweep.py"
SHEET = REPO / "docs" / "blocked" / "DEMO-TOPIC-SAMPLE-ID-IS-A-PLACEHOLDER.md"
SEEDER = REPO / "harness" / "demo_seed_topic.py"

DSN = os.environ.get("FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")
# demo 库里那六条**真**主题的 id 前缀。判据只**读**它们，NEVER 写。
REAL_TOPIC_PREFIX = "topic-demo14bf9d94b0-"


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


@pytest.fixture()
def seeded() -> Any:
    from harness.demo_seed_topic import seed

    _run(seed(dsn=DSN))
    yield
    _run(seed(drop_only=True, dsn=DSN))


def _get(path: str) -> Any:
    import httpx

    from flint.api.views import ViewsApiDeps, create_views_app

    async def go() -> Any:
        app = create_views_app(ViewsApiDeps(dsn=DSN))
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver",
        ) as client:
            return await client.get(path)

    return _run(go())


# ───────────────────────── 一、种下去了，而且是完整的一条


@pytest.mark.compose
def test_the_topic_detail_endpoint_no_longer_returns_404(seeded: None) -> None:
    """**本卡的核心**：这一屏第一次有东西可看。"""
    from harness.demo_seed_topic import TOPIC_ID

    resp = _get(f"/topics/{TOPIC_ID}")

    assert resp.status_code == 200, resp.text


@pytest.mark.compose
def test_the_topic_carries_every_field_the_screen_needs(seeded: None) -> None:
    """`seed_id` · 两维 tag · `why_now`（含 `speculative` 与逐条证据）· `keyword_mapping`。

    少一样都会让详情屏上出现一个空槽，而空槽读起来像「这一项没有」，
    真相是「这条种子没种全」。
    """
    from harness.demo_seed_topic import SEED_ID, TOPIC_ID

    topic = _get(f"/topics/{TOPIC_ID}").json()["topic"]

    assert topic["seed_id"] == SEED_ID
    assert topic["target_user_tag"] and topic["form_factor_tag"]
    assert topic["keyword_mapping"], "keyword_mapping 是空的"
    why_now = topic["why_now"]
    assert why_now["claim"]
    assert why_now["speculative"] is False
    assert len(why_now["evidences"]) == 2, f"证据条数不对：{why_now['evidences']}"


@pytest.mark.compose
def test_every_evidence_carries_a_citation_that_really_exists(seeded: None) -> None:
    """每条证据的 `citation_id` **在库里解得开**。

    只判「字段非空」的话，编一个 `cit-xxx` 也能过——
    而屏上那条引用点开是空的，用户读到的是「这里有出处」而它没有。
    """
    import asyncpg

    from harness.demo_seed_topic import TOPIC_ID

    evidences = _get(f"/topics/{TOPIC_ID}").json()["topic"]["why_now"]["evidences"]

    async def exists(citation_id: str) -> bool:
        conn = await asyncpg.connect(DSN)
        try:
            return bool(await conn.fetchval(
                "SELECT 1 FROM citations WHERE citation_id = $1", citation_id))
        finally:
            await conn.close()

    for evidence in evidences:
        assert evidence["citation_id"], f"证据没有 citation_id：{evidence}"
        assert _run(exists(evidence["citation_id"])), (
            f"引用解不开：{evidence['citation_id']}")
        assert evidence["event"] and evidence["event_date"]


@pytest.mark.compose
def test_the_fixture_says_it_is_a_fixture_in_the_data_itself(seeded: None) -> None:
    """**NEVER 冒充模型产出**。

    标记要写在**数据里**，不是只写在脚本注释里——注释不会跟着数据被查询出来，
    而截图外传的时候带走的是数据。
    """
    from harness.demo_seed_topic import TOPIC_ID

    topic = _get(f"/topics/{TOPIC_ID}").json()["topic"]

    assert "-demo-fixture-" in topic["topic_id"]
    assert "夹具" in topic["one_liner"], f"屏上第一行没标出它是夹具：{topic['one_liner']}"
    assert "夹具" in topic["why_now"]["claim"]


# ───────────────────────── 二、幂等，且不碰真数据


@pytest.mark.compose
def test_running_the_seed_twice_does_not_create_a_second_row(seeded: None) -> None:
    """**恒幂等**：重复跑不产生第二条。

    不幂等的话，一次手滑重跑会让屏上出现两条一模一样的主题，
    而用户读到的是「模型生成了两条重复的」。
    """
    import asyncpg

    from harness.demo_seed_topic import TOPIC_ID, seed

    _run(seed(dsn=DSN))          # 第二次
    _run(seed(dsn=DSN))          # 第三次

    async def count() -> int:
        conn = await asyncpg.connect(DSN)
        try:
            return int(await conn.fetchval(
                "SELECT count(*) FROM topics WHERE topic_id = $1", TOPIC_ID) or 0)
        finally:
            await conn.close()

    assert _run(count()) == 1


@pytest.mark.compose
def test_the_drop_takes_everything_back(seeded: None) -> None:
    """`--drop` 原样撤干净——夹具要能**不留痕地**拿掉。

    撤不干净的话，下一个人看到库里那几行会以为它们是产品数据。
    """
    import asyncpg

    from harness.demo_seed_topic import (
        SEED_ID,
        TOPIC_ID,
        fixture_citations,
        fixture_docs,
        seed,
    )

    _run(seed(drop_only=True, dsn=DSN))

    async def leftovers() -> list[str]:
        conn = await asyncpg.connect(DSN)
        try:
            found: list[str] = []
            if await conn.fetchval(
                    "SELECT 1 FROM topics WHERE topic_id = $1", TOPIC_ID):
                found.append(TOPIC_ID)
            if await conn.fetchval(
                    "SELECT 1 FROM topic_seeds WHERE seed_id = $1", SEED_ID):
                found.append(SEED_ID)
            for citation in fixture_citations():
                if await conn.fetchval(
                        "SELECT 1 FROM citations WHERE citation_id = $1",
                        citation.citation_id):
                    found.append(citation.citation_id)
            for doc in fixture_docs():
                if await conn.fetchval(
                        "SELECT 1 FROM docs WHERE doc_id = $1", doc.doc_id):
                    found.append(doc.doc_id)
            return found
        finally:
            await conn.close()

    assert _run(leftovers()) == []
    _run(seed(dsn=DSN))          # 还原，让 fixture 的收尾照常


def test_the_seeder_never_deletes_without_a_where_clause() -> None:
    """`_drop` 里每一条 DELETE 都带 WHERE。

    一条漏了 WHERE 的 DELETE 会把 demo 库里那六条**真**主题一起清掉——
    而它们没有任何脚本能重造。
    """
    import re

    code = "\n".join(
        line for line in SEEDER.read_text(encoding="utf-8").splitlines()
        if not line.lstrip().startswith("#"))
    deletes = re.findall(r'"DELETE FROM [^"]*"', code)

    assert deletes, "扫不到任何 DELETE——这条判据在空转"
    for statement in deletes:
        assert "WHERE" in statement, f"这条 DELETE 没有 WHERE：{statement}"


def test_the_seeder_only_touches_its_own_prefixed_rows() -> None:
    """夹具的每个 id 都带 `-demo-fixture-` 前缀。

    前缀是「哪些行属于这个脚本」的**唯一依据**，`_drop` 按它限定。
    漏一个前缀，那一行就再也撤不掉了。
    """
    from harness.demo_seed_topic import (
        ORIGIN_ID,
        SEED_ID,
        TOPIC_ID,
        fixture_citations,
        fixture_docs,
    )

    ids = [TOPIC_ID, SEED_ID, ORIGIN_ID]
    ids += [c.citation_id for c in fixture_citations()]
    ids += [d.doc_id for d in fixture_docs()]

    for identifier in ids:
        assert "-demo-fixture-" in identifier, f"这个 id 没有夹具前缀：{identifier}"


_SQL_VERBS = ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "DROP", "ALTER")


def sql_statements(source: str) -> list[str]:
    """脚本里的**每一条 SQL 字面量**。

    ## 为什么判 SQL 而不是判整份源码

    「作用范围」就是这些语句——脚本能碰到库里什么，全在这里。
    整份源码扫的话，判据会把**说明问题的那些话**当成问题本身：
    本脚本的模块 docstring、`_drop` 的函数 docstring、
    甚至收尾 `print` 的那句「那六条真主题未受影响」，
    都逐字写着 `topic-demo14bf9d94b0`——它们是在解释「为什么还要种夹具」，
    不是在碰它们。

    本仓这是第十次撞见同一形状（规格 `#2.4` · `backfill.py` · 噪声基线 ·
    `check_fe_be_parity` 旧白名单 · `FIX-12` 枚举扫描 · `test_endpoint_triage`
    读缓存判据 · `GAUGE-14` 首段清单 · `STALE-01` 时间戳禁令 ·
    `REGION-11` 迁移回填 · 本处）。**每一次的修法都是给「引用」一个位置，
    而不是把判据放宽**——这里给的位置是「不是 SQL 的字符串不算」。
    """
    import ast

    found: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            continue
        text = node.value.lstrip()
        if text.upper().startswith(_SQL_VERBS):
            found.append(" ".join(node.value.split()))
    return found


def test_the_six_real_topics_are_not_in_the_seeders_blast_radius() -> None:
    """那六条**真**主题不在这个脚本的作用范围里。

    它们是模型产出、是一次过去运行的痕迹，**没有任何脚本能重造**。
    误删一次就永久没了，所以这里逐条查**每一句 SQL**：
    既没有它们的 id，也没有前缀通配。
    """
    statements = sql_statements(SEEDER.read_text(encoding="utf-8"))

    assert statements, "一句 SQL 都没扫到——这条判据在空转"
    assert any(s == "DELETE FROM topics WHERE topic_id = $1" for s in statements), (
        f"删主题那条不是按单 id 限定：{statements}")
    for statement in statements:
        assert "LIKE" not in statement.upper(), f"前缀通配会扫到别人的行：{statement}"
        assert "topic-demo14bf9d94b0" not in statement, f"这句碰到了真主题：{statement}"


def test_the_sql_scanner_would_catch_a_real_reference() -> None:
    """**阴性对照**：只判 SQL 不是放行。

    上一条把说明文字排除在外。而真有一句 SQL 去删真主题时，它必须照样被抓到——
    否则「只判 SQL」就成了一个豁免通道。
    """
    injected = sql_statements(
        '"""说明：这里提到 topic-demo14bf9d94b0 只是举例。"""\n'
        'def go(conn):\n'
        '    print("那六条 topic-demo14bf9d94b0-* 未受影响")\n'
        "    conn.execute(\"DELETE FROM topics WHERE topic_id LIKE "
        "'topic-demo14bf9d94b0-%'\")\n")

    assert len(injected) == 1, f"说明文字被算成了 SQL：{injected}"
    assert "LIKE" in injected[0] and "topic-demo14bf9d94b0" in injected[0]


# ───────────────────────── 三、取证样例换过来，404 额度撤掉


def test_the_smoke_sample_points_at_the_seeded_topic() -> None:
    """占位串退役。

    留着占位串的话，这一屏的取证永远是一张 404 截图，
    而那张截图会被读成「这屏坏了」。
    """
    from harness.demo_seed_topic import TOPIC_ID

    code = SMOKE.read_text(encoding="utf-8")

    assert f'"/topics/[id]": "{TOPIC_ID}"' in code, "样例 id 没换过来"
    assert '"tp-placeholder"' not in code, "占位串还在"


def test_the_console_allowance_for_the_topic_screen_is_withdrawn() -> None:
    """**`DEC-041` 那条硬判据**：`/topics/[id]` 的 404 额度撤掉。

    不撤的话额度还在，屏上哪天真退回 404 时**没有一条判据会响**——
    额度是当初为「那一屏本来就没有数据」开的，数据有了，额度就该收回去。
    """
    code = SWEEP.read_text(encoding="utf-8")
    baseline = code[code.index("CONSOLE_BASELINE"):code.index("def _report")]
    entries = [
        line for line in baseline.splitlines()
        if line.lstrip().startswith('"/') and ":" in line
    ]

    assert not any('"/topics/[id]"' in line for line in entries), (
        "额度还挂在 CONSOLE_BASELINE 里")


def test_the_withdrawal_left_a_note_saying_why() -> None:
    """撤掉之后要留一句为什么。

    一条**消失了的**基线与一条**从来没有过的**基线长得一模一样——
    下一个人看到这一屏零额度时，读不出这里曾经有过一条、以及它是怎么被清掉的。
    """
    code = SWEEP.read_text(encoding="utf-8")

    assert "SEED-01" in code and "DEC-041" in code, "撤额度没写依据"
    assert "topics/[id]" in code, "撤掉的是哪一屏都没写"


# ───────────────────────── 四、单据关掉


def test_the_sheet_is_closed_and_records_which_option_won() -> None:
    text = SHEET.read_text(encoding="utf-8")
    head = "\n".join(text.splitlines()[:8])

    assert "**状态** closed" in head, f"单据还开着：{head!r}"
    assert "DEC-041" in text and "SEED-01" in text
    assert "甲" in text, "没写清 owner 挑的是哪一项"
    assert "六条" in text, "没记下「库里其实已经有六条真主题」这个实况"
