"""BE-09 · 分享端点（暴露 `flint/share` · v2 屏 2.18 外链只读页）。

`flint/share/links.py` 把门禁逻辑写好了（三个状态码不合并、判断顺序、
口令只以 hash 存在），但**零 API 出口**。本卡暴露三个动作：
创建分享链接 / 按 token 只读取内容 / 撤销分享。

四条判据线：

1. **外链那条路上没有身份**——响应里 NEVER 出现 owner，
   也 NEVER 出现另一个没被分享的兄弟资源。
2. **token 由服务端生成且不可枚举**——客户端**递不进来**一个 token
   （`extra="forbid"`），两次生成必不同，熵取自 `secrets`。
3. **撤销不可逆、与过期分开**（冻结件原话：「过期可续期，撤销不可逆」）。
   撤销后立刻 410，而不是把链接删掉——删掉就变成 404「没这条」，
   持链人会以为自己拿错了链接。
4. **口令走头不走查询串**：查询串会进访问日志与 Referer。
"""
from __future__ import annotations

import ast
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from flint.api.share import ShareApiDeps, ShareLinkStore, create_share_app

MODULE = Path("flint/api/share.py")

ME = "u-me"
OTHER = "u-other"
NOW = datetime(2026, 6, 7, 8, 9, tzinfo=UTC)

PUBLIC = "/public/shares"


def _app(
    *, now: datetime = NOW, content: dict[str, Any] | None = None,
    asked: list[tuple[str, str]] | None = None,
    store: ShareLinkStore | None = None,
) -> tuple[TestClient, ShareLinkStore]:
    store = store or ShareLinkStore()
    body = content if content is not None else {"title": "报告", "blocks": []}

    async def load_content(target_kind: str, target_id: str) -> dict[str, Any] | None:
        if asked is not None:
            asked.append((target_kind, target_id))
        if target_id == "d-missing":
            return None
        return dict(body)

    deps = ShareApiDeps(store=store, load_content=load_content, now=lambda: now)
    return TestClient(create_share_app(deps)), store


def _create(client: TestClient, user: str = ME, **overrides: Any) -> Any:
    payload: dict[str, Any] = {"target_kind": "deliverable", "target_id": "d-1"}
    payload.update(overrides)
    return client.post("/shares", json=payload, headers={"X-User-Id": user})


def _token(client: TestClient, **kwargs: Any) -> str:
    response = _create(client, **kwargs)
    assert response.status_code == 200, response.text
    token: str = response.json()["token"]
    return token


# ───────────────────────── 一、创建（acceptance①③）


def test_creating_a_link_returns_a_token() -> None:
    client, _ = _app()

    body = _create(client).json()

    assert body["token"]
    assert body["target_kind"] == "deliverable"
    assert body["revoked"] is False


def test_the_token_is_server_generated_and_not_enumerable() -> None:
    """两次必不同、够长；熵取自 `secrets`，NEVER 用 `random`（可预测）。"""
    client, _ = _app()

    first, second = _token(client), _token(client, target_id="d-2")

    assert first != second
    assert len(first) >= 32

    identifiers = _identifiers()
    assert "secrets" in identifiers
    assert "random" not in identifiers


def test_a_client_supplied_token_is_rejected() -> None:
    """递得进来一个 token，就等于让调用方自己挑一条别人猜得到的链接。"""
    client, _ = _app()

    assert _create(client, token="aaaa").status_code == 422


def test_an_unknown_target_kind_is_422_and_lists_the_options() -> None:
    client, _ = _app()

    response = _create(client, target_kind="cluster")

    assert response.status_code == 422
    assert response.json()["detail"]["allowed"] == ["deliverable", "graph", "topic"]


def test_the_password_is_never_echoed_back() -> None:
    """明文 NEVER 落库、NEVER 出现在返回值里；hash 也不回——它是校验材料。"""
    client, store = _app()

    response = _create(client, password="hunter2")

    assert "hunter2" not in response.text
    assert "password_hash" not in response.json()
    assert store.get(response.json()["token"]).password_hash is not None


def test_identity_is_required_to_create() -> None:
    client, _ = _app()

    assert client.post(
        "/shares", json={"target_kind": "topic", "target_id": "t-1"}
    ).status_code == 422


# ───────────────────────── 二、按 token 只读（acceptance①②）


def test_the_public_page_needs_no_identity() -> None:
    """外链就是给没账号的人看的——**NEVER 要求身份**。"""
    client, _ = _app()
    token = _token(client)

    response = client.get(f"{PUBLIC}/{token}")

    assert response.status_code == 200
    assert response.json()["content"] == {"title": "报告", "blocks": []}


