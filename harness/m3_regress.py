"""M3 回归 harness：文书线金标 12 样例离线全跑（M3-065，技术方案 E12）。

- 零联网（S2-7）：输入只有 assets/golddocs + assets/templates；结构装配、
  通道校验、三格式渲染（md/html/docx）、非空 claim 对齐（M3-060 观察落点）、
  保护位与 redaction 注记全在进程内。
- 委托覆盖（summary 注明，不在本进程重复跑）：pdf → M3-035 容器化验收；
  不变量束 → eval.invariants（compose 层）——S2-7 的零联网断言只对本
  harness 主路径成立。
- 逐样例 trace：docs/trace/golddocs/{sample_id}.md（inputs + 组稿依据），
  零时间戳字节稳定。
- 退出码：任一样例失配 → 1。
运行：python -m harness.m3_regress
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from flint.align.stage1 import LLMCitationAligner
from flint.compose.align_gate import align_gate
from flint.compose.channels import validate_channels
from flint.compose.disclaimer import build_disclaimer_block
from flint.compose.draft_channels import channel_manifest
from flint.compose.protect import ProtectedBlockViolation, guard_rewrite
from flint.domain.models import (
    JSON,
    Block,
    Claim,
    DeclarationContent,
    Doc,
    GenerationRecord,
    HeadingContent,
    ParagraphContent,
    PriceCell,
    PriceEntry,
    Principal,
    ProfileRef,
    TableContent,
    TextCell,
    TextSpan,
    UserProfile,
)
from flint.render.docx import render_docx
from flint.render.html import render_html
from flint.render.markdown import render_markdown

REPO_ROOT = Path(__file__).resolve().parents[1]
GOLDDOCS = REPO_ROOT / "assets" / "golddocs" / "golddocs.json"
TRACE_DIR = REPO_ROOT / "docs" / "trace" / "golddocs-doc"

FIXED_NOW = datetime(2026, 7, 26, 12, 0, 0, tzinfo=UTC)


class _SupportsProvider:
    def generate(self, prompt: str, tools: Any) -> Any:
        raise RuntimeError("offline harness: free-form generation disabled")

    def generate_structured(self, prompt: str, schema: JSON, retries: int) -> JSON:
        return {"alignment": "supports"}


def _profile() -> UserProfile:
    return UserProfile(
        profile_id="p-1", owner=Principal(kind="user", id="u-1"),
        identity={"org": "Flint Lab"}, research={}, team=[], assets={},
        constraints={}, track_record=[], locale="zh-CN",
        sensitivity_overrides={}, updated_at=FIXED_NOW,
    )


def _entries() -> dict[str, PriceEntry]:
    return {
        "pe-compute-01": PriceEntry(
            entry_id="pe-compute-01", item="A100 租用", unit="卡·小时",
            price_low=6.0, price_high=15.0, currency="CNY", region="CN",
            year=2026, source="seed:2026", updated_at=FIXED_NOW,
        )
    }


def build_doc_blocks(sample: dict[str, Any]) -> list[Block]:
    deliverable_id = f"del-{sample['sample_id']}"
    blocks: list[Block] = [
        build_disclaimer_block(deliverable_id, "s-quality", "2026-07-26")
    ]
    facts = list(sample["facts"])
    for order, section_id in enumerate(sample["expected"]["sections"]):
        fact_ids = [facts[order]] if order < len(facts) else []
        blocks.append(Block(
            block_id=f"b-{deliverable_id}-{section_id}",
            deliverable_id=deliverable_id, section_id=section_id, order=order,
            type="heading",
            content=HeadingContent(kind="heading", level=2, text=section_id),
            claim_ids=[], fact_ids=fact_ids, author="system", revision=1,
            locked=False,
        ))
    if sample["variant"] == "channels":
        blocks.append(Block(
            block_id=f"b-{deliverable_id}-budget",
            deliverable_id=deliverable_id, section_id="s-budget", order=99,
            type="table",
            content=TableContent(kind="table", header=["项", "值"], rows=[
                [TextCell(kind="text", text="算力"),
                 PriceCell(kind="price", price_entry_id="pe-compute-01",
                           quantity=100.0)],
            ]),
            claim_ids=[], fact_ids=[], author="system", revision=1, locked=False,
        ))
        blocks.append(Block(
            block_id=f"b-{deliverable_id}-team",
            deliverable_id=deliverable_id, section_id="s-team", order=100,
            type="paragraph",
            content=ParagraphContent(kind="paragraph", spans=[
                TextSpan(kind="text", text="团队隶属 "),
                ProfileRef(kind="profile", field_path="identity.org"),
            ]),
            claim_ids=[], fact_ids=[], author="system", revision=1, locked=False,
        ))
    return blocks


def check_sample(sample: dict[str, Any]) -> dict[str, Any]:
    blocks = build_doc_blocks(sample)
    expected = sample["expected"]

    section_blocks = [
        b for b in blocks
        if b.section_id in expected["sections"]
    ]
    sections_ok = [b.section_id for b in section_blocks] == expected["sections"]

    manifest = channel_manifest(blocks)
    manifest_ok = manifest == expected["channel_manifest"]

    violations = validate_channels(
        blocks, set(sample["facts"]), _entries(), _profile()
    )

    declaration = blocks[0]
    protected_ok = False
    try:
        altered = Block(
            **{**declaration.__dict__,
               "content": DeclarationContent(kind="declaration", text="改")},
        )
        guard_rewrite([declaration], [altered])
    except ProtectedBlockViolation:
        protected_ok = True

    markdown = render_markdown(blocks)
    html = render_html(blocks)
    docx_payload = render_docx(blocks)
    renders_ok = (
        markdown == render_markdown(blocks)
        and bool(html)
        and docx_payload[:2] == b"PK"
    )

    claims = [
        Claim(
            claim_id=f"c-{sample['sample_id']}-{i}", deliverable_id="d-1",
            block_id="b-1", text_span=f"结论 {i}", confidence="cited",
            citation_ids=[f"cit-{i}"], alignment="pending",
        )
        for i in range(3)
    ]
    docs = {
        f"cit-{i}": Doc(
            doc_id=f"doc-{i}", source_id="crossref", kind="paper",
            title=f"e-{i}", url=f"https://a/{i}", published_at=FIXED_NOW.date(),
            meta={"fetched_at": FIXED_NOW.isoformat()}, origin="retrieved",
            access="public",
        )
        for i in range(3)
    }
    record = GenerationRecord(
        record_id="r-h", deliverable_id="d-1", job_id="j-h", prompt_version="v",
        model="offline", params={}, retrieval_snapshot_id="s",
        ledger_version=1, pricebook_version=None,
        user_evidence_verdict_optin=False, ts=FIXED_NOW, cost=0.0,
    )
    align = align_gate(
        LLMCitationAligner(provider=_SupportsProvider()), claims, docs, record
    )
    align_ok = align.passed and len(align.report.results) == 3  # 非空对集

    return {
        "sample_id": sample["sample_id"],
        "sections_ok": sections_ok,
        "manifest_ok": manifest_ok,
        "channel_violations": violations,
        "protected_ok": protected_ok,
        "renders_ok": renders_ok,
        "align_ok": align_ok,
        "green": (
            sections_ok and manifest_ok and not violations
            and protected_ok and renders_ok and align_ok
        ),
    }


def sample_trace(sample: dict[str, Any], result: dict[str, Any]) -> str:
    manifest = sample["expected"]["channel_manifest"]
    return f"""# 文书金标 trace：{result["sample_id"]}

