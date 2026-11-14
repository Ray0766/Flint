"""FAV-SNAPSHOT / `DEC-055`：收藏的证据快照由**后端**在收藏那一刻自取。

## 改前那一幕

`POST /favorites` 的 `evidence_snapshot` 必填，而广场那个动作手上只有热点卡面
（`cluster_id` / 名称 / 热度）——**它拼不出真快照**。前端拼一份就是编一份证据
（`FAV-WRITES` acceptance④ 逐字禁止），于是它送 `{}`：

> 从广场收的每一条，屏上都说「这条收藏的内容不在了」。
> **那句是实话，而真相是没有人往里面放东西。**

## 三句话 NEVER 合并（`DEC-055` 边界逐字）

| 情形 | 答复 | 用户该做什么 |
|---|---|---|
| 这一族没有取证面 | `503 FAMILY_NOT_CONFIGURED` | 等下一版 |
| 取证面在、这次取不着 | **`502 EVIDENCE_FETCH_FAILED`** | 再试一次 |
| 内容真的被清掉了 | 列表屏 `favorites.content_gone` | 重试一万次也回不来 |

合成一句之后，能重试的人不会重试，而等下一版的人会一直重试。

## 冻结件一字未动

`Favorite.evidence_snapshot` 仍是**内嵌本体**，不是 `snapshot_id`
（它防的是「被引 snapshot 被 180 天周删清掉之后收藏变成空壳」）。
`DEC-055` 改的是**谁来放**，不是放什么——本文件 §四 判这一条。
"""
from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import asyncpg
import pytest

REPO = Path(__file__).resolve().parents[2]
CARD_ACTIONS = REPO / "web" / "components" / "plaza" / "cardActions.ts"
MESSAGES = REPO / "web" / "messages"
FAVORITES_API = REPO / "flint" / "api" / "favorites.py"

import os

DSN = os.environ.get(
    "FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")
NOW = datetime(2026, 8, 11, tzinfo=UTC)


def _deps(**over: Any) -> Any:
    from flint.api.favorites import FavoritesApiDeps
    from flint.fav.pin import SnapshotPins
    from flint.fav.stale import SnapshotHistoryStore
    from flint.fav.store import FavoriteStore

    base: dict[str, Any] = {
        "store": FavoriteStore(),
        "pins": SnapshotPins(),
        "history": SnapshotHistoryStore(),
        "diff_channel": lambda *_a, **_k: None,
        "now": lambda: NOW,
        "project_id_for": lambda _row: "",
        "current_version": lambda: 0,
        "snapshot_for": None,
    }
    base.update(over)
    return FavoritesApiDeps(**base)


def _client(**over: Any) -> Any:
    from fastapi.testclient import TestClient

    from flint.api.favorites import create_favorites_app

    return TestClient(create_favorites_app(_deps(**over)),
                      raise_server_exceptions=False)


def _post(client: Any, **body: Any) -> Any:
    payload = {"favorite_id": f"fav-{uuid.uuid4().hex[:8]}",
               "target_kind": "cluster", "target_id": "c-1", **body}
    return client.post("/favorites", json=payload, headers={"X-User-Id": "u-1"})


# ───────────────────────── 一、前端不再自己拼快照


def test_the_plaza_no_longer_sends_a_snapshot() -> None:
    """广场那个动作 NEVER 再送 `evidence_snapshot`。

    送 `{}` 的话，一份空快照会被当成「用户给的那一份」原样存下去——
    而后端自取那条路**永远走不到**。
    """
    code = CARD_ACTIONS.read_text(encoding="utf-8")
    body = code.split("export function favoriteCluster")[1].split("export ")[0]

    assert "evidence_snapshot" not in body.split('"""')[0].split("*/")[-1], (
        "广场又开始自己拼快照了")
    assert "target_kind" in body and "target_id" in body


def test_the_ban_on_making_up_evidence_is_still_written_down() -> None:
    """「前端 NEVER 自己拼快照」那条禁令**照旧钉着**（acceptance⑤ 逐字）。

    只把那一行删掉是不够的：删完之后，下一个人会以为
    「顺手带一份卡面数据上去」是个好主意。
    """
    code = CARD_ACTIONS.read_text(encoding="utf-8")

    assert "拼不出真快照" in code
    assert "DEC-055" in code


