"""I18N-03 验收：Translator 协议 + fixture 实现 + 幂等缓存 + A7 降级。

acceptance（tasks-v04.json#I18N-03）：
  ① 接口**单点**、fixture/identity 实现（K4 选型位）；
  ② 缓存键 = **原文字节 + 目标语 + 版本**；服务不可用 → **降级信号**（A7）。

## 缓存键为什么必须含版本

E5：翻译归「幂等判别类」缓存。少了 translator 版本这一项，换了译者/模型之后
旧译文会被当成新译者的产物返回——`TranslatedText.translator` 标记与内容对不上，
而那个标记正是 B8 让 UI 显示「机翻」的依据。

## A7 降级不是抛错

翻译服务不可用时**不阻断**：卡片退回 `name_native` 单行（E6 新降级行）。
所以降级路径返回的是「没有译文」这个**明确信号**，NEVER 抛异常打断整条采集/渲染链，
也 NEVER 返回原文冒充译文——那会让 UI 把原文当译文显示，B8 的机翻标记就成了谎。
"""
from __future__ import annotations

import inspect

import pytest

from flint.i18n import translator as translator_module
from flint.i18n.translator import (
    IdentityTranslator,
    TranslationCache,
    TranslationUnavailable,
    Translator,
    cache_key,
    translate_or_degrade,
)

ORIGINAL = "全固体電池の量産ライン"


class _Recording(IdentityTranslator):
    def __init__(self, version: str = "identity@v1") -> None:
        super().__init__(version=version)
        self.calls = 0

    def translate(self, text: str, target: str) -> str:
        self.calls += 1
        return super().translate(text, target)


class _Down:
    version = "down@v1"

    def translate(self, text: str, target: str) -> str:
        raise TranslationUnavailable("fixture: service down")


# ── ① 接口单点 + fixture 实现 ────────────────────────────────────

def test_translator_is_a_single_protocol() -> None:
    assert isinstance(Translator, type)
    assert hasattr(IdentityTranslator, "translate")
    assert IdentityTranslator(version="identity@v1").version == "identity@v1"


def test_identity_translator_returns_input_unchanged() -> None:
    """K4 未决 → fixture 档是 identity：不译、也不假装译过。"""
    t = IdentityTranslator(version="identity@v1")
    assert t.translate(ORIGINAL, "en") == ORIGINAL


def test_no_real_network_symbol_in_module() -> None:
    """§4.3⑤：Translator 恒 fixture 注入，模块里 NEVER 出现网络调用。"""
    source = inspect.getsource(translator_module)
    for forbidden in ("httpx", "requests", "urlopen", "openai", "anthropic"):
        assert forbidden not in source, f"翻译模块里出现 {forbidden!r}"


# ── ② 缓存键三要素 ──────────────────────────────────────────────

def test_cache_key_covers_text_target_and_version() -> None:
    base = cache_key(ORIGINAL, "en", "qwen@v2")
    assert base != cache_key(ORIGINAL + "。", "en", "qwen@v2"), "原文变了键必须变"
    assert base != cache_key(ORIGINAL, "zh", "qwen@v2"), "目标语变了键必须变"
    assert base != cache_key(ORIGINAL, "en", "qwen@v3"), (
        "**版本变了键必须变**：否则换了译者之后旧译文会冒充新译者的产物")


def test_cache_key_is_byte_sensitive() -> None:
    """原文**字节**：全角/半角不同就是不同的原文，NEVER 归一后再算键。"""
    assert cache_key("２０２７年", "en", "v1") != cache_key("2027年", "en", "v1")


def test_cache_hit_avoids_second_call() -> None:
    cache = TranslationCache()
    t = _Recording()
    first = translate_or_degrade(t, ORIGINAL, "en", cache=cache)
    second = translate_or_degrade(t, ORIGINAL, "en", cache=cache)
    assert first == second
    assert t.calls == 1, "同键第二次 MUST 命中缓存"


def test_version_bump_invalidates_cache() -> None:
    cache = TranslationCache()
    old = _Recording(version="identity@v1")
    new = _Recording(version="identity@v2")
    translate_or_degrade(old, ORIGINAL, "en", cache=cache)
    translate_or_degrade(new, ORIGINAL, "en", cache=cache)
    assert new.calls == 1, "换版本 MUST 重算，NEVER 复用旧译文"


# ── A7 降级 ─────────────────────────────────────────────────────

def test_unavailable_service_degrades_instead_of_raising() -> None:
    result = translate_or_degrade(_Down(), ORIGINAL, "en", cache=TranslationCache())
    assert result.degraded is True
    assert result.text is None, "降级 MUST 是「没有译文」，NEVER 返回原文冒充译文"
    assert result.reason


def test_successful_translation_is_not_marked_degraded() -> None:
    result = translate_or_degrade(
        IdentityTranslator(version="identity@v1"), ORIGINAL, "en", cache=TranslationCache())
    assert result.degraded is False
    assert result.text == ORIGINAL


def test_degraded_result_is_not_cached() -> None:
    """降级 NEVER 进缓存：服务恢复后还从缓存拿「没有译文」就成了永久降级。"""
    cache = TranslationCache()
    translate_or_degrade(_Down(), ORIGINAL, "en", cache=cache)
    good = _Recording()
    result = translate_or_degrade(good, ORIGINAL, "en", cache=cache)
    assert result.degraded is False and good.calls == 1


def test_translation_unavailable_is_the_only_swallowed_error() -> None:
    """只吞 TranslationUnavailable：别的异常 NEVER 被降级掩盖成「服务不可用」。"""
    class _Buggy:
        version = "buggy@v1"

        def translate(self, text: str, target: str) -> str:
            raise ValueError("程序错误，不是服务不可用")

    with pytest.raises(ValueError):
        translate_or_degrade(_Buggy(), ORIGINAL, "en", cache=TranslationCache())
