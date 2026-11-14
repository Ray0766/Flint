"""FundingSource v1 占位（M2-013，冻结协议 FundingSource）。

协议注释即规格：v1 实现返回空并标 not_available，前端显示
「信息不足 / 升级解锁」。零网络依赖；付费数据源接口留好（S1 非目标）。
"""
from __future__ import annotations

from flint.domain.models import Doc


class FundingSourceStub:
    source_id: str = "funding"

    def search(self, company: str) -> list[Doc]:
        return []

    def availability(self) -> dict[str, str]:
        return {
            "status": "not_available",
            "user_hint": "信息不足 / 升级解锁",
        }
