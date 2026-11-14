"""BE-05 · 账户端点 `GET /account`（蓝本 R1「端点未建」）。

蓝本外壳 S0 的「用户位」现在写死 `X-User-Id: self`。本卡给它真数据：
**当前 principal 的身份、owner_scope、角色**。

三条判据线：

1. **不存在的东西 NEVER 编**——没有 users / orgs / memberships 三张表（本仓迁移里
   一张都没有），所以档案与组织**全部经注入**取；没注入就说没查过，
   NEVER 拿一个空列表冒充「你不属于任何组织」。
2. **NEVER 返回密钥或凭据**——判据钉在响应键名（递归白名单 + 凭据词正则）
   与模块源码（不许出现 environ / token / secret 这类标识符）两处。
3. **越权在结构上不可达**——本端点没有 id 入参，读到的恒是调用方自己。
   判据钉「路由无路径参数」+「返回的 principal 恒等于头」，
   而不是写一个永远走不到的 404 分支：写那个分支等于给它留一条日后能被接通的路。
"""
from __future__ import annotations

import ast
import re
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from flint.api.account import AccountApiDeps, create_account_app
from flint.domain.models import Membership, Role, User

MODULE = Path("flint/api/account.py")

ME = "u-me"
OTHER = "u-other"


def _user(user_id: str = ME) -> User:
    return User(
        user_id=user_id,
        email="me@example.com",
        display_name="我",
        created_at=datetime(2026, 1, 2, 3, 4, tzinfo=UTC),
    )


def _client(
    *,
    user: User | None = None,
    user_loader: bool = True,
    memberships: Sequence[Membership] | None = None,
    seen: list[str] | None = None,
) -> TestClient:
    async def load_user(uid: str) -> User | None:
        if seen is not None:
            seen.append(uid)
        return user

    async def load_memberships(uid: str) -> Sequence[Membership]:
        if seen is not None:
            seen.append(uid)
        return list(memberships or [])

    deps = AccountApiDeps(
        load_user=load_user if user_loader else None,
        load_memberships=load_memberships if memberships is not None else None,
    )
    return TestClient(create_account_app(deps))


def _body(**kwargs: Any) -> dict[str, Any]:
    response = _client(**kwargs).get("/account", headers={"X-User-Id": ME})
    assert response.status_code == 200, response.text
    out: dict[str, Any] = response.json()
    return out


# ───────────────────────── 一、身份就是调用方（acceptance①③）


def test_the_endpoint_exists() -> None:
    assert _client(user=_user()).get(
        "/account", headers={"X-User-Id": ME}).status_code == 200


def test_identity_is_required() -> None:
    assert _client(user=_user()).get("/account").status_code == 422


def test_the_principal_is_exactly_the_caller() -> None:
    """身份不是查出来的，是头给的。返回的 principal MUST 逐字等于头。"""
    body = _body(user=_user())

    assert body["principal"] == {"kind": "user", "id": ME}


def test_a_caller_with_no_record_is_not_404() -> None:
    """头给了一个库里没有的 id → 仍是 200。

    技术约束清单第 11 条：查询合法但无内容 → 空集合而非 404。
    这里更硬：身份本来就是头给的，**根本没有「未知 id」这回事**。
    """
    # 头值只能是 ascii（httpx 会在编码期就报错），所以这里用 ascii id。
    response = _client(user=None).get("/account", headers={"X-User-Id": "u-newcomer"})

    assert response.status_code == 200
    assert response.json()["principal"] == {"kind": "user", "id": "u-newcomer"}


def test_the_route_has_no_path_parameter() -> None:
    """越权在结构上不可达：没有 id 入参，就没有「取他人资源」这个动作。"""
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    routes = [
        d.args[0].value
        for node in ast.walk(tree)
        if isinstance(node, ast.AsyncFunctionDef | ast.FunctionDef)
        for d in node.decorator_list
        if isinstance(d, ast.Call) and d.args
        and isinstance(d.args[0], ast.Constant) and isinstance(d.args[0].value, str)
        and d.args[0].value.startswith("/")
    ]

    assert routes == ["/account"]
    assert "{" not in routes[0]


