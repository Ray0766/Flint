"""NET-02：抓来的每条数据带出处（URL + 抓取 UTC 时间戳 + 内容 sha256）。

## 采集侧的「数字必有出处」

三条铁律的第二条是「数字必有出处」。那条律此前只管**生成侧**（Fact / PriceCell /
ProfileRef 三通道）；**采集侧没有对应的落点**——一段抓回来的正文进了库之后，
「它是什么时候、从哪个 URL 抓的、抓到的是不是这一份」没有任何字段能回答。

三样**缺一即拒绝入库**：

| 字段 | 少了它会怎样 |
|---|---|
| 源 URL | 引用它的报告没法回到原处（读者只能选择相信） |
| 抓取 UTC 时间戳 | 源站改版之后，说不清「我们抓的是改版前还是改版后」 |
| 内容 sha256 | 回放时无从确认「这就是当初抓到的那份」——fixture 被改过也看不出来 |

**时间戳必须带时区**：不带时区的在跨时区回放时对不上，而对不上的那一刻没有任何
报错——它只是悄悄指向了另一个时刻。带别的时区也收，但**存成 UTC**：
两种时区的时间戳混在一起没法排序。

**哈希由本模块自己算，NEVER 由调用方给**：调用方给的话，「哈希与内容对不上」
这种状态就存在了，而那正是这个字段要排除的东西。

## 变了就留两版，NEVER 覆盖

同一 URL 重复抓：哈希相同 → 去重（不留第二版，否则每天一版全是同一份东西）；
哈希不同 → **两版都留**并记下变化时间。覆盖掉旧版的话，「源站什么时候改的」
这个问题就永远答不了了。**改回旧内容也算一次变化**——「它变过」与「它现在
长什么样」是两件事。

## fixtures 侧走旁挂清单，不改录制件

`flint/testing/replay.py#RecordedExchange` **一个字不动**：给它加字段会让所有既有
fixture 一次性作废（字段对不上），而那些 fixture 是别的卡的验收依据。
出处存在同目录同名的 `*.provenance.json` 里——同目录是因为分开放的话，
搬一个会忘一个。
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, Literal

RecordOutcome = Literal["new", "unchanged", "changed"]
MANIFEST_SUFFIX: Final[str] = ".provenance.json"


class ProvenanceIncomplete(Exception):
    """三样缺一——**拒绝入库**，NEVER 记一条残的。"""


@dataclass(frozen=True)
class Provenance:
    """一次抓取的出处。不可改——改一条已落库的出处等于伪造它的来源。"""

    url: str
    fetched_at: datetime
    content_sha256: str


def content_sha256(content: str | bytes) -> str:
    """内容哈希。str 按 UTF-8 编码——两种入参走同一口径。"""
    raw = content.encode("utf-8") if isinstance(content, str) else content
    return hashlib.sha256(raw).hexdigest()


def make_provenance(*, url: str, fetched_at: datetime, content: str | bytes) -> Provenance:
    """造一条出处。三样缺一即抛。"""
    if not url:
        raise ProvenanceIncomplete("缺 url：没有 URL 的抓取记录没有出处可言")
    if fetched_at.tzinfo is None:
        raise ProvenanceIncomplete(
            "抓取时间戳缺时区：不带时区的时间戳在跨时区回放时对不上，"
            "而对不上的那一刻没有任何报错"
        )
    return Provenance(
        url=url,
        fetched_at=fetched_at.astimezone(UTC),
        content_sha256=content_sha256(content),
    )


@dataclass
class ProvenanceLog:
    """按 URL 分版的出处账。内存实现；SQL 实现随 E2 接入（同 `SnapshotHistoryStore` 房规）。"""

    _versions: dict[str, list[Provenance]] = field(default_factory=dict)
    _changes: dict[str, list[datetime]] = field(default_factory=dict)

    def record(
        self, *, url: str, fetched_at: datetime, content: str | bytes
    ) -> RecordOutcome:
        """记一次抓取。返回 `new` / `unchanged` / `changed`。"""
        prov = make_provenance(url=url, fetched_at=fetched_at, content=content)
        history = self._versions.setdefault(url, [])
        if not history:
            history.append(prov)
            return "new"
        if history[-1].content_sha256 == prov.content_sha256:
            return "unchanged"                 # 去重：同一份东西不留第二版
        history.append(prov)
        self._changes.setdefault(url, []).append(prov.fetched_at)
        return "changed"

    def versions(self, url: str) -> list[Provenance]:
        """该 URL 的全部版本（**副本**，按抓取顺序）。"""
        return list(self._versions.get(url, []))

    def changes(self, url: str) -> list[datetime]:
        """内容发生变化的时刻——「源站改版可查」就靠这个。"""
        return list(self._changes.get(url, []))


# ── fixtures 侧：旁挂清单 ────────────────────────────────────────────

def manifest_path_for(fixture: Path) -> Path:
    """出处清单与 fixture **同目录同名**——分开放的话，搬一个忘一个。"""
    return fixture.with_suffix("").with_name(fixture.stem + MANIFEST_SUFFIX)


def write_manifest(path: Path, provenances: list[Provenance]) -> None:
    """写清单。时间戳按 ISO + UTC 存——本地时区写进去，换台机器读出来就是另一个时刻。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [
        {
            "url": p.url,
            "fetched_at": p.fetched_at.astimezone(UTC).isoformat(),
            "content_sha256": p.content_sha256,
        }
        for p in provenances
    ]
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8"
    )


def read_manifest(path: Path) -> list[Provenance]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [
        Provenance(
            url=str(item["url"]),
            fetched_at=datetime.fromisoformat(str(item["fetched_at"])),
            content_sha256=str(item["content_sha256"]),
        )
        for item in raw
    ]


def verify_fixture(fixture: Path, manifest: Path) -> list[str]:
    """回放前核一遍：**这就是当初抓到的那份吗**。返回问题清单（空 = 都对上）。

    没有清单文件时返回一条问题而**不是**空清单：「没有清单」与「清单说都对」
    在返回值上必须分得开。
    """
    if not manifest.exists():
        return [
            f"出处清单不在：{manifest}——无从确认这份 fixture 是不是当初抓到的那份"
        ]
    expected = {p.url: p for p in read_manifest(manifest)}
    problems: list[str] = []
    for item in json.loads(fixture.read_text(encoding="utf-8")):
        url = str(item.get("url", ""))
        prov = expected.get(url)
        if prov is None:
            problems.append(f"{url}：录了却没记出处（清单里没有它）")
            continue
        actual = content_sha256(str(item.get("body_text", "")))
        if actual != prov.content_sha256:
            problems.append(
                f"{url}：内容哈希对不上（清单 {prov.content_sha256[:12]}… / "
                f"实际 {actual[:12]}…）——这份 fixture 不是当初抓到的那份"
            )
    return problems
