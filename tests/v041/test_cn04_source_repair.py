"""CN-04：两源适配器按真实契约重建（`DEC-053` weibo · `DEC-054` gtrends）。

## 判据全部离线跑

回放的是 `fixtures/_probe/gtrends/real-hk-rss.xml`——**今天从真实站点抓下来的那一份**
（探测留痕 `fixtures/_probe/gtrends/*.json` 记着它的 url / status / 时间戳）。
`S2-7`：CI 恒不联网，所以这里**一个真实请求都不发**。

`ParseDrift` 的阴性对照**拿这份真响应改坏一处**构造，
NEVER 手编一个「想象中的坏响应」——手编的那种只证明解析器认得我编的东西。
"""
from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import httpx
import pytest

from flint.sources.errors import ParseDrift, RateLimitedError, SourceFetchError
from flint.sources.gtrends import (
    EMIT_REGION,
    FETCH_GEO,
    SOURCE_DISPLAY_NAME,
    GoogleTrendsSource,
    board_url,
    parse_rss,
    parse_traffic,
)

REPO = Path(__file__).resolve().parents[2]
PROBE = REPO / "fixtures" / "_probe" / "gtrends"
REAL_RSS = PROBE / "real-hk-rss.xml"
NOW = datetime(2026, 8, 10, 1, 0, tzinfo=UTC)
DAY = date(2026, 8, 10)


def _body() -> str:
    return REAL_RSS.read_text(encoding="utf-8")


def _client(body: str = "", status: int = 200) -> httpx.Client:
    """离线客户端：所有请求回同一份预置响应。**一个包都不发。**"""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, text=body or _body())

    return httpx.Client(transport=httpx.MockTransport(handler))


# ───────────────────────── 一、真实响应真的解析得动


def test_the_real_response_is_on_disk_with_its_probe_receipt() -> None:
    """夹具源是**真抓下来的**，且那次往返有留痕——两样缺一，这组判据就没有依据。"""
    assert REAL_RSS.exists(), "真实响应不在盘上"
    receipts = [json.loads(p.read_text(encoding="utf-8"))
                for p in PROBE.glob("*.json")]
    hk = [r for r in receipts if r["url"].endswith("geo=HK") and r["status"] == 200]

    assert hk, "没有一次 geo=HK 的成功往返留痕"
    assert hk[0]["authorized_by"] == "DEC-052"


def test_parsing_the_real_response_yields_real_keywords() -> None:
    """解析真实响应 → 拿到真词面。**NEVER 只断言「没抛异常」**。"""
    items = parse_rss(_body(), now=NOW, url=board_url())

    assert len(items) >= 5, f"只解析出 {len(items)} 条"
    assert all(i.keyword.strip() for i in items), "有条目没有词面"
    # 真实港区榜是中文的——合成夹具那批 `热搜话题NN` 不长这样。
    assert any(any("\u4e00" <= ch <= "\u9fff" for ch in i.keyword) for i in items)


def test_the_score_is_the_lower_bound_never_a_made_up_number() -> None:
    """`ht:approx_traffic` 是**区间下界**（`DEC-054`）。"""
    assert parse_traffic("200+") == 200.0
    assert parse_traffic("100+") == 100.0
    assert parse_traffic("20K+") == 20_000.0

    items = parse_rss(_body(), now=NOW, url=board_url())
    assert all(i.score > 0 for i in items), "有条目热度是 0——上游不给时该抛，不是记 0"


# ───────────────────────── 二、DEC-054 的三件东西（`DEC-056` 之后**只剩证据链那一件**）


