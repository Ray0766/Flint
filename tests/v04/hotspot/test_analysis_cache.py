"""HOTSPOT-05 验收：分析结果缓存（同参二次 0 新 job、0 计费）。

acceptance（tasks-v04.json#HOTSPOT-05）：
**缓存键 = cluster + lang + 档位 + 账本版本；二次请求 0 新 job 断言**。

## 四个要素少一个都会出事

- 少 **cluster**：不用说；
- 少 **lang**：中文点过一次，切英文再点会拿到中文那次的结果——用户看到的是
  一份读不懂的报告，而界面告诉他这就是最新分析；
- 少 **档位**：免费档点过之后再点深度档会直接回免费档结果，**钱花了、深度没给**；
- 少 **账本版本**：账本前进意味着事实变了，还回旧结果等于让用户拿着**过期判定**
  去做决定，而界面上没有任何迹象说明它是旧的。

## 「0 新 job」这条断言必须配阴性对照

第二次点击不新建作业，可能是因为缓存生效，也可能是因为**第一次就什么都没提交**。
所以每条复用测试都先断言第一次确实提交了、确实计了一次费。
"""
from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from dataclasses import dataclass
from typing import Any, TypeVar

import pytest

from flint.analysis.cache import (
    AnalysisCacheKey,
    InMemoryAnalysisCache,
    LedgerVersionUnknown,
    submit_or_reuse,
)
from flint.analysis.deep_job import BILLING_FLAG, DEEP_TIER, ChargeIntent, DeepAnalysisPricing
from flint.config import FeatureFlags, InMemoryFlagStore
from flint.domain.models import JobKind, Principal

PAID = DeepAnalysisPricing(budget=2.5, charge_cny=19.0)

T = TypeVar("T")


def run(coro: Coroutine[Any, Any, T]) -> T:
    return asyncio.run(coro)


@dataclass
class SpyRunner:
    calls: list[dict[str, Any]]

    async def submit(
        self, kind: JobKind, payload: Any, budget: float,
        owner_scope: Principal, initiated_by: str,
    ) -> str:
        self.calls.append({"kind": kind, "payload": payload, "budget": budget})
        return f"job-{len(self.calls)}"


def _flags(billing: bool = True) -> FeatureFlags:
    store = InMemoryFlagStore()
    store.write(BILLING_FLAG, billing)
    return FeatureFlags(store=store)


@dataclass
class Fixture:
    runner: SpyRunner
    cache: InMemoryAnalysisCache
    charged: list[ChargeIntent]
    flags: FeatureFlags

    def click(self, **kwargs: Any) -> Any:
        defaults: dict[str, Any] = {
            "cluster_id": "c-1", "lang": "zh", "tier": DEEP_TIER, "ledger_version": 7,
            "owner_scope": Principal(kind="user", id="u1"), "initiated_by": "u1",
            "flags": self.flags, "pricing": PAID, "cache": self.cache,
            "charge": self.charged.append,
        }
        defaults.update(kwargs)
        return run(submit_or_reuse(self.runner, **defaults))


@pytest.fixture
def fx() -> Fixture:
    return Fixture(
        runner=SpyRunner(calls=[]), cache=InMemoryAnalysisCache(),
        charged=[], flags=_flags(),
    )


# ───────────────────────── 同参二次：0 新 job、0 计费


def test_second_click_same_params_creates_no_job_and_no_charge(fx: Fixture) -> None:
    first = fx.click()
    assert len(fx.runner.calls) == 1        # 阴性对照：第一次真的提交了
    assert len(fx.charged) == 1             # 阴性对照：第一次真的计了费

    second = fx.click()

    assert len(fx.runner.calls) == 1        # 0 新 job
    assert len(fx.charged) == 1             # 0 新计费
    assert second.job_id == first.job_id    # 回的是同一次运行
    assert second.reused is True
    assert second.billed is False           # 复用这一次没有产生新账
    assert first.reused is False


def test_third_click_still_reuses(fx: Fixture) -> None:
    """连点不是只挡住第二下：第三下同样 0 新 job。"""
    fx.click()
    fx.click()
    fx.click()

    assert len(fx.runner.calls) == 1
    assert len(fx.charged) == 1


