"""FIX-16：解引用端点的鉴权方向——**匿名 NEVER 比带身份更有权限**。

## steward 看到的与真相

工单 §2 记的实测是：`GET /facts/fact-demo-vecdb-cost` 不带 `X-User-Id` 回 **200 真内容**，
带 `self / demo / u-demo` 三种身份**全部 404**；`/price-entries/{id}` 恒 422。

**方向确实是反的——而它不是代码里的方向反了。** 本卡逐条查到三个各自独立的根因，
三条都真，三条的修法完全不同：

| 看到的 | 根因 | 修在哪 |
|---|---|---|
| 匿名 200 | 跑着的 `:8000` 是**旧进程**，它早于 `x_user_id: str = Header()` 那次改动 | 重起后端（人工，`docs/blocked/` 记着） |
| 带身份 404 | 那三个 id **都不是这批 demo 数据的主人**——项目、作业、事实全挂在 `demo-user` 名下 | `start-demo.ps1` 的 `NEXT_PUBLIC_FLINT_USER_ID`：`self` → `demo-user` |
| 价格恒 422 | `quantity` 是必填 query，探针那几条 curl 没带 | 探针的调法；前端一直带（`DEREF_PATHS.price` 默认 `1`） |

## 而这张卡真正要保住的东西，此前是**靠匿名撑着的**

`derefClient.ts` **一个身份头都不发**（只发 `Accept`）。报告屏之所以还能看到事实与价格，
恰恰因为它打的是那个不要求身份头的旧进程——**那个进程一换，报告屏就整片丢内容**，
而屏上只会说「取不到」。本卡把身份头补上（`API_USER_ID`，没配就不发）。

## 一致的那条规则

**身份必需**，三族一律：匿名一律 422。至于**看得到什么**，三族不同且各有出处：

- `facts` 按 owner 切表（项目私有数据）→ 别人回 **404 而不是 403**：
  403 等于告诉对方「这个 id 存在，只是不给你看」，状态码本身就泄露了存在性；
- `price-entries` / `citations` 是**全局参考数据**（`pricebook` 表没有 owner 列，
  口径见 `docs/trace/FB-05.md`）→ 任何有身份的人都看得到。

这不是「方向不一致」：**要不要身份**这件事三族完全一致，
不一致的是**数据本身属不属于某个人**，而那是数据模型的事实，不是鉴权的口径。
"""
from __future__ import annotations

import asyncio
import json
import os
import re
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import asyncpg
import pytest
from fastapi.testclient import TestClient

from flint.api.deref import DerefApiDeps, create_deref_app

pytestmark = pytest.mark.compose

REPO = Path(__file__).resolve().parents[2]
WEB = REPO / "web"
CLIENT = WEB / "lib" / "derefClient.ts"
SCRIPT = REPO / "start-demo.ps1"

# **测试库**，不是 demo 库。
#
# 首版打的是 demo 库（那批 `fact-demo-*` 数据就在那儿），`DSN-ISO` 当场拦下：
# 「tests/ 里 NEVER 出现无 env 兜底的真 DSN 字面量」——那条尺子是对的，
# 而且更要紧的一层是**判据不该依赖某台机器上的 demo 数据**：
# 那批数据是某次 demo 跑留下的，没人能重造，换台机器这组判据就全 skip。
# 所以这里自己种一份最小夹具，三族各一条。
DSN = os.environ.get("FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")
PREFIX = "fix16-"
NOW = datetime(2026, 8, 9, 12, 0, tzinfo=UTC)

OWNER = f"{PREFIX}owner"     # 这批数据真正的主人
STRANGER = f"{PREFIX}nobody"

FACT = f"{PREFIX}fact"
PRICE = f"{PREFIX}price"
CITATION = f"{PREFIX}citation"


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


