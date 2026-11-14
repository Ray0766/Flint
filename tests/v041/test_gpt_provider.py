"""JUDGE-04：GPT-5.6 三档接入（第二校准点与仲裁票）。

## 三档按用途分工，NEVER 同级互校

卡面写死了分工与理由：

| 档 | 用途 | 为什么是它 |
|---|---|---|
| **Luna** | 大批量低难度分类；DeepSeek 的**产能备胎** | 便宜 |
| **Terra** | **校准票**（默认） | 校准票是「当裁判的裁判」，必须至少与被校准者同级或更强 |
| **Sol** | **仲裁票**，三家分歧时才动 | 最强，只在打平时花这笔钱 |

**Luna 不能当校准票**：它与 DeepSeek V4 Flash 同级——拿同级模型校准，
一致也不代表对、不一致也无法归因。而整批只需 1~3 次校准，
Luna 相对 Terra 只省不到 3 美元，**换不来这个代价**。

## 本地备胎优先于云端备胎

产能不够时先用本机 `deepseek-r1:32b`（零成本），`gpt-5.6-luna` 是**第二**备胎。
能不花钱就不花——这条有断言守着顺序。

## 价目 NEVER 内置

三档的单价全从环境读。**没配价的档 = 不可用**，NEVER 拿卡面上的数当默认值：
卡面是人写的一句话，环境变量是这台机器的事实，两者不是一回事。
"""
from __future__ import annotations

import inspect
from decimal import Decimal
from pathlib import Path

import pytest

from flint.llm.openai_compat import (
    GPT_MODELS,
    ROLE_ARBITRATION,
    ROLE_BULK,
    ROLE_CALIBRATION,
    BalanceExhausted,
    BalanceGuard,
    GptRoleUnavailable,
    OpenAICompatProvider,
    choose_capacity_backup,
    load_gpt_roles,
    register_gpt_roles,
)

REPO = Path(__file__).resolve().parents[2]

ENV = {
    "FLINT_OPENAI_API_KEY": "sk-not-a-real-key",
    "FLINT_OPENAI_BULK_USD_PER_MTOK_INPUT": "0.20",
    "FLINT_OPENAI_BULK_USD_PER_MTOK_OUTPUT": "1.20",
    "FLINT_OPENAI_CALIBRATION_USD_PER_MTOK_INPUT": "2.00",
    "FLINT_OPENAI_CALIBRATION_USD_PER_MTOK_OUTPUT": "12.00",
    "FLINT_OPENAI_ARBITRATION_USD_PER_MTOK_INPUT": "5.00",
    "FLINT_OPENAI_ARBITRATION_USD_PER_MTOK_OUTPUT": "30.00",
}

REPLY = {
    "id": "x", "choices": [{"message": {"content": "ok"}}],
    "usage": {"prompt_tokens": 10, "completion_tokens": 2},
}


class _Response:
    status_code = 200

    @staticmethod
    def json() -> object:
        return REPLY


class _Client:
    """替身 client：**测试恒回放**，一次真实调用都没有。"""

    def __init__(self) -> None:
        self.posts: list[dict] = []

    def post(self, url: str, json: dict) -> _Response:
        self.posts.append({"url": url, "body": json})
        return _Response()


def _provider(role: str = ROLE_CALIBRATION) -> OpenAICompatProvider:
    spec = load_gpt_roles(ENV)[role]
    return OpenAICompatProvider(
        api_key="sk-not-a-real-key", model=spec.model, pricing=spec.pricing,
        role=role, http_client=_Client())


# ───────────────────────── 一、复用既有适配器（acceptance①）


def test_it_reuses_the_existing_cloud_adapter() -> None:
    """acceptance①：**复用 `flint/llm/cloud.py`**，NEVER 另建调用路径。

    判的是最贴的那一层：`CloudOpenAIProvider` 已经把「云端 = 本地传输 +
    key 必填 + 真价目」写好了。只判「是不是 LocalProvider 的子类」不行——
    直接继承 LocalProvider 也满足那条，而那正是 JUDGE-01 犯过的错。
    """
    from flint.llm.cloud import CloudOpenAIProvider

    assert issubclass(OpenAICompatProvider, CloudOpenAIProvider)


def test_the_module_does_not_build_its_own_request_path() -> None:
    """模块里不自己拼端点——请求路径是继承来的。"""
    from flint.llm import openai_compat

    code = "\n".join(
        line for line in inspect.getsource(openai_compat).splitlines()
        if not line.strip().startswith("#")
    )

    assert "/chat/completions" not in code


def test_it_satisfies_the_frozen_provider_protocol() -> None:
    """冻结协议 `LLMProvider` 的两个方法逐字都在（名字 + 形参名 + 顺序）。"""
    from flint.domain.protocols import LLMProvider

    provider = _provider()
    for name in ("generate", "generate_structured"):
        expected = inspect.signature(getattr(LLMProvider, name))
        actual = inspect.signature(getattr(provider, name))
        assert list(actual.parameters) == [
            p for p in expected.parameters if p != "self"]


