"""DOC-03：证据卡吃正文（卡真变厚）+ 引文端点把正文三件套给出去。

## 「变厚」要能被量出来，不能靠感觉

acceptance① 要的是「用**每卡可引用事实数**的前后对照证明」。所以本卡的核心判据是
一个可复现的对照：同一张卡、同一批 Doc，一次只有 `title` + `url`（DOC-02 之前的世界），
一次带上正文——两次数出来的可引用条目数必须**差得出来**。

## 三通道纪律：正文里抽出来的**只进 Fact 通道**

S2-2 的三条通道各有各的来源：

| 通道 | 来源 | 正文能不能产它 |
|---|---|---|
| `Fact` | 陈述 + 数值 + 引用 | **能**——本卡抽的就是它 |
| `PriceCell` | PriceBook 的价目行 | **NEVER**——价格要有价目出处，从正文里读一个数当价格就是编造出处 |
| `ProfileRef` | 用户档案字段 | **NEVER**——正文里没有「这个用户的档案」 |

判据把这条钉死：抽取器的产物一律带 `channel == "fact"`，且模块里 NEVER 出现
构造 PriceCell / ProfileRef 的路径。

## 截断标记一路传到产物

DOC-02 存下了 `content_truncated`。截断过的正文里抽出来的事实，**必须带着那个标记**
一路走到产物——不确定 NEVER 伪装成确定。一条抽自被截断正文的事实，
读者有权知道「这篇后面还有，我们没读到」。
"""
from __future__ import annotations

import sys
from datetime import UTC, date, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from flint.evidence.enrich import (
    ExtractedFact,
    citable_fact_count,
    extract_facts_from_content,
    thickening_report,
)

NOW = datetime(2026, 8, 5, 0, 0, 0, tzinfo=UTC)

BODY = (
    "固态电池的量产成本在 2026 年降到每千瓦时 78 美元。"
    "宁德时代宣布 2027 年产线扩产至 120 GWh。"
    "这一段没有任何数字，只是背景描述。"
    "行业渗透率预计达到 15%。"
)


def _doc(**over: object) -> object:
    from contracts_v04.models_v04 import Doc

    base = {
        "doc_id": "d-1", "source_id": "gtrends", "kind": "news", "title": "固态电池成本",
        "url": "https://x.test/a", "published_at": date(2026, 8, 1), "meta": {},
        "origin": "retrieved", "access": "public", "region": None, "source_country": None,
        "content": BODY, "content_sha256": "sha-1", "content_truncated": False,
    }
    base.update(over)
    return Doc(**base)  # type: ignore[arg-type]


# ───────────────────────── 一、从正文抽事实（acceptance①）


def test_a_sentence_with_a_number_becomes_a_citable_fact() -> None:
    facts = extract_facts_from_content(_doc(), now=NOW)

    assert facts, "带数字的正文一条事实都没抽出来"
    assert any("78" in (f.value or "") for f in facts)


def test_the_statement_is_the_sentence_it_came_from() -> None:
    """陈述要能对回原文那一句——对不回去的话，引用就无从核验。"""
    facts = extract_facts_from_content(_doc(), now=NOW)

    for fact in facts:
        assert fact.statement in BODY, f"这条陈述不在原文里：{fact.statement}"


def test_a_sentence_without_a_number_yields_nothing() -> None:
    """没有数值的句子不产事实。

    产了的话，「事实」就退化成「正文的分句」——那不是可引用的事实，
    是把整篇文章按句号切开。
    """
    facts = extract_facts_from_content(_doc(content="这一段没有任何数字。"), now=NOW)

    assert facts == []


def test_every_fact_carries_the_doc_it_came_from() -> None:
    """每条事实都要指回它的 doc：指不回去的数字就是没有出处的数字。"""
    facts = extract_facts_from_content(_doc(doc_id="d-42"), now=NOW)

    assert facts
    for fact in facts:
        assert fact.doc_id == "d-42"
        assert fact.url == "https://x.test/a"


def test_a_doc_without_content_yields_nothing_rather_than_guessing() -> None:
    """`content=None` 是「还没提取」——NEVER 从标题里凑一条事实出来。

    标题里**带数字**：不带数字的标题证明不了这条——抽取器就算真的回落到标题，
    也会因为标题里没有数值而交白卷，判据照样绿（变异考⑤ 实测就是这么活下来的）。
    """
    assert extract_facts_from_content(
        _doc(content=None, title="固态电池成本降到每千瓦时 78 美元"), now=NOW) == []


def test_an_empty_body_does_not_fall_back_to_the_title_either() -> None:
    """`content=""` 是「提取过、结果是空」——同样 NEVER 回落到标题。

    回落的话，一条「抽自正文」的事实实际抽自标题，而标题是我们自己写的摘要，
    不是那篇文章说的话。
    """
    assert extract_facts_from_content(
        _doc(content="", title="产能扩至 120 GWh"), now=NOW) == []