def test_the_url_still_keeps_the_real_hk_address() -> None:
    """**真实地址一字不改地留在 `url` 里**（`DEC-054` 第二件，`DEC-056` 之后照旧）。

    改前这条判据同时断言「落 CN」——那是 `DEC-054` 的代理口径，
    `DEC-056`（owner 2026-08-10）**撤销了它**：CN = 微博，HK = Google 趋势，
    落库地区改成 HK，与采集地区一致。

    **翻面而不是删掉**：这一条守的那件事一天都没有松动过——
    provenance 记的 URL MUST 是真的那一份。代理口径没了之后它仍然要守，
    因为往 `url` 里写一个 `geo=CN` 的地址，任何时候都是把出处改掉。

    「落哪个区」那一半搬去了 `test_region_cn_hk.py`（本卡的继任者）。
    """
    items = parse_rss(_body(), now=NOW, url=board_url())

    assert FETCH_GEO == "HK" and EMIT_REGION == "HK", "DEC-056：两者一致"
    assert all(i.region == "HK" for i in items)
    assert all(i.url == "https://trends.google.com/trending/rss?geo=HK"
               for i in items)
    assert all("geo=CN" not in i.url for i in items)


def test_the_display_name_no_longer_needs_to_say_hong_kong() -> None:
    """署名**不再带地区缀**（`DEC-054` 第三件随代理口径一起退役）。

    那个后缀当初是代理口径唯一在用户那一侧看得见的部分：
    数据采自 HK 而落在 CN 区时，没有它，屏上就是「港区的榜冒充大陆热点」。

    `DEC-056` 两区分家之后 `region` 本身就是 HK，
    **再把地区缀进源名字里，是把两根正交轴拧成一根**
    （`PRINCIPLES#A3`：源与地区各是一根轴）。

    这一条因此从「必须带港区」翻成「必须不带」——**同一件事的两面**：
    署名 MUST 与库里的 region 说同一件事，NEVER 各说各的。
    """
    assert SOURCE_DISPLAY_NAME == "Google 趋势"
    assert GoogleTrendsSource.display_name == SOURCE_DISPLAY_NAME
    assert "港区" not in GoogleTrendsSource.display_name


def test_the_module_records_why_the_proxy_exists_and_when_it_ends() -> None:
    """代理口径与**它的退出条件**都写在文件头里。

    只写「采 HK 落 CN」而不写为什么、不写什么时候撤销的话，
    下一版做多区的人会把它当成一条正常口径留着。
    """
    text = (REPO / "flint" / "sources" / "gtrends.py").read_text(encoding="utf-8")

    assert "DEC-054" in text
    assert "geo=CN` 回 400" in text or "geo=CN" in text
    # 退出条件**兑现了**：`DEC-056` 是它自己写下的那个条件触发的。
    # 文件头因此要同时留着「当初为什么代理」与「什么时候撤的」——
    # 只留后者的话，下一个人读不出这个源为什么曾经采一个地方、落另一个地方。
    assert "下一版做多区时本代理口径撤销" in text
    assert "DEC-056" in text


# ───────────────────────── 三、旧端点 NEVER 再出现


def test_the_dead_endpoint_is_gone() -> None:
    """`dailytrends` 已被 Google 下线（实测 404）——它 NEVER 再出现在取数路上。

    留着它的话，下一个人会以为还有一条备用路，而那条路今天回的是 404 页面。
    """
    text = (REPO / "flint" / "sources" / "gtrends.py").read_text(encoding="utf-8")
    code = "\n".join(ln for ln in text.splitlines()
                     if not ln.strip().startswith("#"))
    body = code.split('"""', 2)[-1]        # 去掉模块 docstring（那里记着它为什么死）

    assert "api/dailytrends" not in body
    assert board_url().startswith("https://trends.google.com/trending/rss?geo=")


def test_the_new_endpoint_never_pretends_to_accept_a_date() -> None:
    """新端点不吃日期——**NEVER 硬拼一个上游不认的 query 去装作能选日期**。

    拼上去它照样回今天那一份，而调用方会以为自己取到了那一天。
    """
    source = GoogleTrendsSource(client=_client())

    assert source._url(DAY) == source._url(date(2020, 1, 1))
    assert "ed=" not in source._url(DAY)


# ───────────────────────── 四、错误分类一一对应（不增不减不改名）


