"""ASM-05：端到端冒烟——主链第一次真跑通（录制回放，机器可验）。

提交 → 入队 → 消费 → 组稿 → 渲染，五步一条链真跑一次。此前这条链断在中间：没有进程
消费组稿作业，默认生成器只产占位 heading，demo 报告页看到的是 fixture 播种的数据
（`harness/demo_seed_report.py`，`del-demo-fixture-` 前缀即其标记）。

零真实网络：LLM 走 `httpx.MockTransport` 录制回放；postgres/redis 是本机容器（工单 §4）。
`respx` 护栏包住整条链——除录制回放与 ASGI 传输外的任何 http 出网都会当场炸。
"""
from __future__ import annotations

import asyncio
import json
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import asyncpg
import httpx
import pytest
import respx

from flint.domain.models import Principal, UserProfile
from flint.llm.local import LocalProvider
from harness.e2e_smoke import (
    FIXTURE_PREFIX,
    STEP_ORDER,
    SmokeConfig,
    SmokeFailure,
    render_status,
    run_e2e_smoke,
)

REPO = Path(__file__).resolve().parents[2]
DSN = os.environ.get(
    "FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test"
)
REDIS_URL = os.environ.get("FLINT_TEST_REDIS", "redis://localhost:56379/0")
NOW = datetime(2026, 7, 26, 12, 0, 0, tzinfo=UTC)
PROSE = "本次真跑由录制回放 provider 产出的正文。"

pytestmark = pytest.mark.compose


def run(coro: Any) -> Any:
    return asyncio.run(coro)


