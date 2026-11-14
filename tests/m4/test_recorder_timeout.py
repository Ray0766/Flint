"""死因确认（owner 修复令步 2）：证实 harness 录制传输层是否真正执行
配置的读超时。

Probe A（recorder 包裹的 client）冷启 ~32 分才 ReadTimeout，而暖态 smoke
用**裸** httpx.Client(timeout=600) 单调 242s 正常返回——差异点就是录制传输
层。本测复刻 harness 内 `_Recorder`（BaseTransport 包 HTTPTransport），
对一个「收到请求后静默 sleep」的本地回环服务器发请求，断言：配 T 秒读超时
的 client 必须在 ~T 秒（而非服务器 sleep 时长）抛 httpx.ReadTimeout。

裸 client 与 recorder 包裹 client 并列对照：若二者都在 ~T 抛 → 超时在录制
层生效（32 分死因非「超时未生效」）；若 recorder 版拖到 sleep 时长才抛 →
录制层吞掉了超时（32 分死因 = 超时未生效，触发步 4 修复）。

回环 socket，零外部网络（S2-7 合规）。
"""
from __future__ import annotations

import socket
import threading
import time

import httpx
import pytest

READ_TIMEOUT = 1.0  # 紧读超时
SERVER_SILENCE = 5.0  # 服务器收到请求后静默时长（远大于读超时）
TOLERANCE = 3.0  # 抛异常须在 <TOLERANCE 秒（证 ~READ_TIMEOUT 而非 SILENCE）


class _RecorderReplica(httpx.BaseTransport):
    """与 harness.prod_caliber 内 `_Recorder` 结构逐字一致（录制交换）。"""

    def __init__(self) -> None:
        self._inner = httpx.HTTPTransport()
        self.calls = 0

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        self.calls += 1
        response = self._inner.handle_request(request)
        body = response.read()
        return httpx.Response(
            response.status_code, headers=response.headers, content=body
        )


def _silent_server(sock: socket.socket, silence: float) -> None:
    """接受一个连接，读请求，静默 silence 秒，再回最小 200。"""
    try:
        conn, _ = sock.accept()
    except OSError:
        return
    try:
        conn.recv(65536)
        time.sleep(silence)
        conn.sendall(
            b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\n{}"
        )
    except OSError:
        pass
    finally:
        conn.close()


def _serve() -> tuple[int, threading.Thread, socket.socket]:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", 0))
    sock.listen(1)
    port = sock.getsockname()[1]
    thread = threading.Thread(
        target=_silent_server, args=(sock, SERVER_SILENCE), daemon=True
    )
    thread.start()
    return port, thread, sock


def _time_read_timeout(client: httpx.Client, port: int) -> float:
    start = time.monotonic()
    with pytest.raises(httpx.ReadTimeout):
        client.post(f"http://127.0.0.1:{port}/x", json={"k": "v"})
    return time.monotonic() - start


def test_plain_client_enforces_read_timeout() -> None:
    """基线：裸 httpx.Client(timeout=T) 在 ~T 抛 ReadTimeout（非 sleep 时长）。"""
    port, thread, sock = _serve()
    try:
        with httpx.Client(timeout=READ_TIMEOUT) as client:
            elapsed = _time_read_timeout(client, port)
        assert elapsed < TOLERANCE, (
            f"plain client waited {elapsed:.2f}s (>{TOLERANCE}) — read timeout "
            "not enforced"
        )
    finally:
        sock.close()
        thread.join(timeout=SERVER_SILENCE + 2)


def test_recorder_wrapped_client_enforces_read_timeout() -> None:
    """死因确认：recorder 包裹的 client 是否同样在 ~T 抛（而非拖到 sleep）。"""
    port, thread, sock = _serve()
    try:
        transport = _RecorderReplica()
        with httpx.Client(transport=transport, timeout=READ_TIMEOUT) as client:
            elapsed = _time_read_timeout(client, port)
        assert transport.calls == 1
        assert elapsed < TOLERANCE, (
            f"recorder-wrapped client waited {elapsed:.2f}s (>{TOLERANCE}) — "
            "record transport swallowed the read timeout (32-min death cause "
            "= timeout not in effect; owner remediation step 4 triggered)"
        )
    finally:
        sock.close()
        thread.join(timeout=SERVER_SILENCE + 2)


# 滴流参数（宽裕余量防满载下调度抖动导致 flake）：读超时 2.0，间隔 0.6
# （<<超时），字节数 5 → 总接收 ~3.0s > 超时。用 Content-Length 定长收发
# （避免 chunked 分帧 + 关闭竞态在满载时抛 ReadError）。
DRIBBLE_TIMEOUT = 2.0
DRIBBLE_GAP = 0.6
DRIBBLE_BYTES = 5


def _dribble_server(sock: socket.socket, gap: float, nbytes: int) -> None:
    """立即回 200 + Content-Length，然后每 gap 秒滴 1 字节（gap<<读超时，
    但总时长>读超时）——模拟推理期逐 token 增量交付。定长收发更稳。"""
    try:
        conn, _ = sock.accept()
    except OSError:
        return
    try:
        conn.recv(65536)
        header = (
            f"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
            f"Content-Length: {nbytes}\r\n\r\n"
        ).encode()
        conn.sendall(header)
        for _ in range(nbytes):
            time.sleep(gap)
            conn.sendall(b"x")
        time.sleep(0.3)  # 客户端读满 Content-Length 后即返回；linger 后再关
    except OSError:
        pass
    finally:
        conn.close()


def test_chunked_dribble_bypasses_total_read_timeout() -> None:
    """确认「增量读取绕过超时」机制：每字节间隔 < 读超时时，总接收时长可
    远超读超时而不抛——证读超时只捕获**停顿**（静默间隔），不捕获**慢而
    有进展**的长生成。这正是长生成一节可跑很久而不被读超时快失败的机理。"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", 0))
    sock.listen(1)
    port = sock.getsockname()[1]
    thread = threading.Thread(
        target=_dribble_server, args=(sock, DRIBBLE_GAP, DRIBBLE_BYTES),
        daemon=True,
    )
    thread.start()
    try:
        transport = _RecorderReplica()
        start = time.monotonic()
        with httpx.Client(
            transport=transport, timeout=DRIBBLE_TIMEOUT
        ) as client:
            resp = client.post(f"http://127.0.0.1:{port}/x", json={"k": "v"})
        elapsed = time.monotonic() - start
        assert resp.status_code == 200
        assert elapsed > DRIBBLE_TIMEOUT, (
            f"total receive {elapsed:.2f}s should exceed read timeout "
            f"{DRIBBLE_TIMEOUT}s — proves per-gap (not total) semantics"
        )
    finally:
        sock.close()
        thread.join(timeout=DRIBBLE_GAP * DRIBBLE_BYTES + 2)