async def _seed(conn: asyncpg.Connection) -> None:
    """三族各一条：私有的 fact、全局的 price 与 citation。"""
    await conn.execute(
        "INSERT INTO projects (project_id, owner, origin_id, topic_ids, "
        "chosen_topic_id, deliverable_ids, change_log, status, created_at) "
        "VALUES ($1, $2, $3, $4, NULL, $5, $6, 'active', $7)",
        f"{PREFIX}proj", json.dumps({"kind": "user", "id": OWNER}), f"{PREFIX}origin",
        json.dumps([]), json.dumps([]), json.dumps([]), NOW)
    await conn.execute(
        "INSERT INTO facts_ledgers (ledger_id, project_id, version, parent_version, "
        "derivation_reason, created_from, created_at, actor) "
        "VALUES ($1, $2, 1, NULL, 'initial', $3, $4, 'seed')",
        f"{PREFIX}led", f"{PREFIX}proj", json.dumps([]), NOW)
    await conn.execute(
        "INSERT INTO facts (ledger_id, fact_id, statement, value, unit, citation_ids, "
        "status, origin, created_in_version, source_claim_id, promoted_from) "
        "VALUES ($1, $2, '向量库托管月成本', $3, '美元', $4, 'frozen', 'injected', 1, NULL, NULL)",
        f"{PREFIX}led", FACT, json.dumps(12.5), json.dumps([CITATION]))
    await conn.execute(
        "INSERT INTO pricebook (entry_id, item, unit, price_low, price_high, currency, "
        "region, year, source, updated_at, stale_after_months) "
        "VALUES ($1, '托管向量库', '实例月', 800.0, 1500.0, 'CNY', 'CN', 2026, "
        "'夹具数据 · FIX-16', $2, 12)", PRICE, NOW)
    await conn.execute(
        "INSERT INTO docs (doc_id, source_id, kind, title, url, published_at, meta, "
        "origin, access) VALUES ($1, 'arxiv', 'paper', '夹具文献', "
        "'https://example.invalid/fix16', $2, '{}'::jsonb, 'retrieved', 'public')",
        f"{PREFIX}doc", date(2026, 6, 20))
    await conn.execute(
        "INSERT INTO citations (citation_id, doc_id, locator, quote_span) "
        "VALUES ($1, $2, 'p.1', '夹具引文')", CITATION, f"{PREFIX}doc")


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
            await conn.execute(f"DELETE FROM citations WHERE citation_id LIKE '{PREFIX}%'")
            await conn.execute(f"DELETE FROM docs WHERE doc_id LIKE '{PREFIX}%'")
            await conn.execute(f"DELETE FROM pricebook WHERE entry_id LIKE '{PREFIX}%'")
            await _seed(conn)
        finally:
            await conn.close()

    _run(wipe())


def _code_only(path: Path) -> str:
    text = re.sub(r"/\*[\s\S]*?\*/", "", path.read_text(encoding="utf-8"))
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("//")
    )


@pytest.fixture
def client() -> TestClient:
    """**进程内**打真代码。

    `:8000` 上跑的是哪个版本，取决于谁什么时候起的它——拿它当判据的对象，
    量到的是那个进程的年龄，不是这份代码的行为。本卡开工时踩的正是这一脚。
    """
    return TestClient(create_deref_app(DerefApiDeps(dsn=DSN)))


def _get(client: TestClient, path: str, who: str | None) -> int:
    headers = {} if who is None else {"x-user-id": who}
    return client.get(path, headers=headers).status_code


PATHS = {
    "facts": f"/facts/{FACT}",
    "price-entries": f"/price-entries/{PRICE}?quantity=3",
    "citations": f"/citations/{CITATION}",
}


# ───────────────────────── 一、两种调用者 × 三族端点


def test_anonymous_is_refused_by_every_family(client: TestClient) -> None:
    """**匿名一律拒**——这是「方向」这件事上唯一的口径。

    `NEVER 停在「匿名比带身份更有权限」`：那种状态下，用户一登录就丢内容，
    而屏上说的是「取不到」——他会以为是自己的数据没了。
    """
    for family, path in PATHS.items():
        assert _get(client, path, None) == 422, f"{family} 对匿名放行了"


def test_the_owner_sees_all_three_families(client: TestClient) -> None:
    """带**对的**身份，三族全部 200。

    工单里那三个 id（`self` / `demo` / `u-demo`）一个都不是这批数据的主人——
    「带身份 404」量的是**身份给错了**，不是鉴权方向反了。
    """
    for family, path in PATHS.items():
        assert _get(client, path, OWNER) == 200, f"{family} 对主人回了非 200"


def test_a_stranger_never_sees_more_than_the_owner(client: TestClient) -> None:
    """**一致性判据**：同一个 id，陌生人看到的 NEVER 多于主人。

    这条比「三族答复一样」更要紧也更真：三族的**数据归属本来就不同**，
    要求它们回同一个码等于要求 pricebook 长出一个 owner 列。
    """
    for family, path in PATHS.items():
        owner = _get(client, path, OWNER)
        stranger = _get(client, path, STRANGER)
        assert owner == 200
        assert stranger in (200, 404), f"{family} 对陌生人回了 {stranger}"
        assert not (stranger == 200 and owner != 200), f"{family} 陌生人比主人看得多"


def test_private_data_hides_existence_and_shared_data_does_not(client: TestClient) -> None:
    """两种归属各自的正确答复，逐族钉住。

    - `facts` 是**项目私有**：陌生人 404（`404 而不是 403`——403 会泄露存在性，
      还能被用来枚举 id）；
    - `price-entries` / `citations` 是**全局参考数据**：有身份就看得到。

    钉住它是因为哪天 pricebook 长出 owner 列，这里必须红一次让人来改，
    而不是悄悄继续对所有人放行。
    """
    assert _get(client, PATHS["facts"], STRANGER) == 404
    assert _get(client, PATHS["price-entries"], STRANGER) == 200
    assert _get(client, PATHS["citations"], STRANGER) == 200


