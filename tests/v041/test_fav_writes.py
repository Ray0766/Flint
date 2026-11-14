"""FAV-WRITES：收藏三张表真的在存了，屏上却没有入口按下去。

`favorites` 表由 `PERSIST-01` 建好、库里已有真行，而三条写操作
（`DELETE /favorites/{id}` · `refresh-snapshot` · `staleness`）
**一处都没被调**——对账器把它们记在「已装配未调用」里。
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import uuid
from pathlib import Path

import httpx
import pytest

REPO = Path(__file__).resolve().parents[2]
CLIENT = REPO / "web" / "lib" / "favoritesClient.ts"
COMPONENT = REPO / "web" / "components" / "favorites-library" / "FavoritesLibrary.tsx"
PAGE = REPO / "web" / "app" / "favorites" / "page.tsx"
ZH = REPO / "web" / "messages" / "zh.json"
API = os.environ.get("FLINT_API_BASE", "http://localhost:8000")

THREE = ("remove", "refresh", "staleness")


def _code(path: Path) -> str:
    text = re.sub(r"/\*.*?\*/", "", path.read_text(encoding="utf-8"), flags=re.DOTALL)
    return "\n".join(
        ln for ln in text.splitlines() if not ln.strip().startswith("//"))


# ───────────────────────── 一、三条都接上了


def test_all_three_write_paths_have_a_client() -> None:
    code = _code(CLIENT)

    assert "removeFavorite" in code and '"DELETE"' in code
    assert "refreshFavoriteSnapshot" in code and "refresh-snapshot" in code
    assert "checkFavoriteStaleness" in code and "staleness" in code


def test_the_screen_renders_all_three_entries() -> None:
    """三个入口真的在屏上，且**不传回调就不渲染**。

    渲染一个按不动的按钮，与「这个能力没有」在屏上长得一样，
    而用户会以为自己没点到——`LOCALE-SAVE` 治的正是那种形状。
    """
    component = _code(COMPONENT)
    page = _code(PAGE)

    for action in THREE:
        assert f'data-favorite-action="{action}"' in component, action
    assert "onRemove ?" in component and "onRefresh ?" in component
    for handler in ("onRemove=", "onRefresh=", "onCheckStaleness="):
        assert handler in page, handler


# ───────────────────────── 二、三条各说各的（acceptance②）


def test_each_failure_says_its_own_thing() -> None:
    """**NEVER 合成一句「操作失败」**：三条失败之后用户该做的事完全不同。

    取消失败 = 那条还在；更新失败 = 收藏还在但快照没换；
    看陈旧失败 = **不知道它旧没旧**（NEVER 显示成「最新」）。
    """
    messages = json.loads(ZH.read_text(encoding="utf-8"))
    texts = [messages[f"favorites.error.{a}"] for a in THREE]

    assert len(set(texts)) == 3, f"三条失败措辞有重样的：{texts}"
    assert "还在" in messages["favorites.error.remove"]
    assert "快照" in messages["favorites.error.refresh"]
    # 第三条最要紧：它 MUST 说清「查不到 ≠ 最新」。
    assert "不等于" in messages["favorites.error.staleness"]


def test_a_missing_favourite_is_its_own_answer_not_a_failure() -> None:
    """404 单列一档：**这一条不在**（或不是你的），与「后端挂了」不是一回事。"""
    code = _code(CLIENT)

    assert '"not_found"' in code
    assert 'res.status === 404' in code


def test_not_checked_is_never_folded_into_false() -> None:
    """`not_checked` 是**一等答案**，NEVER 折成 `false`。

    折了的话屏上会说「最新」——而真相是我们没查过。
    """
    code = _code(CLIENT)

    assert '"not_checked"' in code
    assert "snapshot_stale?: boolean" in code, (
        "陈旧那一格被写成必填了——那样没查过时只能编一个")
    # 字段名照后端实况：写成 `stale` 的话读出来恒是 undefined，
    # 屏上会安静地显示「没判过」，**而库里其实判过了**（实测被对账器抓到）。
    assert re.search(r"^\s*snapshot_stale\?", code, re.MULTILINE)


# ───────────────────────── 三、写完重取，NEVER 前端自己抹掉那一条


def test_the_screen_refetches_instead_of_editing_its_own_list() -> None:
    """屏上那份要**跟着库走**。

    前端自己把那一条抹掉的话，后端其实没删成时屏上与库里就分叉了——
    而分叉的那一侧看起来完全正常。
    """
    page = _code(PAGE)

    assert "refetch()" in page
    assert "filter(" not in page, "屏自己在改列表"


# ───────────────────────── 四、归属：陌生人 NEVER 看到别人的收藏


@pytest.mark.compose
def test_a_stranger_can_neither_read_nor_delete_someone_elses_favourite() -> None:
    """两个方向各断言一次（acceptance③）。

    方向一：本人读得到、删得掉；方向二：陌生人**读不到也删不掉**。
    只判其中一个方向的话，一个「谁都读得到」的实现在方向一上照样绿。
    """
    mine = f"fav-owner-{uuid.uuid4().hex[:8]}"
    stranger = f"fav-stranger-{uuid.uuid4().hex[:8]}"
    favorite_id = f"fav-{uuid.uuid4().hex[:8]}"

    with httpx.Client(base_url=API, timeout=10.0) as client:
        made = client.post("/favorites", headers={"x-user-id": mine}, json={
            "favorite_id": favorite_id, "target_kind": "cluster",
            "target_id": "c-fav-writes",
            # 内嵌证据快照是**必填**（冻结件 `Favorite` 的原话：只存 snapshot_id
            # 的话，被引 snapshot 被周删清掉之后收藏就变成一个指向空处的壳）。
            # 这里是判据在种一行，给的是一份**标了来源的**最小快照。
            "evidence_snapshot": {"seeded_by": "test_fav_writes"}})
        if made.status_code in (401, 503):
            pytest.skip(f"这个身份或存储面不可用：{made.status_code}")
        assert made.status_code in (200, 201), made.text

        # 方向一：本人读得到。
        mine_list = client.get("/favorites", headers={"x-user-id": mine}).json()
        assert any(f["favorite_id"] == favorite_id
                   for f in mine_list.get("items", [])), mine_list

        # 方向二：陌生人读不到、删不掉。
        theirs = client.get("/favorites", headers={"x-user-id": stranger}).json()
        assert not any(f["favorite_id"] == favorite_id
                       for f in theirs.get("items", [])), "陌生人看到了别人的收藏"
        denied = client.delete(f"/favorites/{favorite_id}",
                               headers={"x-user-id": stranger})
        assert denied.status_code == 404, denied.text

        # 收尾：本人删掉自己的（顺带证明方向一的删也通）。
        gone = client.delete(f"/favorites/{favorite_id}",
                             headers={"x-user-id": mine})
        assert gone.status_code == 204, gone.text


# ───────────────────────── 五、对账器少三条


def test_the_three_endpoints_left_the_unused_list() -> None:
    """acceptance⑤：`backend_unused_by_frontend` 里不再有这三条。"""
    done = subprocess.run(
        [sys.executable, str(REPO / "tools" / "check_fe_be_parity.py"), "--json"],
        capture_output=True, text=True, encoding="utf-8", cwd=REPO, check=False)
    unused = [f["subject"] for f in json.loads(done.stdout)["findings"]
              if f["kind"] == "backend_unused_by_frontend"]

    for gone in ("/favorites/{}", "/favorites/{}/refresh-snapshot",
                 "/favorites/{}/staleness"):
        assert gone not in unused, f"接完了它还在「已装配未调用」里：{gone}"


def test_the_frontend_never_invents_snapshot_content() -> None:
    """acceptance④：前端 **NEVER 自己拼一份快照**。

    改前广场送的是 `evidence_snapshot: {}`——空的。空不是编，
    而那时「谁该把真快照放进去」没有答案（单据
    `docs/blocked/FAV-SNAPSHOT-HAS-NO-PROVIDER.md`，已关）。

    `DEC-055`（owner 2026-08-10）给了答案：**后端在收藏那一刻自取**。
    于是广场**连那一格都不再送**——这条禁令因此变得更硬：
    从「里面 NEVER 出现前端编出来的字段」变成「**整格都不由前端说**」。

    翻面而不是删掉：它守的那件事没变，只是前端能碰的面积缩到了零。
    """
    actions = _code(REPO / "web" / "components" / "plaza" / "cardActions.ts")
    block = actions[actions.index("favoriteCluster"):]
    block = block[: block.index("\n}")]

    assert "evidence_snapshot" not in block, (
        "广场又开始自己送快照了——`DEC-055` 之后这一格整格由后端放")
    assert "cluster_id:" not in block and "keyword" not in block, (
        "前端往请求里塞了自己编的证据字段")
    assert "target_kind" in block and "target_id" in block, (
        "前端连「收哪一条」都不说了，那后端无从自取")
