"""GATE1-REAL / `DEC-057`：Gate① 第一次在真网络上跑通，`cluster_verdicts` 不再是 0 行。

## 那一跑（2026-08-11，`DEC-057` 授权）

```
提交    POST /projects/proj-gate1real/analysis  {topic_id, keywords, budget_cny}
        → 200 job-4c558f32-f8a2-4a25-9215-f76c6781ff91
跑      run_gate1(..., topic_id="topic-gate1real")   经录制闸
        28s · 步骤 plan → retrieve → judge → validate
真实请求 28 发（额度 40，剩 12）· 全部 200 · 全部落 fixtures/_probe/gate1/
出口    cluster_verdicts 0 → 2 行
        GET /clusters/c-20260810-000/verdict → 200，all_satisfied=["D_insufficient"]
        分析屏显示「Gate① 判定 · D_insufficient」，不再是「还没有判定」
```

竞品里有 `Sentdex/BCI`——**真实搜到的 GitHub 仓库**，不是夹具里编的。

## 判据为什么全离线

`DEC-057` 逐字：「跑完 MUST 把真响应转成回放夹具，判据全部离线跑
（CI 恒不联网，`S2-7`）」。本文件因此**一发真实请求都不发**：
它读 `fixtures/gate1/real-2026-08-11.json`（那一跑的真响应）与
`fixtures/_probe/gate1/` 的留痕。

## 本文件判三样

1. **那三道闸拦得住**——授权 / 域名 / 额度，各有阴性对照；
2. **留痕齐**且额度没被突破；
3. **判定真的落库且取得回来**（用那一跑的真响应离线重放解析）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx
import pytest

REPO = Path(__file__).resolve().parents[2]
PROBE = REPO / "fixtures" / "_probe" / "gate1"
FIXTURE = REPO / "fixtures" / "gate1" / "real-2026-08-11.json"
PROVENANCE = FIXTURE.with_suffix(".provenance.json")

sys.path.insert(0, str(REPO / "fixtures"))


def _gate() -> object:
    import _gate1_real

    return _gate1_real


def _receipts() -> list[dict[str, object]]:
    return [json.loads(p.read_text(encoding="utf-8"))
            for p in sorted(PROBE.glob("*.json"))]


# ───────────────────────── 一、三道闸各有阴性对照


def test_an_unauthorised_caller_is_refused() -> None:
    """**阴性对照①**：没有逐字给出 `DEC-057` → 拦下。

    默认值是 `None`，也就是「谁都没授权过」——**一个默认放行的闸不是闸**。
    大小写也不放过：`dec-057` 不是 `DEC-057`。
    """
    gate = _gate()
    for given in (None, "", "DEC-052", "dec-057", "DEC-0570"):
        with pytest.raises(gate.NotAuthorised):        # type: ignore[attr-defined]
            gate.RecordingTransport(authorised_by=given)  # type: ignore[attr-defined]

    # 正例：给对了就装得起来
    assert gate.RecordingTransport(  # type: ignore[attr-defined]
        authorised_by="DEC-057",
        inner=httpx.MockTransport(lambda _r: httpx.Response(200, text="x")))


@pytest.mark.parametrize("url,allowed", [
    ("https://api.github.com/search/repositories?q=x", True),
    ("https://github.com/a/b", True),
    ("https://export.arxiv.org/api/query?x", True),
    ("https://arxiv.org/abs/1", True),
    # 后缀匹配落在**点边界**上——否则这一条会被放行
    ("https://github.com.evil.example/x", False),
    ("https://notarxiv.org/x", False),
    # `DEC-052` 的域**不在**本窗口里：两个窗口各自封闭
    ("https://trends.google.com/trending/rss?geo=HK", False),
    ("https://s.weibo.com/top/summary", False),
])
def test_only_the_two_evidence_hosts_are_allowed(url: str, allowed: bool) -> None:
    """**阴性对照②**：域名族之外一律拒（`DEC-057` 逐字「NEVER 扩到任何其他站点」）。"""
    assert _gate().host_allowed(url) is allowed  # type: ignore[attr-defined]


def test_a_host_outside_the_list_raises_before_any_request() -> None:
    """域外那一发**在发出去之前**就被拦下。

    发出去再判的话，那一发已经打出去了——**闸装在事后就不是闸**。
    这里内层用 MockTransport：闸没拦住的话它会回 200，判据就绿了。
    """
    gate = _gate()
    reached: list[str] = []

    def _inner(request: httpx.Request) -> httpx.Response:
        reached.append(str(request.url))
        return httpx.Response(200, text="不该走到这里")

    client = httpx.Client(transport=gate.RecordingTransport(  # type: ignore[attr-defined]
        authorised_by="DEC-057", inner=httpx.MockTransport(_inner)))
    with pytest.raises(gate.OutsideAllowlist):  # type: ignore[attr-defined]
        client.get("https://trends.google.com/x")

    assert reached == [], f"域外那一发真的打出去了：{reached}"


def test_the_budget_is_counted_from_receipts_on_disk() -> None:
    """**阴性对照③**：额度数的是**盘上的回执**，不是内存计数器。

    内存计数器进程重起一次就归零，而 `DEC-057` 那 40 发不会跟着归零。
    """
    gate = _gate()

    assert gate.BUDGET == 40, "额度被改了——那是 owner 写死的数"  # type: ignore[attr-defined]
    assert gate.spent() == len(_receipts())  # type: ignore[attr-defined]
    assert gate.spent() + gate.remaining() >= gate.BUDGET  # type: ignore[attr-defined]


def test_the_run_stayed_inside_the_budget() -> None:
    """那一跑没有超额，且**每份回执自己说得出用到哪儿了**。

    靠人回头数文件的话，超额只会在事后才被发现。
    """
    receipts = _receipts()

    assert receipts, "一份留痕都没有"
    assert len(receipts) <= 40, f"超额了：{len(receipts)} 发"
    for r in receipts:
        assert r["budget"] == 40
        assert isinstance(r["spent_before_this"], int)


# ───────────────────────── 二、留痕齐（格式与 `DEC-052` 同一套）


def test_every_receipt_carries_the_authorisation_and_the_evidence() -> None:
    """每一发都记着**谁授权的**与**它拿回了什么**（`DEC-057` 逐字五项）。"""
    for r in _receipts():
        assert r["schema"] == "probe/1"
        assert r["authorized_by"] == "DEC-057", (
            f"这一发不是 DEC-057 授权的：{r['authorized_by']!r}")
        for key in ("url", "status", "headers", "body_head", "requested_at_utc"):
            assert key in r, f"留痕缺 {key}"
        assert len(str(r["body_head"])) <= 2048, "body 留多了——留痕是给人读的证据"


def test_every_recorded_host_is_inside_the_window() -> None:
    """事后复核：**盘上没有一发打到窗口外**。

    闸是事前拦，这一条是事后查——两者缺一不可：
    闸可能被绕过（有人直接用别的客户端），而留痕不会说谎。
    """
    gate = _gate()
    outside = [r["url"] for r in _receipts()
               if not gate.host_allowed(str(r["url"]))]  # type: ignore[attr-defined]

    assert outside == [], f"这些发打到了窗口外：{outside}"


def test_the_run_only_touched_the_two_sources() -> None:
    """两源之外一个都没有；且两源**都真的被打过**。

    只判「没有第三源」的话，一次只打了 arxiv 的跑也会全绿。
    """
    sources = {r["source"] for r in _receipts()}

    assert sources == {"github", "arxiv"}, sources


# ───────────────────────── 三、夹具是真响应转出来的，且有出处


def test_the_fixture_came_from_that_run() -> None:
    """夹具**有 provenance**，说得出它从哪一跑来的。

    没有出处的夹具，下一个人分不出它是录来的还是编的。
    """
    assert FIXTURE.exists(), "回放夹具没生成"
    prov = json.loads(PROVENANCE.read_text(encoding="utf-8"))

    assert prov["authorized_by"] == "DEC-057"
    assert prov["job_id"].startswith("job-")
    assert prov["real_requests"] == len(_receipts())
    assert prov["distinct_urls"] < prov["real_requests"], (
        "去重之后条数没有变少？那说明每条 URL 只打过一次——"
        "与那一跑实测到的「每条打两遍」对不上")


def test_the_fixture_replays_the_real_github_response() -> None:
    """拿夹具里那份**真 GitHub 响应**离线跑一遍解析。

    NEVER 只断言「夹具里有东西」：那证明不了它能被解析。
    """
    from flint.testing.replay import load_fixture

    got = [e for e in load_fixture(FIXTURE) if "api.github.com" in e.url]
    assert got, "夹具里没有 github 那一份"

    payload = json.loads(got[0].body_text)
    assert payload["total_count"] > 0
    assert payload["items"], "真响应里一个仓库都没有？"
    assert all(item["html_url"].startswith("http") for item in payload["items"])


def test_the_fixture_replays_the_real_arxiv_response() -> None:
    """真 arXiv feed 离线解析得动，且**真的有 entry**。"""
    from datetime import UTC, datetime

    from flint.sources.arxiv import parse_atom
    from flint.testing.replay import load_fixture

    got = [e for e in load_fixture(FIXTURE) if "arxiv.org" in e.url]
    assert got, "夹具里没有 arxiv 那一份"

    with_entries = [e for e in got if "<entry>" in e.body_text]
    assert with_entries, "录到的 arxiv 响应里一条 entry 都没有"
    items = parse_atom(with_entries[0].body_text, categories=None,
                       now=datetime(2026, 8, 11, tzinfo=UTC))
    assert items, "真 feed 解析不出条目"


# ───────────────────────── 四、出口：判定落库且取得回来


def test_the_verdict_snapshot_of_that_run_is_on_the_record() -> None:
    """那一跑的**出口**记在 trace 里，逐条可核。

    出口只写在对话里的话，下一个人无从判断这一跑到底算不算通。
    """
    trace = (REPO / "docs" / "trace" / "GATE1-REAL.md").read_text(encoding="utf-8")

    for must in ("cluster_verdicts", "D_insufficient", "DEC-057",
                 "job-4c558f32", "28"):
        assert must in trace, f"trace 里没写 {must}"


def test_the_read_path_does_not_import_the_generation_channel() -> None:
    """读端点 NEVER import 生成通道——本卡跑通之后这条更要守着。

    判定第一次真的落库之后，最容易的偷懒是让读端点直接去调生成那一侧。
    """
    text = (REPO / "flint" / "repo" / "cluster_verdict.py").read_text(encoding="utf-8")
    # **先剥注释与 docstring 再扫**：那个文件的文件头**正是在解释
    # 「为什么它不 import 生成通道」**，一条只认字面的判据会把那段解释
    # 当成违规本身（本仓这一坑第八次）。
    body = text.split('"""', 2)[-1]
    code = " ".join(ln for ln in body.splitlines()
                    if not ln.strip().startswith("#"))

    assert "flint.jobs" not in code, "读端点开始 import 生成通道了"
    assert "run_gate1" not in code


def test_the_window_is_for_one_run_only() -> None:
    """`DEC-057` 只授权这一次；**每日定时的持续真实分析 NEVER 顺手接上**。

    判据扫的是录制器：它里面 NEVER 出现任何调度器。
    """
    recorder = (REPO / "fixtures" / "_gate1_real.py").read_text(encoding="utf-8")

    for scheduler in ("cron", "schedule", "APScheduler", "while True"):
        assert scheduler not in recorder, f"录制器里出现了调度器：{scheduler}"
    assert "只授权这一次" in recorder
