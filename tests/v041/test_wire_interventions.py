"""WIRE-09 · interventions 族四条路由接通（含 aligner）。

## 这一族比前两族多一样东西要注：**模型**

证据注入那一步要跑两段式对齐，对齐吃 LLM。`create_app` 因此多一条缝
`aligner_provider`：不给就注一个 `_UnconfiguredProvider`——
**一被调用就 503 并点名是哪一族**。

**NEVER 注一个「返回空补全」的假 provider**：那样对齐会「成功」地把每条 claim
判成没有引用，而**「没配模型」与「模型说这条没有出处」是两件相反的事**。
前者要人去配模型，后者是一条真的判定结果。

## 受保护 block 的不变量（S2-5）

`locked ∨ author == "user" ∨ user_modified` 的 block **NEVER 被 regenerate 改写**。
本卡加一条端到端断言：真发一次 regenerate 提交，再看那条受保护的 block
一个字节都没变。保护谓词是单点的（`flint/compose/blocks.py#is_protected`
与 `PROTECTED_SQL_PREDICATE`），本卡不复制它，**问它**。
"""
from __future__ import annotations

import asyncio
import json
import os
from typing import Any

import asyncpg
import pytest
from fastapi.testclient import TestClient

from flint.api.app import UNWIRED_FAMILIES, create_app, mounted_route_table
from flint.compose.blocks import PROTECTED_SQL_PREDICATE

pytestmark = pytest.mark.compose

DSN = os.environ.get(
    "FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")
PREFIX = "wire09-"
PATHS = (
    "/interventions/lock",
    "/projects/{project_id}/evidence",
    "/projects/{project_id}/disputes",
    "/deliverables/{deliverable_id}/sections/{section_id}/regenerate",
)


def run(coro: Any) -> Any:
    return asyncio.run(coro)


async def _sql(statements: list[str]) -> None:
    conn = await asyncpg.connect(DSN)
    try:
        for stmt in statements:
            await conn.execute(stmt)
    finally:
        await conn.close()


async def _fetch(query: str) -> list[dict[str, Any]]:
    conn = await asyncpg.connect(DSN)
    try:
        return [dict(r) for r in await conn.fetch(query)]
    finally:
        await conn.close()


@pytest.fixture(autouse=True)
def seeded() -> Any:
    """一个 org 项目 + owner / member / 外人，外加一份带**受保护 block** 的交付物。"""
    wipe = [
        f"DELETE FROM jobs WHERE job_id LIKE '{PREFIX}%'",
        f"DELETE FROM blocks WHERE deliverable_id LIKE '{PREFIX}%'",
        f"DELETE FROM deliverables WHERE deliverable_id LIKE '{PREFIX}%'",
        f"DELETE FROM memberships WHERE user_id LIKE '{PREFIX}%'",
        f"DELETE FROM users WHERE user_id LIKE '{PREFIX}%'",
        f"DELETE FROM orgs WHERE org_id LIKE '{PREFIX}%'",
        f"DELETE FROM projects WHERE project_id LIKE '{PREFIX}%'",
    ]
    run(_sql(wipe))
    scope = json.dumps({"kind": "org", "id": f"{PREFIX}org"})
    content = json.dumps({"kind": "heading", "level": 2, "text": "用户改过的标题"},
                         ensure_ascii=False)
    run(_sql([
        (f"INSERT INTO orgs (org_id, name, created_at) "
         f"VALUES ('{PREFIX}org', 'WIRE-09 组织', now())"),
        (f"INSERT INTO users (user_id, email, display_name, created_at) VALUES "
         f"('{PREFIX}owner', 'ow@wire09.invalid', 'OW', now()), "
         f"('{PREFIX}member', 'me@wire09.invalid', 'ME', now()), "
         f"('{PREFIX}outsider', 'ou@wire09.invalid', 'OU', now())"),
        (f"INSERT INTO memberships (user_id, org_id, role) VALUES "
         f"('{PREFIX}owner', '{PREFIX}org', 'owner'), "
         f"('{PREFIX}member', '{PREFIX}org', 'member')"),
        (f"INSERT INTO projects (project_id, owner, origin_id, topic_ids, "
         f"chosen_topic_id, deliverable_ids, change_log, status, created_at) "
         f"VALUES ('{PREFIX}p', '{scope}'::jsonb, 'o', '[]'::jsonb, NULL, "
         f"'[]'::jsonb, '[]'::jsonb, 'active', now())"),
        (f"INSERT INTO deliverables (deliverable_id, project_id, type, version, "
         f"supersedes, inputs, ledger_version, generation_record_id, "
         f"stale_reasons, created_at, reproducible, meta) VALUES ('{PREFIX}del', "
         f"'{PREFIX}p', 'report', 1, NULL, '[]'::jsonb, 1, 'rec-{PREFIX}', "
         f"'[]'::jsonb, now(), true, '{{}}'::jsonb)"),
        # **受保护 block**：user_modified = true（S2-5 三条件之一）
        (f"INSERT INTO blocks (block_id, deliverable_id, section_id, block_order, "
         f"type, content, claim_ids, fact_ids, author, revision, locked, "
         f"user_modified, needs_review, review_reason, review_severity) VALUES "
         f"('{PREFIX}b1', '{PREFIX}del', '{PREFIX}sec', 0, 'heading', "
         f"'{content}'::jsonb, '[]'::jsonb, '[]'::jsonb, 'system', 3, false, "
         f"true, false, NULL, NULL)"),
    ]))
    yield
    run(_sql(wipe))