# ───────────────────────── 二、后端自取：拿得到 → 快照非空且来自后端


def test_the_backend_fetches_the_snapshot_itself() -> None:
    """不带快照收一次 → 存下的那一份**来自 provider**，不是调用方给的。

    判「非空」不够：一个把 `{"ok": true}` 硬塞进去的实现也非空。
    所以这里判**内容逐字来自 provider**。
    """
    made = {"schema": "favorite-evidence/1", "target_id": "c-1",
            "cards": [{"card_id": "card-1", "cluster_id": "c-1"}]}
    seen: list[tuple[str, str]] = []

    def provider(kind: str, target: str) -> dict[str, Any]:
        seen.append((kind, target))
        return made

    got = _post(_client(snapshot_for=provider))

    assert got.status_code == 200, got.text
    assert got.json()["evidence_snapshot"] == made
    assert seen == [("cluster", "c-1")], f"provider 没被按目标问：{seen}"


def test_a_caller_supplied_snapshot_still_wins() -> None:
    """调用方自己带了就用他那份——**既有调用点逐字不受影响**。

    改成「一律后端自取」的话，那些已经拿着真快照的调用点
    会被悄悄换成另一份内容。
    """
    mine = {"schema": "mine/1", "cards": []}

    def provider(_k: str, _t: str) -> dict[str, Any]:
        raise AssertionError("调用方带了快照，provider 不该被问")

    got = _post(_client(snapshot_for=provider), evidence_snapshot=mine)

    assert got.status_code == 200, got.text
    assert got.json()["evidence_snapshot"] == mine


def test_an_explicitly_empty_snapshot_is_rejected_not_silently_replaced() -> None:
    """`{}` 与不给 **NEVER 合成一件事**——而 `{}` 本身是**被拒**的。

    `SCHEMA-09` 的既有基线（`flint/fav/store.py#add_favorite`）逐字写着
    「evidence_snapshot NEVER 为空：空快照的收藏就是一个指向空处的壳」，
    所以显式送 `{}` → **422**，本卡一字未动它。

    要紧的是**它 NEVER 被后端那份悄悄顶掉**：顶掉的话，
    调用方送来的数据被我们替换了，而他不会知道。

    > 这条判据第一版断言 `{}` 会带着 200 存下去——**错的是判据，不是代码**。
    > 既有实现早就守着这一条，本卡只是没有把它读出来。

    于是广场那一侧的实况比单据写的还硬：它送 `{}`，
    **那条请求根本存不下去**（422），不是「存下了一份空的」。
    """
    def provider(_k: str, _t: str) -> dict[str, Any]:
        return {"schema": "fetched/1", "cards": [{"card_id": "x"}]}

    client = _client(snapshot_for=provider)
    got = _post(client, evidence_snapshot={})

    assert got.status_code == 422, got.text
    assert got.json()["code"] == "VALIDATION_FAILED"
    assert client.get("/favorites", headers={"X-User-Id": "u-1"}
                      ).json()["items"] == [], "空快照被后端那份顶掉并存下了"


def test_the_three_refusals_have_three_different_codes() -> None:
    """三种「没存下」**各有各的码**，一条都 NEVER 合并。

    | 送什么 | 码 | 用户该做什么 |
    |---|---|---|
    | 显式 `{}` | `VALIDATION_FAILED`（422） | 别送空的 |
    | 不送、而没有取证面 | `FAMILY_NOT_CONFIGURED`（503） | 等下一版 |
    | 不送、取证面在但取不着 | `EVIDENCE_FETCH_FAILED`（502） | 再试一次 |
    """
    empty = _post(_client(snapshot_for=lambda _k, _t: {"a": 1}),
                  evidence_snapshot={})
    absent = _post(_client(snapshot_for=None))
    failed = _post(_client(snapshot_for=lambda _k, _t: {}))

    codes = [r.json()["code"] for r in (empty, absent, failed)]
    statuses = [r.status_code for r in (empty, absent, failed)]

    assert codes == ["VALIDATION_FAILED", "FAMILY_NOT_CONFIGURED",
                     "EVIDENCE_FETCH_FAILED"], codes
    assert statuses == [422, 503, 502], statuses
    assert len(set(codes)) == 3


