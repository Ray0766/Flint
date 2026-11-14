"""CN-07：两源的查询窗口写错，**结构上恒回 0 条**，而回执记成 `ok`。

## 不是「今天恰好没有」

| 源 | 改前的窗口 | 为什么恒空 |
|---|---|---|
| ghtrend | `created:>{今天}` | 查的是「创建**晚于今天**」的仓——只有当天当刻之后新建的才落得进来 |
| arxiv | `submittedDate:[{今天} TO {今天}]` | arXiv 有公告延迟、周末整天不公告；凌晨跑必空、周末跑必空 |

`CN-06` 那次真跑（UTC 03:37）实测：ghtrend `total_count: 0` · arxiv 空 feed。
**而回执照旧写 `ok`、当日 `degradation_notes` 0 行**——
盘上完全看不出这两源是空的，广场少了两源也没有人会知道。

## 三件事

1. 窗口改成当天真能取到东西的口径（各 7 天，理由写在各自的 `LOOKBACK_DAYS` 上）；
2. **「跑成了」与「拿到了」分开**：往返成功而 0 条目 → `DegradationNote(reason="empty_result")`；
3. `CN-05` 的契约判据回填——那条此前拿 0 条目响应过的，现在用**真的有条目**的那份。
"""
from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import httpx
import pytest

from flint.sources.arxiv import ArxivSource, parse_atom
from flint.sources.degradation import DegradationReason
from flint.sources.ghtrend import GitHubTrendingSource

REPO = Path(__file__).resolve().parents[2]
PROBE = REPO / "fixtures" / "_probe"
GH_BODY = PROBE / "ghtrend" / "real-search.json"
AX_BODY = PROBE / "arxiv" / "real-feed.xml"
NOW = datetime(2026, 8, 11, tzinfo=UTC)
DAY = date(2026, 8, 10)


def _offline(body: str, ctype: str) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(
        lambda _req: httpx.Response(200, text=body,
                                    headers={"content-type": ctype})))


# ───────────────────────── 一、窗口不再是「当天必空」那一种


def test_the_ghtrend_window_looks_back_instead_of_forward() -> None:
    """`created:>` 的下界是**过去某一天**，NEVER 是当天。

    以当天为下界时，能落进窗口的只有当天当刻之后新建的仓——
    **那不是一个窄窗口，那是一个空窗口**。
    """
    url = GitHubTrendingSource(client=_offline("{}", "application/json"))._url(DAY)
    since = url.split("created:>")[1].split("&")[0]

    assert since < DAY.isoformat(), f"下界还是当天或未来：{since}"
    assert GitHubTrendingSource.LOOKBACK_DAYS >= 1


def test_the_arxiv_window_ends_before_today() -> None:
    """arXiv 的窗口**截到昨天**——当天提交的当天检索不到（公告延迟）。"""
    url = ArxivSource(client=_offline("<feed/>", "application/atom+xml"))._url(DAY)
    window = url.split("submittedDate:[")[1].split("]")[0]
    since, until = window.split("+TO+")

    assert until[:8] < DAY.strftime("%Y%m%d"), f"上界还是当天：{until}"
    assert since[:8] < until[:8], (since, until)


def test_the_reason_for_the_window_size_is_written_down() -> None:
    """`LOOKBACK_DAYS` 的**理由**写在源码里，且两处各写各的。

    不写理由的话，下一个人只会看到一个 `7`——而 7 这个数
    对两源的含义完全不同（一个是「最近在热什么」，一个是「覆盖得住公告延迟与周末」）。
    """
    gh = (REPO / "flint" / "sources" / "ghtrend.py").read_text(encoding="utf-8")
    ax = (REPO / "flint" / "sources" / "arxiv.py").read_text(encoding="utf-8")

    assert "LOOKBACK_DAYS" in gh and "结构上恒空" in gh
    assert "LOOKBACK_DAYS" in ax and "公告延迟" in ax


# ───────────────────────── 二、阴性对照：窗口改回「当天」→ 红且点名