def test_rate_limit_and_fetch_errors_keep_their_own_names() -> None:
    """429 → `RateLimitedError`；其余非 200 → `SourceFetchError`。"""
    with pytest.raises(RateLimitedError):
        GoogleTrendsSource(client=_client(status=429)).fetch_daily(DAY)
    with pytest.raises(SourceFetchError):
        GoogleTrendsSource(client=_client(status=500)).fetch_daily(DAY)
    # `geo=CN` 那 400 走的也是这一档——它是「上游拒绝」，不是结构漂移。
    with pytest.raises(SourceFetchError):
        GoogleTrendsSource(client=_client(status=400)).fetch_daily(DAY)


# ───────────────────────── 五、ParseDrift 的阴性对照：拿真响应改坏一处


@pytest.mark.parametrize("label,broken", [
    ("热度整条不见", lambda t: t.replace("<ht:approx_traffic>", "<ht:gone>")
                              .replace("</ht:approx_traffic>", "</ht:gone>")),
    ("热度值不是数", lambda t: t.replace("<ht:approx_traffic>100+", "<ht:approx_traffic>很多")),
    ("一条都没有了", lambda t: t.replace("<item>", "<gone>").replace("</item>", "</gone>")),
    ("整个不是 XML", lambda t: "<!doctype html><title>404</title>404 Not Found"),
])
def test_a_real_response_broken_in_one_place_raises_parse_drift(
    label: str, broken: object,
) -> None:
    """**拿今天那份真响应改坏一处**，NEVER 手编一个想象中的坏响应。

    手编的坏响应只证明「解析器认得我编的东西」；
    改坏真响应证明的是「上游真变了的时候它会喊」。
    """
    with pytest.raises(ParseDrift):
        parse_rss(broken(_body()), now=NOW, url=board_url())  # type: ignore[operator]


def test_a_title_that_went_missing_is_drift_not_an_empty_keyword() -> None:
    """词面没了 = 结构漂移，**不是一条空热点**。

    静默产出一条空词的热点，广场上就是一张没有名字的卡。
    """
    with pytest.raises(ParseDrift):
        parse_rss(_body().replace("<title>馬國明</title>", "<title></title>", 1),
                  now=NOW, url=board_url())


# ═════════════════════ weibo 半（`DEC-053` 访客握手 + 真榜四种行）

from flint.sources.weibo import (
    WeiboHotSource,
    parse_board,
    skipped_rows,
)
from flint.sources.weibo_visitor import (
    FINGERPRINT,
    VisitorHandshakeFailed,
    handshake,
)

REAL_BOARD = REPO / "fixtures" / "_probe" / "weibo" / "real-board.html"


def _board() -> str:
    return REAL_BOARD.read_text(encoding="utf-8")


def test_the_real_board_is_on_disk_with_its_handshake_receipt() -> None:
    """真榜是**握手之后真抓下来的**，那三跳各有留痕。"""
    assert REAL_BOARD.exists()
    # 这个目录里既有**探测留痕**（dict，`schema: probe/1`）也有由真响应转出来的
    # **回放夹具**（list）。按 schema 筛，NEVER 假设目录里只有一种东西。
    loaded = [json.loads(p.read_text(encoding="utf-8"))
              for p in (REPO / "fixtures" / "_probe" / "weibo").glob("*.json")]
    receipts = [r for r in loaded
                if isinstance(r, dict) and r.get("schema") == "probe/1"]
    board = [r for r in receipts if r.get("after_visitor_handshake")]

    assert board and board[0]["status"] == 200
    assert board[0]["authorized_by"] == "DEC-052"
    # **cookie 的值 NEVER 进仓库**，留痕里只有名字。
    assert "SUB" in board[0]["cookie_names"]
    assert all("cookie_value" not in r for r in receipts)


def test_the_four_row_shapes_are_all_handled() -> None:
    """真榜 52 行 → **50 条入榜、2 条跳过**，跳过的两条各自点名。"""
    items = parse_board(_board(), now=NOW)
    skipped = skipped_rows()

    assert len(items) == 50, f"入榜 {len(items)} 条"
    assert len(skipped) == 2, skipped
    assert any(s.startswith("pinned:") for s in skipped), "置顶行没被认出来"
    assert any(s.startswith("ad:") for s in skipped), "广告行没被认出来"


