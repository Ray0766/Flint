"""CN-06：端到端真实录制一次 → 灌库 → 广场显当天真热点。

判据**全部离线回放本卡录下的真实夹具**（`S2-7`：CI 恒不联网）。
"""
from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
FIXTURES = REPO / "fixtures"
RECORDER = FIXTURES / "_record_cn_real.py"
RECEIPT = REPO / "docs" / "cn-01-real-ingest-receipt.json"
ROBOTS = FIXTURES / "robots"
ZH = REPO / "web" / "messages" / "zh.json"
SOURCES = ("weibo", "gtrends", "ghtrend", "arxiv")


def _receipt() -> dict[str, object]:
    return json.loads(RECEIPT.read_text(encoding="utf-8"))


def _day() -> str:
    return str(_receipt()["day"])


# ───────────────────────── 一、说真话的旗标


def test_the_recorder_has_its_own_authorised_flag() -> None:
    """`DEC-052` 预授权的运行用 `--authorized-by=DEC-052`。

    **NEVER 冒用 `--owner-is-here`**：那个旗标的语义是「owner 此刻在场」，
    而这个窗口是预授权、owner 并不在场。
    **旗标的名字就是它的诚实性**——冒用一次之后，
    盘上再也分不出「谁点的头」，而那正是这两个旗标存在的全部理由。
    """
    code = RECORDER.read_text(encoding="utf-8")

    assert '"--authorized-by"' in code
    # 那个旗标的语义**一字不动**。
    assert "owner 此刻在场" in code or "owner 当场点头" in code
    assert "NEVER 做成环境变量" in code


def test_the_receipt_says_who_authorised_it() -> None:
    """回执分得出「owner 在场那一次」与「预授权那一次」。"""
    receipt = _receipt()

    assert receipt["authorized_by"] == "DEC-052", receipt


def test_both_dates_are_printed_and_recorded() -> None:
    """acceptance⑤：UTC 与本机两个日期都要有（owner 被单时钟绊过一次）。"""
    code = RECORDER.read_text(encoding="utf-8")
    receipt = _receipt()

    assert "本机日期" in code and "UTC 日期" in code
    assert "utc_date" in receipt and "local_date" in receipt
    # 夹具命名照旧只按 UTC（`E12`），NEVER 改。
    assert receipt["day"] == receipt["utc_date"]


# ───────────────────────── 二、四源各录各的（本卡实测栽过一次）


def test_every_source_has_its_own_adapter_in_one_place() -> None:
    """**分派收在一处**。

    改前是「weibo 用 `WeiboHotSource`，**其余一律 `GoogleTrendsSource`**」——
    两源时代那是对的。扩到四源之后它把 `ghtrend` 与 `arxiv`
    **都录成了 gtrends 的响应**，而回执报的是 `ok`。

    **这比失败更坏**：失败会喊，而这一种安安静静地把三份一样的东西
    存进三个不同的目录，且它们有 manifest、有 sha256、看起来样样齐全。
    """
    code = RECORDER.read_text(encoding="utf-8")

    assert "_ADAPTERS" in code
    assert 'else GoogleTrendsSource' not in code, "分派又散回 if/else 了"
    for source in SOURCES:
        assert f'"{source}"' in code


@pytest.mark.parametrize("source", SOURCES)
def test_each_source_recorded_its_own_endpoint(source: str) -> None:
    """provenance 里记的是**那一源自己的** URL。

    这一条就是上面那个缺陷的现场证据：改前 `ghtrend` 与 `arxiv` 的 manifest
    里躺着 `trends.google.com/trending/rss?geo=HK`。
    """
    expected = {
        "weibo": "weibo.com",
        "gtrends": "trends.google.com/trending/rss?geo=HK",
        "ghtrend": "api.github.com/search/repositories",
        "arxiv": "export.arxiv.org/api/query",
    }[source]
    manifest = json.loads(
        (FIXTURES / source / f"{_day()}.provenance.json").read_text(encoding="utf-8"))
    urls = " ".join(e["url"] for e in manifest)

    assert expected in urls, f"{source} 的 manifest 记的不是它自己的端点：{urls[:120]}"


@pytest.mark.parametrize("source", SOURCES)
def test_the_three_artefacts_are_all_there(source: str) -> None:
    """抓完必录：fixtures + provenance manifest + robots 快照，**三样缺一即 fail**。"""
    fixture = FIXTURES / source / f"{_day()}.json"
    manifest = FIXTURES / source / f"{_day()}.provenance.json"

    assert fixture.exists(), fixture
    assert manifest.exists(), manifest
    # **NEVER 按字节数判**：那是一个拍出来的门槛。
    # `ghtrend` 当天只有 303 字节（`created:>今天` 在 UTC 凌晨自然没什么仓库），
    # 而那份响应**是真的也是合法的**——按字节判会把一个诚实的空日子判成缺陷。
    # 判的是「它真的是一次记下来的往返」。
    recorded = json.loads(fixture.read_text(encoding="utf-8"))
    assert recorded and recorded[-1]["status_code"] == 200, recorded[:1]
    assert recorded[-1]["body_text"].strip(), "录下来的是空正文"