# ───────────────────────── 二、三档分工（acceptance①）


def test_the_three_roles_map_to_the_three_confirmed_model_ids() -> None:
    """三个模型 id 是 steward 实测确认过的，**NEVER 再猜**。"""
    assert GPT_MODELS[ROLE_BULK] == "gpt-5.6-luna"
    assert GPT_MODELS[ROLE_CALIBRATION] == "gpt-5.6-terra"
    assert GPT_MODELS[ROLE_ARBITRATION] == "gpt-5.6-sol"


def test_the_calibration_vote_is_never_the_cheap_tier() -> None:
    """**NEVER 用同级模型互校**：校准票不能落到 Luna 上。

    Luna 与 DeepSeek V4 Flash 同级——拿它校准，一致也不代表对、
    不一致也无法归因。这条是本卡最要紧的一条分工。
    """
    roles = load_gpt_roles(ENV)

    assert roles[ROLE_CALIBRATION].model != GPT_MODELS[ROLE_BULK]
    assert roles[ROLE_CALIBRATION].pricing.usd_per_mtok_input > \
        roles[ROLE_BULK].pricing.usd_per_mtok_input


def test_the_arbitration_tier_is_the_dearest_and_last() -> None:
    """仲裁票最贵，所以**只在三家分歧时才动**——它的价就是它的使用纪律。"""
    roles = load_gpt_roles(ENV)

    assert roles[ROLE_ARBITRATION].pricing.usd_per_mtok_output > \
        roles[ROLE_CALIBRATION].pricing.usd_per_mtok_output
    assert roles[ROLE_ARBITRATION].when == "three_way_disagreement"


def test_each_role_says_what_it_is_for() -> None:
    """每档都带一句用途——没有用途说明的档位，下一个人只会挑最便宜的那个。"""
    for spec in load_gpt_roles(ENV).values():
        assert len(spec.purpose) >= 10


# ───────────────────────── 三、价目从环境读，没配即不可用


def test_a_role_without_configured_prices_is_unavailable() -> None:
    """**没配价的档 = 不可用**，NEVER 拿卡面上的数当默认值。

    卡面是人写的一句话，环境变量是这台机器的事实，两者不是一回事——
    把卡面的数当默认，账就会按一个没人确认过的价记。
    """
    partial = {k: v for k, v in ENV.items() if "ARBITRATION" not in k}

    roles = load_gpt_roles(partial)

    assert ROLE_ARBITRATION not in roles
    with pytest.raises(GptRoleUnavailable) as err:
        roles[ROLE_ARBITRATION]  # type: ignore[misc]
    assert "FLINT_OPENAI_ARBITRATION_USD_PER_MTOK_INPUT" in str(err.value)


def test_the_error_names_the_variable_not_its_value() -> None:
    """缺配置只列变量名，NEVER 回显任何值（尤其 key）。"""
    no_key = {k: v for k, v in ENV.items() if k != "FLINT_OPENAI_API_KEY"}

    with pytest.raises(Exception) as err:
        load_gpt_roles(no_key, require_key=True)

    assert "FLINT_OPENAI_API_KEY" in str(err.value)
    assert ENV["FLINT_OPENAI_API_KEY"] not in str(err.value)


def test_the_key_never_appears_in_the_source() -> None:
    """key 永不进代码。扫的是**代码面**，不是注释。"""
    from flint.llm import openai_compat

    code = "\n".join(
        line for line in inspect.getsource(openai_compat).splitlines()
        if not line.strip().startswith("#")
    )

    assert "sk-" not in code


# ───────────────────────── 四、本地备胎优先（acceptance③）


def test_the_local_backup_comes_before_the_cloud_one() -> None:
    """acceptance③：**能不花钱就不花**——本机模型排在云端便宜档前面。"""
    order = choose_capacity_backup(local_available=True, cloud_available=True)

    assert order[0].startswith("local:")
    assert order[1] == GPT_MODELS[ROLE_BULK]


def test_the_cloud_backup_is_used_when_local_is_down() -> None:
    """阴性对照：本机不可用时才轮到云端——否则这条顺序等于禁用了云端备胎。"""
    order = choose_capacity_backup(local_available=False, cloud_available=True)

    assert order == [GPT_MODELS[ROLE_BULK]]


def test_no_backup_at_all_is_an_empty_list_not_a_guess() -> None:
    """两个都不可用时返回**空**，NEVER 回落到某个默认模型。"""
    assert choose_capacity_backup(local_available=False, cloud_available=False) == []


def test_the_local_backup_is_the_model_the_card_names() -> None:
    """本机备胎就是 owner 说的那个（已在 ollama 里），不是随便挑一个。"""
    order = choose_capacity_backup(local_available=True, cloud_available=False)

    assert order == ["local:deepseek-r1:32b"]


# ───────────────────────── 五、余额将尽照实降级（acceptance⑤）


