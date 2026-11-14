"""AUTH-05 · demo 栈那只假手退役。

## 那只手

`harness/demo_server.py` 里三处 `lambda _u, _o: "owner"`——**谁问都答 owner**。
它被称作「demo 里明知故犯的口径」，而 `WIRE-01` 拒绝挂四族路由的理由正是
「这只手在可部署应用里是安全洞」。

**根因留着，口子就留着。** 所以这份判据不只看 demo：它扫**整棵产品树与 harness**，
任何形如「返回一个常量角色」的解析都判红。

## 判据判语法树，NEVER 判正文

`AUTH-02` 在这上面踩过一次：按行扫字符串时，模块 docstring 里
「它替掉的是 `lambda _u, _o: "owner"`」被判成了违规——**说明问题的那句话被当成犯下问题**。
所以这里走 `ast`：只看 `Lambda` 的 body 与 `Return` 的值是不是一个常量角色字符串。

## demo 的身份是**库里一行真的 users**

`seed_demo_identity()` 种一个用户、一个组织、一条 membership，幂等。
demo 里绝大多数资源是个人归属（`kind == "user"`），那条路根本不问角色；
这条 membership 是给 org 归属的资源准备的——没有它，
任何 org 归属的东西在 demo 上都会被真解析器**如实拒掉**（那是对的，但会让人以为坏了）。
"""
from __future__ import annotations

import ast
import asyncio
import os
from pathlib import Path
from typing import Any

import asyncpg
import pytest

from flint.api.app import create_app, mounted_route_table
from flint.authz import build_role_resolver

pytestmark = pytest.mark.compose

REPO = Path(__file__).resolve().parents[2]
DSN = os.environ.get(
    "FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")
ROLES = frozenset({"owner", "admin", "member", "viewer"})
# 扫描面：产品树 + harness。**tests/ 不在其中**——判据自己要造反例
# （`AUTH-04` 的 `_fake_hand` 就是一个），扫进去等于逼判据删掉自己的对照。
SCANNED = ("flint", "harness")
DEMO = REPO / "harness" / "demo_server.py"


def run(coro: Any) -> Any:
    return asyncio.run(coro)


async def _sql(statements: list[str]) -> None:
    conn = await asyncpg.connect(DSN)
    try:
        for stmt in statements:
            await conn.execute(stmt)
    finally:
        await conn.close()


