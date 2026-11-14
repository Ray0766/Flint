"""NET-01：录制回放守门器——**联网只在采集阶段，验证阶段恒回放**（S2-7 可执行化）。

## S2-7 说的是什么

「CI NEVER 联网；一切外部调用 MUST 走录制回放（M1-008 机制）」。

这句话此前只是一句话：**没有任何东西在查它**。一个测试里写一行裸 `httpx.Client()`
去打真站，跑起来照样绿（本机有网），而它会在三个地方咬人——CI 无网时红、
被限流时红、对方改了返回时红，**而这三种红都不是被测代码的问题**。

## 判据：结构，不是词

- **算违规**：`httpx.Client(...)` / `AsyncClient(...)` **没有 `transport=`**
  （`MockTransport` / ASGI 传输都从这里进）、`urlopen(` / `requests.*` / `aiohttp`；
- **不算**：
  - 模块用了 `respx`（它拦的就是整层传输）；
  - 文件里的 http(s) 字面量**全是本机**（localhost / 127.0.0.1 / testserver）——
    §6 明写「本机不算外网：postgres :55432 · redis · 本机模型 · localhost:3000/:8000」；
  - 在**白名单**里的采集脚本（逐条列名 + 写明理由）。

## 采集与验证的边界写死在白名单里

采集**允许**联网（工单 §6 的 B 档：真实源抓取，抓完必录 `fixtures/`）；
验证**恒回放**。两者的边界不能靠人记——所以白名单逐条列名，
新加一个就要在那里报到并说清它为什么可以联网。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from tools.check_no_live_network import (
    LIVE_COLLECTORS,
    SCAN_ROOTS,
    audit,
    scan_source,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

BARE = 'import httpx\n\n\ndef f():\n    return httpx.Client(timeout=5.0)\n'
GUARDED = (
    "import httpx\n\n\ndef f():\n"
    "    return httpx.Client(transport=httpx.MockTransport(lambda r: None))\n"
)


# ───────────────────────── 一、算违规的那几类


def test_a_bare_httpx_client_is_flagged() -> None:
    """acceptance①：没有 `transport=` 的裸客户端即红，并点名行号。"""
    findings = scan_source(BARE, "x.py")

    assert [f.line for f in findings] == [5]
    assert "transport" in findings[0].detail


def test_a_bare_async_client_is_flagged_too() -> None:
    findings = scan_source(
        "import httpx\n\n\nasync def f():\n    return httpx.AsyncClient()\n", "x.py"
    )

    assert len(findings) == 1


@pytest.mark.parametrize(
    "snippet",
    [
        "from urllib.request import urlopen\n\n\ndef f():\n    return urlopen('http://a.b')\n",
        "import requests\n\n\ndef f():\n    return requests.get('http://a.b')\n",
    ],
)
def test_other_live_paths_are_flagged(snippet: str) -> None:
    """httpx 不是唯一的出网口——`urlopen` 与 `requests` 同样算。"""
    assert scan_source(snippet, "x.py")


def test_the_finding_names_the_file_and_line() -> None:
    """点名文件行号，否则报告没法往下查。"""
    findings = scan_source("\n\n\n\nimport httpx\nc = httpx.Client()\n", "tests/a/b.py")

    assert (findings[0].path, findings[0].line) == ("tests/a/b.py", 6)


# ───────────────────────── 二、不算违规的三类（acceptance③ 的不误伤）


def test_a_mock_transport_is_not_a_violation() -> None:
    """给了 `transport=` 就是被拦住的——`MockTransport` 从这里进。"""
    assert scan_source(GUARDED, "x.py") == []


def test_an_asgi_transport_is_not_a_violation() -> None:
    """ASGI 传输是**进程内**调用，一个字节都不出网。"""
    source = (
        "import httpx\nfrom httpx import ASGITransport\n\n\n"
        "async def f(app):\n"
        "    return httpx.AsyncClient(transport=ASGITransport(app=app), base_url='http://t')\n"
    )

    assert scan_source(source, "x.py") == []


def test_a_respx_module_is_not_a_violation() -> None:
    """`respx` 拦的是整层传输，模块里用了它就不必逐个客户端看。"""
    source = "import httpx\nimport respx\n\n\ndef f():\n    return httpx.Client()\n"

    assert scan_source(source, "x.py") == []


def test_a_localhost_only_module_is_not_a_violation() -> None:
    """文件里的 http 字面量全是本机 → 不算出网（§6：本机不算外网）。"""
    source = (
        "import httpx\n\n\ndef f(port):\n"
        "    with httpx.Client() as c:\n"
        "        return c.get(f'http://127.0.0.1:{port}/x')\n"
    )

    assert scan_source(source, "x.py") == []


def test_one_external_url_makes_the_whole_module_suspect() -> None:
    """阴性对照：只要有**一个**外部 URL 字面量，本机豁免就不成立。

    半本机半外网的文件是最危险的一种——跑起来一半是回放、一半在真打。
    """
    source = (
        "import httpx\n\n\ndef f():\n"
        "    c = httpx.Client()\n"
        "    c.get('http://127.0.0.1:8000/a')\n"
        "    return c.get('https://api.github.com/search')\n"
    )

    assert scan_source(source, "x.py")


def test_a_client_handed_to_someone_else_loses_the_local_exemption() -> None:
    """客户端被**交出去**时，本机豁免不成立。

    `Searcher(httpx.Client(...))` 里，它去打哪个站由收下它的那一方决定——
    本文件的 URL 字面量说明不了任何事。

    这一条是核实白名单时补的：`harness/demo_server.py` 文件里**只有 localhost
    字面量**，而它交出去的那个客户端在真打 github/arxiv。补之前它的白名单条目
    是死的（豁免了一个根本没被判红的文件）。
    """
    escaping = (
        "import httpx\n\n\ndef f():\n"
        "    return Searcher(httpx.Client(timeout=30.0), 'http://localhost:1/x')\n"
    )
    kept_home = (
        "import httpx\n\n\ndef f():\n"
        "    with httpx.Client() as c:\n"
        "        return c.get('http://localhost:1/x')\n"
    )

    assert scan_source(escaping, "x.py"), "交出去的客户端被本机豁免放过了"
    assert scan_source(kept_home, "x.py") == [], "本机自用的客户端被误报"


# ───────────────────────── 三、白名单：采集允许联网（acceptance②）


def test_every_whitelisted_collector_really_has_a_live_hit() -> None:
    """白名单里每一条今天**真的**有命中——只增不减的名单会变成一张许可证。

    （BL-03 的同款反向断言；本卡靠它发现 `demo_server.py` 那条曾经是死的。）
    """
    report = audit(list(SCAN_ROOTS))
    hit_paths = {item["path"] for item in report["exempted"]}

    dead = [path for path in LIVE_COLLECTORS if path not in hit_paths]

    assert dead == [], f"白名单里这些条目今天没有任何命中，该删：{dead}"


def test_the_whitelist_names_collectors_one_by_one_with_reasons() -> None:
    """采集脚本**逐条列名 + 写明理由**，NEVER 整目录放行。

    放一个目录，下一个人会把验证代码写进那个目录。
    """
    assert LIVE_COLLECTORS, "白名单为空说明豁免机制没建"
    for path, reason in LIVE_COLLECTORS.items():
        assert path.startswith("harness/"), f"白名单只给采集脚本：{path}"
        assert (REPO_ROOT / path).exists(), f"白名单条目不在盘上：{path}"
        assert len(reason) >= 12, f"{path} 的理由太短：{reason}"


def test_the_whitelist_never_covers_a_test_file() -> None:
    """**验证面一条都不许豁免**——这就是采集与验证的边界。"""
    for path in LIVE_COLLECTORS:
        assert not path.startswith("tests/"), f"白名单里混进了测试文件：{path}"


def test_a_whitelisted_hit_is_reported_separately_not_hidden(tmp_path: Path) -> None:
    """豁免的照样列出来（进 `exempted`），只是不判红。

    藏起来的话，「采集脚本里有多少处真联网」就没人知道了。
    """
    probe = REPO_ROOT / "harness" / "_net01_probe.py"
    probe.write_text(BARE + "URL = 'https://api.github.com/x'\n", encoding="utf-8")
    try:
        without = audit(["harness"], whitelist={})
        with_rule = audit(["harness"], whitelist={"harness/_net01_probe.py": "自造探针"})
    finally:
        probe.unlink()

    assert any("_net01_probe" in f["path"] for f in without["findings"])
    assert all("_net01_probe" not in f["path"] for f in with_rule["findings"])
    assert any("_net01_probe" in f["path"] for f in with_rule["exempted"])


# ───────────────────────── 四、扫描面与真跑（acceptance③）


def test_both_roots_are_scanned() -> None:
    """测试面与采集面都在扫描面上——只扫 tests 的话，白名单机制无从谈起。"""
    assert SCAN_ROOTS == ("tests", "harness")


def test_the_repository_has_no_unguarded_live_network_today() -> None:
    """全仓实跑（真实结果写进 `docs/trace/NET-01.md#4`）。"""
    report = audit(list(SCAN_ROOTS))

    assert report["unreadable"] == [], "有文件读不了，扫描面是残的"
    assert report["findings"] == [], f"无护栏的真实外部请求：{report['findings']}"
    assert report["scanned"] > 100, "扫描面太小，可能根本没扫到 tests/"


def test_the_cli_exits_zero_on_a_clean_tree() -> None:
    done = subprocess.run(
        [sys.executable, "tools/check_no_live_network.py"],
        cwd=REPO_ROOT, capture_output=True, text=True, encoding="utf-8",
        errors="replace", check=False,
    )

    assert done.returncode == 0, done.stdout + done.stderr


def test_the_cli_exits_one_and_names_the_offender() -> None:
    """acceptance③ 阴性对照：造一个裸 httpx 调用的测试文件 → 退出码 1 且点名。

    没有这一条，「今天全仓干净」与「守门器瞎了」长得一模一样。
    """
    offender = REPO_ROOT / "tests" / "v041" / "_net01_violation_probe.py"
    offender.write_text(
        "import httpx\n\n\ndef test_probe():\n"
        "    httpx.Client().get('https://api.github.com/search')\n",
        encoding="utf-8",
    )
    try:
        done = subprocess.run(
            [sys.executable, "tools/check_no_live_network.py", "--root", "tests"],
            cwd=REPO_ROOT, capture_output=True, text=True, encoding="utf-8",
            errors="replace", check=False,
        )
    finally:
        offender.unlink()

    assert done.returncode == 1
    assert "_net01_violation_probe.py:5" in done.stderr


def test_a_broken_file_is_reported_not_counted_as_clean() -> None:
    """读不了的文件要报出来，NEVER 当成「没命中」。"""
    broken = REPO_ROOT / "tests" / "v041" / "_net01_broken_probe.py"
    broken.write_text("def f(:\n", encoding="utf-8")
    try:
        report = audit(["tests"])
    finally:
        broken.unlink()

    assert any("_net01_broken_probe" in item for item in report["unreadable"])
