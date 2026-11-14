"""生产 Gate① → 真实源切换（Feature B）：把真实 github/arxiv 检索接进 run_gate1。

两条路，都用 `build_live_deps`（注入真实 provider+searcher，run_gate1 内核不变、契约不改）：
- **scripted 路（CI 可回放，零 LLM 网）**：`ScriptedGateProvider`（判官确定、产真英文检索词）+
  真实 `GithubArxivSearcher`。只有搜索走网 → 录制回放（M1-008，S2-7）。证"真实源检索流进 Gate①、
  verdict 引真 doc（非 .example 占位）"。
- **live 路（payoff）**：免费本地 qwen3.6:35b-a3b（LocalProvider）+ 真实 github/arxiv。owner 令的
  端到端真实主题跑。

门 2=R1：仅 github/arxiv（GithubArxivSearcher 只搜这两家）。§3.5：Doc 只元信息、过 check_provenance。
NEVER 切生产默认（main 保 offline）——default→live = owner 一行决策。
"""
from __future__ import annotations

import asyncio
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import asyncpg
import httpx

from flint.domain.models import JSON, Completion
from flint.evidence.search import GithubArxivSearcher
from flint.jobs.gate1 import build_live_deps, run_gate1
from flint.testing.replay import RecordedExchange, load_fixture, save_fixture

REPO = Path(__file__).resolve().parents[1]
FX = REPO / "fixtures" / "gate1_live"
ASSET = REPO / "assets" / "gate1_live"

# 本模块**会写库**（_wipe 删 jobs/job_steps/job_events/snapshots，run_gate1 再写回），
# 而它有两个身份：
#   · 被 tests/m2/test_featb_gate1_live.py 导入 → 必须写**测试库**，否则每跑一次
#     pytest 就把 demo 的 job/snapshot 清一遍（这正是要根治的那个坑）；
#   · 被人手动 `python -m harness.gate1_live replay-qwen` 跑 → 目的就是往 **demo 库**
#     恢复 Gate① 判定样本，那时才该连 demo。
# 于是：模块默认 = 测试库（导入路径安全兜底），CLI 在 __main__ 里显式切 demo 库。
# 判断错的代价不对称——默认连测试库，最坏是测试库被自己的用例覆写；反过来会毁 demo。
TEST_DSN = os.environ.get(
    "FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")
DEMO_DSN = os.environ.get(
    "FLINT_DEMO_DSN", "postgresql://flint:flint@localhost:55432/flint")
DSN = TEST_DSN
NOW = datetime(2026, 7, 26, 12, 0, 0, tzinfo=UTC)
KEYWORD = "检索增强生成"
ENGLISH = "retrieval augmented generation"
LOCALE = "en"


class ScriptedGateProvider:
    """判官确定 + 产真英文检索词（零 LLM 网，CI 可回放）。真实检索仍走 github/arxiv。"""

    def generate(self, prompt: str, tools: list[JSON] | None) -> Completion:
        raise RuntimeError("offline: free-form generation disabled")

    def generate_structured(self, prompt: str, schema: JSON, max_retries: int) -> JSON:
        if "转成英文学术检索术语" in prompt:
            return {"english": ENGLISH}
        if "broader（上位）" in prompt:
            return {"synonyms": [], "broader": [], "narrower": []}
        if "判定检索相关性" in prompt:
            return {"relevant": True}
        if "判定引用对齐" in prompt:
            return {"alignment": "supports"}
        if "抽取竞品记录" in prompt:
            return {"competitors": []}
        raise RuntimeError(f"scripted: unhandled prompt: {prompt[:40]}")


class _RecordingTransport(httpx.BaseTransport):
    def __init__(self, inner: httpx.BaseTransport, sink: list[RecordedExchange]) -> None:
        self._inner = inner
        self._sink = sink

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        resp = self._inner.handle_request(request)
        body = resp.read()
        ctype = resp.headers.get("content-type", "")
        self._sink.append(RecordedExchange(
            method=request.method, url=str(request.url), status_code=resp.status_code,
            content_type=ctype, body_text=body.decode("utf-8")))
        headers = {"content-type": ctype} if ctype else None
        return httpx.Response(resp.status_code, headers=headers, content=body)


def _replay_client(exchanges: list[RecordedExchange]) -> httpx.Client:
    by_url = {ex.url: ex for ex in exchanges}

    def handler(request: httpx.Request) -> httpx.Response:
        ex = by_url[str(request.url)]
        return httpx.Response(ex.status_code, content=ex.body_text.encode("utf-8"),
                              headers={"content-type": ex.content_type})

    return httpx.Client(transport=httpx.MockTransport(handler))


async def _wipe(job_id: str) -> None:
    conn = await asyncpg.connect(DSN)
    try:
        await conn.execute("DELETE FROM job_steps WHERE job_id=$1", job_id)
        await conn.execute("DELETE FROM job_events WHERE job_id=$1", job_id)
        await conn.execute(
            "DELETE FROM snapshots WHERE snapshot_id LIKE $1", f"snap-{job_id}-%")
        await conn.execute("DELETE FROM jobs WHERE job_id=$1", job_id)
    finally:
        await conn.close()


async def _snapshot(job_id: str, suffix: str) -> JSON:
    conn = await asyncpg.connect(DSN)
    try:
        payload: bytes | None = await conn.fetchval(
            "SELECT payload FROM snapshots WHERE snapshot_id=$1", f"snap-{job_id}-{suffix}")
    finally:
        await conn.close()
    return {} if payload is None else cast("JSON", json.loads(payload.decode("utf-8")))