def test_spending_is_allowed_while_there_is_budget() -> None:
    guard = BalanceGuard(budget_usd=Decimal(20), spent_usd=Decimal(1))

    assert guard.may_spend(Decimal("0.5")) is True
    assert guard.degraded is False


def test_crossing_the_budget_degrades_and_says_so() -> None:
    """余额将尽 → **降级并照实标注**，NEVER 静默失败。"""
    guard = BalanceGuard(budget_usd=Decimal(20), spent_usd=Decimal("19.9"))

    assert guard.may_spend(Decimal("0.5")) is False
    assert guard.degraded is True
    # 说明要包含**数**与**后果**两半：只说「余额将尽」的话，
    # 读的人不知道接下来发生了什么（变异考实测：把后果那句删掉，25 条全绿）。
    assert "余额" in guard.note and "20" in guard.note
    assert "未校准" in guard.note or "不调用" in guard.note, (
        f"降级说明没写后果：{guard.note}")


def test_a_spend_past_the_budget_raises_rather_than_silently_succeeding() -> None:
    """真花超了要**报错**：静默花超会让账单上出现没人预期的一笔。"""
    guard = BalanceGuard(budget_usd=Decimal(20), spent_usd=Decimal(20))

    with pytest.raises(BalanceExhausted):
        guard.charge(Decimal("0.01"))


def test_the_guard_records_what_it_already_spent() -> None:
    """花过的钱累进去——不累的话，这道门第一次之后就永远放行。"""
    guard = BalanceGuard(budget_usd=Decimal(20), spent_usd=Decimal(0))

    guard.charge(Decimal(3))
    guard.charge(Decimal(2))

    assert guard.spent_usd == Decimal(5)


def test_the_note_is_empty_while_healthy() -> None:
    """阴性对照：没降级时**不带**降级说明——每次都带等于没带。"""
    guard = BalanceGuard(budget_usd=Decimal(20), spent_usd=Decimal(0))

    assert guard.note == ""


# ───────────────────────── 六、同一本账（acceptance⑤）


def test_a_call_lands_a_record_in_the_same_ledger_type() -> None:
    """acceptance⑤：用量记账与 DeepSeek **同一本账**（同一个 `UsageLedger`）。"""
    from flint.llm.deepseek import UsageLedger

    provider = _provider()
    provider.generate_with_purpose("hi", purpose="judge_calibration")

    assert isinstance(provider.ledger, UsageLedger)
    record = provider.ledger.records()[0]
    assert record.purpose == "judge_calibration"
    assert record.input_tokens == 10 and record.output_tokens == 2


def test_the_record_carries_the_role_so_the_bill_can_be_split() -> None:
    """账上要看得出这笔是哪一档花的——三档单价差 25 倍，混在一起没法归因。

    用途标签故意**不含档位名**：传 `purpose="arbitration"` 的话，
    档位从 model 字段里拿掉也照样绿——判的就成了「我传进去的那个字符串」
    （变异考实测：25 条全过）。
    """
    provider = _provider(ROLE_ARBITRATION)
    provider.generate_with_purpose("hi", purpose="tie_break")

    record = provider.ledger.records()[0]
    assert ROLE_ARBITRATION in record.model, f"账上看不出档位：{record.model}"
    assert ROLE_ARBITRATION in record.pricing_version


def test_the_cost_uses_the_role_price() -> None:
    """贵档的同一次调用**更贵**——价目真的在用，不是记了不算。"""
    cheap = _provider(ROLE_BULK)
    cheap.generate_with_purpose("hi", purpose="p")
    dear = _provider(ROLE_ARBITRATION)
    dear.generate_with_purpose("hi", purpose="p")

    assert dear.ledger.records()[0].cost_usd > cheap.ledger.records()[0].cost_usd


# ───────────────────────── 七、注册进既有 registry


def test_the_roles_register_through_the_existing_registry() -> None:
    """走既有 `ProviderRegistry`，三档各占一个 provider_id，tier=paid。"""
    from flint.llm.registry import ProviderRegistry

    registry = ProviderRegistry()
    register_gpt_roles(registry, env=ENV, http_client=_Client())

    assert registry.available_for_tier("paid") == sorted(
        f"gpt:{role}" for role in (ROLE_BULK, ROLE_CALIBRATION, ROLE_ARBITRATION))


def test_an_unconfigured_role_is_not_registered() -> None:
    """没配价的档**不进注册表**——注册了却不能用，比没注册更难查。"""
    from flint.llm.registry import ProviderRegistry

    partial = {k: v for k, v in ENV.items() if "ARBITRATION" not in k}
    registry = ProviderRegistry()
    register_gpt_roles(registry, env=partial, http_client=_Client())

    assert f"gpt:{ROLE_ARBITRATION}" not in registry.available()


def test_the_test_module_makes_no_live_call() -> None:
    """本文件零真实网络（S2-7）。"""
    from tools.check_no_live_network import scan_source as net_scan

    assert net_scan(Path(__file__).read_text(encoding="utf-8"),
                    "tests/v041/test_gpt_provider.py") == []