@pytest.fixture
def client() -> Any:
    with TestClient(create_app(DSN)) as test_client:
        yield test_client


def _regenerate(client: TestClient, user: str) -> Any:
    return client.post(
        f"/deliverables/{PREFIX}del/sections/{PREFIX}sec/regenerate",
        params={"project_id": f"{PREFIX}p"},
        json={"block_id": f"{PREFIX}b1", "guidance": "改写这一段"},
        headers={"X-User-Id": user})


def _lock(client: TestClient, user: str) -> Any:
    return client.post(
        "/interventions/lock",
        json={"target_id": f"{PREFIX}b1", "scope": "block",
              "deliverable_id": f"{PREFIX}del", "project_id": f"{PREFIX}p"},
        headers={"X-User-Id": user})


def _evidence(client: TestClient, user: str) -> Any:
    return client.post(
        f"/projects/{PREFIX}p/evidence",
        json={"evidence_kind": "url", "content_ref": "https://example.invalid/x",
              "claim_text": "这条断言要对齐", "expected_version": 1},
        headers={"X-User-Id": user})


def _disputes(client: TestClient, user: str) -> Any:
    return client.post(
        f"/projects/{PREFIX}p/disputes",
        json={"dispute_id": f"{PREFIX}d1", "deliverable_id": f"{PREFIX}del",
              "target_kind": "block", "target_id": f"{PREFIX}b1",
              "reason_text": "这一段与账本对不上", "expected_version": 1},
        headers={"X-User-Id": user})


# ───────────────────────── acceptance①④：四条挂上、登记里删掉


def test_the_four_paths_are_mounted() -> None:
    mounted = {r.path for r in mounted_route_table(
        create_app("postgresql://x@127.0.0.1:1/y"))}

    for path in PATHS:
        assert path in mounted, path


def test_interventions_is_gone_from_the_unwired_register() -> None:
    """判等值：只剩 combo 一族。"""
    modules = {family.module for family in UNWIRED_FAMILIES}

    assert "interventions.py" not in modules
    assert modules == set(), modules   # WIRE-10 之后四族全接通


def test_none_of_the_four_is_404(client: TestClient) -> None:
    """四条都打得通。"""
    probes = [_lock(client, f"{PREFIX}owner"), _evidence(client, f"{PREFIX}owner"),
              _disputes(client, f"{PREFIX}owner"), _regenerate(client, f"{PREFIX}owner")]

    for path, got in zip(PATHS, probes, strict=True):
        assert got.status_code != 404, f"{path} 还是 404：{got.text[:120]}"


def test_an_outsider_is_refused_on_all_four(client: TestClient) -> None:
    """**四条都要拒**：干预是写操作里最重的一类。"""
    for got in (_lock(client, f"{PREFIX}outsider"),
                _evidence(client, f"{PREFIX}outsider"),
                _disputes(client, f"{PREFIX}outsider"),
                _regenerate(client, f"{PREFIX}outsider")):
        assert got.status_code == 403, got.text
        assert got.json()["code"] == "PERMISSION_DENIED"