# ───────────────────────── 二、档案：三态分得开（acceptance④⑤）


def test_without_a_user_loader_the_profile_is_not_checked() -> None:
    """没注入档案源 → 说「没查」，NEVER 给一个空档案冒充「查过、是空的」。"""
    profile = _body(user_loader=False)["profile"]

    assert profile["status"] == "not_checked"
    assert "display_name" not in profile
    assert "email" not in profile


def test_a_missing_user_record_is_no_record_not_not_checked() -> None:
    """查过了、库里确实没有——与「没查」是两件事。"""
    profile = _body(user=None)["profile"]

    assert profile["status"] == "no_record"
    assert "display_name" not in profile


def test_a_known_user_reports_the_frozen_fields() -> None:
    profile = _body(user=_user())["profile"]

    assert profile == {
        "status": "known",
        "display_name": "我",
        "email": "me@example.com",
        "created_at": "2026-01-02T03:04:00+00:00",
    }


def test_no_display_name_is_invented() -> None:
    """NEVER 拿 id 拼一个显示名——那是假数据，前端会把它当真名显示。"""
    profile = _body(user=None)["profile"]

    assert ME not in str(profile)


# ───────────────────────── 三、owner_scope 与角色（acceptance①）


def test_the_direct_scope_is_always_there() -> None:
    """冻结件 Principal docstring：授权 = **归属直属**，或经 Membership.role 解析。
    第一条分支恒成立：个人使用无需先建 Org。
    """
    scopes = _body(user=_user())["scopes"]

    assert scopes["direct"] == {
        "principal": {"kind": "user", "id": ME}, "role": "owner", "via": "direct"}


def test_the_direct_scope_is_never_presented_as_a_membership() -> None:
    """个人 scope 不是一条 Membership 记录——把它塞进 memberships 就是造了一行库里没有的数据。"""
    memberships = _body(user=_user(), memberships=[])["scopes"]["memberships"]

    assert memberships["items"] == []


def test_without_a_membership_loader_the_orgs_are_not_checked() -> None:
    """没注入 → not_checked。空列表会被前端读成「你不属于任何组织」，那是一句没查过的断言。"""
    memberships = _body(user=_user())["scopes"]["memberships"]

    assert memberships["status"] == "not_checked"
    assert "items" not in memberships


def test_no_memberships_is_an_empty_list_not_404() -> None:
    memberships = _body(user=_user(), memberships=[])["scopes"]["memberships"]

    assert memberships == {"status": "checked", "items": []}


def test_an_org_membership_carries_the_role_from_the_record() -> None:
    body = _body(user=_user(), memberships=[
        Membership(user_id=ME, org_id="org-a", role="admin")])

    assert body["scopes"]["memberships"]["items"] == [
        {"principal": {"kind": "org", "id": "org-a"}, "role": "admin", "via": "membership"}
    ]


def test_every_role_passes_through_unchanged() -> None:
    """四个角色都照记录报，NEVER 折叠成两档。"""
    roles: list[Role] = ["owner", "admin", "member", "viewer"]
    body = _body(user=_user(), memberships=[
        Membership(user_id=ME, org_id=f"org-{r}", role=r) for r in roles])

    assert [i["role"] for i in body["scopes"]["memberships"]["items"]] == roles


# ───────────────────────── 四、NEVER 泄露他人与凭据（acceptance②）


def test_another_users_membership_is_dropped() -> None:
    """数据源投毒（按 org 查而不是按人查，会捞到同组织别人的行）→ 端点自己再滤一遍。

    多租户隔离 NEVER 只靠调用方查对了：这里是最后一道，也是唯一一道在本模块里的。
    """
    body = _body(user=_user(), memberships=[
        Membership(user_id=ME, org_id="org-a", role="viewer"),
        Membership(user_id=OTHER, org_id="org-a", role="owner"),
    ])

    items = body["scopes"]["memberships"]["items"]
    assert items == [
        {"principal": {"kind": "org", "id": "org-a"}, "role": "viewer", "via": "membership"}
    ]
    assert OTHER not in str(body)


