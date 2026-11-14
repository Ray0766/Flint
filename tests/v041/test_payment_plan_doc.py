"""PAY-01：托管收银台接入方案调研（档 A 只读）。

## 这份判据守的是「调研」而不是「文章」

一份调研文档最容易出的问题不是写得不好，是**把没查到的东西写得像查到的**。
所以判据分三层：

1. **每条结论都有出处**：官方链接 + 查阅日期，逐条；
2. **读到了与没读到分开标**——本轮实测里，微信与支付宝的**费率与结算周期**
   都在商户后台/JS 渲染页后面，`WebFetch` 只拿到标题。那两格 MUST 标成
   「未读到」且**不许给数字**。给了数字就是把记忆当成了调研；
3. **本卡只出方案不接线**（acceptance④）：仓里 NEVER 因为这张卡多出任何支付
   SDK 依赖、网关调用或商户密钥。

## 为什么判据不去联网

S2-7：CI 恒回放、验证面 NEVER 联网。链接的**可达性**在采集期实测过一次
（`curl -o /dev/null -w %{http_code}`），结果作为一张表写进文档；
本判据只核对「文档里引的每条链接，都在那张实测表里」——
把联网留在采集期，验证期只读盘。
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DOC = REPO / "docs" / "支付接入方案-v041.md"

PROVIDERS = ("微信支付", "支付宝", "PayPal", "Apple Pay")

# 五个维度，卡上逐字写死。
DIMENSIONS = ("申请材料", "接口形态", "回调机制", "结算周期", "费率")

# 官方域名白名单：出处只认官方站。第三方博客的「费率 0.6%」查不了、也过期得最快。
OFFICIAL_HOSTS = (
    "pay.weixin.qq.com",
    "opendocs.alipay.com",
    "b.alipay.com",
    "developer.paypal.com",
    "www.paypal.com",
    "developer.apple.com",
)

READ_MARK = "实读"
UNREAD_MARK = "未读到"

_LINK = re.compile(r"https://[^\s)\]｜|、，。]+")
_PROBE_ROW = re.compile(r"^\|\s*(\d{3})\s*\|\s*(https://\S+?)\s*\|", re.MULTILINE)


def _doc() -> str:
    assert DOC.exists(), f"没有 {DOC.name}"
    return DOC.read_text(encoding="utf-8")


def _section(title: str) -> str:
    """取某个二级标题下的正文（不含标题行）。

    判在节里不判全文：全文里「费率」「回调」这些词到处都是，
    按全文判的话，把某一节整条删掉毫无反应（前几卡反复撞到的同一形状）。
    """
    body = _doc()
    start = body.find(f"## {title}")
    assert start != -1, f"文档里没有「{title}」这一节"
    end = body.find("\n## ", start + 1)
    return body[start:end if end != -1 else len(body)].split("\n", 1)[1]


def _probe_table() -> dict[str, str]:
    """采集期实测的链接可达表：URL → HTTP 状态码。"""
    return {url: code for code, url in
            ((m.group(1), m.group(2)) for m in _PROBE_ROW.finditer(_doc()))}


def _matrix_rows() -> list[list[str]]:
    """逐源逐维度那张主表的数据行。

    切到**第一个三级标题为止**：那一节下面还有一张「采集期链接实测」表（两列），
    不切的话它的行会混进来，判据去读第 6 格就越界（实测就是这么红的一次）。
    行宽不足**报红而不是跳过**：跳过的话，一行写坏的格子会以「不存在」的样子过关。
    """
    section = _section("四家逐条对照（每条附官方出处与查阅日期）")
    section = section.split("\n### ", 1)[0]
    rows = [
        [cell.strip() for cell in line.strip().strip("|").split("|")]
        for line in section.splitlines()
        if line.strip().startswith("|") and "---" not in line
    ][1:]
    narrow = [r for r in rows if len(r) < 6]
    assert narrow == [], f"这些行的格子不够六列：{narrow}"
    return rows


# ───────────────────────── 一、四家 × 五维度全在（acceptance①）


def test_the_document_exists() -> None:
    assert DOC.exists()


def test_all_four_providers_are_covered() -> None:
    rows = _matrix_rows()
    covered = {row[0] for row in rows}

    for provider in PROVIDERS:
        assert provider in covered, f"没调研 {provider}"


def test_every_provider_covers_every_dimension() -> None:
    """四家 × 五维度 = 20 格，缺一格判红。

    缺格与「查不到」是两回事：查不到也要有那一格，写明查不到。
    没有那一格的话，读的人不知道是没查还是不适用。
    """
    rows = _matrix_rows()
    have = {(row[0], row[1]) for row in rows}

    missing = [(p, d) for p in PROVIDERS for d in DIMENSIONS if (p, d) not in have]
    assert missing == [], f"这些格子没有：{missing}"


def test_every_row_carries_an_official_link_and_a_date() -> None:
    """acceptance①：**每条**附官方文档链接与查阅日期。"""
    for row in _matrix_rows():
        link = row[3]
        assert link.startswith("https://"), f"{row[:2]} 没有链接：{link}"
        assert any(host in link for host in OFFICIAL_HOSTS), f"{row[:2]} 的出处不是官方站：{link}"
        assert re.search(r"\d{4}-\d{2}-\d{2}", row[4]), f"{row[:2]} 没写查阅日期：{row[4]}"


def test_every_cited_link_was_probed_at_collection_time() -> None:
    """文档里引的每条官方链接，都要在采集期实测表里有一行。

    引一条没验过的链接，读的人点进去可能是 404——而文档看起来照样很完整。
    """
    probed = _probe_table()
    assert probed, "没有采集期实测表"

    for row in _matrix_rows():
        assert row[3] in probed, f"{row[:2]} 引的链接没进实测表：{row[3]}"


def test_every_probed_link_answered_200() -> None:
    probed = _probe_table()

    bad = {url: code for url, code in probed.items() if code != "200"}
    assert bad == {}, f"这些链接实测不是 200：{bad}"


# ───────────────────────── 二、读到了与没读到分开标（本卡最要紧的一条）


def test_each_cell_declares_whether_it_was_actually_read() -> None:
    """每一格都要标明是**实读**还是**未读到**。

    不标的话，一份「凭记忆写的费率」与一份「从官方页读到的费率」在纸上长得一样。
    """
    for row in _matrix_rows():
        assert row[5] in (READ_MARK, UNREAD_MARK), f"{row[:2]} 没标读没读到：{row[5]}"


def test_an_unread_cell_never_states_a_number() -> None:
    """**未读到的格子里 NEVER 出现具体数字**。

    本轮实测：微信与支付宝的费率、结算周期页都在商户后台或 JS 渲染之后，
    抓到的只有标题。那两格写上「0.6%」「T+1」就是把记忆当成了调研——
    而记忆里的费率既没有出处，也不知道是哪一年的。
    """
    for row in _matrix_rows():
        if row[5] != UNREAD_MARK:
            continue
        finding = row[2]
        assert not re.search(r"\d+(\.\d+)?\s*%", finding), f"{row[:2]} 未读到却给了百分比：{finding}"
        assert not re.search(r"T\s*\+\s*\d", finding), f"{row[:2]} 未读到却给了结算周期：{finding}"


def test_an_unread_cell_says_why_it_could_not_be_read() -> None:
    """未读到要说**为什么**：是要登录、是 JS 渲染、还是页面没这一段。

    只写「未读到」的话，下一个人不知道该换个入口再试，还是该去问 owner。
    """
    for row in _matrix_rows():
        if row[5] == UNREAD_MARK:
            assert len(row[2]) >= 10, f"{row[:2]} 只写了未读到，没写为什么：{row[2]}"


# 格子正文里出现这些说法，就等于自己承认「没读到」。
# 标记与正文对不上时，**以正文为准**——正文是当时写下的实况，标记只是一个字。
_ADMITS_UNREAD = ("未取到", "未读到", "只拿到标题", "未写", "未逐字取到", "没有费率正文")


def test_a_cell_that_admits_it_could_not_be_read_is_marked_that_way() -> None:
    """标记与格子正文 NEVER 互相矛盾。

    单判「标记是这两个词之一」挡不住把「未读到」偷偷改成「实读」——
    那一格的正文还写着「本轮未取到字段表」，而标记说读到了（变异考⑤ 实测）。
    一份自相矛盾的调研比一份承认没查到的调研危险：读的人会信那个标记。
    """
    for row in _matrix_rows():
        admits = [w for w in _ADMITS_UNREAD if w in row[2]]
        if admits:
            assert row[5] == UNREAD_MARK, (
                f"{row[:2]} 正文说 {admits}，标记却是「{row[5]}」")


def test_a_cell_marked_read_really_states_a_finding() -> None:
    """反向：标了「实读」的格子要真的有内容，NEVER 是一句空话。"""
    for row in _matrix_rows():
        if row[5] == READ_MARK:
            assert len(row[2]) >= 12, f"{row[:2]} 标了实读却几乎没写：{row[2]}"


def test_at_least_one_cell_was_really_read() -> None:
    """反向：不能整张表都标「未读到」——那不叫调研，叫没查。"""
    marks = [row[5] for row in _matrix_rows()]

    assert marks.count(READ_MARK) >= len(PROVIDERS), "实读的格子太少，这份调研没有成色"


# ───────────────────────── 三、owner 的两条裁决写进文档（acceptance②）


def test_the_two_rulings_are_stated_in_their_own_section() -> None:
    body = _section("owner 裁决（2026-08-04）：两条硬边界")

    assert "NEVER 自建支付系统" in body
    assert "NEVER 存储卡号" in body or "NEVER 存卡号" in body
    assert "对方页面" in body, "没写清「用户在对方页面付款、我们只收回调」"


# ───────────────────────── 四、优先级建议：两条路径各带理由与材料（acceptance③）


def test_the_recommendation_covers_both_audiences() -> None:
    body = _section("接入优先级建议（中国用户 / 海外用户各一条）")

    assert "中国用户" in body
    assert "海外用户" in body


def _recommendation_paths() -> dict[str, str]:
    """建议那一节下的每条三级路径 → 它自己的正文。

    **逐条切开**：整节判「有没有出现『需要 owner 提供』」的话，
    Apple Pay 那一段顺口写的一句「届时需要 owner 提供…」就把它喂饱了——
    把两条主推荐路径里的材料清单整段删掉毫无反应（变异考⑯ 实测）。
    """
    body = _section("接入优先级建议（中国用户 / 海外用户各一条）")
    parts = body.split("\n### ")
    return {p.split("\n", 1)[0].strip(): p for p in parts[1:]}


def test_each_recommended_path_says_what_owner_must_provide() -> None:
    """**每条**推荐路径各自写清需要 owner 提供什么——那是这份调研的落地出口。"""
    paths = _recommendation_paths()
    assert len(paths) >= 2, f"建议里少于两条路径：{sorted(paths)}"

    for name, text in paths.items():
        assert "需要 owner 提供" in text, f"「{name}」这条没写要 owner 提供什么"

    joined = "".join(paths.values())
    for material in ("营业执照", "商户号"):
        assert material in joined, f"没写要 owner 提供 {material}"


def test_the_recommendation_gives_reasons_not_just_a_ranking() -> None:
    """只排个序不算建议：排序背后的理由要写出来，否则没人能反驳它。"""
    body = _section("接入优先级建议（中国用户 / 海外用户各一条）")

    assert "理由" in body


# ───────────────────────── 五、只出方案不接线（acceptance④）


def test_the_card_added_no_payment_dependency() -> None:
    """仓里 NEVER 因为这张卡多出支付 SDK 依赖。"""
    for rel in ("requirements.lock", "pyproject.toml", "web/package.json"):
        text = (REPO / rel).read_text(encoding="utf-8").lower()
        for sdk in ("wechatpay", "alipay", "paypal", "stripe", "braintree"):
            assert sdk not in text, f"{rel} 里出现了 {sdk}"


def test_the_billing_module_still_touches_no_gateway() -> None:
    """`flint/billing/` 仍然零网关调用——本卡只出方案。"""
    for path in (REPO / "flint" / "billing").glob("*.py"):
        code = "\n".join(
            ln for ln in path.read_text(encoding="utf-8").splitlines()
            if not ln.strip().startswith("#"))
        for marker in ("api.mch.weixin.qq.com", "openapi.alipay.com",
                       "api-m.paypal.com", "httpx", "requests."):
            assert marker not in code, f"{path.name} 碰了网关：{marker}"


def test_no_real_merchant_credential_landed_in_the_repo() -> None:
    """红线：真实商户密钥 NEVER 进仓（S2-10 / 工单 §六.5）。

    判的是**形态**：文档里出现看起来像真密钥的串即红。
    示例值要一眼看得出是示例。
    """
    body = _doc()
    for pattern in (r"\bmch_?id\s*[:=]\s*['\"]?\d{8,}",
                    r"\bAPIv3[Kk]ey\s*[:=]\s*['\"]?\w{16,}",
                    r"\bclient_secret\s*[:=]\s*['\"]?[A-Za-z0-9_-]{20,}"):
        assert not re.search(pattern, body), f"文档里像是有真密钥：{pattern}"


def test_the_doc_says_wiring_is_the_next_card() -> None:
    """acceptance④：本卡只出方案，真实网关接入是 PAY-02 且要 owner 的资质与密钥。"""
    body = _doc()

    assert "PAY-02" in body
    assert "本卡只出方案" in body or "只出方案不接线" in body
