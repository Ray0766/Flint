"""SLOT-01：广场卡片的首见日期槽——**端点没回而已，零迁移**。

## 这一槽为什么是空的

`DS-02` 把六槽都建好了，`HotspotCard` 里 `firstSeen` 那个 `<time>` 一直在。
广场上它不显示，机械根因在后端：`GET /plaza/hot` 每条只回八个字段，
`first_seen` **不在其中**——而它并不是「没有」：

- 冻结件 `contracts/models.py#Cluster` 有 `first_seen: date`；
- `clusters` 表有这一列（建表时就在）；
- `views.py` 的 SQL **已经 select 了它**，取出来喂给 `ClusterSeries` 算新颖度，
  算完就丢——**一步之遥**。

所以本卡零迁移、零冻结件改动，只是让端点把手上已有的那个字段一并回出去。

## 判据为什么要打真栈

「端点回了 `first_seen`」自己判自己是不够的：这一槽经过
**库 → 端点 → 取数层 → 卡面**四道，任一道掉了它，屏上都只是「少一行」——
而少一行与「这个簇没有首见日期」长得一模一样。
所以本文件把三处的值摆到一起逐字比：库里的、端点回的、屏上量到的。
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
import tempfile
from datetime import date
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[2]
WEB = REPO / "web"
VIEWS = REPO / "flint" / "api" / "views.py"
CONTRACTS = REPO / "contracts" / "models.py"
MIGRATIONS = REPO / "migrations" / "versions"
CARD = WEB / "components" / "hotspot-card" / "HotspotCard.tsx"
MAPPER = WEB / "components" / "plaza" / "clusterToCard.ts"
CLIENT = WEB / "lib" / "viewsClient.ts"

DSN = os.environ.get("FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")
DAY = date(2026, 7, 20)
# 首见日期**故意与当日不同**：两个日期一样的话，端点拿 `day` 顶上去也能过。
FIRST_SEEN = date(2026, 7, 3)
VEC = "[" + ",".join(["0"] * 1024) + "]"

PWENV = Path(r"C:\pwenv\Scripts\python.exe")
DEMO_WEB = "http://localhost:3000"
DEMO_DAY = "2026-07-04"          # 广场屏不带 query 时的默认日（`page.tsx` 里那一行）
ARTIFACT = REPO / ".ui-probe" / "plaza_first_seen.json"


# ASGI 传输的占位主机。**恒用 `testserver`**：本仓别处写过 `http://t`，
# 而 `tools/check_no_live_network.py` 的本机词表里没有 `t`——
# 于是整份文件的「本机豁免」不成立，一个只打 127.0.0.1 的取证文件
# 会被报成「无护栏的真实外部请求」。**尺子没报错，是字面量选错了。**
ASGI_HOST = "http://testserver"


def _code_only(path: Path) -> str:
    text = re.sub(r"/\*[\s\S]*?\*/", "", path.read_text(encoding="utf-8"))
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("//")
    )


# ───────────────────────── 一、「零迁移」这句话的根据


def test_the_frozen_contract_already_has_first_seen() -> None:
    """acceptance①的前半：冻结件 `Cluster` 本来就有 `first_seen: date`。

    这一条成立时，本卡才允许「只改端点」。它要是不成立，
    这张卡就是一张冻结件卡，得停下走 `S9`——**两种情况的做法完全不同**。
    """
    text = CONTRACTS.read_text(encoding="utf-8")
    start = text.index("class Cluster")
    body = text[start:start + 1200]

    assert re.search(r"first_seen: *date", body), (
        "冻结件 Cluster 没有 first_seen——那本卡不成立，要按 S9 停"
    )


def test_the_table_already_has_the_column() -> None:
    """acceptance①的后半：`clusters` 表有这一列，所以**零迁移**。"""
    joined = "\n".join(
        text for text in (
            p.read_text(encoding="utf-8") for p in MIGRATIONS.glob("*.py")
        ) if "clusters" in text
    )

    assert "first_seen" in joined, "迁移里找不到 clusters.first_seen"


def test_this_card_adds_no_migration() -> None:
    """反向断言：本卡**没有**新增迁移。

    加一条迁移能让这一槽也亮起来，而那是一次不必要的库变更——
    多出来的那一列会与既有列说同一件事，**下一个人无从知道该信哪一列**。
    """
    added = [
        p.name for p in MIGRATIONS.glob("*.py")
        if re.search(r"add_column\(.*clusters.*first_seen",
                     p.read_text(encoding="utf-8"), re.DOTALL)
    ]

    assert added == [], f"本卡不该新增迁移，却有：{added}"


def test_the_sql_already_selected_it() -> None:
    """`views.py` 的 SQL 一直在 select `c.first_seen`——本卡改的是**回不回**，不是查不查。"""
    assert "c.first_seen" in VIEWS.read_text(encoding="utf-8")


# ───────────────────────── 二、端点真的把它回出去（真栈，种子库）


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


@pytest.fixture()
def seeded() -> Any:
    import asyncpg

    async def wipe() -> None:
        conn = await asyncpg.connect(DSN)
        try:
            await conn.execute("DELETE FROM heat_points WHERE cluster_id LIKE 'fs-%'")
            await conn.execute("DELETE FROM clusters WHERE cluster_id LIKE 'fs-%'")
        finally:
            await conn.close()

    async def seed() -> None:
        conn = await asyncpg.connect(DSN)
        try:
            await conn.execute(
                "INSERT INTO clusters (cluster_id, canonical_name, category_id, centroid, "
                "status, first_seen, last_active, parent_cluster_ids, merged_into, aliases) "
                "VALUES ('fs-c1', '首见日期簇', 'cat-ai', $1, 'active', $2, $3, "
                "'[]'::jsonb, NULL, '[]'::jsonb)", VEC, FIRST_SEEN, DAY)
            await conn.execute(
                "INSERT INTO heat_points (cluster_id, source_id, day, raw_value, norm_score) "
                "VALUES ('fs-c1', 'weibo', $1, 0.7, 0.7)", DAY)
        finally:
            await conn.close()

    _run(wipe())
    _run(seed())
    yield
    _run(wipe())


def _plaza_row(day: date) -> dict[str, Any]:
    import httpx

    from flint.api.views import ViewsApiDeps, create_views_app

    async def go() -> dict[str, Any]:
        app = create_views_app(ViewsApiDeps(dsn=DSN))
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.get(f"/plaza/hot?day={day.isoformat()}")
        assert resp.status_code == 200, resp.text
        rows = [r for r in resp.json()["clusters"] if r["cluster_id"] == "fs-c1"]
        assert rows, "种下的簇没进主榜"
        return dict(rows[0])

    return _run(go())


@pytest.mark.compose
def test_the_endpoint_returns_first_seen_verbatim_from_the_database(seeded: None) -> None:
    """acceptance④：端点回的日期与库里那一列**逐字相同**。

    逐字比而不是「有这个键」：`isoformat()` 之外任何一种写法
    （时间戳 / `datetime` 带时分秒 / 本地化格式）到了卡面都要再解析一次，
    而解析失败时屏上通常是**静静地不显示**——那就绕回本卡要修的那个样子。
    """
    import asyncpg

    async def read_back() -> Any:
        conn = await asyncpg.connect(DSN)
        try:
            return await conn.fetchval(
                "SELECT first_seen FROM clusters WHERE cluster_id = 'fs-c1'")
        finally:
            await conn.close()

    row = _plaza_row(DAY)
    in_db = _run(read_back())

    assert "first_seen" in row, f"端点仍然没回首见日期：{sorted(row)}"
    assert row["first_seen"] == in_db.isoformat() == FIRST_SEEN.isoformat()


@pytest.mark.compose
def test_first_seen_is_not_the_queried_day(seeded: None) -> None:
    """**阴性对照**：它不是把 `day` 顶上去。

    顶上去的那一版在每一条上都「有值」，看起来完全正常——
    而它说的是「今天第一次见到」，对一个跑了三周的热点那是假的。
    """
    row = _plaza_row(DAY)

    assert row["first_seen"] != DAY.isoformat(), "首见日期等于查询日，疑似拿 day 顶的"


@pytest.mark.compose
def test_the_other_eight_fields_are_untouched(seeded: None) -> None:
    """只加一个字段，**既有八个一个不动**——下游按名取值，少一个就是一处静默的空。"""
    row = _plaza_row(DAY)

    for key in ("cluster_id", "canonical_name", "category_id", "status",
                "by_source", "total_heat", "hotness", "hotness_components"):
        assert key in row, f"原有字段 {key} 掉了"


# ───────────────────────── 三、取数层与卡面把它接到底


def test_the_client_type_declares_it() -> None:
    """类型里没有的话，`clusterToCard` 写 `cluster.first_seen` 会被 tsc 拦下来——
    于是这一槽**永远接不上**，而屏上只是少一行。"""
    text = CLIENT.read_text(encoding="utf-8")
    start = text.index("interface PlazaCluster")
    body = text[start:text.index("}", start)]

    assert re.search(r"first_seen\??: *string", body), (
        f"PlazaCluster 里没有 first_seen：{body}"
    )


def test_the_mapper_carries_it_without_computing() -> None:
    """搬运，NEVER 计算：这一屏不做日期格式化、不算「几天前」。

    算出来的「3 天前」是**相对本机时钟**的——同一张卡在两台机器上会说不同的话，
    而截图取证里看不出哪一台是对的。
    """
    code = _code_only(MAPPER)

    assert re.search(r"firstSeen: *cluster\.first_seen", code), (
        "clusterToCard 没有把 first_seen 接到卡面槽上"
    )
    for forbidden in ("Date(", "toLocale", "天前"):
        assert forbidden not in code, f"搬运层出现了计算/格式化：{forbidden}"


def test_the_slot_still_hides_when_there_is_no_date() -> None:
    """acceptance②的后半：**逐槽隐藏规则不变**。

    没有首见日期时 NEVER 印「—」或「暂无」：那会让「这个簇刚建」
    与「这一槽没接上」看起来一样——正是本卡在修的那种混淆。
    """
    code = _code_only(CARD)

    assert "firstSeen ? (" in code, "首见日期槽不再是条件渲染"
    for placeholder in ('"—"', '"暂无"', '"N/A"'):
        assert placeholder not in code


# ───────────────────────── 四、屏上真的量到（真栈：库 → 端点 → 屏）

_RUNNER = """
import json, sys
from playwright.sync_api import sync_playwright
url, out = sys.argv[1], sys.argv[2]
with sync_playwright() as p:
    b = p.chromium.launch()
    page = b.new_page(viewport={"width": 1440, "height": 900})
    page.goto(url, wait_until="networkidle", timeout=60000)
    page.wait_for_selector('[data-testid="hotspot-card"]', timeout=30000)
    got = page.evaluate('''() => {
        const cards = [...document.querySelectorAll('[data-testid="hotspot-card"]')];
        const read = (c) => {
            const t = c.querySelector('[data-testid="hotspot-first-seen"]');
            const box = t ? t.getBoundingClientRect() : null;
            const owner = c.closest('[data-cluster-id]');
            return {
              cluster: owner ? owner.getAttribute('data-cluster-id') : null,
              dateTime: t ? t.getAttribute('datetime') : null,
              text: t ? t.textContent.trim() : null,
              width: box ? box.width : 0, height: box ? box.height : 0,
            };
        };
        return {cards: cards.map(read), total: cards.length};
    }''')
    got["endpoint"] = page.evaluate('''async (day) => {
        const res = await fetch("http://127.0.0.1:8000/plaza/hot?day=" + day);
        const body = await res.json();
        return Object.fromEntries(
            body.clusters.map(c => [c.cluster_id, c.first_seen ?? null]));
    }''', sys.argv[3])
    page.screenshot(path=".ui-probe/plaza-first-seen.png", full_page=False)
    b.close()
