"""生产 Gate①→真实源切换：真实 github/arxiv 检索接进 run_gate1（离线回放，S2-7 零联网）。

证：build_live_deps 注入真实 GithubArxivSearcher（回放录制的真实 arxiv/github 响应）→ run_gate1
四步跑通 → 检索到**真实 arxiv 论文**（arxiv.org，非 `.example` 占位）→ support_claim 引真 doc_id。
契约不改（Gate1Deps 字段照冻结）；判官用 ScriptedGateProvider（确定、零 LLM 网）隔离出"真实检索"。
"""
from __future__ import annotations

import pytest

from harness.gate1_live import replay, replay_qwen

pytestmark = pytest.mark.compose


def test_live_gate1_retrieves_real_docs_offline() -> None:
    result = replay()                                    # 回放录制搜索，零联网
    assert result["steps"] == ["plan", "retrieve", "judge", "validate"]
    docs = result["retrieved_docs"]
    assert docs, "应检索到真实文档"
    # 真实源（非 .example 占位）：arxiv 真论文
    assert all(".example" not in d["url"] for d in docs)
    assert any("arxiv.org" in d["url"] and d["source_id"] == "arxiv" for d in docs)


def test_verdict_cites_real_doc() -> None:
    result = replay()
    claims = result["support_claims"]
    assert claims, "应有支持向 claim 引真 doc"
    cited = {c["doc_id"] for c in claims}
    real_doc_ids = {d["url"] for d in result["retrieved_docs"]}
    assert real_doc_ids, "检索到真实 doc"
    # 被引 doc_id 是内容寻址于真实 url 的真 doc（非 doc-vendor-*/doc-<hash> 占位）
    assert all(not c.startswith("doc-vendor-") for c in cited)


def test_live_qwen_gate1_produces_grounded_verdict_offline() -> None:
    # payoff：真实 qwen 判官 + 真实 github/arxiv（LLM+搜索双录制回放，零联网）
    result = replay_qwen()
    assert result["steps"] == ["plan", "retrieve", "judge", "validate"]
    docs = result["retrieved_docs"]
    # qwen 查询扩展 → 检索到多篇真实 arxiv 论文（远厚于 scripted 的 2 篇）
    assert len(docs) >= 5
    assert all(".example" not in d["url"] for d in docs)
    assert any("arxiv.org" in d["url"] for d in docs)
    assert result["support_claims"], "qwen 判官产出支持向 claim 引真 doc"
    # Step 1：verdict 的引用钉了真论文的短 quote_span（§3.5：短段、非全文）
    pinned = result["pinned_citations"]
    assert pinned, "被引真论文应钉 quote_span"
    for p in pinned:
        assert "arxiv.org" in p["doc_url"]
        assert p["quote_span"] and len(p["quote_span"]) <= 281   # 短段封顶
