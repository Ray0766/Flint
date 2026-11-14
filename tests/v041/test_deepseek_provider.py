"""JUDGE-01：DeepSeek 适配器（走既有 `LLMProvider` 协议与既有调用路径）+ 用量账本。

## 为什么不新写一条 HTTP 调用路径

DeepSeek 是 **OpenAI 兼容**端点，而仓里已经有一个 OpenAI 兼容适配器：
`flint/llm/local.py#LocalProvider`（免费本地档走的就是它）。
再写一条 POST 就是 acceptance① 禁的「另建调用路径」——两条路径的重试语义、
错误分类、栅栏剥离迟早会分叉，而分叉之后没人知道哪条是对的。

所以本卡的适配器**继承 `LocalProvider`**，只加它没有的三件事：

1. **真价目**（`LocalProvider` 写死 `UsageMeter(pricing=FREE)`——对本地是对的，
   对付费档是错的）；
2. **缓存命中分开记**（`LocalProvider` 把 usage 压成 input/output 两项，
   丢掉了 `prompt_cache_hit_tokens`）；
3. **用途标签 + append-only 账本**。

拿到原始 usage 的办法是**注入一个会记住上一次响应体的 client**，
而不是去改 `local.py` 开一个钩子——改它就超出本卡 outputs 了。

## 三条红线

- **key 只从环境变量读**，永不进代码、仓库、日志、trace；
- **测试恒回放**，CI 里一次真调都没有；真实调用的录制件按 NET-02 留痕；
- **价目 NEVER 内置**：`usd_per_mtok_*` 全从环境读，账上的钱有出处。
"""
from __future__ import annotations

import inspect
import json
from decimal import Decimal
from pathlib import Path

import pytest

from flint.llm.deepseek import (
    DEEPSEEK_PROVIDER_ID,
    CachePriceUnknown,
    DeepSeekPricing,
    DeepSeekProvider,
    LedgerImmutable,
    UsageLedger,
    UsageRecord,
    breakdown_from_usage,
    load_deepseek_pricing,
    register_deepseek,
)

REPO = Path(__file__).resolve().parents[2]
FIXTURE = REPO / "fixtures" / "deepseek" / "chat_completion_minimal.json"

ENV = {
    "FLINT_DEEPSEEK_API_KEY": "sk-not-a-real-key",
    "FLINT_DEEPSEEK_MODEL": "deepseek-v4-flash",
    "FLINT_DEEPSEEK_USD_PER_MTOK_INPUT": "0.14",
    "FLINT_DEEPSEEK_USD_PER_MTOK_OUTPUT": "0.28",
    "FLINT_DEEPSEEK_USD_PER_MTOK_CACHE_HIT": "0.0028",
}


def _recorded_payload() -> dict:
    record = json.loads(FIXTURE.read_text(encoding="utf-8"))[0]
    return json.loads(record["body_text"])


