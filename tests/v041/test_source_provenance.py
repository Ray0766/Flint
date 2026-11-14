"""NET-02：抓来的每条数据带出处（URL + 抓取 UTC 时间戳 + 内容 sha256）。

## 采集侧的「数字必有出处」

三条铁律的第二条是「数字必有出处」。此前那条律只管**生成侧**（Fact / PriceCell /
ProfileRef 三通道）；**采集侧没有对应的落点**——一段抓回来的正文进了库之后，
「它是什么时候、从哪个 URL 抓的、抓到的是不是这一份」没有任何字段能回答。

本卡补的就是这三样，且**缺一即拒绝入库**。

## 为什么是这三样

| 字段 | 少了它会怎样 |
|---|---|
| 源 URL | 引用它的报告没法回到原处（读者只能选择相信） |
| 抓取 UTC 时间戳 | 源站改版之后，说不清「我们抓的是改版前还是改版后」 |
| 内容 sha256 | 回放时无从确认「这就是当初抓到的那份」——fixture 被人改过也看不出来 |

时间戳**必须带时区**：不带时区的时间戳在跨时区回放时对不上，而对不上的那一刻
没有任何报错——它只是悄悄指向了另一个时刻。

## 变了就留两版，NEVER 覆盖

同一 URL 重复抓：哈希相同 → 去重（不留第二版）；哈希不同 → **两版都留**，
并记下变化时间。覆盖掉旧版的话，「源站什么时候改的」这个问题就永远答不了了。
"""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

from flint.sources.provenance import (
    ProvenanceIncomplete,
    ProvenanceLog,
    content_sha256,
    make_provenance,
    read_manifest,
    verify_fixture,
    write_manifest,
)

T0 = datetime(2026, 8, 4, 6, 0, tzinfo=UTC)
T1 = T0 + timedelta(days=1)
T2 = T0 + timedelta(days=2)
URL = "https://api.github.com/search/repositories?q=flint"


# ───────────────────────── 一、三样缺一即拒（acceptance①）


def test_a_complete_record_is_accepted() -> None:
    prov = make_provenance(url=URL, fetched_at=T0, content="hello")

    assert prov.url == URL
    assert prov.fetched_at == T0
    assert prov.content_sha256 == hashlib.sha256(b"hello").hexdigest()


def test_an_empty_url_is_refused() -> None:
    """没有 URL 的抓取记录**没有出处可言**。"""
    with pytest.raises(ProvenanceIncomplete, match="url"):
        make_provenance(url="", fetched_at=T0, content="x")


def test_a_naive_timestamp_is_refused() -> None:
    """时间戳**必须带时区**。

    不带时区的在跨时区回放时对不上，而对不上的那一刻没有任何报错——
    它只是悄悄指向了另一个时刻。
    """
    naive = datetime(2026, 8, 4, 6, 0)  # noqa: DTZ001 — 本条测的就是「没有时区」
    with pytest.raises(ProvenanceIncomplete, match="时区"):
        make_provenance(url=URL, fetched_at=naive, content="x")


def test_a_non_utc_timestamp_is_normalised_to_utc() -> None:
    """带别的时区也收，但**存成 UTC**——两种时区的时间戳混在一起没法排序。"""
    east8 = timezone(timedelta(hours=8))
    prov = make_provenance(
        url=URL, fetched_at=datetime(2026, 8, 4, 14, 0, tzinfo=east8), content="x",
    )

    assert prov.fetched_at == datetime(2026, 8, 4, 6, 0, tzinfo=UTC)
    assert prov.fetched_at.tzinfo == UTC


def test_the_hash_is_computed_here_never_taken_from_the_caller() -> None:
    """哈希由本模块**自己算**，NEVER 由调用方给。

    调用方给的话，「哈希与内容对不上」这种状态就存在了——而那正是这个字段
    要排除的东西。
    """
    import inspect

    from flint.sources import provenance

    signature = inspect.signature(provenance.make_provenance)

    assert "content_sha256" not in signature.parameters
    assert "content" in signature.parameters