def test_the_pinned_row_is_skipped_and_never_given_a_made_up_heat() -> None:
    """置顶行**不入榜**，且 NEVER 拿到一个编出来的热度（`CN-04` acceptance 第 11 条）。

    它是一条真热搜，只是上游不给热度。给 `0` 的话它会排到榜尾，
    **而它实际上在榜首**——那不是「没有数据」，那是一个错的数据。
    """
    items = parse_board(_board(), now=NOW)
    pinned = next(s for s in skipped_rows() if s.startswith("pinned:"))
    word = pinned.split(":", 1)[1]

    assert all(i.keyword != word for i in items), "置顶行被入榜了"
    assert all(i.score > 0 for i in items), "有条目热度是 0——那是编出来的"


def test_a_missing_heat_row_never_takes_down_the_whole_page() -> None:
    """**NEVER 因为一行没热度就判整页漂移**（同上，第 11 条的另一半）。"""
    items = parse_board(_board(), now=NOW)

    assert len(items) >= 10, "整页被判漂移了"


def test_the_ad_row_is_judged_by_its_marker_not_by_an_empty_heat() -> None:
    """广告行靠**上游自己的结构标记**判，NEVER 靠「热度是空的」判。

    靠空热度判的话，哪天某条真热搜的数字暂时缺了，它会被当成广告丢掉——
    而那是一条真的热点。

    对照造法：拿一条**正常行**（有真 `href`、有热度）把它的热度掏空。
    它应当落进 `pinned` 那一档（没热度 → 不入榜），**而不是 `ad`**——
    两者都不入榜，而**理由不同**，理由正是这条判据要量的东西。

    （改前这条判据是把广告行的 `topic_ad` 去掉再看它还算不算广告——
    **写错了**：真广告行身上有两个标记（`topic_ad=1` 与
    `href="javascript:void(0);"`），去掉一个它仍然是广告，
    于是判据量的是「两个标记去掉一个」，而不是「靠不靠空热度判」。）
    """
    text = _board().replace("<span> 216585</span>", "<span></span>", 1)
    parse_board(text, now=NOW)
    skipped = skipped_rows()
    掏空的 = next((s for s in skipped if "台风白海豚" in s), "")

    assert 掏空的, f"掏空热度的那一行没被跳过：{skipped}"
    assert 掏空的.startswith("pinned:"), (
        f"它被当成广告了——判的是空热度不是标记：{掏空的}")


def test_a_heat_that_is_present_but_not_a_number_is_still_drift() -> None:
    """**「缺席」与「损坏」分开判**：没给热度跳一行，给了但不是数**喊一声**。

    合成一档的话，上游哪天把热度换成一段文案，我们会**安静地少掉半张榜**——
    而每一条剩下的都看起来是对的。
    """
    text = _board().replace("<span> 216585</span>", "<span>敬请期待</span>", 1)

    with pytest.raises(ParseDrift, match="non-numeric heat"):
        parse_board(text, now=NOW)


def test_the_category_prefix_in_the_heat_is_read_not_rejected() -> None:
    """`<span>盛典 305559</span>` 取的是**同一个数**，不是另算一个。"""
    items = parse_board(_board(), now=NOW)
    top = [i for i in items if i.keyword == "百花奖"]

    assert top and top[0].score == 305559.0, top


def test_reading_nothing_out_of_a_full_page_is_drift() -> None:
    """底线守卫：跳过是给**已知的两种非榜行**留的口子，不是给「解析不动」留的。

    造法：把真榜里**每一行的热度都掏掉**——于是每行都落进「缺席」那一档，
    读到 0 条、丢掉一堆。这正是「安静地交出三条热点」的极端形态。

    （改前这条判的是一个写死的下限 `< 10`，而那个数是拍出来的：
    上游把榜缩到 8 行时它会把一张正常的榜判成漂移，
    只喂一行的既有单测也被它误伤过——`tests/m1/test_m1_012.py` 实测撞上。）
    """
    import re as _re

    text = _re.sub(r"<span>[^<]*</span>", "<span></span>", _board())

    with pytest.raises(ParseDrift, match="no rankable rows"):
        parse_board(text, now=NOW)


