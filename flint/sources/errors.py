"""数据源共用异常（M1-011~014）。

- SourceFetchError：上游返回非成功状态（5xx / 网络层失败）。
- RateLimitedError：上游 429 限频，是 SourceFetchError 的子类，
  单源降级（M1-015）与限频合规层（M1-016）据此分流处置。
- ParseDrift：页面/接口结构漂移导致解析失败——显式报错，
  NEVER 静默产出错数据（M1-012 验收）。
"""
from __future__ import annotations


class SourceFetchError(Exception):
    def __init__(self, source_id: str, status_code: int, detail: str) -> None:
        super().__init__(f"[{source_id}] fetch failed with HTTP {status_code}: {detail}")
        self.source_id = source_id
        self.status_code = status_code


class RateLimitedError(SourceFetchError):
    pass


class ParseDrift(Exception):
    def __init__(self, source_id: str, expectation: str) -> None:
        super().__init__(f"[{source_id}] upstream structure drifted: {expectation}")
        self.source_id = source_id
