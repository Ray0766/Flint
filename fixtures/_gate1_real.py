"""GATE1-REAL / `DEC-057`：Gate① 那一跑的录制闸。

## 与 `_probe_real.py` 的分工

`_probe_real.py`（`DEC-052`）是**我主动去打一发**：命令行给 URL，它打、它留痕。
本模块是**别人在打，而我要拦住并记下来**——真实请求由
`flint/evidence/search.py#GithubArxivSearcher` 在作业里发出，
我这一侧只能在 httpx 的传输层截住它。

所以本模块提供的是一个 `httpx.BaseTransport`，包在真传输外面：
**每一发都先过三道闸，过了才放行，回来立刻落一份留痕。**

## 三道闸（`DEC-057` 逐字，一道都不能靠「我记得」）

| 闸 | 拦什么 | 不过时 |
|---|---|---|
| 授权 | 调用方必须显式给出 `DEC-057` | `NotAuthorised` |
| 域名 | 只许 `github.com`（含 `api.`）与 `arxiv.org` / `export.arxiv.org` | `OutsideAllowlist` |
| 额度 | **本次总共 ≤40 个真实请求（跨源合并计）** | `BudgetExhausted` |

额度是**跨源合并**的一个数，不是每源一个——`DEC-057` 逐字。
计数落在**盘上的回执**而不是内存计数器：进程重起一次内存归零，而授权不会。

## 本窗口**只授权这一次**跑通

`DEC-057` 逐字：跑通之后再要真实分析，回来找 owner。
**每日定时的持续真实分析 NEVER 顺手接上**（与 `DEC-052` 同一条边界）——
所以本模块里 NEVER 出现任何调度器：一个能自己再跑一次的录制器，
就是一个把「一次授权」变成「长期授权」的东西。

## 「跑不通就停下开单，NEVER 加码重试」

第 41 发直接抛 `BudgetExhausted` 而不是等一等再试。
额度用完而没跑通时，多打一发不会让它变通，只会让下一次授权更难要。

## 留痕格式与 `DEC-052` 同一套

`schema: "probe/1"` · `authorized_by: "DEC-057"` · url / status / 关键响应头 /
body 前 2048 字节 / UTC 时间戳。落在 `fixtures/_probe/gate1/`。

`full_body` 另存一份 `.body`——**留痕是给人读的证据，夹具是另一件东西**，
两者分开写，NEVER 让留痕悄悄变成夹具（`_probe_real.py` 同一条理由）。
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx

PROBE_DIR = Path(__file__).resolve().parent / "_probe" / "gate1"

#: `DEC-057` 逐字：证据检索的既有两家，别的域一律拒。
ALLOWED_SUFFIXES: tuple[str, ...] = (
    "github.com",
    "arxiv.org",
)

#: `DEC-057` 逐字：本次授权总共 ≤40 个真实请求（跨源合并计）。
BUDGET: int = 40

#: 这一次授权的编号。**调用方必须逐字给出它**——
#: 从环境变量读的话，一个忘了清的变量会让下一次跑变成「没人授权过的真实请求」。
AUTHORISATION = "DEC-057"

#: 回执里留哪些响应头。全留会把一堆无关的东西钉进仓库。
KEEP_HEADERS = frozenset({
    "content-type", "content-length", "server", "date",
    "x-ratelimit-remaining", "x-ratelimit-limit", "x-ratelimit-reset",
    "retry-after",
})

BODY_KEEP = 2048


class NotAuthorised(RuntimeError):
    """没有逐字给出 `DEC-057`。"""


class OutsideAllowlist(RuntimeError):
    """打到了授权域名族之外。"""


class BudgetExhausted(RuntimeError):
    """额度用完。**NEVER 加码重试**（`DEC-057` 逐字）。"""


def host_allowed(url: str) -> bool:
    """按**后缀**匹配：`api.github.com` 算 `github.com`，
    而 `github.com.evil.example` **不算**——后缀比对前先落到点边界上。
    """
    host = (urlsplit(url).hostname or "").lower()
    return any(host == s or host.endswith("." + s) for s in ALLOWED_SUFFIXES)


def spent() -> int:
    """已经花掉几发。**数盘上的回执**，不是内存计数器。

    进程重起一次内存就归零，而 `DEC-057` 那 40 发不会跟着归零。
    """
    if not PROBE_DIR.exists():
        return 0
    return sum(
        1 for p in PROBE_DIR.glob("*.json")
        if json.loads(p.read_text(encoding="utf-8")).get("schema") == "probe/1"
    )


def remaining() -> int:
    return max(0, BUDGET - spent())


class RecordingTransport(httpx.BaseTransport):
    """包在真传输外面的三道闸 + 留痕。

    `authorised_by` **必须逐字等于 `DEC-057`**：默认值是 `None`，
    也就是「谁都没授权过」——一个默认放行的闸不是闸。
    """

    def __init__(
        self,
        *,
        authorised_by: str | None = None,
        inner: httpx.BaseTransport | None = None,
        full_body: bool = True,
    ) -> None:
        if authorised_by != AUTHORISATION:
            raise NotAuthorised(
                f"真实请求要 {AUTHORISATION} 的逐字授权，收到的是 {authorised_by!r}。"
                "NEVER 从环境变量读它：一个忘了清的变量会让下一次跑"
                "变成「没人授权过的真实请求」。"
            )
        self._inner = inner or httpx.HTTPTransport()
        self._full_body = full_body

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if not host_allowed(url):
            raise OutsideAllowlist(
                f"{url} 不在 {AUTHORISATION} 的域名族里（{ALLOWED_SUFFIXES}）"
            )
        left = remaining()
        if left <= 0:
            raise BudgetExhausted(
                f"{AUTHORISATION} 的 {BUDGET} 发额度已经用完（盘上 {spent()} 份回执）。"
                "跑不通就停下开单——多打一发不会让它变通，"
                "只会让下一次授权更难要。"
            )

        started = datetime.now(UTC)
        response = self._inner.handle_request(request)
        response.read()
        self._record(request, response, started)
        return response

    def _record(
        self, request: httpx.Request, response: httpx.Response, started: datetime,
    ) -> None:
        PROBE_DIR.mkdir(parents=True, exist_ok=True)
        stamp = started.strftime("%Y-%m-%dT%H-%M-%S-%f")
        source = "github" if "github.com" in str(request.url) else "arxiv"
        record: dict[str, Any] = {
            "schema": "probe/1",
            "authorized_by": AUTHORISATION,
            "source": source,
            "url": str(request.url),
            "method": request.method,
            "requested_at_utc": started.isoformat(),
            "status": response.status_code,
            "headers": {k: v for k, v in response.headers.items()
                        if k.lower() in KEEP_HEADERS},
            "body_head": response.text[:BODY_KEEP],
            "body_bytes": len(response.content),
            # 这一发是第几个。**留痕自己说得出额度用到哪儿了**——
            # 靠人回头数文件的话，超额只会在事后才被发现。
            "spent_before_this": spent(),
            "budget": BUDGET,
        }
        (PROBE_DIR / f"{stamp}.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
        if self._full_body:
            # 留痕只留 2048 字节（给人读的证据）；这一份是**要转成回放夹具**的
            # 原样响应，单独一个文件——NEVER 让留痕悄悄变成夹具。
            (PROBE_DIR / f"{stamp}.body").write_bytes(response.content)


def authorised_client(*, authorised_by: str | None = None,
                      timeout: float = 30.0) -> httpx.Client:
    """装好三道闸的 httpx 客户端，交给 `GithubArxivSearcher` 用。"""
    return httpx.Client(
        transport=RecordingTransport(authorised_by=authorised_by),
        timeout=timeout, follow_redirects=True,
    )
