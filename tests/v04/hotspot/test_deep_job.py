"""HOTSPOT-04 验收：AI 深度分析按钮 → 既有 JobRunner（计费落点为配置开关）。

acceptance（tasks-v04.json#HOTSPOT-04）：
① job 提交走既有 runner（§6-H7）；LLM 恒 mock 注入 NEVER 真实调用；
② 计费落点为配置开关（K7 两态皆可运行）。

## 为什么「按钮」这张卡的重点全在**不做什么**

深度分析是这个产品里唯一一处「点一下就花钱」的动作。所以这一张卡的价值不在
它能提交作业，而在三条边界：**不新写 runner**（新写一个就有了第二套幂等键与
重试语义，同一个按钮点两下可能跑出两笔账）、**不在提交路径上碰 LLM**
（按钮按下到作业入队之间一次模型调用都不该有，否则每次点开都在付钱）、
**计费开关关掉时零计费落点调用**（K7 未决期间免费/付费两条路线都要能跑）。

计费开关打开而落点没接时**大声失败**：静默跳过等于把付费运行免费送出去，
而且送出去的那些跑没有任何记录——比报错难查得多。
"""
from __future__ import annotations

import ast
import asyncio
from collections.abc import Coroutine
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from flint.analysis.deep_job import (
    BILLING_FLAG,
    DEEP_ANALYSIS_JOB_KIND,
    DEEP_TIER,
    ChargeIntent,
    ChargeLandingMissing,
    DeepAnalysisPricing,
    deep_analysis_payload,
    submit_deep_analysis,
)
from flint.config import DEFAULT_FLAGS, FeatureFlags, InMemoryFlagStore
from flint.domain.models import JobKind, Principal

REPO_ROOT = Path(__file__).resolve().parents[3]
DEEP_JOB_SRC = REPO_ROOT / "flint" / "analysis" / "deep_job.py"

FREE_PRICING = DeepAnalysisPricing(budget=0.0, charge_cny=0.0)
PAID_PRICING = DeepAnalysisPricing(budget=2.5, charge_cny=19.0)



def run[T](coro: Coroutine[Any, Any, T]) -> T:
    return asyncio.run(coro)


@dataclass
class SpyRunner:
    """记录 submit 的假 runner。它只是**记录**——本卡断言的是提交面的形状。"""

    calls: list[dict[str, Any]]

    async def submit(
        self,
        kind: JobKind,
        payload: Any,
        budget: float,
        owner_scope: Principal,
        initiated_by: str,
    ) -> str:
        self.calls.append({
            "kind": kind, "payload": payload, "budget": budget,
            "owner_scope": owner_scope, "initiated_by": initiated_by,
        })
        return f"job-{len(self.calls)}"


@dataclass
class SpyProvider:
    """假 LLM provider：被调一次就记一次。提交路径上它应当**一次都不被调**。"""

    calls: list[str]

    def generate(self, prompt: str, **_: Any) -> str:
        self.calls.append(prompt)
        return "NEVER 该出现在提交路径上"


def _flags(billing: bool | None = None) -> FeatureFlags:
    store = InMemoryFlagStore()
    if billing is not None:
        store.write(BILLING_FLAG, billing)
    return FeatureFlags(store=store)


def _owner() -> Principal:
    return Principal(kind="user", id="u1")


def _submit(runner: SpyRunner, **kwargs: Any) -> Any:
    defaults: dict[str, Any] = {
        "cluster_id": "c-1", "lang": "zh", "owner_scope": _owner(),
        "initiated_by": "u1", "flags": _flags(), "pricing": FREE_PRICING,
    }
    defaults.update(kwargs)
    return run(submit_deep_analysis(runner, **defaults))


# ───────────────────────── acceptance ① 走既有 runner，零 LLM


def test_kind_is_a_contract_jobkind_never_a_new_one() -> None:
    """深度档用的是契约里既有的 gate1_analysis：档位是 payload 里的参数。

    造一个新的 JobKind 就要改冻结件（S2-1 NEVER）；而「深度」本来就是同一条
    分析链路的档位差异，不是另一种作业。
    """
    from typing import get_args

    assert DEEP_ANALYSIS_JOB_KIND == "gate1_analysis"
    assert DEEP_ANALYSIS_JOB_KIND in get_args(JobKind)


def test_submit_goes_through_the_injected_runner() -> None:
    runner = SpyRunner(calls=[])
    result = _submit(runner)

    assert len(runner.calls) == 1
    call = runner.calls[0]
    assert call["kind"] == DEEP_ANALYSIS_JOB_KIND
    assert call["payload"]["cluster_id"] == "c-1"
    assert call["payload"]["tier"] == DEEP_TIER
    assert call["payload"]["lang"] == "zh"
    assert call["initiated_by"] == "u1"
    assert result.job_id == "job-1"


def test_module_never_writes_its_own_runner() -> None:
    """§6-H7 的「不新写」断言：模块里没有 runner **实现**，也不碰 jobs 表 / arq 队列。

    断的是实现而不是名字：描述注入面的 Protocol（体恒为 `...`）不是第二套 runner，
    真正要挡的是「自己实现一个 submit」——那会带来第二份幂等键与重试语义。
    """
    source = DEEP_JOB_SRC.read_text(encoding="utf-8")
    tree = ast.parse(source)
    for cls in [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]:
        is_protocol = any(
            isinstance(b, ast.Name) and b.id == "Protocol" for b in cls.bases
        )
        methods = [
            n for n in cls.body if isinstance(n, ast.AsyncFunctionDef | ast.FunctionDef)
        ]
        submits = [m for m in methods if m.name == "submit"]
        if not is_protocol:
            assert submits == [], f"{cls.name} 自己实现了 submit"
            continue
        for m in submits:  # Protocol 体只许是 `...`，不许藏实现
            assert all(isinstance(stmt, ast.Expr) for stmt in m.body)
    for forbidden in ("INSERT INTO jobs", "asyncpg", "arq", "enqueue_job"):
        assert forbidden not in source, f"提交路径自己动手了：{forbidden}"


