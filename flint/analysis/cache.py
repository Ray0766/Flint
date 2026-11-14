"""HOTSPOT-05：分析结果缓存（同参二次点击 0 新 job、0 计费）。

缓存键 = **cluster + lang + 档位 + 账本版本**（卡上 acceptance 逐字）。四个要素
少一个都会让用户看到一份「看起来是最新的、其实不是他要的」结果：

- 少 **lang**：中文点过一次，切英文再点回中文那份——用户拿到一份读不懂的报告；
- 少 **档位**：免费档点过之后点深度档直接回免费档结果，**钱花了、深度没给**；
- 少 **账本版本**：账本前进意味着事实变了，还回旧结果等于让用户拿着**过期判定**
  去做决定，而界面上没有任何迹象说明它是旧的。

## 账本版本未知时 NEVER 复用

版本未知就无从证明缓存里那份是不是过期的。宁可多跑一次（用户看到的是当下事实），
也不回一份**无法证明其时效**的结果——这与 A7/E6 的降级口径同源：缺就是缺。

## 查表在租户命名空间内进行

缓存回的是**别人那次运行的 job_id**，跨租户复用等于把另一个账号的作业交出去（D7）。
故键的四要素保持卡上口径不变，命名空间另走 owner——见 DECISIONS-v04.md#DEC-011。

## 失败的运行由调用方 forget

不给 forget 留口子的话，一次失败的运行会被永久回放：用户每次点开都拿到同一个
失败作业，而按钮看起来是好的。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from flint.analysis.deep_job import (
    DEEP_TIER,
    ChargeLanding,
    DeepAnalysisPricing,
    DeepAnalysisSubmission,
    submit_deep_analysis,
)
from flint.config import FeatureFlags

# 指纹分隔符：正文里出现它就转义，防 ("c-1|zh", "") 与 ("c-1", "zh") 撞同一个键。
_SEP = "|"
_ESCAPED = "\\|"


class LedgerVersionUnknown(Exception):
    """账本版本未知却要建缓存键。"""

    def __init__(self) -> None:
        super().__init__(
            "ledger_version NEVER 为空：版本未知时无从判断缓存是否过期，"
            "这种情况下不建键、不复用"
        )


@dataclass(frozen=True)
class AnalysisCacheKey:
    cluster_id: str
    lang: str
    tier: str
    ledger_version: int

    def __post_init__(self) -> None:
        if self.ledger_version is None:
            raise LedgerVersionUnknown

    def fingerprint(self) -> str:
        parts = (self.cluster_id, self.lang, self.tier, str(self.ledger_version))
        return _SEP.join(p.replace(_SEP, _ESCAPED) for p in parts)


class AnalysisCacheStore(Protocol):
    """缓存后端。查表带 owner 命名空间（D7），键本身保持四要素口径。"""

    def get(self, owner_id: str, fingerprint: str) -> str | None: ...

    def remember(self, owner_id: str, fingerprint: str, job_id: str) -> None: ...

    def forget(self, owner_id: str, fingerprint: str) -> None: ...


class InMemoryAnalysisCache:
    """进程内实现（单测与本地跑）。持久化实现随 C9 接线落库。"""

    def __init__(self) -> None:
        self._entries: dict[tuple[str, str], str] = {}

    def get(self, owner_id: str, fingerprint: str) -> str | None:
        return self._entries.get((owner_id, fingerprint))

    def remember(self, owner_id: str, fingerprint: str, job_id: str) -> None:
        self._entries[(owner_id, fingerprint)] = job_id

    def forget(self, owner_id: str, fingerprint: str) -> None:
        self._entries.pop((owner_id, fingerprint), None)

    def size(self) -> int:
        return len(self._entries)


@dataclass(frozen=True)
class CachedSubmission:
    job_id: str
    reused: bool
    billed: bool


async def submit_or_reuse(
    runner: Any,
    *,
    cluster_id: str,
    lang: str,
    owner_scope: Any,
    initiated_by: str,
    flags: FeatureFlags,
    pricing: DeepAnalysisPricing,
    cache: AnalysisCacheStore,
    ledger_version: int | None,
    tier: str = DEEP_TIER,
    charge: ChargeLanding | None = None,
    provider: Any = None,
) -> CachedSubmission:
    """命中缓存 → 回既有 job_id（0 新 job、0 新计费）；否则走既有提交路径。

    `ledger_version is None` 时**整条缓存路径跳过**：不查、不写、每次都是新作业。
    """
    if ledger_version is None:
        fresh = await _submit(
            runner, cluster_id=cluster_id, lang=lang, owner_scope=owner_scope,
            initiated_by=initiated_by, flags=flags, pricing=pricing,
            charge=charge, provider=provider,
        )
        return CachedSubmission(job_id=fresh.job_id, reused=False, billed=fresh.billed)

    key = AnalysisCacheKey(
        cluster_id=cluster_id, lang=lang, tier=tier, ledger_version=ledger_version,
    )
    fingerprint = key.fingerprint()
    owner_id = str(getattr(owner_scope, "id", owner_scope))
    hit = cache.get(owner_id, fingerprint)
    if hit is not None:
        return CachedSubmission(job_id=hit, reused=True, billed=False)

    fresh = await _submit(
        runner, cluster_id=cluster_id, lang=lang, owner_scope=owner_scope,
        initiated_by=initiated_by, flags=flags, pricing=pricing,
        charge=charge, provider=provider,
    )
    cache.remember(owner_id, fingerprint, fresh.job_id)
    return CachedSubmission(job_id=fresh.job_id, reused=False, billed=fresh.billed)


async def _submit(runner: Any, **kwargs: Any) -> DeepAnalysisSubmission:
    """提交仍走 HOTSPOT-04 的既有通道——缓存层 NEVER 自建提交路径（§6-H7）。"""
    return await submit_deep_analysis(runner, **kwargs)