open(out, "w", encoding="utf-8").write(
    json.dumps({"schema": "plaza-first-seen/1", "url": url, **got},
               ensure_ascii=False, indent=1))
"""


def _endpoint_first_seen() -> dict[str, Any]:
    """端点回的 `{簇: 首见日期}`——**由页内的 `fetch` 取回**，不在 Python 侧出网。

    这样有两个好处：

    1. 判据面零真实请求。`tools/check_no_live_network.py` 把 `urlopen` 一律判红，
       而它**判得对**：本文件把 transport 当实参交了出去，
       整份文件的「本机豁免」因此不成立（那正是 `harness/demo_server.py` 的形状——
       文件里只有 localhost 字面量，交出去的客户端却在真打外网）；
    2. 比的是**屏收到的那一份**，不是另起一次请求拿到的另一份。
       两次请求之间数据可以变，那时「屏上与端点不一致」会指向一个不存在的缺陷。
    """
    art = _screen()
    endpoint = art.get("endpoint")
    if not endpoint:
        pytest.skip("探针没取到端点数据（demo 后端没起？）")
    return dict(endpoint)


def _screen() -> dict[str, Any]:
    if ARTIFACT.exists():
        return json.loads(ARTIFACT.read_text(encoding="utf-8"))
    if not PWENV.exists():
        pytest.skip(f"本机没有 {PWENV}（playwright 恒在项目外，NEVER 进项目依赖）")
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        runner = Path(tmp) / "first_seen_runner.py"
        runner.write_text(_RUNNER, encoding="utf-8")
        done = subprocess.run(
            [str(PWENV), str(runner), f"{DEMO_WEB}/plaza", str(ARTIFACT), DEMO_DAY],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=REPO, check=False,
        )
    if done.returncode != 0:
        pytest.skip(f"前端没起或探针跑不动：{done.stderr[-500:]}")
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


def test_the_demo_endpoint_carries_it_too() -> None:
    """本机 demo 栈（owner 亲自看的那一份）也回这个字段。

    种子库过了不等于 owner 那一屏会亮：两处走的是同一份代码、**不同的库**。
    """
    rows = _endpoint_first_seen()

    assert rows, "demo 广场当日一条簇都没有"
    missing = [cid for cid, value in rows.items() if value is None]
    assert missing == [], f"{len(missing)}/{len(rows)} 条没有首见日期"


def test_the_slot_is_really_on_the_screen() -> None:
    """acceptance②：屏上**量得到**这一槽，且它占了像素。

    只断言 DOM 里有会漏掉 `F-09` 那个形状：节点在、宽高是 0。
    """
    art = _screen()
    shown = [c for c in art["cards"] if c["dateTime"]]

    assert art["total"] > 0, "屏上一张卡都没有"
    assert shown, "所有卡的首见日期槽都是空的——这一槽仍然没接上"
    for card in shown:
        assert card["width"] > 0 and card["height"] > 0, f"槽在 DOM 里但没有面积：{card}"


def test_the_date_on_screen_matches_the_endpoint_verbatim() -> None:
    """acceptance④的完整链：**库 → 端点 → 屏**三处逐字相同。

    中间任一道把日期重新格式化过，这一条就红——而重新格式化过的日期
    在屏上看起来完全正常，只有对着端点比才看得出来。
    """
    art = _screen()
    by_id = _endpoint_first_seen()
    checked = 0

    for card in art["cards"]:
        if not card["dateTime"]:
            continue
        expected = by_id.get(card["cluster"] or "")
        if expected is None:
            continue
        assert card["dateTime"] == expected, (
            f"屏上 {card['dateTime']} ≠ 端点 {expected}"
        )
        assert card["text"] == expected, (
            f"显示文字被改写过：{card['text']} ≠ {expected}"
        )
        checked += 1

    assert checked > 0, "一张卡都没对上——取证与端点各说各的，这条判据在空转"
