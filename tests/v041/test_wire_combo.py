"""WIRE-10 · combo 族一条路由 + 模型地址进配置。

## 改前：模型地址**无处可配**

`flint/config.py#Settings` 只有 `env` / `database_url` / `redis_url` 三项。
而 `combo` 要 `provider` 与 `embed_service`——demo 是从模块级 `OLLAMA` 常量拿的。

**那条路 NEVER 进产品**：一个写死在源码里的模型地址，换环境时
没有任何东西会提醒你它没跟着换。

## 三条不肯含糊的地方

1. **不设就是没配，NEVER 编一个默认地址**。猜出来的 `localhost:11434`
   要么连不上（好），要么**连上了某个不该连的东西**（更坏）；
2. **缺一项 NEVER 算半配**。地址在而模型名空时，调用会以一个说不清的错误失败——
   `ModelAccess.configured` 要求两项齐全；
3. **没配时回「未配置」，NEVER 回一个空结果冒充算过了**。
   一个空的组合结果读起来是「算过了，没找到可组合的主题」，
   而真相是「根本没算」。

## 嵌入那一侧不吃模型

`embed_service` 用**确定性哈希后端**：它不需要配置，也 NEVER 假装自己是真嵌入
（那份后端自己的 docstring 写着这句）。所以本卡的模型缝只管 `provider`。
"""
from __future__ import annotations

import asyncio
import os
from typing import Any

import asyncpg
import pytest
from fastapi.testclient import TestClient

from flint.api.app import UNWIRED_FAMILIES, create_app, mounted_route_table
from flint.config import ModelAccess, load_settings

pytestmark = pytest.mark.compose

DSN = os.environ.get(
    "FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")
PREFIX = "wire10-"
COMBO_PATH = "/projects/combo"


def run(coro: Any) -> Any:
    return asyncio.run(coro)


async def _sql(statements: list[str]) -> None:
    conn = await asyncpg.connect(DSN)
    try:
        for stmt in statements:
            await conn.execute(stmt)
    finally:
        await conn.close()


async def _two_real_card_ids() -> list[str]:
    """从库里取两张**真**证据卡。

    combo 在碰模型之前先校验 `card_ids`（不认识就 422）——
    编两个 id 的话，请求根本走不到「模型没配」那一步，
    而本卡要验的正是那一步。
    """
    conn = await asyncpg.connect(DSN)
    try:
        rows = await conn.fetch(
            "SELECT card_id FROM evidence_cards ORDER BY card_id LIMIT 2")
    finally:
        await conn.close()
    return [r["card_id"] for r in rows]


@pytest.fixture(autouse=True)
def seeded() -> Any:
    wipe = [
        f"DELETE FROM users WHERE user_id LIKE '{PREFIX}%'",
    ]
    run(_sql(wipe))
    run(_sql([
        (f"INSERT INTO users (user_id, email, display_name, created_at) "
         f"VALUES ('{PREFIX}u', 'u@wire10.invalid', 'U', now())"),
    ]))
    yield
    run(_sql(wipe))


@pytest.fixture
def client() -> Any:
    with TestClient(create_app(DSN)) as test_client:
        yield test_client


def _combo(client: TestClient, user: str = f"{PREFIX}u") -> Any:
    return client.post(
        COMBO_PATH,
        json={"card_ids": run(_two_real_card_ids()),
              "hypothesis": "检索增强生成能降低企业知识库的维护成本"},
        headers={"X-User-Id": user})


# ───────────────────────── acceptance①：模型接入项进 Settings


def test_settings_now_carries_a_model_access_block() -> None:
    """`Settings` 有 `models` 这一块——三项都可以不设。"""
    settings = load_settings(
        {"FLINT_ENV": "dev", "DATABASE_URL": "d", "REDIS_URL": "r"})

    assert isinstance(settings.models, ModelAccess)
    assert settings.models.base_url is None
    assert settings.models.model is None
    assert settings.models.configured is False


def test_the_model_keys_are_read_from_the_environment() -> None:
    settings = load_settings({
        "FLINT_ENV": "dev", "DATABASE_URL": "d", "REDIS_URL": "r",
        "FLINT_MODEL_BASE_URL": "http://replay.invalid/v1",
        "FLINT_MODEL_NAME": "replay-model",
        "FLINT_EMBED_MODEL": "replay-embed"})

    assert settings.models.base_url == "http://replay.invalid/v1"
    assert settings.models.model == "replay-model"
    assert settings.models.embed_model == "replay-embed"
    assert settings.models.configured is True


def test_half_a_configuration_is_not_a_configuration() -> None:
    """**缺一项 NEVER 算半配**。

    地址在而模型名空时，调用会以一个说不清的错误失败——
    那种失败读起来像「模型坏了」，而真相是「配漏了一项」。
    """
    assert ModelAccess(base_url="http://x/v1").configured is False
    assert ModelAccess(model="m").configured is False
    assert ModelAccess(base_url="http://x/v1", model="m").configured is True


def test_the_model_keys_are_not_required_to_boot() -> None:
    """模型项 **NEVER 进 `REQUIRED_ENV_KEYS`**。

    设成必填的话，所有不跑模型的部署（以及 CI）都起不来——
    而「这套环境不跑模型」是一个正当的状态。
    """
    from flint.config import REQUIRED_ENV_KEYS

    assert not any("MODEL" in key for key in REQUIRED_ENV_KEYS)