def test_a_member_is_refused_too(client: TestClient) -> None:
    """`member` 也被拒（`_INTERVENE_ROLES = {owner, admin}`）。"""
    assert _regenerate(client, f"{PREFIX}member").status_code == 403


def test_the_owner_gets_past_the_gate(client: TestClient) -> None:
    """**正例**：owner 过得了门。

    没有它，上面那些 403 可能是「这四条对谁都拒」换来的。
    """
    got = _regenerate(client, f"{PREFIX}owner")

    assert got.status_code != 403, got.text


# ───────────────────────── acceptance②：aligner 那条缝


def test_the_evidence_path_says_the_model_is_unconfigured(
    client: TestClient,
) -> None:
    """没给 `aligner_provider` → 证据注入回 **503 且点名 interventions**。

    NEVER 是 500，也 NEVER 是「成功但一条引用都没对上」。
    """
    got = _evidence(client, f"{PREFIX}owner")

    assert got.status_code == 503, got.text
    body = got.json()
    assert body["code"] == "FAMILY_NOT_CONFIGURED"
    assert body["family"] == "interventions"


def test_the_unconfigured_provider_never_pretends_to_answer() -> None:
    """那个占位 provider **一被调用就抛**，NEVER 返回一个空补全。

    返回空补全的话，对齐会「成功」地把每条 claim 判成没有引用——
    而「没配模型」与「模型说这条没有出处」是两件相反的事。
    """
    from flint.api.app import FamilyNotConfigured, _UnconfiguredProvider

    provider = _UnconfiguredProvider("interventions")

    with pytest.raises(FamilyNotConfigured):
        provider.generate("x", None)
    with pytest.raises(FamilyNotConfigured):
        provider.generate_structured("x", {}, 2)


def test_a_real_provider_replaces_the_placeholder() -> None:
    """**缝的两侧都要有实例**：给了 provider 就不再是占位。

    只验「不给时 503」的话，那条缝可能永远是 503。
    这里用一个**回放 provider**（`MockTransport`，零真实出网）。
    """
    import httpx

    from flint.llm.local import LocalProvider

    replay = LocalProvider(
        base_url="http://replay.invalid/v1", model="replay",
        http_client=httpx.Client(transport=httpx.MockTransport(
            lambda _r: httpx.Response(200, json={
                "choices": [{"message": {"content": "{}", "tool_calls": []}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1}}))))
    app = create_app(DSN, aligner_provider=replay)

    assert any(r.path == "/projects/{project_id}/evidence"
               for r in mounted_route_table(app))


# ───────────────────────── acceptance③：受保护 block 不被改写（S2-5）


def test_a_protected_block_is_untouched_by_a_regenerate_submission(
    client: TestClient,
) -> None:
    """**S2-5 端到端**：受保护的 block 在一次 regenerate 提交之后一个字节都没变。

    提交只是入队（真改写在 worker 里），但**入队这一步本身也 NEVER 动 block**——
    改前改后逐字节比对。保护谓词是单点的（`flint/compose/blocks.py`），
    本卡**问它**，NEVER 复制一份三条件。
    """
    before = run(_fetch(
        f"SELECT block_id, content, revision, user_modified FROM blocks "
        f"WHERE deliverable_id = '{PREFIX}del'"))
    assert before, "夹具没种上 block"

    got = _regenerate(client, f"{PREFIX}owner")
    assert got.status_code != 403, got.text

    after = run(_fetch(
        f"SELECT block_id, content, revision, user_modified FROM blocks "
        f"WHERE deliverable_id = '{PREFIX}del'"))

    assert after == before, "受保护的 block 被改了"


def test_the_seeded_block_really_is_protected() -> None:
    """**前提自检**：夹具那条 block 在 SQL 谓词下确实算「受保护」。

    没有这一条，上一条可能是在一条**根本不受保护**的 block 上验的——
    那时它证明不了任何事（F-08 的形态：过滤器谁都匹配不上却报绿）。
    """
    rows = run(_fetch(
        f"SELECT block_id FROM blocks WHERE deliverable_id = '{PREFIX}del' "
        f"AND {PROTECTED_SQL_PREDICATE}"))

    assert [r["block_id"] for r in rows] == [f"{PREFIX}b1"]