class _Response:
    def __init__(self, payload: object, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def json(self) -> object:
        return self._payload


class _Client:
    """替身 client：**测试恒回放**，一次真实网络调用都没有。"""

    def __init__(self, payload: object, status_code: int = 200) -> None:
        self._payload = payload
        self._status = status_code
        self.posts: list[dict] = []

    def post(self, url: str, json: dict) -> _Response:
        self.posts.append({"url": url, "body": json})
        return _Response(self._payload, self._status)


def _provider(payload: object | None = None, **kw: object) -> DeepSeekProvider:
    return DeepSeekProvider(
        api_key="sk-not-a-real-key",
        model="deepseek-v4-flash",
        pricing=load_deepseek_pricing(ENV),
        http_client=_Client(payload if payload is not None else _recorded_payload()),
        **kw,  # type: ignore[arg-type]
    )


# ───────────────────────── 一、走既有协议与既有路径（acceptance①）


def test_it_satisfies_the_frozen_provider_protocol() -> None:
    """冻结协议 `LLMProvider` 的两个方法**逐字**都在（名字 + 形参名 + 顺序）。

    用签名比对而不是 `isinstance`：冻结件的 `LLMProvider` 没有
    `@runtime_checkable`，isinstance 直接抛 TypeError；而给冻结件加装饰器
    是改冻结件（S2-1 禁）。
    """
    from flint.domain.protocols import LLMProvider

    provider = _provider()
    for name in ("generate", "generate_structured"):
        expected = inspect.signature(getattr(LLMProvider, name))
        actual = inspect.signature(getattr(provider, name))
        assert list(actual.parameters) == [
            p for p in expected.parameters if p != "self"
        ], f"{name} 的形参与冻结协议不一致：{actual}"


def test_it_reuses_the_existing_openai_compatible_adapter() -> None:
    """acceptance①：**NEVER 另建调用路径**——继承既有的 OpenAI 兼容适配器。

    再写一条 POST 的话，两条路径的重试语义、错误分类、栅栏剥离迟早会分叉，
    而分叉之后没人知道哪条是对的。
    """
    from flint.llm.cloud import CloudOpenAIProvider

    # 判的是**最贴的那一层**：`CloudOpenAIProvider` 已经把「云端 = 本地传输 +
    # key 必填 + 真价目」写好了。只判「是不是 LocalProvider 的子类」不行——
    # 直接继承 LocalProvider 也满足那条，而那正是本卡第一版犯的错：
    # 把 cloud 那一层又写了一遍（差一层就是一份影子实现）。
    assert issubclass(DeepSeekProvider, CloudOpenAIProvider)


def test_the_module_does_not_build_its_own_request_path() -> None:
    """acceptance①：请求路径是**继承**来的，本模块不自己拼端点。

    判据钉在两件结构上：
    1. 代码面里没有 `/chat/completions` 字面量——拼端点是「另建路径」的第一步；
    2. 唯一的 `.post(` 是包装层对**注入进来的那个 client** 的转发
       （`self._inner.post`），不是对某个自己造的 client。

    只判「有没有 post(」不行：包装层的转发本来就该有一个，
    而按字面找会把 docstring 里那句「再写一条 POST」也算进来。
    """
    import ast

    from flint.llm import deepseek

    source = inspect.getsource(deepseek)
    code = "\n".join(
        line for line in source.splitlines() if not line.strip().startswith("#")
    )
    tree = ast.parse(source)

    posts = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        and node.func.attr == "post"
    ]
    targets = [
        n.func.value.attr for n in posts
        if isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Attribute)
    ]

    assert "/chat/completions" not in code, "模块自己拼了端点路径"
    assert targets == ["_inner"], f"post 的对象不只是被注入的 client：{targets}"


def test_it_hits_the_chat_completions_path() -> None:
    """端点路径就是 steward 实测确认的那条（OpenAI 兼容 `/chat/completions`）。"""
    provider = _provider()
    provider.generate("你好", tools=None)

    assert provider.recorder.posts[0]["url"].endswith("/chat/completions")
    assert provider.recorder.posts[0]["url"].startswith("https://api.deepseek.com")


def test_it_registers_through_the_existing_registry() -> None:
    """走既有 `ProviderRegistry`，tier=paid，**工厂零参**（配置在闭包里）。"""
    from flint.llm.registry import ProviderRegistry

    registry = ProviderRegistry()
    register_deepseek(registry, env=ENV, http_client=_Client(_recorded_payload()))

    assert registry.available_for_tier("paid") == [DEEPSEEK_PROVIDER_ID]
    assert isinstance(registry.get(DEEPSEEK_PROVIDER_ID), DeepSeekProvider)


def test_registering_twice_is_refused() -> None:
    """重复注册拒绝（既有 registry 的纪律：NEVER 静默覆盖）。"""
    from flint.llm.registry import ProviderAlreadyRegistered, ProviderRegistry

    registry = ProviderRegistry()
    register_deepseek(registry, env=ENV, http_client=_Client(_recorded_payload()))

    with pytest.raises(ProviderAlreadyRegistered):
        register_deepseek(registry, env=ENV, http_client=_Client(_recorded_payload()))


# ───────────────────────── 二、key 只从环境读（acceptance②）


def test_the_key_never_appears_in_the_source() -> None:
    """acceptance②：key 永不进代码。**扫的是代码面**，不是注释。"""
    from flint.llm import deepseek

    code = "\n".join(
        line for line in inspect.getsource(deepseek).split("\n")
        if not line.strip().startswith("#")
    )

    assert "sk-" not in code, "源码里出现了形似 key 的字面量"