def _code_of(path: Path) -> str:
    """只要**代码**，不要 docstring 与注释。

    走 `ast.unparse`：docstring 是 `Expr`，注释根本不进语法树。
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)) and (
                node.body and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
                and isinstance(node.body[0].value.value, str)):
            node.body = node.body[1:] or [ast.Pass()]
    return ast.unparse(tree)


def _constant_role_sites(path: Path) -> list[str]:
    """这个文件里「返回一个常量角色」的位置。判 `ast`，NEVER 判正文。"""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return [f"{path}: 语法坏了，扫不动——NEVER 当成没命中"]
    found: list[str] = []
    for node in ast.walk(tree):
        body: ast.expr | None = None
        if isinstance(node, ast.Lambda):
            body = node.body
        elif isinstance(node, ast.Return):
            body = node.value
        if isinstance(body, ast.Constant) and body.value in ROLES:
            where = (path.relative_to(REPO).as_posix()
                     if path.is_relative_to(REPO) else str(path))
            found.append(f"{where}:{node.lineno}")
    return found


# ───────────────────────── acceptance①③：假手退役，且全仓没有第二只


def test_the_demo_server_holds_no_constant_role_anymore() -> None:
    """`harness/demo_server.py` 里那三处没了。"""
    assert _constant_role_sites(DEMO) == []


def test_no_constant_role_resolution_survives_anywhere_in_the_product_tree() -> None:
    """**产品树与 harness 全域**：一处常量角色都不许有。

    这条是这次装不上四族的根因——留一个口子，下一次就从那里回来。
    """
    offenders: list[str] = []
    for root in SCANNED:
        for path in sorted((REPO / root).rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            offenders.extend(_constant_role_sites(path))

    assert offenders == [], f"这些地方仍把角色写成常量：{offenders}"


def test_the_scanner_would_catch_the_hand_if_it_came_back(tmp_path: Path) -> None:
    """**自证**：把那只手写进一个临时文件，扫描器认得出来。

    没有这一条，上面两条的绿可能是「扫描器谁都匹配不上」换来的（`F-08` 的形态）。
    """
    planted = tmp_path / "planted.py"
    planted.write_text(
        "def build():\n"
        "    return lambda _u, _o: \"owner\"\n", encoding="utf-8")

    assert _constant_role_sites(planted), "扫描器认不出那只手"


def test_the_demo_server_imports_the_real_resolver() -> None:
    """demo 不再自己造解析器——那三族由 `create_app` 装配（WIRE-07~09）。"""
    # `WIRE-07~09` 之后，要解析器的三族都由 `create_app` 自己装配，
    # demo 这一侧**不再造 runner、也不再传解析器**——
    # 所以这里判的是「它没有自己造一只手」，而不是「它传了真手」。
    #
    # **判 `ast`，NEVER 判正文**：第一版加了一条
    # `assert "lambda _u, _o:" not in text`，当场把 docstring 里
    # 「这里原本是 `lambda _u, _o: "owner"`」判成了违规——
    # **说明问题的那句话又一次被当成犯下问题**（本批第三次踩，
    # 前两次在 `AUTH-02` 与 `AUTH-05`）。
    assert _constant_role_sites(DEMO) == [], "demo 又造了一只常量手"
    assert "role_resolver=" not in _code_of(DEMO), (
        "demo 又自己传解析器了——那三族已由 create_app 装配"
    )


# ───────────────────────── acceptance②：demo 的身份是真行


def test_the_seed_puts_a_real_user_and_membership_in_the_database() -> None:
    """种子跑完之后，真解析器答得出 demo 用户的角色。

    **先清干净再种**：不清的话，上一轮留下的那一行会让「种子什么都不种」
    这个变异照样绿——本卡实测撞到过，那是判据在读别人留下的状态。

    这一条同时证明种子**幂等**：连跑两次不炸、答案不变。
    """
    from harness.demo_server import DEMO_ORG, DEMO_USER, seed_demo_identity

    run(_sql([
        f"DELETE FROM memberships WHERE user_id = '{DEMO_USER}'",
        f"DELETE FROM users WHERE user_id = '{DEMO_USER}'",
        f"DELETE FROM orgs WHERE org_id = '{DEMO_ORG}'",
    ]))
    resolve = build_role_resolver(DSN)
    assert resolve(DEMO_USER, DEMO_ORG) is None, "清场没清干净，后面的绿不算数"

    run(seed_demo_identity(DSN))
    run(seed_demo_identity(DSN))

    assert resolve(DEMO_USER, DEMO_ORG) == "owner"


def test_a_stranger_is_still_refused_on_the_demo_data() -> None:
    """**阴性对照**：种了 demo 身份，不等于谁来都通过。

    假手在的时候，这一条会绿着说「stranger 也是 owner」。
    """
    from harness.demo_server import DEMO_ORG, seed_demo_identity

    run(seed_demo_identity(DSN))
    resolve = build_role_resolver(DSN)

    assert resolve("auth05-stranger", DEMO_ORG) is None


# ───────────────────────── acceptance④：WIRE-02 的判据不倒


def test_the_demo_stack_still_covers_the_deployable_app() -> None:
    """demo 栈的路由面仍 ⊇ 可部署应用（`WIRE-02` 那条判据）。

    换掉解析器不该让任何一条路由掉下去——掉了就是装配被改坏了。
    """
    from harness.demo_server import build_app

    demo = {(m, r.path) for r in mounted_route_table(build_app()) for m in r.methods}
    deployable = {
        (m, r.path)
        for r in mounted_route_table(create_app("postgresql://x@127.0.0.1:1/y"))
        for m in r.methods
    }

    assert deployable - demo == set(), f"demo 少了这些：{sorted(deployable - demo)}"


def test_building_the_demo_app_touches_no_database() -> None:
    """**建应用期间一次库都不连**——种子是单独一步，NEVER 混进 `build_app()`。

    混进去的话，任何 import 了 demo 栈的测试都会写一次库。

    **真量一次**：把 `asyncpg.connect` 换成一个一调就炸的桩。
    第一版只断言「应用建起来了、路由够多」——那时把 `seed_demo_identity()`
    塞进 `build_app()` 里，判据照样绿（本卡实测）。
    """
    from unittest.mock import patch

    from harness.demo_server import build_app

    def _boom(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("build_app() 期间连了库——种子 MUST 是单独一步")

    with patch("asyncpg.connect", new=_boom):
        app = build_app()

    assert app.title == "flint-demo"
    assert len(app.router.routes) > 40


def test_the_entrypoint_seeds_before_serving() -> None:
    """`__main__` 里先种身份再起服务。

    顺序反了的话，第一个请求打进来时库里还没有那个用户——
    而那时的拒绝会被读成「鉴权坏了」。
    """
    text = DEMO.read_text(encoding="utf-8")
    tail = text[text.index('if __name__ == "__main__":'):]

    assert tail.index("seed_demo_identity") < tail.index("uvicorn.run")