async def _pin_citations(job_id: str, search_client: httpx.Client) -> list[dict[str, Any]]:
    """Step 1：给 verdict 的被引 doc 钉 quote_span（复用生产 pin_verdict_citations，回放 client）。"""
    from flint.evidence.enrich import pin_verdict_citations

    pairs = await pin_verdict_citations(DSN, job_id, NOW, http_client=search_client)
    return [{"doc_url": d.url, "quote_span": c.quote_span} for d, c in pairs]


async def _run(job_id: str, search_client: httpx.Client) -> dict[str, Any]:
    await _wipe(job_id)
    searcher = GithubArxivSearcher(search_client, NOW, per_source=2, resilient=True)
    deps = build_live_deps(DSN, REPO, ScriptedGateProvider(), searcher, NOW)
    report = await run_gate1(job_id, [KEYWORD], LOCALE, deps)
    docs = cast("list[JSON]", await _snapshot(job_id, "docs"))
    judge = await _snapshot(job_id, "judge")
    pinned = await _pin_citations(job_id, search_client)
    return {
        "steps": report.steps_run,
        "retrieved_docs": [
            {"source_id": d["source_id"], "kind": d["kind"], "url": d["url"]}
            for d in docs
        ],
        "support_claims": judge.get("support_claims", []),
        "pinned_citations": pinned,
        "verdict": await _snapshot(job_id, "verdict"),
    }


def record() -> dict[str, Any]:
    sink: list[RecordedExchange] = []
    client = httpx.Client(
        transport=_RecordingTransport(httpx.HTTPTransport(), sink),
        timeout=30.0, follow_redirects=True)
    out = asyncio.run(_run("job-gate1-live-scripted", client))
    save_fixture(FX / "scripted" / "search.json", sink)
    ASSET.mkdir(parents=True, exist_ok=True)
    (ASSET / "scripted.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def replay() -> dict[str, Any]:
    exchanges = load_fixture(FX / "scripted" / "search.json")
    return asyncio.run(_run("job-gate1-live-scripted", _replay_client(exchanges)))


# ── live 路（payoff）：真实 qwen 判官 + 真实 github/arxiv 检索 ─────────────

QWEN = "qwen3.6:35b-a3b"
QJOB = "job-gate1-live-qwen"


async def _run_qwen(
    llm_client: httpx.Client, search_client: httpx.Client
) -> dict[str, Any]:
    from flint.llm.local import LocalProvider
    await _wipe(QJOB)
    provider = LocalProvider(
        base_url="http://localhost:11434/v1", model=QWEN,
        http_client=llm_client, disable_reasoning=True, max_tokens=4096)
    searcher = GithubArxivSearcher(search_client, NOW, per_source=2, resilient=True)
    deps = build_live_deps(DSN, REPO, provider, searcher, NOW)
    report = await run_gate1(QJOB, [KEYWORD], LOCALE, deps)
    docs = cast("list[JSON]", await _snapshot(QJOB, "docs"))
    judge = await _snapshot(QJOB, "judge")
    pinned = await _pin_citations(QJOB, search_client)
    return {
        "steps": report.steps_run,
        "retrieved_docs": [
            {"source_id": d["source_id"], "kind": d["kind"], "url": d["url"]}
            for d in docs
        ],
        "support_claims": judge.get("support_claims", []),
        "pinned_citations": pinned,
    }


def record_qwen() -> dict[str, Any]:
    from harness.topic_caliber import _RecordingTransport
    llm_sink: list[RecordedExchange] = []
    search_sink: list[RecordedExchange] = []
    llm = httpx.Client(
        transport=_RecordingTransport(httpx.HTTPTransport(), llm_sink), timeout=600.0)
    search = httpx.Client(
        transport=_RecordingTransport(httpx.HTTPTransport(), search_sink),
        timeout=30.0, follow_redirects=True)
    out = asyncio.run(_run_qwen(llm, search))
    save_fixture(FX / "qwen" / "llm.json", llm_sink)
    save_fixture(FX / "qwen" / "search.json", search_sink)
    ASSET.mkdir(parents=True, exist_ok=True)
    (ASSET / "qwen.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def replay_qwen() -> dict[str, Any]:
    from harness.topic_caliber import _OrderedReplayTransport
    llm_ex = load_fixture(FX / "qwen" / "llm.json")
    search_ex = load_fixture(FX / "qwen" / "search.json")
    llm = httpx.Client(transport=_OrderedReplayTransport(llm_ex))
    return asyncio.run(_run_qwen(llm, _replay_client(search_ex)))


if __name__ == "__main__":
    import sys
    # CLI 路径 = 人手动往 demo 库恢复判定样本。显式切库并打出来，NEVER 让人猜写进了哪个库。
    DSN = DEMO_DSN
    print(f"[gate1_live] 写入库：{DSN}")
    mode = sys.argv[1] if len(sys.argv) > 1 else "record"
    dispatch = {"record": record, "replay": replay,
                "record-qwen": record_qwen, "replay-qwen": replay_qwen}
    result = dispatch[mode]()
    print("steps:", result["steps"])
    print("retrieved real docs:", len(result["retrieved_docs"]))
    for d in result["retrieved_docs"]:
        print("  ", d["source_id"], d["kind"], d["url"])
    print("support_claims (real cited docs):",
          [c["doc_id"] for c in result["support_claims"]])
    print("pinned quote_spans:")
    for p in result.get("pinned_citations", []):
        print(f"   {p['doc_url']} — “{p['quote_span'][:70]}”")