def test_a_missing_key_names_the_variable_not_its_value() -> None:
    """缺配置时**只列变量名**，NEVER 回显任何值（尤其 key）。"""
    from flint.llm.production import ProviderWiringError

    incomplete = {k: v for k, v in ENV.items() if k != "FLINT_DEEPSEEK_API_KEY"}

    with pytest.raises(ProviderWiringError) as err:
        load_deepseek_pricing(incomplete, require_key=True)

    assert "FLINT_DEEPSEEK_API_KEY" in str(err.value)
    assert ENV["FLINT_DEEPSEEK_API_KEY"] not in str(err.value)


def test_the_ledger_never_stores_the_key() -> None:
    """账本里一条记录都不带 key——账要能给人看，key 不能。"""
    provider = _provider()
    provider.generate_with_purpose("你好", purpose="judge_calibration")

    dumped = json.dumps([r.as_dict() for r in provider.ledger.records()],
                        ensure_ascii=False)

    assert "sk-" not in dumped


# ───────────────────────── 三、每次调用记账（acceptance③）


def test_every_call_lands_one_ledger_record() -> None:
    """acceptance③：每次调用记一笔——token 数、金额、用途标签。"""
    provider = _provider()

    provider.generate_with_purpose("你好", purpose="judge_calibration")

    records = provider.ledger.records()
    assert len(records) == 1
    assert records[0].purpose == "judge_calibration"
    assert records[0].input_tokens > 0
    assert records[0].output_tokens > 0


def test_two_calls_land_two_records_in_order() -> None:
    """账本 append-only 且**按顺序**：对账要能顺着看下来。"""
    provider = _provider()

    provider.generate_with_purpose("一", purpose="a")
    provider.generate_with_purpose("二", purpose="b")

    assert [r.purpose for r in provider.ledger.records()] == ["a", "b"]


def test_the_ledger_refuses_to_be_rewritten() -> None:
    """账一旦会改，它就不是账了（与 `flint/billing/ledger.py` 同一条纪律）。"""
    ledger = UsageLedger()
    record = UsageRecord(
        call_id="c1", model="m", purpose="p", input_tokens=1, output_tokens=1,
        cache_hit_tokens=0, cache_miss_tokens=1, cost_usd=Decimal(0),
        pricing_version="v1",
    )
    ledger.append(record)

    with pytest.raises(LedgerImmutable):
        ledger.append(record)


def test_the_returned_records_are_copies() -> None:
    """返回副本：改返回值 NEVER 影响账本。"""
    provider = _provider()
    provider.generate_with_purpose("你好", purpose="p")

    provider.ledger.records().clear()

    assert len(provider.ledger.records()) == 1


def test_the_cost_comes_from_the_configured_price_not_a_built_in_table() -> None:
    """价目从环境读——**账上的钱有出处**（S2 三通道：数字必有出处）。

    价目改一半就该改一半：把输入单价翻倍，这一笔的钱必须跟着变。
    """
    cheap = _provider()
    cheap.generate_with_purpose("你好", purpose="p")

    dear_pricing = load_deepseek_pricing({**ENV, "FLINT_DEEPSEEK_USD_PER_MTOK_INPUT": "1.4"})
    dear = DeepSeekProvider(
        api_key="sk-not-a-real-key", model="deepseek-v4-flash", pricing=dear_pricing,
        http_client=_Client(_recorded_payload()),
    )
    dear.generate_with_purpose("你好", purpose="p")

    assert dear.ledger.records()[0].cost_usd > cheap.ledger.records()[0].cost_usd


def test_the_pricing_version_travels_with_the_record() -> None:
    """口径版本记在每一笔上：两次改价之间的账混在一起就再也分不开。"""
    provider = _provider()
    provider.generate_with_purpose("你好", purpose="p")

    assert provider.ledger.records()[0].pricing_version == provider.pricing.version


def test_the_version_changes_when_the_price_changes() -> None:
    """口径版本**由单价算出**：改了价，版本必须跟着变。

    写死一个 `v1` 的话，`mixed_pricing` 那道对账门就永远报不出混用——
    两次改价之间的账混在一起，而对账表上看起来只有一个口径
    （变异考实测：版本写成常量，29 条全绿）。
    """
    cheap = DeepSeekPricing(usd_per_mtok_input=0.14, usd_per_mtok_output=0.28,
                            usd_per_mtok_cache_hit=0.0028)
    dear = DeepSeekPricing(usd_per_mtok_input=1.4, usd_per_mtok_output=0.28,
                           usd_per_mtok_cache_hit=0.0028)
    no_hit = DeepSeekPricing(usd_per_mtok_input=0.14, usd_per_mtok_output=0.28,
                             usd_per_mtok_cache_hit=None)

    assert len({cheap.version, dear.version, no_hit.version}) == 3