def test_a_source_with_nothing_that_day_is_still_recorded_honestly() -> None:
    """**「那天没有」也要录下来**，NEVER 当成失败、也 NEVER 补一份假的。

    `ghtrend` 这一次录到的是 `total_count: 0`——`created:>今天` 在 UTC 凌晨
    自然没什么新仓库。那份响应是真的、合法的，回执照实记 `ok`。

    这与 `CN-05` 给 arxiv 接上 `totalResults` 是同一条纪律：
    **「查过了、是空的」是一等答案**。
    """
    body = json.loads(
        (FIXTURES / "ghtrend" / f"{_day()}.json").read_text(encoding="utf-8")
    )[0]["body_text"]
    payload = json.loads(body)

    assert "total_count" in payload, "少了那个能分辨空与坏的字段"
    assert isinstance(payload.get("items"), list)


@pytest.mark.parametrize("source", SOURCES)
def test_every_source_came_back_ok(source: str) -> None:
    """四源全部抓成。抓失败的源**如实降级**——这里断言这一次没有失败的。"""
    row = next(r for r in _receipt()["results"] if r["source"] == source)  # type: ignore[index,union-attr]

    assert row["outcome"] == "ok", row


# ───────────────────────── 三、DEC-054 的三件东西


def test_the_screen_name_no_longer_needs_the_region_suffix() -> None:
    """第三件**随代理口径一起退役**（`DEC-056`）。

    这一条改前断言署名必须是「Google 趋势（港区）」——那是 `DEC-054`
    代理口径的第三条腿：数据采自 HK 而**落在 CN 区**时，
    署名是用户那一侧唯一能看出这件事的地方，缺了它屏上就是
    「港区的榜冒充大陆热点」。

    `DEC-056` 两区分家之后 `region` 本身就是 HK，
    **再把地区缀进源名字里，是把两根正交轴拧成一根**
    （`PRINCIPLES#A3`：源与地区各是一根轴）。

    所以这一条从「必须带港区」翻成「必须不带」——**同一件事的两面**：
    署名 MUST 与库里的 region 说同一件事，NEVER 各说各的。
    翻面而不是删掉：它守的那件事一天都没有松动过。
    """
    messages = json.loads(ZH.read_text(encoding="utf-8"))
    shown = messages["source.name.gtrends"]

    assert shown == "Google 趋势"
    assert "港区" not in shown, f"署名又带上地区了：{shown!r}"


def test_the_manifest_keeps_the_real_hk_url() -> None:
    """第二件：manifest 记的是**真实的 `geo=HK` 地址**，NEVER 一个 `geo=CN` 的假地址。"""
    manifest = json.loads(
        (FIXTURES / "gtrends" / f"{_day()}.provenance.json").read_text(encoding="utf-8"))
    urls = [e["url"] for e in manifest]

    assert any("geo=HK" in u for u in urls), urls
    assert all("geo=CN" not in u for u in urls), urls


# ───────────────────────── 四、录下来的是真词面（离线回放）


def test_the_recorded_weibo_board_has_real_words_not_synthetic_ones() -> None:
    """录下来的是真榜——`热搜话题NN` 那批合成词面**一个都没有**。"""
    body = json.loads(
        (FIXTURES / "weibo" / f"{_day()}.json").read_text(encoding="utf-8"))[-1]["body_text"]

    assert "热搜话题" not in body, "录下来的还是合成夹具"
    assert body.count('class="td-02"') >= 20


def test_the_pinned_row_is_skipped_and_named() -> None:
    """置顶行如实跳过，且 `skipped_rows()` **说得出是哪一条**。

    广场因此会少一条真热搜——那是有意的（`CN-04` acceptance 第 11 条：
    NEVER 判整页漂移、NEVER 编一个热度），而**它必须是可见的**。
    """
    from flint.sources.weibo import parse_board, skipped_rows

    body = json.loads(
        (FIXTURES / "weibo" / f"{_day()}.json").read_text(encoding="utf-8"))[-1]["body_text"]
    items = parse_board(body, now=datetime(2026, 8, 10, tzinfo=UTC))
    skipped = skipped_rows()

    assert items, "一条都没解析出来"
    assert any(s.startswith("pinned:") for s in skipped), skipped
    # 跳过的那一条**有名字**——只说「跳了一行」的话，没人知道少了什么。
    assert all(len(s.split(":", 1)[1]) > 1 for s in skipped), skipped


def test_the_recorded_gtrends_feed_is_the_hk_board() -> None:
    """gtrends 录的是港区那一份，且热度是**区间下界**。"""
    body = json.loads(
        (FIXTURES / "gtrends" / f"{_day()}.json").read_text(encoding="utf-8"))[0]["body_text"]

    assert "geo=HK" in body
    assert "ht:approx_traffic" in body
    assert re.search(r"<ht:approx_traffic>\d+\+?</ht:approx_traffic>", body)


# ───────────────────────── 五、每日定时采集 NEVER 顺手接上


def test_no_scheduled_real_collection_was_wired() -> None:
    """acceptance⑧：**每日定时的持续真实采集 NEVER 在本卡接上**。

    那是上线动作，`DEC-052` 明写不含它。
    """
    code = RECORDER.read_text(encoding="utf-8")

    for scheduler in ("schedule.every", "APScheduler", "croniter", "cron_job"):
        assert scheduler not in code, f"接上了定时采集：{scheduler}"