# ───────────────────────── 三、取不着：NEVER 存空快照冒充成功


def test_a_failed_fetch_refuses_to_save() -> None:
    """provider 抛 → **502 且一条都没存**（acceptance④）。

    存下去的话，收藏会带着 200 落库，而屏上说「内容不在了」——
    **一句实话盖住一次失败**。
    """
    def provider(_k: str, _t: str) -> dict[str, Any]:
        raise RuntimeError("库不通")

    client = _client(snapshot_for=provider)
    got = _post(client)

    assert got.status_code == 502, got.text
    assert got.json()["code"] == "EVIDENCE_FETCH_FAILED"
    assert client.get("/favorites", headers={"X-User-Id": "u-1"}
                      ).json()["items"] == [], "取证失败了却还是存了一条"


def test_an_empty_fetch_is_also_a_failure() -> None:
    """provider 回空 → 同样 502。

    回空不是「这条没有证据所以收藏一份空的」——**是取不着**。
    存一份空的下去，用户翻回来看到的与「内容被清理了」一模一样。
    """
    client = _client(snapshot_for=lambda _k, _t: {})
    got = _post(client)

    assert got.status_code == 502
    assert got.json()["code"] == "EVIDENCE_FETCH_FAILED"
    assert client.get("/favorites", headers={"X-User-Id": "u-1"}
                      ).json()["items"] == []


def test_no_provider_is_a_different_answer_from_a_failed_fetch() -> None:
    """**没有取证面** 与 **取证失败** 是两码事，两个码、两个状态。

    合成一个的话，「这功能还没上」会被当成「再试一次」，反过来也一样。
    """
    absent = _post(_client(snapshot_for=None))
    failed = _post(_client(snapshot_for=lambda _k, _t: {}))

    assert absent.status_code == 503
    assert absent.json()["code"] == "FAMILY_NOT_CONFIGURED"
    assert failed.status_code == 502
    assert failed.json()["code"] == "EVIDENCE_FETCH_FAILED"
    assert absent.json()["code"] != failed.json()["code"]


def test_the_failure_sentence_is_not_the_content_gone_sentence() -> None:
    """屏上那两句**不一样**（`DEC-055` 边界逐字）。

    「取证失败」能重试，「内容已被清理」重试一万次也回不来。
    """
    for name in ("zh", "en"):
        messages = json.loads(
            (MESSAGES / f"{name}.json").read_text(encoding="utf-8"))
        fetch_failed = messages["favorites.evidence_fetch_failed"]
        gone = messages["favorites.content_gone"]

        assert fetch_failed != gone, f"{name}: 两句合并了"
        assert fetch_failed, f"{name}: 取证失败那一句是空的"


def test_the_error_code_is_not_borrowed_from_another_meaning() -> None:
    """`EVIDENCE_FETCH_FAILED` 是**自己一码**，NEVER 借 `SERVICE_UNAVAILABLE`。

    借一个已经有主的码去说另一件事，接的人分不清撞的是哪一条
    （`DEC-034` / `DEC-038` 反复禁的同一条）。
    """
    from flint.api.schemas import ERROR_CODES

    assert "EVIDENCE_FETCH_FAILED" in ERROR_CODES
    assert "SERVICE_UNAVAILABLE" in ERROR_CODES, "既有那一码没了"


# ───────────────────────── 四、冻结件语义一字未动


def test_the_favorite_still_embeds_rather_than_references() -> None:
    """`Favorite.evidence_snapshot` 仍是**内嵌本体**。

    换成 `snapshot_id` 的话，被引快照被周删清掉之后收藏就变成空壳——
    而那正是冻结件 docstring 里写死不做的事（§9-P1 提案，owner 未采纳）。
    """
    from typing import get_type_hints

    from contracts_v04.models_v04 import Favorite

    hints = get_type_hints(Favorite)

    assert "evidence_snapshot" in hints
    assert "snapshot_id" not in hints, "内嵌被换成引用了——那是 owner 未采纳的提案"


def test_the_endpoint_records_who_puts_the_snapshot_there() -> None:
    """理由写在缝自己的文件里，NEVER 只写在 trace 里。"""
    code = FAVORITES_API.read_text(encoding="utf-8")

    assert "DEC-055" in code
    assert "NEVER 存空快照" in code or "NEVER 存一份空快照" in code
    assert "snapshot_for" in code