def test_the_ledger_reconciles_and_flags_mixed_pricing() -> None:
    """对账：笔数 + 金额合计 + **口径混用要报出来**（照 SHIP-01 的既有形状）。"""
    ledger = UsageLedger()
    for i, version in enumerate(("v1", "v2")):
        ledger.append(UsageRecord(
            call_id=f"c{i}", model="m", purpose="p", input_tokens=10, output_tokens=5,
            cache_hit_tokens=0, cache_miss_tokens=10, cost_usd=Decimal("0.001"),
            pricing_version=version,
        ))

    summary = ledger.reconcile()

    assert summary["count"] == 2
    assert summary["total_usd"] == Decimal("0.002")
    assert summary["mixed_pricing"] is True


# ───────────────────────── 四、缓存命中分开记（acceptance⑤）


def test_cache_hit_tokens_are_recorded_separately() -> None:
    """acceptance⑤：命中的 token **单独一栏**，不混进 miss。"""
    payload = _recorded_payload()
    payload["usage"] = {
        "prompt_tokens": 100, "completion_tokens": 10,
        "prompt_cache_hit_tokens": 64, "prompt_cache_miss_tokens": 36,
    }
    provider = _provider(payload)

    provider.generate_with_purpose("你好", purpose="p")
    record = provider.ledger.records()[0]

    assert record.cache_hit_tokens == 64
    assert record.cache_miss_tokens == 36
    assert record.input_tokens == 100


def test_a_cache_hit_is_charged_at_the_hit_price() -> None:
    """命中按**命中价**计。DeepSeek 的命中价比未命中低两个数量级，

    按未命中价算就是把一笔省下来的钱记成花掉了——账会与账单对不上。
    """
    hit_payload = _recorded_payload()
    hit_payload["usage"] = {
        "prompt_tokens": 1000, "completion_tokens": 0,
        "prompt_cache_hit_tokens": 1000, "prompt_cache_miss_tokens": 0,
    }
    miss_payload = _recorded_payload()
    miss_payload["usage"] = {
        "prompt_tokens": 1000, "completion_tokens": 0,
        "prompt_cache_hit_tokens": 0, "prompt_cache_miss_tokens": 1000,
    }

    hit = _provider(hit_payload)
    hit.generate_with_purpose("x", purpose="p")
    miss = _provider(miss_payload)
    miss.generate_with_purpose("x", purpose="p")

    assert hit.ledger.records()[0].cost_usd < miss.ledger.records()[0].cost_usd


def test_a_hit_without_a_configured_hit_price_is_refused() -> None:
    """没配命中价却出现了命中 → **报错**，NEVER 按未命中价顶上。

    顶上去的账会**高于**真实账单，而账对不上时最难查的正是这种「差一点」。
    """
    no_hit_price = {k: v for k, v in ENV.items()
                    if k != "FLINT_DEEPSEEK_USD_PER_MTOK_CACHE_HIT"}
    payload = _recorded_payload()
    payload["usage"] = {
        "prompt_tokens": 100, "completion_tokens": 1,
        "prompt_cache_hit_tokens": 64, "prompt_cache_miss_tokens": 36,
    }
    provider = DeepSeekProvider(
        api_key="sk-not-a-real-key", model="deepseek-v4-flash",
        pricing=load_deepseek_pricing(no_hit_price),
        http_client=_Client(payload),
    )

    with pytest.raises(CachePriceUnknown):
        provider.generate_with_purpose("x", purpose="p")


def test_no_hit_without_a_hit_price_is_fine() -> None:
    """阴性对照：没有命中时，缺命中价**不该**报错——否则这道门会拦住正常调用。"""
    no_hit_price = {k: v for k, v in ENV.items()
                    if k != "FLINT_DEEPSEEK_USD_PER_MTOK_CACHE_HIT"}
    provider = DeepSeekProvider(
        api_key="sk-not-a-real-key", model="deepseek-v4-flash",
        pricing=load_deepseek_pricing(no_hit_price),
        http_client=_Client(_recorded_payload()),
    )

    provider.generate_with_purpose("x", purpose="p")

    assert provider.ledger.records()[0].cache_hit_tokens == 0