def test_bytes_and_text_hash_the_same_way() -> None:
    """同一份内容，给 str 还是 bytes 都是同一个哈希（UTF-8 口径）。"""
    assert content_sha256("热点") == content_sha256("热点".encode())


def test_the_provenance_is_frozen() -> None:
    """出处不可改——改一条已经落库的出处，等于伪造它的来源。"""
    prov = make_provenance(url=URL, fetched_at=T0, content="x")

    with pytest.raises(Exception, match="(?i)frozen|cannot assign"):
        prov.url = "https://evil"  # type: ignore[misc]


# ───────────────────────── 二、去重与留两版（acceptance②）


def test_the_first_fetch_is_new() -> None:
    log = ProvenanceLog()

    assert log.record(url=URL, fetched_at=T0, content="v1") == "new"
    assert len(log.versions(URL)) == 1


def test_the_same_content_again_is_deduped() -> None:
    """哈希相同 → 去重，**不留第二版**（否则每天一版，全是同一份东西）。"""
    log = ProvenanceLog()
    log.record(url=URL, fetched_at=T0, content="v1")

    assert log.record(url=URL, fetched_at=T1, content="v1") == "unchanged"
    assert len(log.versions(URL)) == 1


def test_changed_content_keeps_both_versions() -> None:
    """acceptance②：内容变了 → **两版都留**。

    覆盖掉旧版的话，「源站什么时候改的」这个问题就永远答不了了。
    """
    log = ProvenanceLog()
    log.record(url=URL, fetched_at=T0, content="v1")

    assert log.record(url=URL, fetched_at=T1, content="v2") == "changed"

    versions = log.versions(URL)
    assert [v.content_sha256 for v in versions] == [
        content_sha256("v1"), content_sha256("v2"),
    ]


def test_the_change_time_is_recorded() -> None:
    """变化时间要能查——「源站改版可查」是这一条的用处。"""
    log = ProvenanceLog()
    log.record(url=URL, fetched_at=T0, content="v1")
    log.record(url=URL, fetched_at=T1, content="v1")     # 没变
    log.record(url=URL, fetched_at=T2, content="v2")     # 变了

    assert log.changes(URL) == [T2]


def test_going_back_to_an_old_content_is_still_a_change() -> None:
    """改回去也算一次变化——「它变过」与「它现在长什么样」是两件事。"""
    log = ProvenanceLog()
    log.record(url=URL, fetched_at=T0, content="v1")
    log.record(url=URL, fetched_at=T1, content="v2")
    outcome = log.record(url=URL, fetched_at=T2, content="v1")

    assert outcome == "changed"
    assert log.changes(URL) == [T1, T2]
    assert len(log.versions(URL)) == 3


def test_two_urls_never_share_a_history() -> None:
    """不同 URL 各记各的——混在一起的话，一个源改版会被记到另一个源头上。"""
    log = ProvenanceLog()
    log.record(url=URL, fetched_at=T0, content="v1")
    log.record(url="https://arxiv.org/list/cs.AI/recent", fetched_at=T0, content="v1")

    assert len(log.versions(URL)) == 1
    assert log.changes(URL) == []


def test_versions_returns_a_copy() -> None:
    """返回副本：改返回值 NEVER 影响账本（同 FAV-01 / SnapshotPins 口径）。"""
    log = ProvenanceLog()
    log.record(url=URL, fetched_at=T0, content="v1")

    log.versions(URL).clear()

    assert len(log.versions(URL)) == 1


def test_an_incomplete_record_never_enters_the_log() -> None:
    """acceptance①：三样缺一 → **拒绝入库**（不是记一条残的）。"""
    log = ProvenanceLog()

    with pytest.raises(ProvenanceIncomplete):
        log.record(url="", fetched_at=T0, content="x")

    assert log.versions("") == []


# ───────────────────────── 三、fixtures 侧同样带三样（acceptance③）


def test_a_manifest_round_trips(tmp_path: Path) -> None:
    """出处清单写得出、读得回，字段一个不少。"""
    path = tmp_path / "gtrends" / "2026-08-04.provenance.json"
    provs = [make_provenance(url=URL, fetched_at=T0, content="body-1")]

    write_manifest(path, provs)

    assert read_manifest(path) == provs