def _provider(text: str = PROSE, *, boom: bool = False) -> LocalProvider:
    def respond(_req: httpx.Request) -> httpx.Response:
        if boom:
            raise RuntimeError("provider 炸了（用于验证失败定位）")
        return httpx.Response(200, json={
            "choices": [{"message": {
                "content": json.dumps(
                    {"blocks": [{"type": "paragraph", "text": text, "fact_ids": []}]},
                    ensure_ascii=False,
                ),
                "tool_calls": [],
            }}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
        })
    return LocalProvider(
        base_url="http://local/v1", model="qwen3.6:27b",
        http_client=httpx.Client(transport=httpx.MockTransport(respond)),
    )


def _profile() -> UserProfile:
    return UserProfile(
        profile_id="p-smoke", owner=Principal(kind="user", id="u-smoke"),
        identity={}, research={}, team=[], assets={}, constraints={},
        track_record=[], locale="zh-CN", sensitivity_overrides={}, updated_at=NOW,
    )


def _config(prefix: str, provider: LocalProvider | None = None) -> SmokeConfig:
    tag = uuid.uuid4().hex[:8]
    return SmokeConfig(
        dsn=DSN, redis_url=REDIS_URL, repo_root=REPO,
        provider=provider if provider is not None else _provider(),
        profile=_profile(), now=NOW,
        project_id=f"{prefix}p-{tag}", analysis_id=f"{prefix}src-{tag}",
        job_id=f"{prefix}{tag}", queue_name=f"arq:asm05-{tag}",
    )


async def _sql(statements: list[str]) -> None:
    conn = await asyncpg.connect(DSN)
    try:
        for stmt in statements:
            await conn.execute(stmt)
    finally:
        await conn.close()


def _wipe(prefix: str) -> None:
    run(_sql([
        f"DELETE FROM job_events WHERE job_id LIKE '{prefix}%'",
        f"DELETE FROM job_steps WHERE job_id LIKE '{prefix}%'",
        f"DELETE FROM jobs WHERE job_id LIKE '{prefix}%'",
        f"DELETE FROM snapshots WHERE snapshot_id LIKE 'snap-{prefix}%'",
        f"DELETE FROM blocks WHERE deliverable_id LIKE 'del-{prefix}%'",
        f"DELETE FROM generation_records WHERE record_id LIKE 'rec-{prefix}%'",
        f"DELETE FROM deliverables WHERE deliverable_id LIKE 'del-{prefix}%'",
        ("DELETE FROM facts WHERE ledger_id IN (SELECT ledger_id FROM "
         f"facts_ledgers WHERE project_id LIKE '{prefix}%')"),
        f"DELETE FROM facts_ledgers WHERE project_id LIKE '{prefix}%'",
        f"DELETE FROM claims WHERE claim_id LIKE '{prefix}%'",
    ]))


def _seed_claim(cfg: SmokeConfig, prefix: str) -> None:
    run(_sql([
        (f"INSERT INTO claims (claim_id, deliverable_id, block_id, text_span, "
         f"confidence, citation_ids, alignment, promoted_fact_id) VALUES "
         f"('{prefix}c1', '{cfg.analysis_id}', 'b-src', '市场规模 12 亿', 'cited', "
         f"'[\"cit-1\"]'::jsonb, 'supports', NULL) ON CONFLICT (claim_id) DO "
         f"UPDATE SET promoted_fact_id = NULL"),
    ]))


def _smoke(cfg: SmokeConfig) -> Any:
    """整条链包在 respx 护栏里：录制回放走 MockTransport、API 走 ASGI 传输，
    两者都不经默认 http 传输；任何真出网请求都会在这里当场炸。"""
    with respx.mock(assert_all_called=False):
        return run(run_e2e_smoke(cfg))


# ── acceptance ①：一条链路真跑 ──────────────────────────────────────────

def test_full_chain_runs_end_to_end() -> None:
    prefix = "asm05a-"
    _wipe(prefix)
    cfg = _config(prefix)
    _seed_claim(cfg, prefix)
    result = _smoke(cfg)

    assert result.step_names() == list(STEP_ORDER), (
        f"五步没跑齐：{result.step_names()}"
    )
    assert result.blocks, "/blocks 是空的"
    assert any(b["type"] == "paragraph" for b in result.blocks), (
        f"/blocks 里没有 paragraph（块型={[b['type'] for b in result.blocks]}）"
    )
    assert result.markdown.strip(), "/render 出了空 markdown"
    assert PROSE in result.markdown, "渲染出来的 markdown 里没有本次生成的正文"


# ── acceptance ②：数据不是 fixture 播种的 ───────────────────────────────

def test_smoke_data_is_not_fixture_seeded() -> None:
    prefix = "asm05b-"
    _wipe(prefix)
    cfg = _config(prefix)
    _seed_claim(cfg, prefix)
    result = _smoke(cfg)

    assert not result.deliverable_id.startswith(FIXTURE_PREFIX), (
        f"冒烟读到的是 fixture 播种的产物：{result.deliverable_id}"
    )
    assert result.deliverable_id == f"del-{result.job_id}", (
        "产物 id 与本次作业对不上"
    )
    for block in result.blocks:
        assert block["author"] == "system", f"块 author 不是本次生成：{block['author']}"
        assert block["revision"] == 1, f"块 revision 不是本次首版：{block['revision']}"
        assert result.job_id in block["block_id"], (
            f"块 id 不带本次 job_id：{block['block_id']}"
        )


def test_the_fixture_prefix_assertion_is_not_vacuous() -> None:
    """反例：fixture 播种用的正是这个前缀——证明上一条断言认得出它。"""
    seed = (REPO / "harness" / "demo_seed_report.py").read_text(encoding="utf-8")
    assert f'DELIVERABLE_ID = "{FIXTURE_PREFIX}' in seed


# ── acceptance ③：导出闸门两种用例都要有 ────────────────────────────────

def _set_review(deliverable_id: str, block_id: str, *, blocking: bool) -> None:
    if blocking:
        run(_sql([
            ("UPDATE blocks SET needs_review = true, review_severity = 'blocking', "
             "review_reason = 'fact_removed' WHERE deliverable_id = "
             f"'{deliverable_id}' AND block_id = '{block_id}'"),
        ]))
    else:
        run(_sql([
            ("UPDATE blocks SET needs_review = false, review_severity = NULL, "
             f"review_reason = NULL WHERE deliverable_id = '{deliverable_id}'"),
        ]))


def test_export_gate_blocks_and_names_the_blocking_blocks() -> None:
    prefix = "asm05c-"
    _wipe(prefix)
    cfg = _config(prefix)
    _seed_claim(cfg, prefix)
    result = _smoke(cfg)

    target = result.blocks[0]["block_id"]
    _set_review(result.deliverable_id, target, blocking=True)
    status, body = render_status(cfg, result.deliverable_id)
    assert status == 409, f"门禁没拦下（返回 {status}：{body}）"
    assert body["code"] == "EXPORT_BLOCKED"
    assert target in body["detail"]["blocking_block_ids"], (
        f"409 没点名被拦的块：{body['detail']}"
    )


def test_export_gate_lets_a_clean_deliverable_through() -> None:
    prefix = "asm05d-"
    _wipe(prefix)
    cfg = _config(prefix)
    _seed_claim(cfg, prefix)
    result = _smoke(cfg)

    _set_review(result.deliverable_id, result.blocks[0]["block_id"], blocking=False)
    status, body = render_status(cfg, result.deliverable_id)
    assert status == 200, f"干净产物被拦了（返回 {status}：{body}）"
    assert PROSE in str(body["text"])


# ── acceptance ⑤：失败时报出断在哪一步 ─────────────────────────────────

def test_failure_names_the_step_it_broke_at() -> None:
    prefix = "asm05e-"
    _wipe(prefix)
    cfg = _config(prefix, provider=_provider(boom=True))
    _seed_claim(cfg, prefix)
    with pytest.raises(SmokeFailure) as err:
        _smoke(cfg)
    assert err.value.step == "consume", f"断点定位错了：{err.value.step}"
    message = str(err.value)
    assert "consume" in message and "断在" in message, message
    assert err.value.detail, "只报了一句断言失败，没说清断在哪"


def test_every_step_has_a_named_failure_path() -> None:
    """五步都必须能单独报名字——否则「断在哪一步」这条验收是空的。

    AST 面收 `raise SmokeFailure("<step>", ...)` 的首参常量，不做文本匹配：文本匹配
    会被换行排版骗过（改个缩进就假绿）。
    """
    import ast

    source = (REPO / "harness" / "e2e_smoke.py").read_text(encoding="utf-8")
    named: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Raise) or not isinstance(node.exc, ast.Call):
            continue
        callee = node.exc.func
        if isinstance(callee, ast.Name) and callee.id == "SmokeFailure":
            first = node.exc.args[0] if node.exc.args else None
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                named.add(first.value)
    missing = [s for s in STEP_ORDER if s not in named]
    assert missing == [], f"这些步没有具名失败路径：{missing}"
