"""K4-01：翻译接线——本地模型优先，谷歌免费档兜底。

## K4 之前是什么样

`flint/i18n/translator.py` 建的是**接口**：`Translator` 协议 + `IdentityTranslator`
（「不译，也不假装译过」）+ 幂等缓存 + A7 降级。选型未决，所以只有 identity 一个实现。

owner 裁决：**本地模型优先，谷歌免费档兜底**。本卡把这两个实现接上去，
**调用点仍然只有一个**（`select_translator`）——两个入口的话，
换引擎时总有一处会被忘掉，而忘掉的那一处会继续用旧引擎，
产物上却标着新引擎的名字。

## 三条不许越的线

1. **机翻 NEVER 看起来像人工译文**：每份译文带 `TranslationProvenance`
   （哪个引擎、什么版本、什么时候翻的）；
2. **失败 NEVER 返回半截**：空串 / 只有空白 / 比原文短得离谱都算失败，
   照实抛 `TranslationUnavailable` 并**保留原文**；
3. **测试 NEVER 触真实翻译服务**：录制件在 `fixtures/translate/`，
   判据有源码断言守着。
"""
from __future__ import annotations

import inspect
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from flint.i18n.translate import (
    ENGINE_LOCAL,
    GoogleFreeTranslator,
    LocalModelTranslator,
    TranslatorConfig,
    parse_google_free_response,
    select_translator,
    translate_marked,
)
from flint.i18n.translator import (
    IdentityTranslator,
    TranslationCache,
    TranslationUnavailable,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE = REPO_ROOT / "fixtures" / "translate" / "google_free_zh_to_en.json"
NOW = datetime(2026, 8, 4, 10, 0, tzinfo=UTC)


class _Provider:
    """本地模型替身。**不是**真调用——测试恒回放。"""

    def __init__(self, reply: str = "quantum computing") -> None:
        self.reply = reply
        self.prompts: list[str] = []

    def generate(self, prompt: str, tools: list[object] | None = None) -> object:
        self.prompts.append(prompt)

        class _Completion:
            text = self.reply

        return _Completion()


class _DeadProvider:
    def generate(self, prompt: str, tools: list[object] | None = None) -> object:
        from flint.llm.local import LocalProviderUnavailable

        raise LocalProviderUnavailable("connection refused")


# ───────────────────────── 一、两个实现 + 单一选择点（acceptance①）


def test_local_is_preferred_when_it_is_configured() -> None:
    """acceptance①：**本地优先**。配了本地就用本地，不去碰兜底。"""
    chosen = select_translator(TranslatorConfig(local_provider=_Provider()))

    assert isinstance(chosen, LocalModelTranslator)


def test_google_is_only_the_fallback() -> None:
    """没有本地才落到谷歌免费档——**兜底不是默认**。"""
    chosen = select_translator(TranslatorConfig(google_client=object()))

    assert isinstance(chosen, GoogleFreeTranslator)


def test_local_still_wins_when_both_are_configured() -> None:
    """两个都配了也走本地：owner 裁决的原话是「本地模型优先」。

    没有这一条，「优先」与「谁先配上用谁」长得一模一样。
    """
    chosen = select_translator(TranslatorConfig(
        local_provider=_Provider(), google_client=object()))

    assert isinstance(chosen, LocalModelTranslator)


def test_neither_configured_falls_back_to_identity_not_to_a_guess() -> None:
    """两个都没配 → `IdentityTranslator`：**不译，也不假装译过**（既有口径）。

    这里 NEVER 静默改用某个默认在线服务——那等于替 owner 开了一个外部依赖。
    """
    chosen = select_translator(TranslatorConfig())

    assert isinstance(chosen, IdentityTranslator)


def test_the_call_site_is_the_only_one() -> None:
    """调用点单一集中：仓里**只有 `select_translator` 构造这两个实现**。

    第二个构造点意味着换引擎时总有一处会被忘掉，而忘掉的那一处会继续用
    旧引擎，产物上却标着新引擎的名字。
    """
    import ast

    hits: list[str] = []
    for path in sorted((REPO_ROOT / "flint").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                continue
            if node.func.id in ("LocalModelTranslator", "GoogleFreeTranslator"):
                hits.append(f"{path.relative_to(REPO_ROOT)}:{node.lineno}")

    assert [h for h in hits if not h.startswith("flint\\i18n\\translate.py")] == [], hits


# ───────────────────────── 二、译文标来源（acceptance②）


def test_the_translation_carries_which_engine_made_it() -> None:
    """acceptance②：**NEVER 让机翻看起来像人工译文**。"""
    result = translate_marked(
        select_translator(TranslatorConfig(local_provider=_Provider())),
        "量子计算", target="en", cache=TranslationCache(), now=lambda: NOW,
    )

    assert result.text == "quantum computing"
    assert result.provenance is not None
    assert result.provenance.engine == ENGINE_LOCAL
    assert result.provenance.translated_at == NOW
    assert result.provenance.machine is True


def test_the_engine_version_is_part_of_the_provenance() -> None:
    """引擎**版本**也要记：换了模型之后，旧译文与新译文一眼要能分开。

    只记「本地模型」的话，换模型后产物上看不出这段是哪个模型翻的。
    """
    translator = select_translator(TranslatorConfig(
        local_provider=_Provider(), local_model="qwen3:14b"))

    assert "qwen3:14b" in translator.version


def test_the_original_text_is_always_kept() -> None:
    """原文一路带着：**译文是附加物，不是替代物**（B9/B10 接地只对原文）。"""
    result = translate_marked(
        select_translator(TranslatorConfig(local_provider=_Provider())),
        "量子计算", target="en", cache=TranslationCache(), now=lambda: NOW,
    )

    assert result.source_text == "量子计算"


def test_identity_output_is_not_marked_as_translated() -> None:
    """identity 档**没有译文**，所以也没有译文来源标记。

    给它标一个 engine 等于宣称「这段翻译过了」，而它一个字没动。
    """
    result = translate_marked(
        select_translator(TranslatorConfig()),
        "量子计算", target="en", cache=TranslationCache(), now=lambda: NOW,
    )

    assert result.provenance is None
    assert result.text == "量子计算"


# ───────────────────────── 三、失败照实报错、保留原文（acceptance④）


@pytest.mark.parametrize("bad", ["", "   ", "\n\t"])
def test_an_empty_result_is_a_failure_not_a_translation(bad: str) -> None:
    """acceptance④：**NEVER 返回空串**。

    空串会被下游当成「这段没内容」，而原文是有内容的——
    错在这里是无声的：卡片上少一行，没人知道是翻译坏了。
    """
    translator = LocalModelTranslator(_Provider(reply=bad), model="m")

    with pytest.raises(TranslationUnavailable):
        translator.translate("量子计算", "en")


def test_a_dead_local_endpoint_raises_the_declared_type() -> None:
    """本地端点不可达 → `TranslationUnavailable`（A7 降级的唯一触发类型）。

    别的异常类型会穿过降级层，把「服务不可用」变成整条链路崩掉。
    """
    translator = LocalModelTranslator(_DeadProvider(), model="m")

    with pytest.raises(TranslationUnavailable):
        translator.translate("量子计算", "en")


def test_a_failure_degrades_and_keeps_the_source() -> None:
    """失败时**保留原文**并明说降级了，NEVER 拿原文冒充译文。"""
    result = translate_marked(
        LocalModelTranslator(_DeadProvider(), model="m"),
        "量子计算", target="en", cache=TranslationCache(), now=lambda: NOW,
    )

    assert result.degraded is True
    assert result.text is None
    assert result.source_text == "量子计算"
    assert result.provenance is None
    assert "不可用" in (result.reason or "")


def test_a_degraded_result_never_enters_the_cache() -> None:
    """降级结果 NEVER 入缓存——服务恢复后还从缓存拿「没有译文」就成了永久降级。"""
    cache = TranslationCache()

    translate_marked(LocalModelTranslator(_DeadProvider(), model="m"),
                     "量子计算", target="en", cache=cache, now=lambda: NOW)

    from flint.i18n.translator import cache_key

    assert cache.get(cache_key("量子计算", "en", "local:m@v1")) is None


def test_the_model_is_not_asked_to_explain_itself() -> None:
    """提示词要求**只返回译文**：模型爱写「这句话的意思是……」，

    那段解释会被当作译文原样显示在卡片上。
    """
    provider = _Provider()
    LocalModelTranslator(provider, model="m").translate("量子计算", "en")

    assert "只返回" in provider.prompts[0]
    assert "en" in provider.prompts[0]


# ───────────────────────── 四、谷歌免费档解析走录制件（acceptance③）


def test_the_recorded_response_is_on_disk_with_its_manifest() -> None:
    """acceptance③：真实调用留 NET-02 三件套（原件 + URL + 时间 + sha256）。"""
    from flint.sources.provenance import manifest_path_for, verify_fixture

    assert FIXTURE.exists(), "没有录制件 = 解析器是照猜的形状写的"
    manifest = manifest_path_for(FIXTURE)
    assert manifest.exists()
    assert verify_fixture(FIXTURE, manifest) == []


def _recorded_payload() -> object:
    """从录制件里取出真实响应体。信封是 NET-02 的 `[{url, body_text}]`——
    与四源的录制件同一个形状，`verify_fixture` 才核得动。
    """
    record = json.loads(FIXTURE.read_text(encoding="utf-8"))[0]
    return json.loads(record["body_text"])


def test_the_parser_reads_the_recorded_shape() -> None:
    """解析器按**录到的真实响应**写，不是按猜的形状。

    编一个响应结构的后果很具体：解析器与它的测试会自洽——两边都按编的形状写，
    全绿；等哪天真连上，它一行也解析不出来。
    """
    out = parse_google_free_response(_recorded_payload())

    assert "Quantum computing" in out
    assert "量子计算" not in out, "原文被当成译文返回了"


def test_a_drifted_response_is_a_failure_not_an_empty_string() -> None:
    """结构漂移 → 报错，NEVER 静默返回空串。

    静默返回空串的话，谷歌哪天改了响应结构，产物上只会**少一行**，
    而没有任何地方记着「翻译从今天起全坏了」。
    """
    for drifted in ([], [[]], [[[]]], {"unexpected": 1}, [[["", ""]]]):
        with pytest.raises(TranslationUnavailable):
            parse_google_free_response(drifted)


def test_multi_segment_responses_are_joined_whole() -> None:
    """长文本会被切成多段返回——**只取第一段就是半截译文**（acceptance④）。"""
    payload = [[["Hello ", "你好 "], ["world", "世界"]], None, "zh-CN"]

    assert parse_google_free_response(payload) == "Hello world"


def test_the_module_never_calls_the_service_at_import_time() -> None:
    """模块里零真实网络调用点：请求由注入的 client 发，测试注入替身。"""
    from flint.i18n import translate
    from tools.check_no_live_network import scan_source as net_scan

    assert net_scan(inspect.getsource(translate), "flint/i18n/translate.py") == []


def test_the_google_translator_uses_the_injected_client() -> None:
    """兜底实现走注入的 client——测试恒回放，NEVER 触真实服务。"""
    payload = _recorded_payload()

    class _Client:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def get(self, url: str, params: dict[str, object]) -> object:
            self.calls.append({"url": url, "params": params})

            class _Response:
                status_code = 200

                @staticmethod
                def json() -> object:
                    return payload

            return _Response()

    client = _Client()
    out = GoogleFreeTranslator(client).translate("量子计算", "en")

    assert out.strip() != ""
    assert client.calls[0]["params"]["tl"] == "en"  # type: ignore[index]


def test_a_non_200_from_google_is_unavailable_not_a_translation() -> None:
    """非 200 → `TranslationUnavailable`，NEVER 把错误页当译文。

    响应体给的是**能解析的合法形状**：给一个解析不了的体，
    这条断言会被解析器的报错喂饱——抽掉状态码检查照样红，
    于是判的其实是解析器，不是状态码（变异考实测：24 条全绿）。
    """
    payload = _recorded_payload()

    class _Client:
        @staticmethod
        def get(url: str, params: dict[str, object]) -> object:
            class _Response:
                status_code = 429

                @staticmethod
                def json() -> object:
                    return payload

            return _Response()

    with pytest.raises(TranslationUnavailable):
        GoogleFreeTranslator(_Client()).translate("量子计算", "en")


def test_a_successful_translation_is_cached() -> None:
    """译文入缓存：同一段原文 + 同一目标语 + 同一引擎版本 **只翻一次**。

    不入缓存的话，同一份卡片每渲染一次就再翻一次——本地模型是算力，
    兜底档是别人的免费配额。
    """
    provider = _Provider(reply="first")
    translator = LocalModelTranslator(provider, model="m")
    cache = TranslationCache()

    first = translate_marked(translator, "量子计算", target="en",
                             cache=cache, now=lambda: NOW)
    provider.reply = "second"
    again = translate_marked(translator, "量子计算", target="en",
                             cache=cache, now=lambda: NOW)

    assert first.text == "first"
    assert again.text == "first", "第二次又去问模型了——缓存没生效"
    assert len(provider.prompts) == 1


def test_the_cache_is_not_shared_across_engines() -> None:
    """换引擎 = 换缓存键：**混了就会串译文**，而产物上标着新引擎的名字。"""
    cache = TranslationCache()
    translate_marked(LocalModelTranslator(_Provider(reply="from-local"), model="m"),
                     "量子计算", target="en", cache=cache, now=lambda: NOW)

    other = translate_marked(
        LocalModelTranslator(_Provider(reply="from-other"), model="other"),
        "量子计算", target="en", cache=cache, now=lambda: NOW)

    assert other.text == "from-other"


def test_the_two_engines_have_different_versions() -> None:
    """两个引擎的 version 不同——缓存键含 version，混了就会串译文。"""
    local = LocalModelTranslator(_Provider(), model="m").version
    google = GoogleFreeTranslator(object()).version

    assert local != google