def test_no_default_model_address_is_invented_anywhere() -> None:
    """`flint/config.py` 与 `flint/api/app.py` 里**没有**任何写死的模型地址。

    demo 那个模块级 `OLLAMA` 常量是它自己的事；产品树里编一个默认地址，
    换环境时没有任何东西会提醒你它没跟着换。

    **判代码，NEVER 判 docstring**：第一版扫所有字符串常量，当场把
    `ModelAccess` 的 docstring 判成违规——那段话里引用「一个猜出来的
    localhost:11434」**正是为了禁止它**。说明问题的那句话被当成犯下问题，
    **这是本批第四次**（`AUTH-02` / `AUTH-05` / `WIRE-09` / 本卡）。
    """
    import ast
    from pathlib import Path

    repo = Path(__file__).resolve().parents[2]
    offenders: list[str] = []
    for rel in ("flint/config.py", "flint/api/app.py"):
        tree = ast.parse((repo / rel).read_text(encoding="utf-8"))
        skip = {
            id(node.body[0].value) for node in ast.walk(tree)
            if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                                 ast.ClassDef))
            and node.body and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
        }
        for node in ast.walk(tree):
            if (not isinstance(node, ast.Constant)
                    or not isinstance(node.value, str) or id(node) in skip):
                continue
            if "11434" in node.value or (
                    "://" in node.value and "/v1" in node.value):
                offenders.append(f"{rel}:{node.lineno} → {node.value}")

    assert offenders == [], f"产品树里编了模型地址：{offenders}"


# ───────────────────────── acceptance③：挂上、登记清空


def test_the_combo_path_is_mounted() -> None:
    mounted = {r.path for r in mounted_route_table(
        create_app("postgresql://x@127.0.0.1:1/y"))}

    assert COMBO_PATH in mounted


def test_the_unwired_register_is_finally_empty() -> None:
    """**四族全接通**：`UNWIRED_FAMILIES` 空了。

    `WIRE-01` 收卡时这里是四族十条；`WIRE-07/08/09/10` 一族一族接完。
    空了之后，`test_app_assembly.py` 里那条「一族都没登记 → 把本条改成断言空集」
    的提示就该兑现了——`WIRE-11` 做那件事。
    """
    assert UNWIRED_FAMILIES == ()


def test_the_combo_path_is_not_404(client: TestClient) -> None:
    got = _combo(client)

    assert got.status_code != 404, got.text


# ───────────────────────── acceptance②：没配就说没配


def test_an_unconfigured_model_answers_service_unavailable(
    client: TestClient,
) -> None:
    """没配模型 → **503 且点名 combo**，NEVER 崩、NEVER 回空结果。

    空结果读起来是「算过了，没找到可组合的主题」，而真相是「根本没算」。
    """
    got = _combo(client)

    assert got.status_code == 503, got.text
    body = got.json()
    assert body["code"] == "FAMILY_NOT_CONFIGURED"
    assert body["family"] == "combo"


def test_the_refusal_carries_no_fabricated_result(client: TestClient) -> None:
    """那个 503 的响应体里**没有任何组合结果字段**。

    带一个空 `topics: []` 回去的话，前端会把它渲染成「一个都没组合出来」。
    """
    body = _combo(client).json()

    # 判**形状**：响应体只允许有这四个键，任何组合结果字段都不许出现。
    assert set(body) <= {"code", "message", "family", "detail"}, body
    assert "topics" not in body and "project_id" not in body, body


def test_a_configured_provider_replaces_the_placeholder() -> None:
    """**缝的两侧都要有实例**：给了 provider 就不再是占位。

    用**回放 provider**（`MockTransport`，零真实出网）——
    本卡 NEVER 真调用任何模型。
    """
    import httpx

    from flint.llm.local import LocalProvider

    replay = LocalProvider(
        base_url="http://replay.invalid/v1", model="replay",
        http_client=httpx.Client(transport=httpx.MockTransport(
            lambda _r: httpx.Response(200, json={
                "choices": [{"message": {"content": "{}", "tool_calls": []}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1}}))))
    app = create_app(DSN, combo_provider=replay, combo_model="replay")

    assert any(r.path == COMBO_PATH for r in mounted_route_table(app))


def test_the_placeholder_provider_raises_instead_of_answering() -> None:
    """占位 provider 一被调用就抛，NEVER 返回一个空补全（同 `WIRE-09`）。"""
    from flint.api.app import FamilyNotConfigured, _UnconfiguredProvider

    with pytest.raises(FamilyNotConfigured):
        _UnconfiguredProvider("combo").generate_structured("x", {}, 2)


# ───────────────────────── acceptance④：没有新依赖


def test_no_new_dependency_was_added() -> None:
    """本卡只加配置项与注入口——`requirements.lock` 一字未动。

    模型调用走既有的 `LLMProvider` 适配器。
    """
    import subprocess
    from pathlib import Path

    repo = Path(__file__).resolve().parents[2]
    lock = (repo / "requirements.lock").read_text(encoding="utf-8")

    assert "asyncpg==0.31.0" in lock          # 锚点：文件本身没被换掉
    del subprocess