def test_the_manifest_stores_the_timestamp_as_iso_utc(tmp_path: Path) -> None:
    """时间戳按 ISO + UTC 存——本地时区写进去，换台机器读出来就是另一个时刻。"""
    path = tmp_path / "m.json"
    write_manifest(path, [make_provenance(url=URL, fetched_at=T0, content="b")])

    raw = json.loads(path.read_text(encoding="utf-8"))

    assert raw[0]["fetched_at"].endswith("+00:00")


def test_verify_fixture_passes_when_the_body_still_matches(tmp_path: Path) -> None:
    """acceptance③：回放时能确认「这就是当初抓到的那份」。"""
    fixture = tmp_path / "f.json"
    fixture.write_text(json.dumps([{
        "method": "GET", "url": URL, "status_code": 200,
        "content_type": "application/json", "body_text": "body-1",
    }]), encoding="utf-8")
    manifest = tmp_path / "f.provenance.json"
    write_manifest(manifest, [make_provenance(url=URL, fetched_at=T0, content="body-1")])

    assert verify_fixture(fixture, manifest) == []


def test_verify_fixture_catches_a_tampered_body(tmp_path: Path) -> None:
    """fixture 被改过就报出来——**这正是内容哈希存在的理由**。

    没有这一条，一份被人手改过的回放件与原件长得一模一样，
    而所有基于它的测试都会理直气壮地绿。
    """
    fixture = tmp_path / "f.json"
    fixture.write_text(json.dumps([{
        "method": "GET", "url": URL, "status_code": 200,
        "content_type": "application/json", "body_text": "body-TAMPERED",
    }]), encoding="utf-8")
    manifest = tmp_path / "f.provenance.json"
    write_manifest(manifest, [make_provenance(url=URL, fetched_at=T0, content="body-1")])

    problems = verify_fixture(fixture, manifest)

    assert len(problems) == 1
    assert URL in problems[0]
    assert "哈希" in problems[0]


def test_verify_fixture_catches_a_missing_manifest_entry(tmp_path: Path) -> None:
    """录了却没记出处 → 报出来，NEVER 当成「这条不用查」。"""
    fixture = tmp_path / "f.json"
    fixture.write_text(json.dumps([
        {"method": "GET", "url": URL, "status_code": 200,
         "content_type": "", "body_text": "a"},
        {"method": "GET", "url": "https://other/x", "status_code": 200,
         "content_type": "", "body_text": "b"},
    ]), encoding="utf-8")
    manifest = tmp_path / "f.provenance.json"
    write_manifest(manifest, [make_provenance(url=URL, fetched_at=T0, content="a")])

    problems = verify_fixture(fixture, manifest)

    assert len(problems) == 1
    assert "https://other/x" in problems[0]


def test_a_missing_manifest_file_is_a_problem_not_a_pass(tmp_path: Path) -> None:
    """清单文件不在 → 报问题，**NEVER 返回「没问题」**。

    「没有清单」与「清单说都对」在返回值上必须分得开。
    """
    fixture = tmp_path / "f.json"
    fixture.write_text("[]", encoding="utf-8")

    problems = verify_fixture(fixture, tmp_path / "absent.provenance.json")

    assert problems and "清单" in problems[0]


def test_the_manifest_path_sits_next_to_the_fixture() -> None:
    """清单与 fixture **同目录同名**——分开放的话，搬一个忘一个。"""
    from flint.sources.provenance import manifest_path_for

    assert manifest_path_for(Path("fixtures/gtrends/2026-08-04.json")) == Path(
        "fixtures/gtrends/2026-08-04.provenance.json"
    )


# ───────────────────────── 四、不碰既有录制模块


def test_the_existing_replay_module_is_untouched() -> None:
    """`flint/testing/replay.py` 一个字没动——本卡走**旁挂清单**，不改录制件形状。

    改 `RecordedExchange` 会让所有既有 fixture 一次性作废（字段对不上），
    而那些 fixture 是别的卡的验收依据。
    """
    import inspect

    from flint.testing import replay

    assert "NET-02" not in inspect.getsource(replay)
    assert "content_sha256" not in inspect.getsource(replay.RecordedExchange)