def test_another_users_profile_is_dropped() -> None:
    """数据源拿回来的不是调用方的档案（键错了、按邮箱查串了行）→ 丢掉。

    变异考⑨ 逼出来的：改成「principal 用档案里的 id」时全绿——
    因为所有用例里档案的 id 恰好等于头。等于说这条隔离当时**根本没被判**。
    """
    body = _body(user=_user(OTHER))

    assert body["principal"] == {"kind": "user", "id": ME}
    assert body["profile"] == {"status": "no_record"}
    assert OTHER not in str(body)
    assert "me@example.com" not in str(body)


def test_the_loaders_are_asked_only_about_the_caller() -> None:
    seen: list[str] = []
    _body(user=_user(), memberships=[], seen=seen)

    assert set(seen) == {ME}


def test_no_credential_shaped_key_is_ever_returned() -> None:
    body = _body(user=_user(), memberships=[
        Membership(user_id=ME, org_id="org-a", role="admin")])

    def keys(node: Any) -> list[str]:
        if isinstance(node, dict):
            return [k for key, v in node.items() for k in [key, *keys(v)]]
        if isinstance(node, list):
            return [k for v in node for k in keys(v)]
        return []

    allowed = {
        "principal", "kind", "id", "profile", "status", "display_name", "email",
        "created_at", "scopes", "direct", "role", "via", "memberships", "items",
    }
    found = set(keys(body))
    assert found <= allowed, f"响应里多出来的键：{sorted(found - allowed)}"

    forbidden = re.compile(
        r"token|secret|password|passwd|credential|api_?key|authorization|cookie|dsn|session",
        re.IGNORECASE)
    assert not [k for k in found if forbidden.search(k)]


def test_the_module_imports_nothing_that_can_reach_a_secret() -> None:
    """凭据泄露的上游是「模块能拿到凭据」。拿不到就漏不出去。

    判在 import 白名单上而不是「有没有出现 environ 这个词」——
    变异考⑬ 证明后者拦不住 `import os`（词没出现，路已经通了）。
    """
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    imported = {n.names[0].name.split(".")[0] for n in ast.walk(tree)
                if isinstance(n, ast.Import)} | {
        (n.module or "").split(".")[0] for n in ast.walk(tree)
        if isinstance(n, ast.ImportFrom)}

    assert imported <= {"__future__", "collections", "dataclasses", "typing",
                        "fastapi", "flint"}, f"多出来的 import：{sorted(imported)}"


def test_the_module_never_reads_secrets() -> None:
    """白名单之内也 NEVER 出现凭据标识符（`flint.config` 那类是合法 import 的下游）。"""
    source = MODULE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {
        n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)} | {
        a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names
    } | {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}

    forbidden = re.compile(
        r"environ|getenv|token|secret|password|credential|api_?key|dsn|settings",
        re.IGNORECASE)
    assert not [n for n in names if forbidden.search(n)]


# ───────────────────────── 五、只读 + NEVER 造字段（acceptance③⑤）


def test_the_module_never_writes() -> None:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    docstrings = {ast.get_docstring(n) for n in ast.walk(tree)
                  if isinstance(n, ast.Module | ast.ClassDef | ast.FunctionDef
                                | ast.AsyncFunctionDef)}
    literals = " ".join(
        node.value for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
        and node.value not in docstrings
    )

    for verb in ("INSERT", "UPDATE", "DELETE", "DROP", "ALTER"):
        assert not re.search(rf"\b{verb}\b", literals, re.IGNORECASE), f"模块里有 {verb}"


def test_the_response_shape_is_exactly_three_things() -> None:
    """卡上写的三样：身份 / owner_scope / 角色。**NEVER 造第四样。**"""
    body = _body(user=_user(), memberships=[])

    assert set(body) == {"principal", "profile", "scopes"}
    assert set(body["scopes"]) == {"direct", "memberships"}


def test_no_plan_or_tier_is_synthesised() -> None:
    """账户屏最容易被顺手加上「套餐/等级/用量」——那三样这里一个都算不出来。

    额度与计费是 BE-06 的事，且它有自己的「未启用」如实态。
    """
    body = _body(user=_user(), memberships=[])

    assert not re.search(r"plan|tier|quota|balance|vip", str(body), re.IGNORECASE)
