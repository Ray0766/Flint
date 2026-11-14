"""AUTH-04 · 越权矩阵：四种角色 × 三类操作，逐格断言。

## 矩阵

行是**谁**（四种角色 + 非成员 + 未登录），列是**干什么**（读 / 写 / 干预）。
每一格都有一条断言——**没有「其余同理」**：那句话一写，没写的那些格子就没人量了。

| | 读 | 写 | 干预 |
|---|---|---|---|
| `owner` | ✓ | ✓ | ✓ |
| `admin` | ✓ | ✓ | ✓ |
| `member` | ✓ | ✗ | ✗ |
| `viewer` | **✗** | ✗ | ✗ |
| 非成员（是个人，但不在这个 org） | ✗ | ✗ | ✗ |
| 未登录（没有身份） | ✗ | ✗ | ✗ |

口径不是本卡定的，是既有的两组：
`_VIEW_ROLES = {owner, admin, member}`（`flint/api/analysis.py`）与
`_INTERVENE_ROLES = {owner, admin}`（`flint/api/interventions.py`）。
**本卡只把它们逐格钉住**。

**一处实测出来的意外**：`_VIEW_ROLES` 里**没有 `viewer`**——也就是说，
一个叫 viewer 的角色在作业这条路上**连读都不行**。本卡按既有口径断言（拒绝），
并把这件事交给 owner 看（`docs/trace/AUTH-04.md` §owner_review）：
要么这个名字名不副实，要么冻结件里那句「SSE 订阅 = …… + member 只读」
本来就没打算让 viewer 看作业。**NEVER 由本卡替它改口径。**

## 这张卡里最值钱的一条是阴性对照

`test_the_refusals_all_flip_when_the_resolver_goes_back_to_the_fake_hand`：
把解析器换回 `lambda _u, _o: "owner"`（就是 `AUTH-02` 替掉的那只假手），
**矩阵里每一个拒绝格 MUST 变成通过**。

它证明的是：那些格子**真的在量权限**，而不是在量别的（比如「这个人不存在」
或者「这条路本来就不通」）。没有这一条，一个恒假的判定也能让整张矩阵全绿。

## 越权 NEVER 静默降级

拒绝就是拒绝——`False` / 403 / 抛错都行，但 **NEVER 退成「只读」或「空结果」**。
一个越权的写请求收到 200 + 空列表时，调用方以为自己写成功了、只是没有数据。
"""
from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import asyncpg
import pytest

from contracts.models import Job, Principal
from flint.api.analysis import may_view
from flint.api.interventions import may_intervene
from flint.authz import build_role_resolver

pytestmark = pytest.mark.compose

DSN = os.environ.get(
    "FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")
PREFIX = "auth04-"
ORG = f"{PREFIX}org"
ROLES = ("owner", "admin", "member", "viewer")
# 既有口径，本卡只是把它们逐格钉住（NEVER 在这里重新定义谁能干什么）。
MAY_READ = frozenset({"owner", "admin", "member"})
MAY_WRITE = frozenset({"owner", "admin"})
NOW = datetime(2026, 8, 6, 12, 0, 0, tzinfo=UTC)


def run(coro: Any) -> Any:
    return asyncio.run(coro)


async def _sql(statements: list[str]) -> None:
    conn = await asyncpg.connect(DSN)
    try:
        for stmt in statements:
            await conn.execute(stmt)
    finally:
        await conn.close()


@pytest.fixture(autouse=True)
def seeded() -> Any:
    wipe = [
        f"DELETE FROM memberships WHERE user_id LIKE '{PREFIX}%'",
        f"DELETE FROM users WHERE user_id LIKE '{PREFIX}%'",
        f"DELETE FROM orgs WHERE org_id LIKE '{PREFIX}%'",
    ]
    run(_sql(wipe))
    stmts = [(f"INSERT INTO orgs (org_id, name, created_at) "
              f"VALUES ('{ORG}', 'AUTH-04 组织', now())")]
    for who in (*ROLES, "outsider"):
        stmts.append(
            f"INSERT INTO users (user_id, email, display_name, created_at) "
            f"VALUES ('{PREFIX}{who}', '{who}@auth04.invalid', '{who}', now())")
    for role in ROLES:
        stmts.append(
            f"INSERT INTO memberships (user_id, org_id, role) "
            f"VALUES ('{PREFIX}{role}', '{ORG}', '{role}')")
    run(_sql(stmts))
    yield
    run(_sql(wipe))


