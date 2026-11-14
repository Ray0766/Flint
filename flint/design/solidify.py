"""DESIGN-28（隔离带·G3）：固化管道（示例 → 插槽 → 注册）。

## 固化在做的是一件很具体的事

把探索期那份「长得对但内容是假的」样板，变成一份**只剩形状**的模板：
被标记的区域换成 `{{block:id}}` / `{{t:key}}`，示例正文、示例数字、水印统统不留。

换不干净的后果不是不好看——那段示例数字会跟着模板进入生产渲染，
而生产渲染只认模板、不再看内容（G6 已立，DESIGN-31）。
**这一步是最后一次能拦住它的地方**，所以宁可拒绝也不放行。

## 水印属于样板，不属于模板

留着的话，正式产物上会印着「这是样板」——那比漏一个示例数字更难解释。

## 一个槽都没标 = 不是模板

那是一张静态页；固化它没有意义，却会占着 template_id 让人以为可以拿来生成
（与契约 `TemplateRecord.slots` 非空同款理由）。

## 注册走既有实现

`register_template`（DESIGN-30）负责去重、版本、checksum 绑定；本模块只把
「变成模板的那份 HTML」交给它，NEVER 另建一份存储。
"""
from __future__ import annotations

import re
from typing import Any

from flint.design.mock_syntax import CONCRETE_NUMBER_PATTERN, CONCRETE_SOURCE_PATTERN
from flint.design.templates.registry import register_template

# 样板里被标记为「将来要填内容」的区域：`data-slot="block:b-1"` / `data-slot="t:title"`
MARKED = re.compile(
    r"<(?P<tag>[a-z0-9]+)([^>]*?)\sdata-slot=\"(?P<slot>[a-z]+:[a-z0-9_-]+)\""
    r"([^>]*)>(?P<body>.*?)</(?P=tag)>",
    re.IGNORECASE | re.DOTALL,
)
WATERMARK_ATTR = re.compile(r"\s*data-mock-watermark=\"[^\"]*\"")
SLOT_TOKEN = re.compile(r"\{\{[a-z]+:[a-z0-9_-]+\}\}", re.IGNORECASE)


class SolidifyBlocked(Exception):
    """固化被拒。`violations` 是**完整清单**，不是第一条。"""

    def __init__(self, violations: list[str]) -> None:
        super().__init__("固化被拒：" + "；".join(violations))
        self.violations = violations


def to_slots(mock_html: str) -> tuple[str, tuple[str, ...]]:
    """样板 → 模板：标记区域换成插槽，水印剥掉，示例残留即拒。"""
    slots: list[str] = []

    def replace(match: re.Match[str]) -> str:
        slot = match.group("slot")
        slots.append(slot)
        return "{{" + slot + "}}"

    templated = MARKED.sub(replace, mock_html)
    templated = WATERMARK_ATTR.sub("", templated)

    if not slots:
        raise SolidifyBlocked(
            ["一个插槽都没有：那不是模板而是一张静态页，固化它只会占着 template_id"]
        )

    # 扫残留前先把插槽本身**遮掉**：`{{block:b-1}}` 里的 "1" 会被数字模式命中，
    # 于是刚换好的插槽反过来被判成「示例数字残留」——检查器把自己的产物拦了下来。
    masked = SLOT_TOKEN.sub(lambda m: " " * len(m.group(0)), templated)

    # 标记之外的示例残留：这一步不拦，它就跟着模板进生产
    violations = [
        f"示例数字残留：{m.group(0)}" for m in CONCRETE_NUMBER_PATTERN.finditer(masked)
    ]
    violations += [
        f"示例来源残留：{m.group(0)}" for m in CONCRETE_SOURCE_PATTERN.finditer(masked)
    ]
    if violations:
        raise SolidifyBlocked(violations)

    return templated, tuple(sorted(set(slots)))


def solidify_mock(
    registry: Any,
    *,
    mock_html: str,
    template_id: str,
    owner: Any,
    name: str,
    source_deliverable_id: str | None,
    now: Any,
    model: Any,
    event_model: Any,
) -> Any:
    """固化并注册；返回 `solidify_result` 事件。"""
    from contracts_v04.models_v04 import template_checksum

    html, slots = to_slots(mock_html)
    record = register_template(
        registry,
        template_id=template_id,
        owner=owner,
        name=name,
        slots=slots,
        html=html,
        source_deliverable_id=source_deliverable_id,
        now=now,
        model=model,
        checksum_of=template_checksum,      # 指纹口径只有契约那一份
    )
    return event_model(
        kind="solidify_result",
        template_id=record.template_id,
        accepted=True,
        reason=None,
    )
