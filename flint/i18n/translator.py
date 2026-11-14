"""I18N-03：Translator 协议 + fixture 实现 + 幂等缓存 + A7 降级。

## 接口单点

全系统只有这一个翻译入口。K4（翻译服务选型）未决期间, 落地实现是
`IdentityTranslator`——**不译, 也不假装译过**。选型落地时新增一个实现类即可,
调用点不动。

## 缓存键 = 原文字节 + 目标语 + translator 版本（E5）

少了版本这一项, 换了译者/模型之后旧译文会被当成新译者的产物返回——
`TranslatedText.translator` 标记与内容对不上, 而那个标记正是 B8 让 UI
显示「机翻」的依据。原文按**字节**入键: 全角与半角是两个不同的原文,
NEVER 归一后再算键（归一就等于认为它们可以共用一份译文）。

## A7 降级不是抛错

翻译服务不可用**不阻断**: 卡片退回 name_native 单行（E6 新降级行）。
降级返回的是「没有译文」这个明确信号:
  · NEVER 抛异常打断整条采集/渲染链;
  · NEVER 返回原文冒充译文——那会让 UI 把原文当译文显示, B8 的机翻标记就成了谎;
  · NEVER 把降级结果写进缓存——服务恢复后还从缓存拿「没有译文」就成了永久降级。
只吞 `TranslationUnavailable`: 别的异常是程序错误, NEVER 被降级掩盖成「服务不可用」。
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


class TranslationUnavailable(Exception):
    """翻译服务不可用（A7 降级触发点）。程序错误 NEVER 用这个类型。"""


@runtime_checkable
class Translator(Protocol):
    """全系统唯一翻译接口。K4 选型落地时新增实现类, 调用点不动。"""

    version: str

    def translate(self, text: str, target: str) -> str: ...


@dataclass
class IdentityTranslator:
    """fixture 档: 原样返回。**不译, 也不假装译过**（K4 未决）。"""

    version: str = "identity@v1"

    def translate(self, text: str, target: str) -> str:
        return text


def cache_key(text: str, target: str, version: str) -> str:
    """内容 hash = 原文**字节** + 目标语 + translator 版本（E5 幂等判别类）。"""
    digest = hashlib.sha256()
    digest.update(text.encode("utf-8"))
    digest.update(b"\x00")
    digest.update(target.encode("utf-8"))
    digest.update(b"\x00")
    digest.update(version.encode("utf-8"))
    return digest.hexdigest()


@dataclass
class TranslationCache:
    """内存缓存; Redis 实现随 E5 接入。降级结果 NEVER 入缓存。"""

    _store: dict[str, str] = field(default_factory=dict)

    def get(self, key: str) -> str | None:
        return self._store.get(key)

    def put(self, key: str, value: str) -> None:
        self._store[key] = value


@dataclass(frozen=True)
class TranslationResult:
    """译文或降级信号。两者互斥: degraded 时 text 恒为 None。"""

    text: str | None
    degraded: bool
    reason: str | None = None


def translate_or_degrade(
    translator: Translator, text: str, target: str, *, cache: TranslationCache
) -> TranslationResult:
    """翻译一段原文；服务不可用则**降级**而不是抛错（A7）。"""
    key = cache_key(text, target, translator.version)
    hit = cache.get(key)
    if hit is not None:
        return TranslationResult(text=hit, degraded=False)

    try:
        translated = translator.translate(text, target)
    except TranslationUnavailable as err:
        return TranslationResult(
            text=None, degraded=True,
            reason=f"翻译服务不可用，退回原文单行显示（A7）：{err}")

    cache.put(key, translated)
    return TranslationResult(text=translated, degraded=False)
