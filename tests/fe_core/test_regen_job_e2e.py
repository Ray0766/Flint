"""FE-CORE-005 端到端（录制回放，CI 离线）。

owner 单一授权真机跑 @2026-07-30（qwen3.6:27b，免费档）已产 assets/prod_caliber/
fe_core_regen_qwen36.json（真实 qwen3.6 块级指令重生成产出）。本测**回放**该录制产出
（M1-008：ReplayProvider 顶替真模型），跑 run_regenerate_job 全链（本地 PG），断言端到端：
① 版本 +1；② 目标块变；③ 未选中兄弟块（含未保护）字节不变；④ 保护块字节不变；
⑤ 真实产出只引账本内 fact（铁律：NEVER 编造）。CI 零联网零付费（S2-7）。
"""
from __future__ import annotations

import asyncio
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import asyncpg
import pytest

from flint.compose.blocks import PgBlockStore
from flint.compose.deliverable import PgDeliverableStore
from flint.domain.models import (
    JSON,
    Block,
    Completion,
    Deliverable,
    GenerationRecord,
    HeadingContent,
    ParagraphContent,
    Principal,
    TextSpan,
    UserProfile,
)
from flint.jobs.regenerate_job import RegenerateJobDeps, run_regenerate_job
from flint.llm.prompts import load_prompt

pytestmark = pytest.mark.compose

DSN = os.environ.get("FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")
REPO = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 7, 26, 12, 0, 0, tzinfo=UTC)
PID = "fecore-e2e-p"
DID = "fecore-e2e-d1"


class ReplayProvider:
    """回放真机 qwen3.6 录制产出（M1-008），顶替真模型——离线、无网。"""

    model = "qwen3.6:27b"

    def __init__(self, output: JSON) -> None:
        self.output = output

    def generate(self, prompt: str, tools: list[JSON] | None) -> Completion:
        raise NotImplementedError

    def generate_structured(self, prompt: str, schema: JSON, max_retries: int) -> JSON:
        return self.output


def run(coro: Any) -> Any:
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def _clean(request: pytest.FixtureRequest) -> Any:
    """测试隔离：清 fecore-e2e-* 行（含重生成派生 deliverable）——块级重生成保留
    block_id，跨版本重名，若不清会污染共享 DB（如 test_m2_001 迁移往返对块 PK 敏感）。"""
    # NARROW-03: tests/v041/test_regen_events.py borrows this fixture, and its static
    # tests run in CI's unit stage with no database. Every test here is compose anyway.
    if request.node.get_closest_marker("compose") is None:
        yield
        return
    async def wipe() -> None:
        conn = await asyncpg.connect(DSN)
        try:
            for tbl, col in [("blocks", "deliverable_id"),
                             ("deliverables", "deliverable_id"),
                             ("generation_records", "deliverable_id")]:
                await conn.execute(f"DELETE FROM {tbl} WHERE {col} LIKE 'fecore-e2e-%'")
            await conn.execute("DELETE FROM facts WHERE ledger_id LIKE 'fecore-e2e-%'")
            await conn.execute("DELETE FROM facts_ledgers WHERE project_id LIKE 'fecore-e2e-%'")
        finally:
            await conn.close()
    run(wipe())
    yield
    run(wipe())


def _blk(bid: str, order: int, content: Any, *, locked: bool = False) -> Block:
    return Block(block_id=bid, deliverable_id=DID, section_id="summary", order=order,
                 type=content.kind, content=content, claim_ids=[], fact_ids=[],
                 author="system", revision=1, locked=locked)


def _seed_tree() -> list[Block]:
    return [
        _blk("b1", 0, HeadingContent(kind="heading", level=2, text="项目摘要")),
        _blk("b2", 1, ParagraphContent(kind="paragraph",
             spans=[TextSpan(kind="text", text="啰嗦的旧摘要，全是空话套话。")])),
        _blk("b3", 2, ParagraphContent(kind="paragraph",
             spans=[TextSpan(kind="text", text="锁定段落一字不动。")]), locked=True),
        _blk("b4", 3, ParagraphContent(kind="paragraph",
             spans=[TextSpan(kind="text", text="未选中兄弟段落不该改。")])),
    ]