def test_an_empty_body_yields_nothing_and_does_not_crash() -> None:
    assert extract_facts_from_content(_doc(content=""), now=NOW) == []


def test_units_are_read_off_the_sentence_not_invented() -> None:
    """单位从句子里读，读不到就留空——**NEVER 猜一个单位**。

    猜出来的单位会让一个数字变成另一个量：78「美元」与 78「元」差着一个汇率，
    而读者看不出这是猜的。
    """
    facts = extract_facts_from_content(
        _doc(content="产能达到 120 GWh。渗透率是 15%。这一年编号 2031 号文件发布。"),
        now=NOW)

    by_value = {f.value: f.unit for f in facts}
    assert by_value.get("120") == "GWh"
    assert by_value.get("15") == "%"
    assert by_value.get("2031") is None, "没有单位的数字被安上了一个单位"


# ───────────────────────── 二、三通道纪律（acceptance③）


def test_everything_extracted_lands_in_the_fact_channel() -> None:
    """正文抽出来的一律走 Fact 通道。"""
    facts = extract_facts_from_content(_doc(), now=NOW)

    assert facts
    assert {f.channel for f in facts} == {"fact"}


def test_the_extractor_never_builds_a_price_cell_or_a_profile_ref() -> None:
    """抽取器里 NEVER 出现另两条通道的构造路径。

    正文里的 78 美元看起来很像一个价格——但价格要有**价目出处**（PriceBook），
    从正文里读一个数当价格就是编造出处。这条判据打在源码上：
    抽取那一段里出现 `PriceCell` / `ProfileRef` 即红。
    """
    import inspect

    from flint.evidence import enrich

    source = inspect.getsource(enrich.extract_facts_from_content)

    assert "PriceCell" not in source
    assert "ProfileRef" not in source


def test_a_currency_amount_is_still_a_fact_not_a_price_cell() -> None:
    """正文里的金额照样只进 Fact 通道，带着它的单位。"""
    facts = extract_facts_from_content(
        _doc(content="托管月成本是 12.5 美元。"), now=NOW)

    assert [f.channel for f in facts] == ["fact"]
    assert facts[0].unit == "美元"


# ───────────────────────── 三、截断标记一路传到产物（acceptance④）


def test_facts_from_a_truncated_body_are_marked() -> None:
    """截断过的正文抽出的事实**带截断标记**——不确定 NEVER 伪装成确定。"""
    facts = extract_facts_from_content(_doc(content_truncated=True), now=NOW)

    assert facts
    assert all(f.from_truncated for f in facts)


def test_facts_from_a_whole_body_are_not_marked() -> None:
    """反向：没截断就不许标。见谁都标一遍的标记等于没有标记。"""
    facts = extract_facts_from_content(_doc(content_truncated=False), now=NOW)

    assert facts
    assert not any(f.from_truncated for f in facts)


def test_the_truncation_mark_has_a_reader_facing_note() -> None:
    """标记要能说成人话：只给一个布尔，产物上就只能显示 `True`。"""
    facts = extract_facts_from_content(_doc(content_truncated=True), now=NOW)

    assert facts[0].note
    assert "截断" in facts[0].note


# ───────────────────────── 四、前后对照：卡真的变厚了（acceptance①）


def test_the_before_and_after_counts_are_measured_not_asserted_by_hand() -> None:
    """「变厚」由**同一段代码**数出来，NEVER 一个手写的期望值。

    手写期望值的话，抽取器退化成一条都不抽时，只要把期望值也改成 0 就绿了。
    """
    docs = [_doc(doc_id="d-1"), _doc(doc_id="d-2", content="产能 120 GWh。")]

    report = thickening_report(card_id="c-1", docs=docs, now=NOW)

    assert report.before == citable_fact_count([], [])
    assert report.after == len(
        [f for d in docs for f in extract_facts_from_content(d, now=NOW)])


def test_the_card_really_gets_thicker() -> None:
    """前后对照：带正文之后可引用事实数**严格变多**。"""
    docs = [_doc(doc_id="d-1"), _doc(doc_id="d-2", content="产能 120 GWh。")]

    report = thickening_report(card_id="c-1", docs=docs, now=NOW)

    assert report.after > report.before
    assert report.before == 0, "DOC-02 之前的世界里，卡上一条可引用事实都没有"


def test_a_card_whose_docs_have_no_content_does_not_pretend_to_thicken() -> None:
    """没正文的卡照实报 0→0，NEVER 报一个好看的增量。"""
    report = thickening_report(
        card_id="c-2", docs=[_doc(content=None), _doc(doc_id="d-3", content=None)], now=NOW)

    assert (report.before, report.after) == (0, 0)
    assert report.thickened is False


