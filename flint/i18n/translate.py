"""K4-01：翻译接线——本地模型优先，谷歌免费档兜底（owner 裁决）。

## 接口早就有了，本卡接的是实现

`flint/i18n/translator.py` 建的是接口：`Translator` 协议 + `IdentityTranslator`
（「不译，也不假装译过」）+ 幂等缓存 + A7 降级。K4 选型未决，所以只有 identity。
裁决落地后本模块加两个实现，**调用点仍然只有一个**（`select_translator`）：
第二个构造点意味着换引擎时总有一处会被忘掉，而忘掉的那一处会继续用旧引擎，
产物上却标着新引擎的名字。

## 优先级是裁决，不是「谁先配上用谁」

`local` 配了就用 `local`，两个都配了还是 `local`，都没配落回 identity——
**NEVER 静默改用某个默认在线服务**，那等于替 owner 开了一个外部依赖。

## 机翻 NEVER 看起来像人工译文

每份译文带 `TranslationProvenance`：哪个引擎、什么版本、什么时候翻的。
identity 档**不带**这个标记——给它标一个 engine 等于宣称「这段翻译过了」，
而它一个字没动。

## 失败 NEVER 变成半截译文

空串 / 只有空白 / 结构漂移 一律抛 `TranslationUnavailable`（A7 降级的唯一触发类型），
**原文一路带着**。静默返回空串的后果是无声的：卡片上少一行，
而没有任何地方记着「翻译从今天起全坏了」。

## 谷歌免费档的响应形状是**录出来的**

`fixtures/translate/google_free_zh_to_en.json` 是真实响应的录制件
（NET-02 三件套：URL / 时间 / sha256）。解析器按录到的形状写——
编一个响应结构的话，解析器与它的测试会自洽，而真连上时一行也解析不出来。

长文本会被切成多段返回，**只取第一段就是半截译文**：`parse_google_free_response`
把所有段拼回整段。
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Final

from flint.i18n.translator import (
    IdentityTranslator,
    TranslationCache,
    TranslationUnavailable,
    Translator,
    cache_key,
)

ENGINE_LOCAL: Final[str] = "local_model"
ENGINE_GOOGLE_FREE: Final[str] = "google_free"

GOOGLE_FREE_URL: Final[str] = "https://translate.googleapis.com/translate_a/single"

DEFAULT_LOCAL_MODEL: Final[str] = "local"

_PROMPT: Final[str] = (
    "把下面的文本翻译成目标语言 {target}。**只返回译文本身**，"
    "不要解释、不要加引号、不要写「这句话的意思是」。\n\n{text}"
)


@dataclass(frozen=True)
class TranslationProvenance:
    """一份译文的来源。**四项一体**：少了 `translated_at`，
    换引擎重译之后分不出哪份是新的；少了 `engine_version`，
    换模型之后产物上看不出这段是哪个模型翻的。
    """

    engine: str
    engine_version: str
    translated_at: datetime
    target: str
    machine: bool = True


@dataclass(frozen=True)
class MarkedTranslation:
    """译文 + 它从哪来 + **原文**。

    原文一路带着：译文是附加物，不是替代物（接地比对只对原文，B9/B10）。
    降级时 `text is None` 且 `provenance is None`——
    NEVER 拿原文冒充译文，那会让 UI 把原文当译文显示。
    """

    source_text: str
    text: str | None
    provenance: TranslationProvenance | None
    degraded: bool = False
    reason: str | None = None


def _guard(raw: object, *, engine: str) -> str:
    """译文出口的唯一检查点：空的就是失败，NEVER 当译文放行。"""
    text = str(raw or "")
    if not text.strip():
        raise TranslationUnavailable(
            f"{engine} 返回了空译文——空串会被下游当成「这段没内容」，"
            "而原文是有内容的：这种错是无声的"
        )
    return text


@dataclass
class LocalModelTranslator:
    """本地模型档（优先）。走既有 `LLMProvider`，零 API 费用、零 key。"""

    provider: Any
    model: str = DEFAULT_LOCAL_MODEL
    engine: str = ENGINE_LOCAL
    # 冻结协议 `Translator.version` 是**可写变量**，不是只读属性——
    # 写成 @property 就不满足协议（mypy --strict 会指出来）。
    version: str = ""

    def __post_init__(self) -> None:
        self.version = self.version or f"local:{self.model}@v1"

    def translate(self, text: str, target: str) -> str:
        from flint.llm.local import LocalProviderUnavailable

        try:
            completion = self.provider.generate(
                _PROMPT.format(target=target, text=text), [])
        except LocalProviderUnavailable as err:
            # 只把「端点不可达」翻成降级信号：模型答错是另一回事，
            # 混起来会让程序错误被降级掩盖成「服务不可用」。
            raise TranslationUnavailable(f"本地模型不可用：{err}") from err
        return _guard(getattr(completion, "text", ""), engine=self.version)


def parse_google_free_response(payload: object) -> str:
    """按**录制件的真实形状**解析：`[[[译文, 原文, ...], ...], ...]`。

    结构对不上就抛错，NEVER 返回空串：静默返回空串的话，
    谷歌哪天改了响应结构，产物上只会少一行。
    """
    try:
        segments = payload[0]  # type: ignore[index]
        parts = [str(seg[0]) for seg in segments]
    except (TypeError, KeyError, IndexError) as err:
        raise TranslationUnavailable(
            f"谷歌免费档的响应结构与录制件不符（{type(err).__name__}）："
            "结构漂移必须报错，否则翻译坏掉是无声的"
        ) from err
    return _guard("".join(parts).strip(), engine=ENGINE_GOOGLE_FREE)


@dataclass
class GoogleFreeTranslator:
    """兜底档：谷歌免费翻译端点（`client=gtx`，无 key）。

    请求由**注入的 client** 发——测试注入替身，恒回放，NEVER 触真实服务。
    """

    client: Any
    source_lang: str = "auto"
    engine: str = ENGINE_GOOGLE_FREE
    version: str = "google-free@v1"

    def translate(self, text: str, target: str) -> str:
        response = self.client.get(GOOGLE_FREE_URL, params={
            "client": "gtx", "sl": self.source_lang, "tl": target,
            "dt": "t", "q": text,
        })
        if getattr(response, "status_code", 0) != 200:
            raise TranslationUnavailable(
                f"谷歌免费档返回 HTTP {getattr(response, 'status_code', '?')}："
                "错误页 NEVER 当译文"
            )
        return parse_google_free_response(response.json())


@dataclass
class TranslatorConfig:
    """选型配置。**两个都没配是合法状态**（identity 档），不是错误。"""

    local_provider: Any = None
    local_model: str = DEFAULT_LOCAL_MODEL
    google_client: Any = None
    identity_version: str = "identity@v1"
    _unused: tuple[()] = field(default=(), repr=False)


def select_translator(config: TranslatorConfig) -> Translator:
    """**全系统唯一的翻译器构造点**。优先级见模块 docstring。"""
    if config.local_provider is not None:
        return LocalModelTranslator(config.local_provider, model=config.local_model)
    if config.google_client is not None:
        return GoogleFreeTranslator(config.google_client)
    return IdentityTranslator(version=config.identity_version)


def _is_identity(translator: Translator) -> bool:
    return isinstance(translator, IdentityTranslator)


def translate_marked(
    translator: Translator,
    text: str,
    *,
    target: str,
    cache: TranslationCache,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> MarkedTranslation:
    """翻一段并**标上来源**；失败则降级并保留原文（A7）。

    降级结果 NEVER 入缓存——服务恢复后还从缓存拿「没有译文」就成了永久降级。
    """
    key = cache_key(text, target, translator.version)
    hit = cache.get(key)
    engine = getattr(translator, "engine", "identity")
    if hit is not None:
        return MarkedTranslation(
            source_text=text, text=hit,
            provenance=None if _is_identity(translator) else TranslationProvenance(
                engine=engine, engine_version=translator.version,
                translated_at=now(), target=target),
        )

    try:
        translated = translator.translate(text, target)
    except TranslationUnavailable as err:
        return MarkedTranslation(
            source_text=text, text=None, provenance=None, degraded=True,
            reason=f"翻译服务不可用，退回原文单行显示（A7）：{err}",
        )

    cache.put(key, translated)
    if _is_identity(translator):
        # identity 档一个字没动，所以**没有译文来源标记**：
        # 标一个 engine 等于宣称「这段翻译过了」。
        return MarkedTranslation(source_text=text, text=translated, provenance=None)
    return MarkedTranslation(
        source_text=text, text=translated,
        provenance=TranslationProvenance(
            engine=engine, engine_version=translator.version,
            translated_at=now(), target=target),
    )
