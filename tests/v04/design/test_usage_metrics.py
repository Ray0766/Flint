"""DESIGN-18 验收：用量与耗时随 job 落库并可查询（G24）。

acceptance：**用量与耗时随 job 落库并可查询**。

## 为什么用量必须挂在 job 上而不是另起一张表

「这次生成花了多少」这个问题，用户问的是**那一次**。用量若与 job 分开存，
两边就要靠时间窗对齐——对不齐的那些会变成无主的账，而账单上却有数。
挂在 job 元数据里，一次运行的成本与它自己绑死。

## 为什么计价用既有的 UsageMeter

价目由配置给出、cost 由 tokens × 价目算出（M4-039 已定的口径）。
本模块再写一份计价，就会出现「两处算出不同的钱」，而账单只能有一个数。
"""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from flint.design.usage import (
    DesignUsage,
    UsageStore,
    read_usage,
    record_usage,
)
from tests.v04._source_scan import code_names

SRC = Path(__file__).resolve().parents[3] / "flint" / "design" / "usage.py"

START = datetime(2026, 8, 3, 10, 0, 0, tzinfo=UTC)
END = datetime(2026, 8, 3, 10, 0, 42, tzinfo=UTC)


def _store() -> UsageStore:
    return UsageStore()


def test_usage_and_duration_land_on_the_job() -> None:
    store = _store()

    usage = record_usage(
        store,
        job_id="job-1",
        input_tokens=1200,
        output_tokens=800,
        started_at=START,
        ended_at=END,
        usd_per_mtok_input=3.0,
        usd_per_mtok_output=15.0,
    )

    assert usage.job_id == "job-1"
    assert usage.input_tokens == 1200
    assert usage.output_tokens == 800
    assert usage.duration_ms == 42_000
    assert read_usage(store, job_id="job-1") == usage


def test_cost_comes_from_the_existing_meter() -> None:
    """计价走既有 UsageMeter：本模块 NEVER 自己乘一遍。"""
    store = _store()

    usage = record_usage(
        store, job_id="job-1", input_tokens=1_000_000, output_tokens=0,
        started_at=START, ended_at=END,
        usd_per_mtok_input=3.0, usd_per_mtok_output=15.0,
    )

    assert usage.cost_usd == pytest.approx(3.0)
    names = code_names(SRC)
    assert "flint.llm.production" in names
    assert "UsageMeter" in names


def test_pricing_must_be_given_explicitly() -> None:
    """价目没有内置默认：一个猜出来的价会变成账单上的真数字。"""
    import inspect

    signature = inspect.signature(record_usage)
    for name in ("usd_per_mtok_input", "usd_per_mtok_output"):
        assert signature.parameters[name].default is inspect.Parameter.empty


def test_unknown_job_reads_none_not_zero() -> None:
    """没记录过就是 None，NEVER 回一份全 0 的用量。

    全 0 看起来像「这次没花钱」，而事实是「我们不知道这次花了多少」。
    """
    assert read_usage(_store(), job_id="job-404") is None


def test_negative_or_backwards_duration_is_rejected() -> None:
    """结束早于开始 = 时钟或接线错了，报错而不是记一个负耗时。"""
    with pytest.raises(ValueError):
        record_usage(
            _store(), job_id="job-1", input_tokens=1, output_tokens=1,
            started_at=END, ended_at=START,
            usd_per_mtok_input=3.0, usd_per_mtok_output=15.0,
        )


def test_negative_tokens_are_rejected() -> None:
    with pytest.raises(ValueError):
        record_usage(
            _store(), job_id="job-1", input_tokens=-1, output_tokens=0,
            started_at=START, ended_at=END,
            usd_per_mtok_input=3.0, usd_per_mtok_output=15.0,
        )


def test_recording_twice_for_one_job_accumulates() -> None:
    """一次 job 可能有多轮模型调用：用量累加，NEVER 后一次覆盖前一次。"""
    store = _store()
    record_usage(
        store, job_id="job-1", input_tokens=100, output_tokens=50,
        started_at=START, ended_at=END,
        usd_per_mtok_input=3.0, usd_per_mtok_output=15.0,
    )
    total = record_usage(
        store, job_id="job-1", input_tokens=200, output_tokens=25,
        started_at=START, ended_at=END,
        usd_per_mtok_input=3.0, usd_per_mtok_output=15.0,
    )

    assert total.input_tokens == 300
    assert total.output_tokens == 75
    assert total.calls == 2
    assert total.duration_ms == 84_000        # 两段耗时相加


def test_usage_of_one_job_never_leaks_into_another() -> None:
    store = _store()
    record_usage(
        store, job_id="job-1", input_tokens=100, output_tokens=0,
        started_at=START, ended_at=END,
        usd_per_mtok_input=3.0, usd_per_mtok_output=15.0,
    )

    assert read_usage(store, job_id="job-2") is None


def test_read_returns_a_copy() -> None:
    """读出去的是副本：调用方改返回值 NEVER 改到账上。"""
    store = _store()
    record_usage(
        store, job_id="job-1", input_tokens=100, output_tokens=0,
        started_at=START, ended_at=END,
        usd_per_mtok_input=3.0, usd_per_mtok_output=15.0,
    )

    stolen = read_usage(store, job_id="job-1")
    assert stolen is not None
    object.__setattr__(stolen, "input_tokens", 999_999)

    after = read_usage(store, job_id="job-1")
    assert after is not None
    assert after.input_tokens == 100


def test_usage_is_a_dataclass_not_free_dict() -> None:
    """用量是有形状的：自由 dict 会让「少记一项」在很久以后才被发现。"""
    usage = DesignUsage(
        job_id="j", input_tokens=1, output_tokens=1, calls=1,
        duration_ms=1, cost_usd=0.0,
    )

    assert usage.job_id == "j"