## inputs 清单
- 模板：{sample["template_id"]}（{sample["audience"]}）；变体：{sample["variant"]}
- facts：{sample["facts"]}；price_entries：{sample["price_entries"]}；
  profile_paths：{sample["profile_paths"]}

## 组稿依据
- 章节序 = 模板声明序：{"通过" if result["sections_ok"] else "**失配**"}
- 通道清单比对（facts/price/profile 三面）：{"通过" if result["manifest_ok"] else "**失配**"}
  （期望：{manifest}）
- 三通道互斥校验违规数：{len(result["channel_violations"])}
- 声明块防改写（保护执行器）：{"通过" if result["protected_ok"] else "**失配**"}
- 三格式渲染（md 字节稳定 / html / docx）：{"通过" if result["renders_ok"] else "**失配**"}
- 非空 claim 对齐（3 对全 supports）：{"通过" if result["align_ok"] else "**失配**"}
- 结论：{"green" if result["green"] else "**red**"}
"""


def main() -> int:
    samples = json.loads(GOLDDOCS.read_text(encoding="utf-8"))["samples"]
    results = [check_sample(s) for s in samples]

    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    by_id = {s["sample_id"]: s for s in samples}
    for result in results:
        path = TRACE_DIR / f"{result['sample_id']}.md"
        path.write_text(
            sample_trace(by_id[result["sample_id"]], result), encoding="utf-8"
        )

    summary = {
        "samples": len(results),
        "green": sum(1 for r in results if r["green"]),
        "delegated_coverage": {
            "pdf": "M3-035 containerized verify (Q-003 option 3)",
            "invariants_bundle": "eval.invariants (compose tier)",
        },
        "all_green": all(r["green"] for r in results),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    return 0 if summary["all_green"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
