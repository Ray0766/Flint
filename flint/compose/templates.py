"""模板规则表装载（M3-017/018；冻结件 TemplateSpec/SectionSpec/Ratio）。

- share 合计必须为 1（容差 1e-6）；unit 与 audience 的双单位互斥
  （human_reader=words / ai_executor=tokens）在装载器执行（v0.3.3）。
- 返回 (TemplateSpec, list[SectionSpec])：Spec 供 outline/占比，SectionSpec
  携带 check_questions/charts（组稿自检面）。
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal, cast

import yaml

from flint.domain.models import Audience, ChartSpec, Ratio, SectionSpec, TemplateSpec

# 域以 contracts/models.py#Ratio.unit / #Audience 为准（校验后精确 cast 惯用法）
RatioUnit = Literal["words", "tokens"]


def load_template(path: Path) -> tuple[TemplateSpec, list[SectionSpec]]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    audience = str(payload["audience"])
    if audience not in ("human_reader", "ai_executor"):
        raise ValueError(f"unknown audience: {audience!r}")
    expected_unit = "words" if audience == "human_reader" else "tokens"

    sections: list[tuple[str, Ratio]] = []
    section_specs: list[SectionSpec] = []
    total_share = 0.0
    for section in payload["sections"]:
        raw_ratio = section["ratio"]
        unit = str(raw_ratio["unit"])
        if unit != expected_unit:
            raise ValueError(
                f"{payload['template_id']}/{section['section_id']}: unit {unit!r} "
                f"conflicts with audience {audience!r} (expects {expected_unit!r})"
            )
        ratio = Ratio(
            share=float(raw_ratio["share"]),
            min_words=int(raw_ratio["min_words"]),
            max_words=int(raw_ratio["max_words"]),
            unit=cast(RatioUnit, unit),
        )
        total_share += ratio.share
        section_id = str(section["section_id"])
        sections.append((section_id, ratio))
        section_specs.append(
            SectionSpec(
                section_id=section_id,
                inputs=[str(i) for i in section.get("inputs", [])],
                check_questions=[str(q) for q in section["check_questions"]],
                charts=[
                    ChartSpec(
                        chart_id=str(c["chart_id"]),
                        chart_type=str(c["chart_type"]),
                        derived_from=[str(d) for d in c["derived_from"]],
                    )
                    for c in section.get("charts", [])
                ],
            )
        )
    if abs(total_share - 1.0) > 1e-6:
        raise ValueError(
            f"{payload['template_id']}: section share sum {total_share} != 1.0"
        )
    spec = TemplateSpec(
        template_id=str(payload["template_id"]),
        locale=str(payload["locale"]),
        sections=sections,
        audience=cast(Audience, audience),
    )
    return spec, section_specs
