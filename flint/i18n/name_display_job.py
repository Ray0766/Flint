"""I18N-04-a：name_display 派生管道（translate JobKind），后端半边。

原卡 I18N-04 按 §4.5 拆分: 本模块 = -a（后端）; -b（前端次要行组件）仍 blocked。

## 派生管道最要紧的一条: 原文一个字节都不能动

派生只写 display 槽。`name_native` 是 B7 的唯一权威, 派生流程碰它一下
（哪怕只是归一化空白）就等于让译文管道有权改写原文——那正是 B7 要禁的。

## 降级时留空, NEVER 用原文填充

翻译不可用（A7）时 display 槽**留空**。用原文填充会让 UI 拿到一个
`translated=True` 却其实是原文的条目, B8 的机翻标记就成了谎;
而留空时 UI 按 A7 退回 name_native 单行, 那是**如实**的。

## H7: 走既有 JobRunner

`translate` 是契约 `JobKind` 的成员（SCHEMA-13 增的三值之一）,
提交走既有 `PgJobRunner.submit`, 本模块只产 payload, **NEVER 新写 runner**。
"""
from __future__ import annotations

from dataclasses import replace
from typing import Any

from flint.i18n.translator import TranslationCache, Translator, translate_or_degrade

# 契约值, NEVER 自定义字符串（SCHEMA-13 已把它加进 JobKind）
TRANSLATE_JOB_KIND = "translate"
_SOURCE_FIELD = "name_native"


def translate_payload(
    *, project_id: str, target_ids: list[str], targets: tuple[str, ...]
) -> dict[str, Any]:
    """构造 translate 作业的 payload（提交仍走既有 JobRunner.submit）。"""
    if not target_ids:
        raise ValueError("target_ids NEVER 为空: 一个不翻译任何东西的翻译作业没有意义")
    return {
        "project_id": project_id,
        "target_ids": list(target_ids),
        "targets": list(targets),
        "source_field": _SOURCE_FIELD,
    }


def derive_name_display(
    cluster: Any, *, targets: tuple[str, ...], translator: Translator,
    cache: TranslationCache,
) -> Any:
    """给一个簇派生 name_display。**只写 display 槽**, 原文一字不动。

    - 已有的译文槽保留: 重跑只补缺的那几种语言;
    - 降级（服务不可用）时该语言**不写入**, NEVER 用原文冒充译文。
    """
    from contracts_v04.models_v04 import TranslatedText

    display: dict[str, Any] = dict(cluster.name_display or {})
    for target in targets:
        if target in display:
            continue
        result = translate_or_degrade(translator, cluster.name_native, target, cache=cache)
        if result.degraded or result.text is None:
            continue                                  # A7: 留空, 由 UI 退回单行
        display[target] = TranslatedText(
            text=result.text, translated=True,
            translator=translator.version, source_field=_SOURCE_FIELD)

    return replace(cluster, name_display=display or None)
