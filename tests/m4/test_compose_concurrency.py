"""组稿并发与服务端单槽对齐（owner 裁决 @2026-07-29）。

NUM_PARALLEL=1 时模型逐个串行处理请求；客户端 CONCURRENCY 若 >1，排队的
节请求要等前面若干节处理完，等待计入 600s 读超时——SCALE=6000 下最坏排队
~735s > 600s，会让某节 ReadTimeout 拖垮整轮 ~3 小时跑批。故 CONCURRENCY
必须 = 1（与单槽对齐；模型吞吐不变——本就串行，只是消除排队超时风险）。
"""
from __future__ import annotations

from harness.prod_caliber import CONCURRENCY


def test_compose_concurrency_serial_for_single_slot() -> None:
    assert CONCURRENCY == 1, (
        "client CONCURRENCY must match server NUM_PARALLEL=1: >1 lets queued "
        "sections wait past the 600s read timeout (owner @2026-07-29)"
    )