async def _seed() -> list[Block]:
    conn = await asyncpg.connect(DSN)
    try:
        for tbl, col in [("blocks", "deliverable_id"), ("deliverables", "deliverable_id"),
                         ("generation_records", "deliverable_id")]:
            await conn.execute(f"DELETE FROM {tbl} WHERE {col} LIKE 'fecore-e2e-%'")
        await conn.execute("DELETE FROM facts WHERE ledger_id = 'fecore-e2e-led'")
        await conn.execute("DELETE FROM facts_ledgers WHERE project_id = $1", PID)
        await conn.execute(
            "INSERT INTO facts_ledgers (ledger_id, project_id, version, parent_version, "
            "derivation_reason, created_from, created_at, actor) "
            "VALUES ('fecore-e2e-led', $1, 1, NULL, 'initial', '[]'::jsonb, $2, 'u')",
            PID, NOW)
        await conn.execute(
            "INSERT INTO facts (ledger_id, fact_id, statement, value, unit, citation_ids, "
            "status, origin, created_in_version, source_claim_id, promoted_from) VALUES "
            "('fecore-e2e-led', 'fact-mkt-1', '数据标注市场年增速约三成', NULL, NULL, "
            "'[]'::jsonb, 'frozen', 'injected', 1, NULL, NULL)")
    finally:
        await conn.close()
    ds = PgDeliverableStore(dsn=DSN)
    await ds.save_generation_record(GenerationRecord(
        record_id="fecore-e2e-rec", deliverable_id=DID, job_id="seed",
        prompt_version="seed@1", model="seed", params={}, retrieval_snapshot_id="none",
        ledger_version=1, pricebook_version=None, user_evidence_verdict_optin=False,
        ts=NOW, cost=0.0))
    await ds.save_deliverable(Deliverable(
        deliverable_id=DID, project_id=PID, type="report", version=1, supersedes=None,
        inputs=[], ledger_version=1, generation_record_id="fecore-e2e-rec",
        stale_reasons=[], created_at=NOW))
    tree = _seed_tree()
    await PgBlockStore(dsn=DSN).save_tree(DID, tree)
    return tree


def _recorded_output() -> JSON:
    fx = json.loads(
        (REPO / "assets" / "prod_caliber" / "fe_core_regen_qwen36.json").read_text(encoding="utf-8")
    )
    return fx["records"][0]["output"]


def test_regenerate_job_e2e_replay_real_qwen36() -> None:
    original = run(_seed())
    provider = ReplayProvider(_recorded_output())
    deps = RegenerateJobDeps(
        dsn=DSN, provider=provider,  # type: ignore[arg-type]
        prompt_text=load_prompt(REPO / "prompts", "section_draft@1").text,
        profile=UserProfile(profile_id="p", owner=Principal(kind="user", id="u"),
                            identity={}, research={}, team=[], assets={}, constraints={},
                            track_record=[], locale="zh-CN", sensitivity_overrides={},
                            updated_at=NOW),
        template_path=REPO / "assets" / "templates" / "generic.yaml", now=lambda: NOW)
    payload = {"action": "regenerate_block", "deliverable_id": DID,
               "section_id": "summary", "project_id": PID, "block_id": "b2",
               "guidance": "更简洁、只用有据事实"}

    new_did = run(run_regenerate_job("e2e-replay", payload, deps))

    new_tree = run(PgBlockStore(dsn=DSN).load_tree(new_did))
    newdel = run(PgDeliverableStore(dsn=DSN).load_deliverable(new_did))
    by_new = {b.block_id: b for b in new_tree}
    by_old = {b.block_id: b for b in original}
    assert newdel.version == 2                                    # ① 版本 +1
    assert by_new["b2"].content != by_old["b2"].content           # ② 目标块变
    assert by_new["b4"].content == by_old["b4"].content           # ③ 未选中兄弟(未保护)不变
    assert by_new["b3"].content == by_old["b3"].content           # ④ 保护块不变
    assert by_new["b1"].content == by_old["b1"].content           # 标题不变
    # ⑤ 铁律：真实产出只引账本内 fact（fact-mkt-1 在账本），无编造
    for fid in by_new["b2"].fact_ids:
        assert fid == "fact-mkt-1"
