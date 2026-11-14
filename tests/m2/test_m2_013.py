"""M2-013 acceptance tests: FundingSource v1 placeholder.

Acceptance: search returns empty and flags not_available; the frontend hint
slot (信息不足 / 升级解锁) is present in the response structure.
"""
from __future__ import annotations

from flint.evidence.funding import FundingSourceStub


def test_search_returns_empty() -> None:
    source = FundingSourceStub()
    assert source.search("Solid State Labs") == []


def test_not_available_flag_and_hint_slot() -> None:
    source = FundingSourceStub()
    source.search("any company")
    availability = source.availability()
    assert availability["status"] == "not_available"
    assert "信息不足" in availability["user_hint"]
    assert "升级解锁" in availability["user_hint"]


def test_no_network_dependency() -> None:
    """v1 占位不发起任何网络调用：构造无需 client。"""
    assert FundingSourceStub().search("x") == []
