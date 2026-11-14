"""`translate` 作业的消费者——把 `name_display` 派生管道接上取号那一头。

> 本模块由 v0.4.1 第 6 批的 `SLOT-03` 建（`docs/steward/tasks-v041-b6.json`）。

## 改前

`flint/jobs/dispatch.py` 自己写着「仓里还没有 translate 作业的消费者」：
`flint/i18n/name_display_job.py` 只产 payload，派生函数 `derive_name_display`
是同步的。提交一条 `translate`，worker 取到只会抛 `JobKindNotWired`。

## 一行派生逻辑都不写

派生转调 `flint/i18n/name_display_job.py#derive_name_display`——它已经守着三条：
只写 display 槽（B7）· 译名带机翻标记（B8）· 翻不出来就留空（A7）。
再写一份的后果不是重复劳动，而是**同一个名字在两条路上被译成两个样子**，
而 UI 只显示其中一个，没人知道另一个存在。

## 取源与落盘为什么是注入的

冻结件 `contracts_v04/models_v04.py#Cluster` 在 `canonical_name` 那一行留了话：

> `canonical_name` 保留：与 `name_native` 的关系由 **REGION-04 命名规则成文**

也就是说「翻译该拿哪一段原文」**今天还没有成文**；而 `name_display` 全库没有落点
（实查：`information_schema` 里 `name_native` / `name_display` 零命中）。

两件都不是本模块能替产品决定的。所以取源与落盘走注入的两个端口，
与 `DesignGenerateDeps` 把 provider 注入进来同理——**装配处没配就大声缺**，
NEVER 猜一段原文去翻：猜错时屏上会出现一个语义正确、指向错误的译名，
而它与译对了长得一模一样。

## 降级不阻断，但要被数出来

一条翻不动 NEVER 打断整批（A7 原话「降级不阻断」）。但报告里 `translated` /
`degraded` / `missing` 三个数**必须加起来等于目标数**——否则「翻完了」与
「有一半根本没找到」在日志里长得一模一样。

## 网络

本模块 NEVER import 任何 HTTP 客户端。翻译恒经注入的 `Translator`
（`flint/i18n/translator.py`）：运行时是本机免费档，判据面是 fixture 回放。
自己发的那一条会绕过所有 respx 护栏，而 CI 恒不联网（S2-7）。
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from flint.i18n.name_display_job import derive_name_display
from flint.i18n.translator import TranslationCache, Translator

_SOURCE_FIELD = "name_native"


class TranslatePayloadInvalid(ValueError):
    """payload 不是 `translate_payload` 产的那个形状。**拒收，NEVER 尽力而为**。

    形状对不上时「尽力翻能翻的」是最坏的做法：它会安静地成功，
    而调用方以为整批都翻过了。
    """


@dataclass
class TranslateDeps:
    """取源 / 落盘 / 译者 / 缓存 / 时钟，全部由装配处给。"""

    load_target: Callable[[str], Any | None]
    save_target: Callable[[str, Any], None]
    translator: Translator
    cache: TranslationCache
    now: Callable[[], datetime]


@dataclass(frozen=True)
class TranslateReport:
    job_id: str
    translated: int
    degraded: int
    missing: tuple[str, ...]
    finished_at: datetime


def _parse(payload: dict[str, Any]) -> tuple[list[str], tuple[str, ...]]:
    source_field = payload.get("source_field")
    if source_field != _SOURCE_FIELD:
        raise TranslatePayloadInvalid(
            f"source_field 必须是 {_SOURCE_FIELD}（B7 的唯一权威原文），收到 "
            f"{source_field!r}——认别的字段等于开一条「从译文再翻一次」的路"
        )
    target_ids = payload.get("target_ids")
    if not isinstance(target_ids, list) or not target_ids:
        raise TranslatePayloadInvalid(
            "target_ids 为空：一个不翻译任何东西的翻译作业没有意义，"
            "而它会安静地成功"
        )
    targets = payload.get("targets")
    if not isinstance(targets, list) or not targets:
        raise TranslatePayloadInvalid(
            "targets 为空：一种语言都不翻的翻译作业没有意义，而它会安静地成功"
        )
    return [str(t) for t in target_ids], tuple(str(t) for t in targets)


async def run_translate(
    job_id: str, payload: dict[str, Any], deps: TranslateDeps,
) -> TranslateReport:
    """逐个目标派生 `name_display` 并落盘。派生本身转调既有管道。"""
    target_ids, targets = _parse(payload)

    translated = 0
    degraded = 0
    missing: list[str] = []

    for target_id in target_ids:
        loaded = deps.load_target(target_id)
        if loaded is None:
            missing.append(target_id)          # 点名，NEVER 静静跳过
            continue
        before = dict(getattr(loaded, "name_display", None) or {})
        derived = derive_name_display(
            loaded, targets=targets, translator=deps.translator, cache=deps.cache,
        )
        after = dict(getattr(derived, "name_display", None) or {})
        # 这一轮真的多出来的语言数；`derive_name_display` 对降级的那一档不写入（A7）。
        gained = set(after) - set(before)
        wanted = {t for t in targets if t not in before}
        if gained:
            translated += 1
        if wanted - gained:
            degraded += 1
        deps.save_target(target_id, derived)

    return TranslateReport(
        job_id=job_id, translated=translated, degraded=degraded,
        missing=tuple(missing), finished_at=deps.now(),
    )
