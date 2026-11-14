"""outline：TemplateSpec → 章节序（M3-019，冻结协议 ReportComposer.outline 面）。

规则表驱动零生成：outline 即模板 sections 声明序（确定性）；locale 随模板
携带（规则表按 locale 分别维护，非翻译——冻结 TemplateSpec 注释口径）。
"""
from __future__ import annotations

from pathlib import Path

from flint.compose.templates import load_template


def outline_for(template_path: Path) -> list[str]:
    spec, _sections = load_template(template_path)
    return [section_id for section_id, _ratio in spec.sections]


def outline_with_locale(template_path: Path) -> tuple[list[str], str]:
    spec, _sections = load_template(template_path)
    return [sid for sid, _r in spec.sections], spec.locale