# ───────────────────────── 五、真取证面：按目标真的去库里取


@pytest.fixture()
def a_cluster_with_cards() -> Any:
    """一条簇 + 两张证据卡，用完删干净。"""
    tag = uuid.uuid4().hex[:8]
    cluster_id = f"c-fav-{tag}"
    cards = [f"card-fav-{tag}-1", f"card-fav-{tag}-2"]

    def _run(sql: str, *args: Any) -> None:
        async def _go() -> None:
            conn = await asyncpg.connect(DSN)
            try:
                await conn.execute(sql, *args)
            finally:
                await conn.close()

        asyncio.run(_go())

    def _erase() -> None:
        _run("DELETE FROM evidence_cards WHERE card_id = ANY($1::text[])", cards)
        _run("DELETE FROM clusters WHERE cluster_id = $1", cluster_id)

    _erase()
    _run(
        "INSERT INTO clusters (cluster_id, canonical_name, category_id, centroid, "
        "status, first_seen, last_active, parent_cluster_ids, aliases, region) "
        "VALUES ($1, $2, 'cat-ai', array_fill(0.0::real, ARRAY[1024])::vector, "
        "'active', $3, $3, '[]'::jsonb, '[]'::jsonb, 'CN')",
        cluster_id, "收藏样本簇", NOW.date())
    for card_id in cards:
        _run(
            "INSERT INTO evidence_cards (card_id, cluster_id, keyword_ids, flags, "
            "top_links) VALUES ($1, $2, $3::jsonb, '{}'::jsonb, $4::jsonb)",
            card_id, cluster_id, json.dumps(["kw-1"]),
            json.dumps([{"url": "https://example.com/a"}]))
    try:
        yield cluster_id, cards
    finally:
        _erase()


@pytest.mark.compose
def test_the_real_source_reads_the_cards_from_the_database(
    a_cluster_with_cards: Any,
) -> None:
    """真取证面按 `cluster_id` 取回那一组卡，且 `jsonb` **解成了值**。

    不解的话，快照里存的是一段 JSON 文本——翻回来的人拿到的是字符串
    而不是一组链接，而那在屏上与「没有链接」长得一样。
    """
    from flint.fav.snapshot_source import SNAPSHOT_SCHEMA, build_snapshot_source

    cluster_id, cards = a_cluster_with_cards
    snapshot = build_snapshot_source(DSN)("cluster", cluster_id)

    assert snapshot["schema"] == SNAPSHOT_SCHEMA
    assert [c["card_id"] for c in snapshot["cards"]] == sorted(cards)
    assert snapshot["cards"][0]["keyword_ids"] == ["kw-1"], "jsonb 没解开"
    assert isinstance(snapshot["cards"][0]["top_links"], list)


@pytest.mark.compose
def test_an_unknown_cluster_yields_nothing_rather_than_a_made_up_snapshot() -> None:
    """查不到的目标 → 回空，**NEVER 造一份「至少有个 id」的最小快照**。

    造了的话收藏会成功，而用户翻回去时看到的是一份我们自己编的证据。
    """
    from flint.fav.snapshot_source import build_snapshot_source

    assert build_snapshot_source(DSN)("cluster", "c-does-not-exist") == {}


@pytest.mark.compose
def test_the_other_three_target_kinds_say_they_have_nothing() -> None:
    """`topic` / `deliverable` / `card` 今天没有取证面——**照实回空**。

    回一份编的快照的话，那三种目标的收藏会带着假证据存下去，
    而没有任何东西会喊。
    """
    from flint.fav.snapshot_source import build_snapshot_source

    source = build_snapshot_source(DSN)
    for kind in ("topic", "deliverable", "card"):
        assert source(kind, "whatever") == {}, f"{kind} 编了一份快照出来"


def test_the_app_wires_the_real_source() -> None:
    """装配面注的是**真件**，不是 `_unconfigured`。

    注占位的话，每一次收藏都是 503——而那与「这功能还没上」是两回事。
    """
    code = (REPO / "flint" / "api" / "app.py").read_text(encoding="utf-8")

    assert "snapshot_for=build_snapshot_source(dsn)" in code
    assert 'snapshot_for=_unconfigured("favorites")' not in code