# ── 握手（`DEC-053`）：离线跑，NEVER 发真实请求


def _handshake_client(gen: str, inc: str, *, set_sub: bool = True) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        if "genvisitor" in str(request.url):
            return httpx.Response(200, text=gen)
        headers = {"set-cookie": "SUB=fake-visitor-value; Path=/"} if set_sub else {}
        return httpx.Response(200, text=inc, headers=headers)

    return httpx.Client(transport=httpx.MockTransport(handler))


_GEN_OK = ('window.gen_callback && gen_callback({"retcode":20000000,"msg":"succ",'
           '"data":{"tid":"TESTTID","new_tid":true}});')
_INC_OK = ('window.cross_domain && cross_domain({"retcode":20000000,"msg":"succ",'
           '"data":{"sub":"x","subp":"y"}});')


def test_the_handshake_reads_the_retcode_not_the_status_code() -> None:
    """两跳**失败时照样回 200**——只看状态码会把失败当成功。"""
    bad = ('window.gen_callback && gen_callback({"retcode":50111,'
           '"msg":"visitor over quota"});')

    with pytest.raises(VisitorHandshakeFailed, match="没回成功码"):
        handshake(_handshake_client(bad, _INC_OK))


def test_no_sub_cookie_means_the_handshake_did_not_land() -> None:
    """没拿到 `SUB` 就等于没握上——**在这里喊，而不是等下一发被 302 弹回去**。"""
    with pytest.raises(VisitorHandshakeFailed, match="没有 SUB cookie"):
        handshake(_handshake_client(_GEN_OK, _INC_OK, set_sub=False))


def test_the_handshake_succeeds_and_hands_back_only_cookie_names() -> None:
    session = handshake(_handshake_client(_GEN_OK, _INC_OK))

    assert session.tid == "TESTTID"
    assert "SUB" in session.cookie_names
    # 交出去的是**名字**，值留在 jar 里。
    assert all("fake-visitor-value" not in n for n in session.cookie_names)


def test_no_cookie_value_is_hardcoded_anywhere() -> None:
    """`DEC-053` 逐字：cookie 值 MUST 每次动态获取，**NEVER 硬编任何一枚**。"""
    text = (REPO / "flint" / "sources" / "weibo_visitor.py").read_text(encoding="utf-8")

    for name in ("SUB=", "SUBP=", "SRF=", "SRT="):
        assert name not in text, f"硬编了 {name}"
    assert "登录" in text and "NEVER 升级成账号登录" in text


def test_the_fingerprint_lives_in_one_place_and_says_it_will_break() -> None:
    """指纹参数集中一处，文件头写明**上游对抗件，预期会碎**（`DEC-053` 边界）。"""
    text = (REPO / "flint" / "sources" / "weibo_visitor.py").read_text(encoding="utf-8")

    assert "上游对抗件，预期会碎" in text
    assert set(FINGERPRINT) >= {"os", "browser", "screenInfo"}
    # 指纹**只此一份**：另一处再写一遍的话，两处会各自漂移。
    assert text.count("screenInfo") == 1


def test_the_replay_path_never_handshakes() -> None:
    """回放路**不握手**——夹具里没有那两跳，默认去握的话每条回放判据都会假红。"""
    source = WeiboHotSource(client=_handshake_client(_GEN_OK, _INC_OK))

    assert source._before_fetch is None


def test_the_real_recorder_does_handshake() -> None:
    """而**真实录制那一侧 MUST 握**——两边各判一次，缺一就会有人忘。"""
    text = (REPO / "fixtures" / "_record_cn_real.py").read_text(encoding="utf-8")

    assert "before_fetch=visitor_handshake" in text
