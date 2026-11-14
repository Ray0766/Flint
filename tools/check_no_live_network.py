"""NET-01：录制回放守门器——**联网只在采集阶段，验证阶段恒回放**（S2-7 可执行化）。

用法：python tools/check_no_live_network.py [--json] [--root <目录>…]
退出码 0 = 验证面没有无护栏的真实外部请求；1 = 有（逐条点名文件:行号）。

## S2-7 此前只是一句话

「CI NEVER 联网；一切外部调用 MUST 走录制回放（M1-008 机制）」——
**没有任何东西在查它**。一个测试里写一行裸 `httpx.Client()` 去打真站，
本机有网时照样绿，而它会在三个地方咬人：CI 无网、被限流、对方改了返回。
**这三种红都不是被测代码的问题**，但排查的人得先想明白这一点。

## 判据是结构，不是词

**算违规**：

- `httpx.Client(...)` / `AsyncClient(...)` **没有 `transport=`**
  （`MockTransport` 与 ASGI 传输都从这个参数进）；
- `urlopen(` / `requests.<verb>(` / `aiohttp.ClientSession(`。

**不算**：

1. 模块用了 `respx`——它拦的是整层传输，不必逐个客户端看；
2. 文件里的 http(s) 字面量**全是本机**（localhost / 127.0.0.1 / 0.0.0.0 / testserver）。
   §6 明写「本机不算外网：postgres :55432 · redis · 本机模型 · localhost:3000/:8000」。
   **只要有一个外部 URL 字面量，这条豁免就不成立**——半本机半外网的文件最危险：
   跑起来一半是回放、一半在真打；
3. 在 `LIVE_COLLECTORS` 白名单里的**采集脚本**。

## 采集与验证的边界写死在白名单里

采集允许联网（工单 §6 的 B 档：真实源抓取，**抓完必录 `fixtures/`**）；
验证恒回放。边界不能靠人记，所以白名单**逐条列名 + 写明理由**，
且**只给 `harness/`**——验证面一条都不许豁免。
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
SCAN_ROOTS: Final[tuple[str, ...]] = ("tests", "harness")
SKIP_DIRS: Final[frozenset[str]] = frozenset({"__pycache__", ".venv", "node_modules"})

_URL: Final[re.Pattern[str]] = re.compile(r"https?://[^\s\"')]+")
_LOCAL: Final[re.Pattern[str]] = re.compile(
    r"https?://(localhost|127\.0\.0\.1|0\.0\.0\.0|testserver)"
)
_CLIENT_NAMES: Final[frozenset[str]] = frozenset({"Client", "AsyncClient"})
_REQUESTS_VERBS: Final[frozenset[str]] = frozenset(
    {"get", "post", "put", "delete", "patch", "head", "request"}
)

# 采集脚本白名单：逐条列名 + 写明**为什么它可以联网**。
# NEVER 整目录放行——放一个目录，下一个人会把验证代码写进那个目录。
# `harness/gate1_live.py` **不在**名单里：它自带 `_RecordingTransport`——
# 边跑边录，本来就走 `transport=`，判据认得出，不需要豁免。
# （这条是反向断言逼出来的：首版把它放进名单，而它一处命中都没有。）
LIVE_COLLECTORS: Final[dict[str, str]] = {
    "harness/demo_server.py": "demo 后端：Gate① 走真实 github/arxiv（采集面，工单 §6-B）",
    "harness/prod_caliber.py": "生产口径跑批：连本机模型与真实源（采集面）",
    "harness/run_worker.py": "worker 进程入口：注入本机 Ollama 客户端（本机档，零 key）",
    # `COMBO-WIRE-01`：本机 Ollama 客户端的**唯一定义处**。它打的是 localhost:11434
    # （本机模型，零 key、零付费、不出网）。此前这同一只客户端在
    # `demo_server.py` 与 `run_worker.py` 里各造一份，两处都已在名单上——
    # **搬到一处之后名单反而短了一格，不是多了一格**。
    "harness/local_model.py": "本机 Ollama 客户端工厂：免费本地档（localhost，零 key）",
    "harness/probe_robots.py": (
        "K2-01 合规实测：只取各源的 robots.txt（A 档只读调研），"
        "NEVER 碰数据端点；抓完落 fixtures/robots/ + manifest"
    ),
}


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    kind: str
    detail: str


def _has_transport(call: ast.Call) -> bool:
    return any(k.arg == "transport" for k in call.keywords)


def _call_name(call: ast.Call) -> str:
    func = call.func
    return func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")


def _is_requests_call(call: ast.Call) -> bool:
    func = call.func
    return (
        isinstance(func, ast.Attribute)
        and isinstance(func.value, ast.Name)
        and func.value.id == "requests"
        and func.attr in _REQUESTS_VERBS
    )


def _local_only(source: str) -> bool:
    """文件里的 http 字面量是否**全是**本机（且至少有一个）。"""
    urls = _URL.findall(source)
    return bool(urls) and all(_LOCAL.match(u) for u in urls)


def _escaping_clients(tree: ast.AST) -> set[int]:
    """被当作**实参交出去**的客户端所在行。

    `Searcher(httpx.Client(...))` 这种写法里，客户端离开了本文件——
    它去打哪个站由收下它的那一方决定，本文件的 URL 字面量说明不了任何事。
    本机豁免对这种写法**不成立**（`harness/demo_server.py` 就是这个形状：
    文件里只有 localhost 字面量，而它交出去的客户端在真打 github/arxiv）。
    """
    escaping: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for arg in [*node.args, *(k.value for k in node.keywords)]:
            if isinstance(arg, ast.Call) and _call_name(arg) in _CLIENT_NAMES:
                escaping.add(arg.lineno)
    return escaping


def scan_source(source: str, display: str) -> list[Finding]:
    """一份源码里的无护栏出网点。注释与 docstring 天然不进 AST。"""
    if "respx" in source:
        return []
    tree = ast.parse(source)
    escaping = _escaping_clients(tree)
    # 本机豁免只对「客户端留在本文件里用」的写法成立（见 `_escaping_clients`）。
    if _local_only(source) and not escaping:
        return []
    findings: list[Finding] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _call_name(node)
        if name in _CLIENT_NAMES and not _has_transport(node):
            if _local_only(source) and node.lineno not in escaping:
                continue                 # 本机自用，不算出网
            findings.append(Finding(
                display, node.lineno, "bare-client",
                f"{name}(…) 没有 transport=：真实出网且无录制回放护栏（S2-7）",
            ))
        elif name == "urlopen":
            findings.append(Finding(
                display, node.lineno, "urlopen", "urlopen(…) 直接出网，无护栏",
            ))
        elif name == "ClientSession":
            findings.append(Finding(
                display, node.lineno, "aiohttp", "aiohttp 会话直接出网，无护栏",
            ))
        elif _is_requests_call(node):
            findings.append(Finding(
                display, node.lineno, "requests", f"requests.{name}(…) 直接出网，无护栏",
            ))
    return findings


def _files(roots: list[str]) -> list[Path]:
    out: list[Path] = []
    for root in roots:
        base = REPO_ROOT / root
        if base.exists():
            out.extend(
                p for p in sorted(base.rglob("*.py"))
                if not any(part in SKIP_DIRS for part in p.parts)
            )
    return out


def audit(roots: list[str], whitelist: dict[str, str] | None = None) -> dict[str, Any]:
    """扫一遍。`whitelist` 可注入——豁免机制本身要能被测。"""
    rules = LIVE_COLLECTORS if whitelist is None else whitelist
    findings: list[Finding] = []
    exempted: list[Finding] = []
    unreadable: list[str] = []
    files = _files(roots)
    for path in files:
        display = path.relative_to(REPO_ROOT).as_posix()
        try:
            found = scan_source(path.read_text(encoding="utf-8"), display)
        except SyntaxError as err:      # 语法坏了要报出来，NEVER 当成「没命中」
            unreadable.append(f"{display}: {err}")
            continue
        # 豁免的**照样列出来**：藏起来的话，「采集脚本里有多少处真联网」没人知道
        (exempted if display in rules else findings).extend(found)
    return {
        "schema": "no-live-network/1",
        "scanned": len(files),
        "findings": [f.__dict__ for f in findings],
        "exempted": [f.__dict__ for f in exempted],
        "whitelist": rules,
        "unreadable": unreadable,
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="录制回放守门器（S2-7）")
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--root", action="append", dest="roots")
    args = parser.parse_args(argv)

    report = audit(args.roots or list(SCAN_ROOTS))
    if args.as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1 if report["findings"] or report["unreadable"] else 0

    print(f"扫描 {report['scanned']} 个 .py 文件（{', '.join(args.roots or SCAN_ROOTS)}）")
    if report["exempted"]:
        print(f"白名单内（采集面，允许联网）{len(report['exempted'])} 处：")
        for item in report["exempted"]:
            print(f"    · {item['path']}:{item['line']} {item['detail']}")
    if report["unreadable"]:
        print(f"读不了的文件 {len(report['unreadable'])} 个（**没进扫描面**）：", file=sys.stderr)
        for item in report["unreadable"]:
            print(f"    ! {item}", file=sys.stderr)
    if not report["findings"]:
        print("验证面没有无护栏的真实外部请求。")
        return 1 if report["unreadable"] else 0

    print(f"\n无护栏的真实外部请求 {len(report['findings'])} 处：", file=sys.stderr)
    for item in report["findings"]:
        print(f"    ✗ {item['path']}:{item['line']}  {item['detail']}", file=sys.stderr)
    print(
        "S2-7：CI NEVER 联网，一切外部调用 MUST 走录制回放。"
        "这些地方会在 CI 无网 / 被限流 / 对方改返回时红，而那三种红都不是被测代码的问题。",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
