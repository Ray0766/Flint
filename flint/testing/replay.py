"""HTTP 录制回放机制（M1-008，技术方案 E12）。

- fixture 布局：`fixtures/{source_id}/{yyyy-mm-dd}.json`（E12），每文件 = 当日该源
  全部请求/响应交换的有序列表。
- record 模式：请求经 RecordingTransport 打到注入的 live transport（真网络或测试
  替身），响应原样返回并落盘。
- replay 模式：respx Router 按录制内容路由，未录制的请求抛 ReplayMiss——绝不静默
  放行到真网络（S2-7：CI NEVER 联网）。
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from types import TracebackType
from typing import Literal, Self

import httpx
import respx

Mode = Literal["record", "replay"]


class ReplayMiss(Exception):
    """Raised in replay mode when a request has no recorded exchange."""


@dataclass
class RecordedExchange:
    method: str
    url: str
    status_code: int
    content_type: str
    body_text: str


def fixture_path(root: Path, source_id: str, day: date) -> Path:
    """E12 layout: fixtures/{source_id}/{yyyy-mm-dd}.json."""
    return root / source_id / f"{day.isoformat()}.json"


def load_fixture(path: Path) -> list[RecordedExchange]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [RecordedExchange(**item) for item in raw]


def save_fixture(path: Path, exchanges: list[RecordedExchange]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps([asdict(e) for e in exchanges], ensure_ascii=False, indent=1)
    path.write_text(payload, encoding="utf-8")


class RecordingTransport(httpx.BaseTransport):
    def __init__(self, inner: httpx.BaseTransport, sink: list[RecordedExchange]) -> None:
        self._inner = inner
        self._sink = sink

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        response = self._inner.handle_request(request)
        body = response.read()
        self._sink.append(
            RecordedExchange(
                method=request.method,
                url=str(request.url),
                status_code=response.status_code,
                content_type=response.headers.get("content-type", ""),
                body_text=body.decode("utf-8"),
            )
        )
        return httpx.Response(
            response.status_code, headers=response.headers, content=body
        )


class HttpReplay:
    """Dual-mode HTTP session factory around one fixture file."""

    def __init__(
        self,
        fixture: Path,
        mode: Mode,
        live_transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._fixture = fixture
        self._mode: Mode = mode
        self._live = live_transport
        self._sink: list[RecordedExchange] = []
        self._router: respx.Router | None = None

    def __enter__(self) -> Self:
        if self._mode == "replay":
            exchanges = load_fixture(self._fixture)  # missing file -> FileNotFoundError
            router = respx.Router(assert_all_mocked=True)
            for ex in exchanges:
                router.request(ex.method, ex.url).mock(
                    return_value=httpx.Response(
                        ex.status_code,
                        content=ex.body_text.encode("utf-8"),
                        headers={"content-type": ex.content_type} if ex.content_type else None,
                    )
                )
            self._router = router
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._mode == "record" and exc is None:
            save_fixture(self._fixture, self._sink)

    def client(self) -> httpx.Client:
        if self._mode == "record":
            inner = self._live if self._live is not None else httpx.HTTPTransport()
            return httpx.Client(transport=RecordingTransport(inner, self._sink))
        router = self._router
        if router is None:
            raise RuntimeError("HttpReplay must be entered as a context manager first")

        def handler(request: httpx.Request) -> httpx.Response:
            try:
                return router.handler(request)
            except AssertionError as err:  # respx all-mocked guard
                raise ReplayMiss(f"no recorded exchange for {request.method} {request.url}") from err

        return httpx.Client(transport=httpx.MockTransport(handler))