# ───────────────────────── 缓存键四要素：改任一即不复用


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("cluster_id", "c-2"),
        ("lang", "en"),
        ("tier", "free"),
        ("ledger_version", 8),
    ],
)
def test_each_key_element_breaks_reuse(fx: Fixture, field: str, value: Any) -> None:
    """四个要素各变一次都必须 miss。

    lang 变了还复用 → 用户看到一份读不懂的报告；档位变了还复用 → 钱花了深度没给；
    账本版本前进还复用 → 拿着过期判定做决定，而界面上没有任何迹象说明它是旧的。
    """
    fx.click()
    assert len(fx.runner.calls) == 1

    result = fx.click(**{field: value})

    assert len(fx.runner.calls) == 2, f"{field} 变了却复用了缓存"
    assert result.reused is False
    assert len(fx.charged) == 2  # 新的一次运行照常计费


def test_fingerprint_covers_exactly_the_four_elements() -> None:
    """键的指纹随四要素变化，且四要素相同即相同（换个顺序拼不出同一个键）。"""
    base = AnalysisCacheKey(cluster_id="c-1", lang="zh", tier="deep", ledger_version=7)
    same = AnalysisCacheKey(cluster_id="c-1", lang="zh", tier="deep", ledger_version=7)
    assert base.fingerprint() == same.fingerprint()

    for other in (
        AnalysisCacheKey(cluster_id="c-2", lang="zh", tier="deep", ledger_version=7),
        AnalysisCacheKey(cluster_id="c-1", lang="en", tier="deep", ledger_version=7),
        AnalysisCacheKey(cluster_id="c-1", lang="zh", tier="free", ledger_version=7),
        AnalysisCacheKey(cluster_id="c-1", lang="zh", tier="deep", ledger_version=8),
    ):
        assert other.fingerprint() != base.fingerprint()

    # 分隔符不可被内容伪造：("c-1|zh", ...) NEVER 与 ("c-1", "zh", ...) 撞同一个键
    forged = AnalysisCacheKey(cluster_id="c-1|zh", lang="", tier="deep", ledger_version=7)
    assert forged.fingerprint() != base.fingerprint()


# ───────────────────────── 不能证明是最新的，就不复用


def test_unknown_ledger_version_never_reuses(fx: Fixture) -> None:
    """账本版本未知 → 每次都是新作业，且什么都不进缓存。

    版本未知时无从判断缓存里那份是不是过期的。宁可多跑一次（用户看到的是当下事实），
    也 NEVER 回一份无法证明其时效的结果。
    """
    fx.click(ledger_version=None)
    fx.click(ledger_version=None)

    assert len(fx.runner.calls) == 2
    assert fx.cache.size() == 0


def test_cache_key_rejects_unknown_ledger_version() -> None:
    """键本身拒绝 None：不给「先建个键回头再补版本」留口子。"""
    with pytest.raises(LedgerVersionUnknown):
        AnalysisCacheKey(cluster_id="c-1", lang="zh", tier="deep", ledger_version=None)  # type: ignore[arg-type]


# ───────────────────────── 复用面的两条边界


def test_never_reuses_another_owners_run(fx: Fixture) -> None:
    """同一把键、不同租户 → 不复用。

    缓存回的是**别人那次运行的 job_id**；跨租户复用等于把另一个账号的作业交出去
    （D7 多租户）。故查表在租户命名空间内进行——键的四要素不变。
    """
    fx.click()
    result = fx.click(owner_scope=Principal(kind="user", id="u2"), initiated_by="u2")

    assert len(fx.runner.calls) == 2
    assert result.reused is False


def test_forgotten_entry_submits_again(fx: Fixture) -> None:
    """作业失败后调用方 forget → 下一次点击重新提交。

    否则一次失败的运行会被永久回放：用户每次点开都拿到同一个失败作业，
    而按钮看起来是好的。
    """
    first = fx.click()
    key = AnalysisCacheKey(cluster_id="c-1", lang="zh", tier=DEEP_TIER, ledger_version=7)
    fx.cache.forget("u1", key.fingerprint())

    second = fx.click()

    assert len(fx.runner.calls) == 2
    assert second.job_id != first.job_id
    assert second.reused is False


def test_module_never_writes_its_own_runner_or_flag_system() -> None:
    """§6-H7 复用断言：缓存层不自建提交路径，提交仍走 deep_job 的既有通道。"""
    from pathlib import Path

    src = Path(__file__).resolve().parents[3] / "flint" / "analysis" / "cache.py"
    source = src.read_text(encoding="utf-8")
    assert "from flint.analysis.deep_job import" in source
    for forbidden in ("INSERT INTO jobs", "asyncpg", "arq", "DEFAULT_FLAGS = "):
        assert forbidden not in source, f"缓存层自己动手了：{forbidden}"