def test_submit_path_makes_zero_llm_calls() -> None:
    """按钮按下到作业入队之间，一次模型调用都没有。

    只断言「没有真实调用」不够——注入一个会记账的假 provider，断言它**一次都没被调**：
    真正的模型工作发生在 worker 里，提交面碰 LLM 就意味着每次点开都在付钱。
    """
    runner = SpyRunner(calls=[])
    provider = SpyProvider(calls=[])
    _submit(runner, provider=provider)

    assert provider.calls == []
    assert len(runner.calls) == 1  # 阴性对照：提交本身确实发生了，不是空转


def test_module_imports_no_real_provider_or_network() -> None:
    """静态断言：提交模块的 import 面里没有真实 provider、没有 HTTP 客户端。

    运行时断言只能证明「这次没调」；import 面断言让「改天在这里 new 一个真 provider」
    先红——真实 API key 与真实网络是 §7 的事前必审项，NEVER 由一张功能卡引入。
    """
    tree = ast.parse(DEEP_JOB_SRC.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)

    forbidden = ("anthropic", "httpx", "openai", "flint.llm.production",
                 "flint.llm.cloud", "flint.llm.provider")
    hits = [m for m in imported for f in forbidden if m == f or m.startswith(f + ".")]
    assert hits == [], f"提交模块接上了真实调用通道：{hits}"


def test_payload_rejects_empty_cluster() -> None:
    """空 cluster_id 直接拒：一个不指向任何热点的深度分析作业没有意义，
    而它一旦入队就会照常计费。"""
    with pytest.raises(ValueError):
        deep_analysis_payload(cluster_id="", lang="zh")


# ───────────────────────── acceptance ② 计费落点是配置开关（K7 两态）


def test_billing_flag_defaults_off() -> None:
    """K7 未决期间默认免费路线：开关缺省即关（既有 DEFAULT_FLAGS，不新写开关系统）。"""
    assert DEFAULT_FLAGS[BILLING_FLAG] is False
    assert _flags().is_enabled(BILLING_FLAG) is False


def test_billing_off_charges_nothing_but_still_runs() -> None:
    """关：计费落点零调用，作业照常提交，预算取免费档配置值。"""
    runner = SpyRunner(calls=[])
    charged: list[ChargeIntent] = []
    result = _submit(
        runner, flags=_flags(False), pricing=FREE_PRICING, charge=charged.append,
    )

    assert charged == []
    assert result.billed is False
    assert result.charge is None
    assert len(runner.calls) == 1
    assert runner.calls[0]["budget"] == FREE_PRICING.budget


def test_billing_on_charges_exactly_once_with_configured_amount() -> None:
    """开：计费落点恰一次，金额逐字来自配置——NEVER 内置价表猜价。"""
    runner = SpyRunner(calls=[])
    charged: list[ChargeIntent] = []
    result = _submit(
        runner, flags=_flags(True), pricing=PAID_PRICING, charge=charged.append,
    )

    assert len(charged) == 1
    assert charged[0].amount_cny == PAID_PRICING.charge_cny
    assert charged[0].cluster_id == "c-1"
    assert charged[0].job_id == result.job_id  # 账要挂在具体那次运行上
    assert charged[0].initiated_by == "u1"
    assert result.billed is True
    assert runner.calls[0]["budget"] == PAID_PRICING.budget


def test_billing_on_without_landing_fails_loudly() -> None:
    """开关打开却没接落点 → 报错，NEVER 静默跳过。

    静默跳过等于把付费运行免费送出去，且送出去的那些跑一条记录都没有——
    比报错难查得多。同时断言**作业没有被提交**：不能既不计费又照跑。
    """
    runner = SpyRunner(calls=[])
    with pytest.raises(ChargeLandingMissing):
        _submit(runner, flags=_flags(True), pricing=PAID_PRICING, charge=None)

    assert runner.calls == []


def test_billing_landing_failure_reports_the_created_job() -> None:
    """落点抛错时异常里带 job_id：作业已经建好了，NEVER 让它变成无人认领的一次运行。"""
    runner = SpyRunner(calls=[])

    def broken(_: ChargeIntent) -> None:
        raise RuntimeError("落点炸了")

    with pytest.raises(RuntimeError) as err:
        _submit(runner, flags=_flags(True), pricing=PAID_PRICING, charge=broken)

    assert len(runner.calls) == 1
    assert "job-1" in str(err.value)


def test_pricing_has_no_builtin_price_table() -> None:
    """价目必须由调用方给出：模块里 NEVER 藏一个默认金额。

    「数字必有出处」在计费这一处最要紧——一个内置的默认价会在没人注意时
    变成实际收费口径，而它的出处只有代码本身。
    """
    import inspect

    signature = inspect.signature(DeepAnalysisPricing.__init__)
    for name in ("budget", "charge_cny"):
        assert signature.parameters[name].default is inspect.Parameter.empty
