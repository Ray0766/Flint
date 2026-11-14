"""DESIGN-18：设计台用量与耗时（G24，随 job 落库）。

## 用量挂在 job 上

「这次生成花了多少」这个问题，用户问的是**那一次**。用量若与 job 分开存，
两边就要靠时间窗对齐——对不齐的那些会变成无主的账，而账单上却有数。
挂在 job 元数据里，一次运行的成本与它自己绑死。

## 计价走既有 UsageMeter

价目由配置给出、cost = tokens × 价目（M4-039 已定的口径）。本模块再写一份计价，
就会出现「两处算出不同的钱」，而账单只能有一个数。价目也**没有内置默认**：
一个猜出来的价会变成账单上的真数字。

## 没记录过是 None，不是全 0

全 0 看起来像「这次没花钱」，而事实是「我们不知道这次花了多少」——
这与 DESIGN-13 的 `unreported ≠ passed` 是同一条纪律。

## 多轮调用累加

一次 job 可能有多轮模型调用。后一次覆盖前一次的话，账面上会只剩最后一轮的钱。
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import datetime

from flint.llm.production import ModelPricing, UsageMeter


@dataclass(frozen=True)
class DesignUsage:
    job_id: str
    input_tokens: int
    output_tokens: int
    calls: int
    duration_ms: int
    cost_usd: float


@dataclass
class UsageStore:
    """内存实现；SQL 实现随 E2 的 job 元数据表接入。"""

    _rows: dict[str, DesignUsage] = field(default_factory=dict)

    def get(self, job_id: str) -> DesignUsage | None:
        row = self._rows.get(job_id)
        return copy.copy(row) if row is not None else None   # 读出去的是副本

    def put(self, usage: DesignUsage) -> None:
        self._rows[usage.job_id] = usage


def record_usage(
    store: UsageStore,
    *,
    job_id: str,
    input_tokens: int,
    output_tokens: int,
    started_at: datetime,
    ended_at: datetime,
    usd_per_mtok_input: float,
    usd_per_mtok_output: float,
) -> DesignUsage:
    """记一轮模型调用的用量与耗时；同一 job 多轮**累加**。"""
    if input_tokens < 0 or output_tokens < 0:
        raise ValueError("token 数 NEVER 为负：那是接线错了，不是一次便宜的调用")
    if ended_at < started_at:
        raise ValueError(
            "ended_at 早于 started_at：时钟或接线错了，NEVER 记一个负耗时"
        )

    previous = store.get(job_id)
    meter = UsageMeter(
        pricing=ModelPricing(
            usd_per_mtok_input=usd_per_mtok_input,
            usd_per_mtok_output=usd_per_mtok_output,
        )
    )
    total_in = (previous.input_tokens if previous else 0) + input_tokens
    total_out = (previous.output_tokens if previous else 0) + output_tokens
    meter.add({"input_tokens": total_in, "output_tokens": total_out})

    duration_ms = int((ended_at - started_at).total_seconds() * 1000)
    usage = DesignUsage(
        job_id=job_id,
        input_tokens=total_in,
        output_tokens=total_out,
        calls=(previous.calls if previous else 0) + 1,
        duration_ms=(previous.duration_ms if previous else 0) + duration_ms,
        cost_usd=meter.cost_usd,          # 计价只有一处：既有 UsageMeter
    )
    store.put(usage)
    return store.get(job_id) or usage


def read_usage(store: UsageStore, *, job_id: str) -> DesignUsage | None:
    """查一次 job 的用量。没记录过回 None——全 0 会看起来像「这次没花钱」。"""
    return store.get(job_id)