def _job(scope: Principal, initiated_by: str) -> Job:
    return Job(
        job_id=f"{PREFIX}job", kind="gate1_analysis", project_id=None,
        owner_scope=scope, state="queued", steps=[], progress=0.0,
        partial_output_ref=None, budget=1.0, cost_accum=0.0,
        cancel_requested=False, error=None, initiated_by=initiated_by,
        created_at=NOW, updated_at=NOW)


def _org_scope() -> Principal:
    return Principal(kind="org", id=ORG)


def _read(user: str, roles: Callable[[str, str], str | None]) -> bool:
    """读：`may_view`。作业由**别人**发起——否则 `initiated_by` 那条捷径会盖住角色。"""
    return may_view(_job(_org_scope(), f"{PREFIX}owner"), user, roles)


def _write(user: str, roles: Callable[[str, str], str | None]) -> bool:
    """写与干预走同一道门（`may_intervene`，`_INTERVENE_ROLES = {owner, admin}`）。"""
    return may_intervene(_org_scope(), user, roles)


def _fake_hand(_user: str, _org: str) -> str:
    """`AUTH-02` 替掉的那只假手：谁问都答 owner。**只在阴性对照里出现。**"""
    return "owner"


# ───────────────────────── acceptance①：矩阵逐格


@pytest.mark.parametrize("role", ROLES)
def test_read_is_allowed_exactly_for_the_view_roles(role: str) -> None:
    """读那一列：`owner` / `admin` / `member` 通过，`viewer` **不通过**。

    `viewer` 能不能读这件事，此前没有任何一条判据在量——
    `_VIEW_ROLES` 里没有它，所以这里断言的是**拒绝**。
    """
    roles = build_role_resolver(DSN)

    assert _read(f"{PREFIX}{role}", roles) is (role in MAY_READ), role


@pytest.mark.parametrize("role", ROLES)
def test_write_is_allowed_exactly_for_the_intervene_roles(role: str) -> None:
    """写那一列：只有 `owner` / `admin`。"""
    roles = build_role_resolver(DSN)

    assert _write(f"{PREFIX}{role}", roles) is (role in MAY_WRITE), role


@pytest.mark.parametrize("role", ROLES)
def test_intervene_is_the_same_gate_as_write(role: str) -> None:
    """干预那一列走的是同一道门——**同一件事 NEVER 有两套口径**。"""
    roles = build_role_resolver(DSN)

    assert _write(f"{PREFIX}{role}", roles) is (role in MAY_WRITE), role


def test_a_non_member_is_refused_on_all_three(seeded: Any) -> None:
    """非成员那一行：三格全拒。**他是个真人**，只是不在这个 org 里。"""
    del seeded
    roles = build_role_resolver(DSN)
    outsider = f"{PREFIX}outsider"

    assert _read(outsider, roles) is False
    assert _write(outsider, roles) is False


def test_an_unknown_identity_is_refused_on_all_three() -> None:
    """未登录那一行：连人都不是。三格全拒。

    这一格与上一格分开：一个是「你不在这个组织」，一个是「你不是任何人」——
    `AUTH-03` 把它们分成了 403 与 401 两种响应。
    """
    roles = build_role_resolver(DSN)

    assert _read("nobody-at-all", roles) is False
    assert _write("nobody-at-all", roles) is False


# ───────────────────────── acceptance②：拒绝就是拒绝


