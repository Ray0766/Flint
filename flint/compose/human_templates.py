"""五套人类模板跑通（M3-029：规则表 → 结构骨架）。

- scaffold_deliverable：模板规则表驱动的确定性骨架——每节一个 heading
  block（outline 序）+ 节级 word 预算（Ratio.min/max）+ check_questions
  随节携带；真实成稿由 draft 管线在骨架上填充（M3-022/023 门内）。
- 模板必须真的在起作用：任两套骨架结构可区分由验收断言看守。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from flint.compose.templates import load_template
from flint.domain.models import Block, HeadingContent


@dataclass(frozen=True)
class SectionScaffold:
    section_id: str
    word_budget: tuple[int, int]
    check_questions: tuple[str, ...]


@dataclass
class DeliverableScaffold:
    template_id: str
    deliverable_id: str
    sections: list[SectionScaffold] = field(default_factory=list)
    blocks: list[Block] = field(default_factory=list)


def scaffold_deliverable(
    template_path: Path, deliverable_id: str
) -> DeliverableScaffold:
    spec, section_specs = load_template(template_path)
    checks_by_id = {s.section_id: tuple(s.check_questions) for s in section_specs}
    scaffold = DeliverableScaffold(
        template_id=spec.template_id, deliverable_id=deliverable_id
    )
    for order, (section_id, ratio) in enumerate(spec.sections):
        scaffold.sections.append(
            SectionScaffold(
                section_id=section_id,
                word_budget=(ratio.min_words, ratio.max_words),
                check_questions=checks_by_id[section_id],
            )
        )
        scaffold.blocks.append(
            Block(
                block_id=f"b-{deliverable_id}-{section_id}",
                deliverable_id=deliverable_id,
                section_id=section_id,
                order=order,
                type="heading",
                content=HeadingContent(kind="heading", level=2, text=section_id),
                claim_ids=[],
                fact_ids=[],
                author="system",
                revision=1,
                locked=False,
            )
        )
    return scaffold