def test_a_missing_quantity_is_a_422_about_quantity_not_about_identity(
    client: TestClient,
) -> None:
    """价格那条「恒 422」的根因：`quantity` 必填，而探针没带。

    **与身份无关**——带着对的身份、不带 quantity，照样 422，
    而报文里说的是 `query.quantity`。两个 422 长得一样，说的是两件事。
    """
    r = client.get(f"/price-entries/{PRICE}", headers={"x-user-id": OWNER})

    assert r.status_code == 422
    assert "quantity" in r.text, r.text[:200]
    # 前端一直带着它（默认 1），所以这条 422 在真界面上不会出现。
    assert 'quantity=${quantity ?? 1}' in _code_only(CLIENT)


# ───────────────────────── 二、前端：身份头此前一个都不发


def test_the_client_sends_the_identity_header() -> None:
    """改前只发 `Accept`。对着当前这份后端代码，那意味着**每一次解引用都是 422**。

    报告屏此前还能看到事实与价格，靠的是一个还不要求身份头的旧进程——
    **那不是「能用」，是「还没撞上」。**
    """
    code = _code_only(CLIENT)

    assert '"x-user-id"' in code, "解引用客户端仍然不发身份头"
    assert "API_USER_ID" in code, "身份不是从配置来的"


def test_no_identity_configured_means_no_header_invented() -> None:
    """`没配就不发`——NEVER 编一个身份。

    发一个编出来的身份会让服务端把别人的数据当成你的
    （`FB-10` 的 A 类里 `X-User-Id` 逐字点名）。
    """
    code = _code_only(CLIENT)

    assert "if (userId) headers" in code, "没配身份时仍然发了那个头"
    for invented in ('"self"', '"demo-user"', '"anonymous"'):
        assert invented not in code, f"客户端里写死了一个身份：{invented}"


def test_the_demo_identity_points_at_the_owner_of_the_demo_data() -> None:
    """`start-demo.ps1` 原本配的是 `self`，而 demo 库里**没有任何东西属于 self**。

    配了身份反而比匿名看得少——那正是工单里「带身份 404」的来处。
    身份要指向真正持有这批数据的那个人，否则「配了身份」等于没配。
    """
    script = SCRIPT.read_text(encoding="utf-8")
    hit = re.search(r"NEXT_PUBLIC_FLINT_USER_ID\s*=\s*'([^']+)'", script)

    assert hit, "启动脚本不再配身份了"
    # demo 栈那一侧的主人叫 `demo-user`（项目、作业、事实全挂在它名下）；
    # 本文件自己种的夹具用另一个前缀，两者 NEVER 混为一谈。
    assert hit.group(1) == "demo-user", (
        f"配的是 {hit.group(1)}，而 demo 库那批数据属于 demo-user")


def test_the_report_screen_reaches_the_three_families_with_that_identity(
    client: TestClient,
) -> None:
    """**这张卡真正要保住的东西**：带身份时，报告屏要的三族内容都拿得到。

    这里把前端会发的那组请求（同一个身份、同样的路径形状）逐条打一遍。
    """
    for family, path in PATHS.items():
        r = client.get(path, headers={"x-user-id": OWNER})
        assert r.status_code == 200, f"{family} 拿不到"
        assert r.json(), f"{family} 回了空"

    facts = client.get(PATHS["facts"], headers={"x-user-id": OWNER}).json()
    price = client.get(PATHS["price-entries"], headers={"x-user-id": OWNER}).json()
    # 三通道 NEVER 混用（S2-2 铁律之三）：各自报出自己是哪条通道。
    assert facts["channel"] == "fact"
    assert price["channel"] == "price"


# ───────────────────────── 三、跑着的那个后端是旧的（人工重起，单据记着）


def test_the_stale_process_is_written_down_not_silently_worked_around() -> None:
    """`:8000` 上跑的是旧进程——**这件事本身要留痕**。

    绕过它（比如把判据也打到 `:8000`）会让下一个人再查一遍同一个假象，
    而这一次他可能会去「修」一个本来就是对的方向。
    """
    sheet = REPO / "docs" / "blocked" / "DEREF-PROBE-HIT-A-STALE-BACKEND.md"

    assert sheet.exists(), "旧进程这件事没留痕"
    text = sheet.read_text(encoding="utf-8")
    assert "重起" in text or "重启" in text, "没写清该怎么处置"
    assert "Header()" in text, "没写清旧进程与当前代码差在哪"