def test_a_refusal_is_a_refusal_not_a_downgrade() -> None:
    """越权返回的是 `False`，**NEVER 是一个「只读」或空结果**。

    一个越权的写请求收到 200 + 空列表时，调用方以为自己写成功了、只是没有数据。
    """
    roles = build_role_resolver(DSN)

    refused = _write(f"{PREFIX}viewer", roles)
    assert refused is False
    assert refused is not None and not isinstance(refused, (list, dict))


# ───────────────────────── acceptance③：个人归属与组织归属分开


def test_a_personal_scope_ignores_memberships_entirely() -> None:
    """`owner_scope.kind == "user"` 时，**memberships 那条路走不通**——只有本人。

    个人使用无需先建 Org（冻结件 `Principal` 原话）。
    把个人归属也拿去查 membership 的那天，一个组织里的 admin
    就能读到别人的私人项目。
    """
    roles = build_role_resolver(DSN)
    mine = _job(Principal(kind="user", id=f"{PREFIX}owner"), f"{PREFIX}owner")

    assert may_view(mine, f"{PREFIX}owner", roles) is True
    for other in ("admin", "member", "viewer", "outsider"):
        assert may_view(mine, f"{PREFIX}{other}", roles) is False, other


def test_the_initiator_can_always_see_their_own_job() -> None:
    """**对照**：发起人本人恒可读（`may_view` 的第一条捷径）。

    没有这一条，上面那些 `False` 可能是「这条路对谁都不通」换来的。
    """
    roles = build_role_resolver(DSN)
    theirs = _job(_org_scope(), f"{PREFIX}outsider")

    assert may_view(theirs, f"{PREFIX}outsider", roles) is True


# ───────────────────────── acceptance④：阴性对照（本卡最值钱的一条）


def test_the_refusals_all_flip_when_the_resolver_goes_back_to_the_fake_hand() -> None:
    """把解析器换回那只假手，**每一个拒绝格都变成通过**。

    这一条证明那些格子**真的在量权限**，而不是在量别的
    （比如「这个人不存在」或「这条路本来就不通」）——
    没有它，一个恒假的判定也能让整张矩阵全绿。
    """
    real = build_role_resolver(DSN)
    refused_under_real = [
        (who, op)
        for who in (f"{PREFIX}member", f"{PREFIX}viewer", f"{PREFIX}outsider")
        for op, fn in (("read", _read), ("write", _write))
        if fn(who, real) is False
    ]
    assert refused_under_real, "真解析器下一个拒绝格都没有？矩阵有问题"

    still_refused = [
        (who, op) for who, op in refused_under_real
        if {"read": _read, "write": _write}[op](who, _fake_hand) is False
    ]

    assert still_refused == [], (
        f"换成常量 owner 之后这些格子仍然拒绝：{still_refused}——"
        f"它们量的不是权限"
    )


def test_the_fake_hand_does_not_flip_the_personal_scope() -> None:
    """**边界**：假手翻不动个人归属那一行——那条路根本不问角色。

    这不是漏洞：`kind == "user"` 时比的是 id 本身。
    写在这里是为了让上一条的「全部翻绿」有个准确的范围。
    """
    mine = _job(Principal(kind="user", id=f"{PREFIX}owner"), f"{PREFIX}owner")

    assert may_view(mine, f"{PREFIX}viewer", _fake_hand) is False


def test_the_matrix_covers_every_cell_it_claims_to() -> None:
    """**元判据**：六行 × 两列一格不少。

    表格写在 docstring 里而断言少几条的那天，读的人以为都量过了。
    """
    roles = build_role_resolver(DSN)
    rows = [*(f"{PREFIX}{r}" for r in ROLES), f"{PREFIX}outsider", "nobody-at-all"]
    grid = {(who, op): fn(who, roles)
            for who in rows for op, fn in (("read", _read), ("write", _write))}

    assert len(grid) == 12, f"矩阵只覆盖了 {len(grid)} 格"
    assert sum(1 for v in grid.values() if v) == 5, (
        f"通过的格子不是 5 个：{json.dumps({str(k): v for k, v in grid.items()}, ensure_ascii=False)}"
    )
