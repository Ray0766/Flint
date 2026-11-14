"""M3-035 容器内 PDF 探针：真实 flint.render.pdf 路径出件。

在容器内以挂载仓库为 PYTHONPATH 执行；产出写 /work/.pdf-probe/out.pdf。
场景：CJK 标题 + 决策边界声明 + 质量卡占位——页结构与中文字形（Noto CJK
内嵌）由宿主侧断言。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, "/work")

from flint.compose.disclaimer import build_disclaimer_block
from flint.domain.models import Block, HeadingContent, QualityCardContent
from flint.render.pdf import render_pdf


def main() -> None:
    blocks = [
        build_disclaimer_block("d-probe", "s-0", "2026-07-26"),
        Block(
            block_id="b-qc", deliverable_id="d-probe", section_id="s-0", order=1,
            type="quality_card",
            content=QualityCardContent(kind="quality_card", card_ref="qc-1"),
            claim_ids=[], fact_ids=[], author="system", revision=1, locked=True,
        ),
        Block(
            block_id="b-h", deliverable_id="d-probe", section_id="s-1", order=0,
            type="heading",
            content=HeadingContent(kind="heading", level=2, text="市场分析与判定"),
            claim_ids=[], fact_ids=[], author="system", revision=1, locked=False,
        ),
    ]
    payload = render_pdf(blocks)
    out = Path("/work/.pdf-probe/out.pdf")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(payload)
    print(f"wrote {len(payload)} bytes")


if __name__ == "__main__":
    main()
