"""REGION-07 验收：fetch_legal_status 抓取门 + fixture-only 网络护栏。

acceptance（tasks-v04.json#REGION-07）：
  ① restricted 源抓取任务**被拒并落 DegradationNote**；
  ② 测试层网络护栏：真实 http 调用**被拦截**（respx 全域断言，S2-7）。

## unknown 为什么也不放行

`FetchLegalStatus` 缺省是 `unknown`（K2 未决：各国合规结论待 owner）。
门只放行 `allowed`——**「不知道能不能抓」NEVER 等于「可以抓」**。
反过来做（默认放行、发现问题再拉黑）意味着第一次抓取就已经发生了。

## 被拒也要留痕

拒绝不是静默跳过：落 `DegradationNote`，让「今天这个源没数据」在广场上可见。
悄悄跳过会让缺口看起来像「今天没热点」。
"""
from __future__ import annotations

from datetime import date

import httpx
import pytest
import respx

from flint.region.fetch_gate import FetchDenied, guard_fetch, may_fetch
from flint.sources.degradation import DegradationNote

DAY = date(2026, 8, 2)


class _Store:
    def __init__(self) -> None:
        self.notes: list[DegradationNote] = []

    def add(self, note: DegradationNote) -> None:
        self.notes.append(note)


# ── ① 抓取门 ─────────────────────────────────────────────────────

def test_allowed_passes() -> None:
    assert may_fetch("allowed") is True


@pytest.mark.parametrize("status", ["restricted", "unknown"])
def test_restricted_and_unknown_are_denied(status: str) -> None:
    """unknown 也不放行：「不知道能不能抓」NEVER 等于「可以抓」（K2 未决）。"""
    assert may_fetch(status) is False


def test_denied_fetch_raises_and_records_note() -> None:
    store = _Store()
    with pytest.raises(FetchDenied, match="restricted"):
        guard_fetch(source_id="s-x", fetch_legal_status="restricted", day=DAY, store=store)
    assert len(store.notes) == 1
    note = store.notes[0]
    assert note.reason == "fetch_denied_by_legal_status"
    assert note.source_id == "s-x"
    assert note.day == DAY
    assert "restricted" in note.detail


def test_unknown_denial_also_records_note() -> None:
    store = _Store()
    with pytest.raises(FetchDenied):
        guard_fetch(source_id="s-y", fetch_legal_status="unknown", day=DAY, store=store)
    assert store.notes[0].source_id == "s-y"


def test_allowed_fetch_records_nothing() -> None:
    """阴性对照：放行时不落降级——否则「降级」这个信号会被噪音淹没。"""
    store = _Store()
    guard_fetch(source_id="s-ok", fetch_legal_status="allowed", day=DAY, store=store)
    assert store.notes == []


def test_denial_is_not_silent() -> None:
    """拒绝 MUST 抛错而不是返回 None：静默跳过会让缺口看起来像「今天没热点」。"""
    store = _Store()
    with pytest.raises(FetchDenied):
        guard_fetch(source_id="s-z", fetch_legal_status="restricted", day=DAY, store=store)


# ── ② 网络护栏（S2-7：CI 永不联网） ──────────────────────────────

@respx.mock
def test_real_http_call_is_intercepted() -> None:
    """respx 全域拦截：测试里任何真实 http 调用都到不了网络。"""
    route = respx.get("https://example.invalid/probe").mock(
        return_value=httpx.Response(200, text="fixture"))
    with httpx.Client() as client:
        resp = client.get("https://example.invalid/probe")
    assert resp.text == "fixture"
    assert route.called, "请求被 respx 接住 = 没有出网"


@respx.mock
def test_unmocked_host_is_refused_not_dialed() -> None:
    """没登记的地址直接被 respx 拒绝——**连不上**才是护栏，不是「碰巧没网」。"""
    expected = respx.MockNotDetected if hasattr(respx, "MockNotDetected") else Exception
    with pytest.raises(expected), httpx.Client() as client:
        client.get("https://not-registered.invalid/x")


def test_fetch_gate_module_makes_no_network_call() -> None:
    """门本身零网络：它只看状态字段，NEVER 试探性地发一个请求。"""
    import inspect

    import flint.region.fetch_gate as module

    source = inspect.getsource(module)
    for forbidden in ("httpx", "requests", "urlopen", "socket"):
        assert forbidden not in source, f"抓取门里出现网络符号 {forbidden!r}"