def test_the_public_page_never_leaks_the_owner() -> None:
    client, _ = _app()
    token = _token(client)

    response = client.get(f"{PUBLIC}/{token}")

    assert ME not in response.text
    assert "created_by" not in response.json()
    assert "owner" not in response.text


def test_the_public_page_asks_only_for_the_shared_target() -> None:
    """NEVER 返回未分享的兄弟资源：内容源只被问了这一个 target。"""
    asked: list[tuple[str, str]] = []
    client, _ = _app(asked=asked)
    token = _token(client, target_id="d-1")

    client.get(f"{PUBLIC}/{token}")

    assert asked == [("deliverable", "d-1")]


def test_an_unknown_token_is_404() -> None:
    """真正需要藏的是「这个 token 存不存在」——那一种才用 404。"""
    client, _ = _app()

    assert client.get(f"{PUBLIC}/nope-nope-nope").status_code == 404


def test_a_shared_target_whose_content_is_gone_is_404() -> None:
    client, _ = _app()
    token = _token(client, target_id="d-missing")

    assert client.get(f"{PUBLIC}/{token}").status_code == 404


def test_a_password_protected_link_is_401_without_the_password() -> None:
    client, _ = _app()
    token = _token(client, password="hunter2")

    response = client.get(f"{PUBLIC}/{token}")

    assert response.status_code == 401


def test_the_password_travels_in_a_header_not_in_the_query_string() -> None:
    """查询串会进访问日志与 Referer，口令 NEVER 走那条路。"""
    client, _ = _app()
    token = _token(client, password="hunter2")

    assert client.get(f"{PUBLIC}/{token}?password=hunter2").status_code == 401
    assert client.get(
        f"{PUBLIC}/{token}", headers={"X-Share-Password": "hunter2"}
    ).status_code == 200


def test_the_public_handler_declares_no_query_parameter_at_all() -> None:
    """连**声明**一个查询串参数都不行（哪怕当下没用它）。

    变异⑯：加一个没接线的 `password: str | None = None` ——行为不变、判据全绿，
    可它已经出现在 OpenAPI 里了，下一个人照着填上就把口令送进了访问日志。
    所以判在签名上：这个处理函数的参数里，除了路径与 Request，
    **每一个都得是 `Header(...)`**。
    """
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    handler = next(
        n for n in ast.walk(tree)
        if isinstance(n, ast.AsyncFunctionDef) and n.name == "public_read")
    defaults = dict(zip(
        [a.arg for a in handler.args.args][-len(handler.args.defaults):],
        handler.args.defaults, strict=True)) if handler.args.defaults else {}

    for name, default in defaults.items():
        assert isinstance(default, ast.Call), f"{name} 是个查询串参数"
        assert isinstance(default.func, ast.Name) and default.func.id == "Header", \
            f"{name} 不是从头里来的"


def test_a_wrong_password_never_echoes_it_back() -> None:
    client, _ = _app()
    token = _token(client, password="hunter2")

    response = client.get(f"{PUBLIC}/{token}", headers={"X-Share-Password": "nope"})

    assert response.status_code == 401
    assert "nope" not in response.text


def test_an_expired_link_is_410_even_with_the_right_password() -> None:
    """判断顺序：先「还有效吗」再「你是谁」。反过来会把「已过期」泄露成「口令错」。"""
    client, store = _app()
    token = _token(client, password="hunter2",
                   expires_at=(NOW + timedelta(days=1)).isoformat())

    # 同一本库，晚两天再读（时钟经注入——靠真等两天是验不了的）。
    later, _ = _app(now=NOW + timedelta(days=2), store=store)
    response = later.get(f"{PUBLIC}/{token}", headers={"X-Share-Password": "hunter2"})

    assert response.status_code == 410


def test_a_write_on_the_token_path_is_403_not_405() -> None:
    """身份没问题、动作不允许——`verify_write_forbidden` 的原话。"""
    client, _ = _app()
    token = _token(client)

    for method in ("post", "put", "delete", "patch"):
        response = getattr(client, method)(f"{PUBLIC}/{token}")
        assert response.status_code == 403, method


def test_a_write_on_the_token_path_changes_nothing() -> None:
    client, store = _app()
    token = _token(client)

    client.delete(f"{PUBLIC}/{token}")

    assert store.get(token).revoked is False, "写请求 NEVER 有副作用"


# ───────────────────────── 三、撤销与列表（acceptance③④⑤）


def test_revoking_makes_the_link_410_not_404() -> None:
    """撤销后 410：告诉持链人「你没走错，它到期了」，而不是让他以为拿错了链接。"""
    client, _ = _app()
    token = _token(client)

    assert client.delete(
        f"/shares/{token}", headers={"X-User-Id": ME}).status_code == 204
    assert client.get(f"{PUBLIC}/{token}").status_code == 410