def test_the_report_names_the_card_and_carries_the_truncation_tally() -> None:
    """报告要说清是哪张卡、其中几条抽自被截断的正文。"""
    docs = [_doc(doc_id="d-1"), _doc(doc_id="d-2", content_truncated=True)]

    report = thickening_report(card_id="c-3", docs=docs, now=NOW)

    assert report.card_id == "c-3"
    assert report.from_truncated > 0
    assert report.from_truncated <= report.after


# ───────────────────────── 四·五、引文端点把正文两位给出去（acceptance②）
#
# **卡面与实况有一处对不上，如实记在这里**：卡上写的是「FB-06 引文端点**预留**的
# content / content_sha256 / content_truncated 三个位填上真值，不再是 null +
# 「接口未提供」」。实查 FB-06 的产物：`citation_json` **从来没有过这三个位**
# （它只回 citation 四字段 + doc 的六项 + 两条纪律位）。所以本卡是**新增**这两位，
# 不是「填上预留位」。差异见 trace §4；做出来的东西与卡的意图一致。
#
# 三个位里只落两位：`content` 本身**不进引用响应**——那个端点回的是「一条引用」，
# 不是「一篇文章」。理由写在 `citation_json` 的 docstring 里。


def _citation_row(**over: object) -> dict[str, object]:
    row: dict[str, object] = {
        "citation_id": "cit-1", "doc_id": "d-1", "locator": None,
        "quote_span": "固态电池成本降到每千瓦时 78 美元",
        "title": "固态电池成本", "url": "https://x.test/a", "kind": "news",
        "published_at": date(2026, 8, 1), "origin": "retrieved", "access": "public",
        "content_sha256": "abc123", "content_truncated": False,
    }
    row.update(over)
    return row


def test_the_citation_response_carries_the_content_fingerprint() -> None:
    """`content_sha256` 随文献给出：下游据此判断手上这份引文与库里那篇是不是同一份。"""
    from flint.api.deref import citation_json

    body = citation_json(_citation_row())

    assert body["doc"]["content_sha256"] == "abc123"


def test_the_citation_response_says_when_the_body_was_truncated() -> None:
    """截断态给出去，并附一句人话——只给布尔的话，产物上只能显示 `True`。"""
    from flint.api.deref import citation_json

    body = citation_json(_citation_row(content_truncated=True))

    assert body["doc"]["content_truncated"] is True
    assert "截断" in str(body["doc"]["content_note"])


def test_an_untruncated_citation_carries_no_scary_note() -> None:
    """反向：没截断就不留那句话。见谁都提醒一遍的提醒等于没有提醒。"""
    from flint.api.deref import citation_json

    body = citation_json(_citation_row(content_truncated=False))

    assert body["doc"]["content_truncated"] is False
    assert body["doc"]["content_note"] is None


def test_a_doc_that_was_never_extracted_reports_null_not_a_fake_hash() -> None:
    """还没提取正文时 `content_sha256` 是 `None`——NEVER 编一个哈希顶上。"""
    from flint.api.deref import citation_json

    body = citation_json(_citation_row(content_sha256=None))

    assert body["doc"]["content_sha256"] is None


def test_the_body_itself_stays_out_of_the_citation_response() -> None:
    """正文本身**不进**引用响应：那个端点回的是一条引用，不是一篇文章。

    塞进去的话，前端每展开一条引用就要下载一篇文章。
    """
    from flint.api.deref import citation_json

    body = citation_json(_citation_row())

    assert "content" not in body["doc"]
    assert "content" not in body


def test_the_citation_sql_actually_selects_the_two_columns() -> None:
    """SQL 里真的取了这两列——`citation_json` 读得到什么，取决于查询给了什么。

    只判序列化函数的话，把 SQL 里那两列删掉，响应里两位会变成 `None`
    而这条判据照样绿（`row.get` 不会报错）。
    """
    from flint.api.deref import _CITATION_SQL

    assert "d.content_sha256" in _CITATION_SQL
    assert "d.content_truncated" in _CITATION_SQL


def test_the_citation_channel_is_still_the_citation_channel() -> None:
    """加了两位不改通道：引用仍走 citation 通道，NEVER 因为带上正文指纹就变成别的。"""
    from flint.api.deref import citation_json

    body = citation_json(_citation_row())

    assert body["channel"] == "citation"


# ───────────────────────── 五、ExtractedFact 自己的形状


def test_an_extracted_fact_is_frozen() -> None:
    """抽出来的事实不可变：产物上那条陈述与它的出处 NEVER 在运行期被改写。"""
    import dataclasses

    import pytest

    fact = extract_facts_from_content(_doc(), now=NOW)[0]

    assert isinstance(fact, ExtractedFact)
    with pytest.raises(dataclasses.FrozenInstanceError):
        fact.value = "999"  # type: ignore[misc]