def test_a_usage_without_cache_fields_does_not_invent_them() -> None:
    """响应里没有缓存字段时，两栏都记 0 并把全部输入算作未命中——

    **NEVER 编一个命中数**：编出来的数会让账看起来比真实更省。
    """
    breakdown = breakdown_from_usage({"prompt_tokens": 30, "completion_tokens": 7})

    assert breakdown.cache_hit_tokens == 0
    assert breakdown.cache_miss_tokens == 30
    assert breakdown.input_tokens == 30


def test_the_two_halves_add_up_to_the_input_total() -> None:
    """命中 + 未命中 = 输入总数。对不上就是解析错了，NEVER 静默放行。"""
    with pytest.raises(ValueError):
        breakdown_from_usage({
            "prompt_tokens": 100, "completion_tokens": 1,
            "prompt_cache_hit_tokens": 64, "prompt_cache_miss_tokens": 20,
        })


# ───────────────────────── 五、录制回放（acceptance④）


def test_the_recorded_response_is_on_disk_with_its_manifest() -> None:
    """acceptance④：真实调用留 NET-02 三件套（原件 + URL + 时间 + sha256）。"""
    from flint.sources.provenance import manifest_path_for, verify_fixture

    assert FIXTURE.exists(), "没有录制件 = 解析器是照猜的形状写的"
    assert verify_fixture(FIXTURE, manifest_path_for(FIXTURE)) == []


def test_the_recorded_response_has_the_fields_the_parser_reads() -> None:
    """解析器读的每个字段，在**真实响应**里都存在。"""
    usage = _recorded_payload()["usage"]

    for field in ("prompt_tokens", "completion_tokens",
                  "prompt_cache_hit_tokens", "prompt_cache_miss_tokens"):
        assert field in usage, f"真实响应里没有 {field}——解析器读的是编出来的字段"


def test_the_recorded_manifest_carries_no_key() -> None:
    """录制件与它的清单里**没有 key**：录制是留痕，不是泄密。"""
    from flint.sources.provenance import manifest_path_for

    for path in (FIXTURE, manifest_path_for(FIXTURE)):
        text = path.read_text(encoding="utf-8")
        assert "sk-" not in text, f"{path.name} 里出现了形似 key 的串"
        assert "Authorization" not in text


def test_the_test_module_makes_no_live_call() -> None:
    """本文件零真实网络：替身 client 注入，CI 一次都不发（S2-7）。"""
    from tools.check_no_live_network import scan_source as net_scan

    source = Path(__file__).read_text(encoding="utf-8")

    assert net_scan(source, "tests/v041/test_deepseek_provider.py") == []


# ───────────────────────── 六、`.env.example` 与代码对得上（acceptance⑥）


def test_the_env_template_uses_the_prefix_the_code_reads() -> None:
    """acceptance⑥：模板写 `ANTHROPIC_API_KEY=`，代码读 `FLINT_ANTHROPIC_API_KEY`。

    照旧模板配会配不上，而**失败形态是「key 读不到」而不是「模板写错」**——
    人会去查代码，不会去查自己那行模板。
    """
    template = (REPO / ".env.example").read_text(encoding="utf-8")
    names = {
        line.split("=", 1)[0].lstrip("# ").strip()
        for line in template.splitlines() if "=" in line
    }

    assert "FLINT_ANTHROPIC_API_KEY" in names
    assert "ANTHROPIC_API_KEY" not in names, "旧的无前缀写法还在"


def test_the_template_covers_every_var_the_loaders_read() -> None:
    """两个云端档的变量**全在模板里**——少一个就是一次配不上的部署。"""
    template = (REPO / ".env.example").read_text(encoding="utf-8")

    for prefix in ("FLINT_DEEPSEEK", "FLINT_OPENAI"):
        for suffix in ("_API_KEY", "_MODEL", "_USD_PER_MTOK_INPUT", "_USD_PER_MTOK_OUTPUT"):
            assert f"{prefix}{suffix}" in template, f"模板缺 {prefix}{suffix}"


def test_the_template_holds_no_real_value() -> None:
    """模板里**一个真实值都没有**：它是模板，不是配置。"""
    template = (REPO / ".env.example").read_text(encoding="utf-8")

    assert "sk-" not in template