def test_revoking_never_deletes_the_row() -> None:
    """撤销不可逆，但记录要留着——删掉就再也说不清那条链接曾经存在过。"""
    client, store = _app()
    token = _token(client)

    client.delete(f"/shares/{token}", headers={"X-User-Id": ME})

    assert store.get(token) is not None
    assert store.get(token).revoked is True


def test_revoking_someone_elses_link_is_404_and_leaves_it_alone() -> None:
    client, store = _app()
    token = _token(client, user=OTHER)

    response = client.delete(f"/shares/{token}", headers={"X-User-Id": ME})

    assert response.status_code == 404
    assert store.get(token).revoked is False


def test_revoking_an_unknown_token_is_404_with_the_same_code() -> None:
    client, _ = _app()
    theirs = _token(client, user=OTHER)

    unknown = client.delete("/shares/nope", headers={"X-User-Id": ME})
    other = client.delete(f"/shares/{theirs}", headers={"X-User-Id": ME})

    assert unknown.status_code == other.status_code == 404
    assert unknown.json()["code"] == other.json()["code"] == "NOT_FOUND"


def test_my_share_list_is_empty_not_404() -> None:
    client, _ = _app()

    response = client.get("/shares", headers={"X-User-Id": ME})

    assert response.status_code == 200
    assert response.json()["items"] == []


def test_my_share_list_never_contains_another_owners_link() -> None:
    client, _ = _app()
    mine = _token(client, user=ME)
    _token(client, user=OTHER, target_id="d-2")

    items = client.get("/shares", headers={"X-User-Id": ME}).json()["items"]

    assert [i["token"] for i in items] == [mine]


def test_expiry_and_revocation_are_reported_separately() -> None:
    """冻结件原话：「过期可续期，撤销不可逆」——**NEVER 合并成一个 bool**。"""
    client, _ = _app()
    _token(client, expires_at=(NOW + timedelta(days=3)).isoformat())

    item = client.get("/shares", headers={"X-User-Id": ME}).json()["items"][0]

    assert item["revoked"] is False
    assert item["expires_at"] == (NOW + timedelta(days=3)).isoformat()


def test_a_link_without_an_expiry_says_so_instead_of_guessing_one() -> None:
    """`expires_at is None` = 不过期（冻结件语义）。NEVER 编一个到期日。"""
    client, _ = _app()
    _token(client)

    item = client.get("/shares", headers={"X-User-Id": ME}).json()["items"][0]

    assert item["expires_at"] is None


# ───────────────────────── 四、结构判据（acceptance②⑥）


def _identifiers() -> set[str]:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    return {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {
        n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)} | {
        a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names
    } | {(n.module or "") for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}


def test_the_module_writes_no_sql_of_its_own() -> None:
    """写-SQL 检测器。

    这里的动词判据带 **SQL 上下文**（`DELETE FROM` 而不是光一个 `DELETE`）：
    本模块的路由方法表里就有 `"DELETE"` 这个字符串，它是 HTTP 方法名，不是 SQL。
    光判动词会把它误判成写库——一把会误伤的尺子，用不了几天就没人再看它。
    """
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    docstrings = {ast.get_docstring(n) for n in ast.walk(tree)
                  if isinstance(n, ast.Module | ast.ClassDef | ast.FunctionDef
                                | ast.AsyncFunctionDef)}
    literals = " ".join(
        node.value for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
        and node.value not in docstrings
    )

    for pattern in (r"INSERT\s+INTO", r"DELETE\s+FROM", r"UPDATE\s+\w+\s+SET",
                    r"DROP\s+(TABLE|COLUMN)", r"ALTER\s+TABLE"):
        assert not re.search(pattern, literals, re.IGNORECASE), f"模块里有 {pattern}"

    # 更硬的一层：本模块**够不着数据库**。够不着就写不进去。
    assert not {"asyncpg", "sqlalchemy", "psycopg"} & _identifiers()


def test_the_gate_is_the_existing_one() -> None:
    """门禁转调既有 `resolve_share` / `verify_write_forbidden`，NEVER 再写一套状态码。"""
    identifiers = _identifiers()

    assert {"resolve_share", "verify_write_forbidden"} <= identifiers
    assert "compare_digest" not in identifiers, "口令比对归 links.py，这里不重写"


def test_the_public_response_shape_is_exactly_three_things() -> None:
    client, _ = _app()
    token = _token(client)

    body = client.get(f"{PUBLIC}/{token}").json()

    assert set(body) == {"target_kind", "target_id", "content"}
