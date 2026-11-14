"""REGION-07：fetch_legal_status 抓取门。

## 只放行 allowed —— unknown 也不放行

`FetchLegalStatus` 缺省是 `unknown`（K2 未决: 各国抓取合规结论待 owner）。
门只认 `allowed`: **「不知道能不能抓」NEVER 等于「可以抓」**。
反过来做（默认放行、出事再拉黑）意味着第一次抓取已经发生了——
合规问题里，第一次就是全部代价。

## 被拒也要留痕

拒绝**不是静默跳过**: 落一条 DegradationNote, 让「今天这个源没数据」在广场上可见。
悄悄跳过会让缺口看起来像「今天没热点」, 而那是两件完全不同的事。

## 门本身零网络

它只看状态字段, NEVER 发一个试探性请求去「看看能不能抓」——
那样门自己就成了第一次越界的人（测试有源码断言守着）。
"""
from __future__ import annotations

from datetime import date
from typing import Protocol

from flint.sources.degradation import DegradationNote

_ALLOWED = "allowed"


class _Store(Protocol):
    def add(self, note: DegradationNote) -> None: ...


class FetchDenied(Exception):
    """抓取被合规门拒绝。"""


def may_fetch(fetch_legal_status: str) -> bool:
    """只有 allowed 放行；restricted 与 unknown 一律不放行。"""
    return fetch_legal_status == _ALLOWED


def guard_fetch(
    *, source_id: str, fetch_legal_status: str, day: date, store: _Store
) -> None:
    """抓取前置门。放行则静默返回；不放行则**落降级并抛错**。

    抛错而不是返回 None: 静默跳过会让缺口看起来像「今天没热点」。
    """
    if may_fetch(fetch_legal_status):
        return
    detail = (
        f"源 {source_id} 的 fetch_legal_status={fetch_legal_status}，抓取被拒。"
        "门只放行 allowed——unknown 表示合规结论未定（K2），NEVER 当作可抓。"
    )
    store.add(DegradationNote(
        day=day, source_id=source_id,
        reason="fetch_denied_by_legal_status", detail=detail))
    raise FetchDenied(detail)