@pytest.mark.parametrize("source", ["ghtrend", "arxiv"])
def test_putting_the_window_back_to_today_makes_it_structurally_empty(
    source: str,
) -> None:
    """**阴性对照**（acceptance⑥）：窗口改回「今天」→ 判据红且**点名是哪一源**。

    造法是拿**真响应**去问：把窗口换回当天之后，那个 URL 与今天录下来的
    这一份**不是同一次查询**——而判据要能说出是哪一源退回去了。

    NEVER 只断言「代码里有 LOOKBACK_DAYS 这个词」：
    `LOOKBACK_DAYS = 0` 面前那种判据照样绿。
    """
    cls = {"ghtrend": GitHubTrendingSource, "arxiv": ArxivSource}[source]
    good = cls(client=_offline("{}", "application/json"))._url(DAY)

    # 旧窗口**逐字重建**（不是用 `LOOKBACK_DAYS = 0` 去模拟——
    # arxiv 那一版两端都是当天，而现在的上界恒为昨天，`0` 造不出它；
    # 第一版就是这么写的，量到的东西与它说的不是一回事）。
    stamp = DAY.strftime("%Y%m%d")
    back_to_today = {
        "ghtrend": f"created:>{DAY.isoformat()}",
        "arxiv": f"submittedDate:[{stamp}0000+TO+{stamp}2359]",
    }[source]

    assert back_to_today not in good, (
        f"{source} 的窗口退回「当天」了——那是一个结构上恒空的查询")


# ───────────────────────── 三、「跑成了」与「拿到了」分开


def test_empty_result_is_its_own_degradation_reason() -> None:
    """往返成功而 0 条目 → **自己一档**，NEVER 与 `fetch_failed` 合并。

    `fetch_failed` 说的是「没问到」，`empty_result` 说的是「问到了，答案是空的」——
    前者去查网络与端点，后者去看窗口与上游。
    """
    from typing import get_args

    assert "empty_result" in get_args(DegradationReason)


def test_a_successful_but_empty_fetch_leaves_a_note() -> None:
    """灌库那一步：0 条目 MUST 落 `DegradationNote`。

    **不落的话回执写着 `ok`、当日 notes 0 行**，
    而广场上少了这一源没有任何人会知道（`CN-06` 那次实测就是这样）。
    """
    code = (REPO / "flint" / "jobs" / "ingest.py").read_text(encoding="utf-8")

    assert 'reason="empty_result"' in code
    assert "if note is None and not items:" in code


# ───────────────────────── 四、真响应里**真的有条目**（acceptance④ 的回填）


def test_the_recorded_ghtrend_response_actually_has_repos() -> None:
    """录下来的那份**不是空的**——0 条目的响应只能证明解析器不崩。"""
    payload = json.loads(GH_BODY.read_text(encoding="utf-8"))

    assert payload["total_count"] > 0, payload["total_count"]
    assert len(payload["items"]) >= 10

    items = GitHubTrendingSource(
        client=_offline(GH_BODY.read_text(encoding="utf-8"), "application/json"),
        now=lambda: NOW).fetch_daily(DAY)
    assert len(items) >= 20, len(items)


def test_the_recorded_arxiv_feed_actually_has_entries() -> None:
    body = AX_BODY.read_text(encoding="utf-8")

    assert body.count("<entry>") >= 10
    assert len(parse_atom(body, categories=None, now=NOW)) >= 10


def test_both_recorded_responses_have_a_probe_receipt() -> None:
    """两份都要有那次往返的留痕（`DEC-052`）。"""
    for source in ("ghtrend", "arxiv"):
        receipts = [json.loads(p.read_text(encoding="utf-8"))
                    for p in (PROBE / source).glob("*.json")]
        ok = [r for r in receipts
              if isinstance(r, dict) and r.get("schema") == "probe/1"
              and r["status"] == 200]
        assert ok, f"{source} 没有成功往返的留痕"
        assert all(r["authorized_by"] == "DEC-052" for r in ok)
