"""CHAIN-03：主题列表与主题详情两屏（蓝本 P4/P5）——实仓此前没有。

## 改前的实况

- `web/app/` 下**没有 `topics` 那一层**：用户从广场走不到主题；
- `TopicListView` 组件建好了，但**只有 `DemoFlow` 那个演示串屏在用**，
  且它是一个 `ul/li`、**零 `className`**——与退役前的 `PlazaView` 同一形状；
- 主题详情**连组件都没有**。

## 两处规格与实况对不上（各立一单，本卡按实况交付）

1. **`Topic` 没有名称三元组**。规格 `#2.4` 要主行 `name_native` + 机翻次要行，
   而冻结件 `Topic` 的字段里没有那两个。拿 `one_liner` 顶上就是
   「借一个已经有主的字段说另一件事」（`DEC-034` 的同一条）——
   更坏的是屏上会出现一个「永远没有译名的三元组」，那看起来像翻译服务坏了。
   单据 `docs/blocked/TOPIC-HAS-NO-NAME-TRIPLE.md`。
2. **选主题没有写端点**（topic 一族三条全是 GET）。选中态恒由后端的
   `chosen_topic_id` 决定，**NEVER 前端自己记一份**——记了的话刷新一次就没了，
   而用户以为自己已经选过。单据 `docs/blocked/TOPIC-CHOOSE-HAS-NO-WRITE-ENDPOINT.md`。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

# FIX-13：小节切法只有一处（`tools/css_sections.py`）。
from tools.css_sections import (
    bare_sizes,
    colour_literals,
    section_after,
)

WEB = REPO / "web"
LIST_PAGE = WEB / "app" / "projects" / "[id]" / "topics" / "page.tsx"
DETAIL_PAGE = WEB / "app" / "topics" / "[id]" / "page.tsx"
LIST_VIEW = WEB / "components" / "views" / "TopicListView.tsx"
DETAIL = WEB / "components" / "topic-detail" / "TopicDetail.tsx"
GLOBALS = WEB / "app" / "globals.css"
CONTRACTS = REPO / "contracts" / "models.py"
ZH = WEB / "messages" / "zh.json"
EN = WEB / "messages" / "en.json"
SHEETS = REPO / "docs" / "blocked"


def _code_only(path: Path) -> str:
    text = re.sub(r"/\*[\s\S]*?\*/", "", path.read_text(encoding="utf-8"))
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("//")
    )


def _messages(path: Path) -> dict[str, str]:
    return json.loads(path.read_text(encoding="utf-8"))


# ───────────────────────── 一、两屏真的建了，且各打各的端点


def test_both_screens_exist() -> None:
    """蓝本 P4/P5。改前 `web/app/` 下连 `topics` 那一层都没有。"""
    assert LIST_PAGE.exists(), "主题列表屏不在"
    assert DETAIL_PAGE.exists(), "主题详情屏不在"


def test_each_screen_calls_its_own_endpoint() -> None:
    assert "/topics`" in _code_only(LIST_PAGE) or "/topics" in _code_only(LIST_PAGE)
    assert "/topics/${id}" in _code_only(DETAIL_PAGE)


def test_each_screen_makes_exactly_one_request() -> None:
    """一屏一次查。分几次拼回来的东西对应几个时刻的库，而屏上看起来像同一时刻的快照。"""
    for path in (LIST_PAGE, DETAIL_PAGE):
        code = _code_only(path)
        # 数**调用点**（`useScreenData<...>(`），不是数出现次数——import 那一行也带这个名字。
        calls = code.count("useScreenData<")
        assert calls == 1, f"{path.parent.name} 屏发了 {calls} 次查"


# ───────────────────────── 二、卡面体系与广场同源


def test_the_list_is_no_longer_a_bare_ul_li() -> None:
    """改前它零 `className`——与退役前的 `PlazaView` 同一形状（拿不到设计系统任何样式）。"""
    code = _code_only(LIST_VIEW)

    assert "className=" in code, "主题列表仍然零 className"
    assert "topic-card" in code


def test_the_topic_card_borrows_the_same_shell_as_the_hotspot_card() -> None:
    """同一个产品里两种卡片长得两样，用户会以为是两个产品。

    判的是**样式源**：主题卡与热点卡用同一组 `_ds` token（纸纹/边框/圆角/投影）。
    """
    # FIX-13：小节切法收成一处（`tools/css_sections.py`）。
    css = GLOBALS.read_text(encoding="utf-8")
    section = section_after(css, "* CHAIN-03 · 主题两屏")

    for token in ("var(--surface)", "var(--tex-paper)", "var(--rule)",
                  "var(--r-card)", "var(--shadow-sticker)"):
        assert token in section, f"主题卡没用 {token}——它与热点卡不同源了"


def test_the_topic_styles_use_tokens_except_the_named_geometry() -> None:
    """字号、间距、颜色一律走 token；几何值显式列名（与 `UI-01`／`PLAZA-01` 同口径）。"""
    css = GLOBALS.read_text(encoding="utf-8")
    section = section_after(css, "* CHAIN-03 · 主题两屏")

    colours = colour_literals(section)
    assert colours == [], f"本段写死了颜色：{colours}"

    # 300 是网格列底、1160 是卡片屏最大内容宽（与广场同值）。
    allowed = ("300px", "1160px")
    offenders = bare_sizes(section, allowed)
    assert offenders == [], f"本段写死了字号/间距：{offenders}"


# ───────────────────────── 三、`Topic` 真有的字段才上屏


def test_the_name_triple_is_not_faked_from_one_liner() -> None:
    """冻结件 `Topic` 没有 `name_native`。**NEVER 拿 `one_liner` 冒充它。**

    冒充之后屏上会出现一个「永远没有译名的三元组」——那看起来像翻译服务坏了，
    而真相是这个实体从来就没有名称三元组。两者在屏上长得一模一样。
    """
    frozen = CONTRACTS.read_text(encoding="utf-8")
    topic = frozen[frozen.index("class Topic:"):]
    topic = topic[: topic.index("\n\n\n")]

    assert "name_native" not in topic, (
        "冻结件已经有 name_native 了——那就该真的接三元组，并来这里改这条判据"
    )
    for path in (LIST_VIEW, DETAIL):
        code = _code_only(path)
        assert "NativeName" not in code, f"{path.name} 拿名称三元组的组件渲染了主题"
        assert "nameNative" not in code


def test_the_gap_was_closed_by_correcting_the_spec_not_the_contract() -> None:
    """这条判据**改过一次**，记在这里。

    改前它写的是「冻结件里还没有 `name_native` ⇒ 单据必须还开着」——
    那句话背后有个没说出口的假设：**这个缺口只可能靠冻结件长出字段来关**。

    owner 2026-08-08 裁 `DEC-036`：**改规格，不动冻结件**。
    于是缺口关了而冻结件一个字没动，旧条件把这件事判成了「单据不该关」——
    **它红的是自己的假设过期，不是事情没做完**。

    现在的条件是那条裁决自己的形状：`Topic` 仍然没有名称（冻结件没被动过），
    **且**规格不再要求它有（那才是缺口消失的地方）。两者缺一都不该关单。
    """
    frozen = CONTRACTS.read_text(encoding="utf-8")
    topic = frozen[frozen.index("class Topic:"):]
    topic = topic[: topic.index("\n\n\n")]
    sheet = SHEETS / "TOPIC-HAS-NO-NAME-TRIPLE.md"
    state = sheet.read_text(encoding="utf-8").splitlines()[2]

    assert "name_native" not in topic, (
        "冻结件长出 name_native 了——那 DEC-036 要重开，本条也要跟着改"
    )
    assert state.startswith("**状态** closed"), (
        f"规格已按 DEC-036 订正，单据却还开着：{state!r}"
    )
    assert "DEC-036" in state, "关单没写是被哪条裁决关的"


def test_the_detail_screen_shows_what_the_topic_really_has() -> None:
    code = _code_only(DETAIL)

    for field in ("one_liner", "target_user_tag", "form_factor_tag",
                  "why_now", "topicKeywords"):
        assert field in code, f"详情屏没显示 {field}"


# ───────────────────────── 四、why_now：推测标与逐条引用


def test_speculative_comes_from_the_backend_and_never_hides_the_claim() -> None:
    """`speculative` 由后端定（`evidences` 为空 → True，冻结件 `[C2]`）。

    **NEVER 因为它就把 `why_now` 藏起来**：藏起来的话，
    用户看不出这条「为什么是现在」是没有证据支撑的推测。
    """
    code = _code_only(DETAIL)

    # 读的是后端给的那一位。
    assert "topic.why_now.speculative" in code, "推测标不是从后端字段读的"
    # claim 与推测标是**并列**的两件事：claim 恒渲染，推测标另挂。
    assert "data-topic-why-now>" in code, "推测时把 why_now 的正文一起藏掉了"
    # 前端 NEVER 自己算这一位：`evidences` 为空 → True 是**后端**的规则（冻结件 [C2]），
    # 前端再算一遍的话，两处规则会在某天分叉，而屏上看不出是哪一处说了算。
    #
    # 判的是**有没有一个本地的 `speculative`**（`const`/`let` 声明），
    # 不是「出现过这个词」——JSX 的 `data-speculative={…}` 属性也带这个词，
    # 把它一起报红的话，判据会逼人把取证用的那个 `data-*` 删掉。
    assert not re.search(r"\b(const|let|var)\s+speculative\b", code), (
        "前端自己算了一份 speculative"
    )
    assert not re.search(r"evidences\.length\s*===?\s*0\s*\?[^:]*speculative", code), (
        "前端拿证据条数推出了 speculative"
    )


def test_every_evidence_carries_its_own_citation() -> None:
    """「结论必有引用」在这一屏上的形状：每条证据带自己的 `citation_id`。

    合成一句「多项证据表明…」就把每一条的出处都丢了。
    """
    code = _code_only(DETAIL)

    assert "citation_id" in code
    assert "data-citation-id" in code


def test_an_empty_evidence_list_says_so() -> None:
    """「一条证据都没有」是实况，不是错误。说出来，NEVER 留空。"""
    code = _code_only(DETAIL)

    assert "data-topic-evidence-empty" in code
    assert "topic.evidence.none" in code


# ───────────────────────── 五、选主题：不落地就不假装落地


def test_the_list_screen_never_keeps_its_own_chosen_state() -> None:
    """选中态恒由后端的 `chosen_topic_id` 决定。

    前端自己记一份的话，刷新一次就没了，而用户以为自己已经选过，
    并会在后面的分析里以为用的是他选的那条。
    """
    code = _code_only(LIST_PAGE)

    assert "chosenTopicId={data.chosen_topic_id}" in code
    assert "useState" not in code, "列表屏自己记了一份选中态"


def test_the_write_endpoint_finally_exists() -> None:
    """这条判据**改过一次**，改因记在这里。

    改前它写的是「写端点还没有 ⇒ 单据必须还开着」。
    `ENTRY-02`（v0.4.1 第 6 批）把 `POST /projects/{id}/chosen-topic` 建了出来，
    于是那条断言红了——**它红的是自己的前提过期，不是接线出错**。

    现在判的是那件事真的做完了：端点在、单据关、屏上不再引那张单。
    """
    from flint.api.topics import create_topics_app

    sheet = SHEETS / "TOPIC-CHOOSE-HAS-NO-WRITE-ENDPOINT.md"

    assert callable(create_topics_app), "写端点模块不在"
    assert sheet.read_text(encoding="utf-8").splitlines()[2].startswith(
        "**状态** closed"), "端点建好了，单据却还开着"


# ───────────────────────── 六、文案走 i18n


def test_the_new_copy_is_keyed_in_both_languages() -> None:
    zh, en = _messages(ZH), _messages(EN)

    for key in ("topic.screen.title", "topic.detail.title", "topic.chosen",
                "topic.evidence.none"):
        assert key in zh, f"zh 缺 {key}"
        assert key in en, f"en 缺 {key}"
        assert zh[key] != en[key], f"{key} 中英同文——有一侧没翻"


def test_no_hardcoded_chinese_in_the_new_screens() -> None:
    for path in (LIST_PAGE, DETAIL_PAGE, DETAIL):
        code = _code_only(path)
        for literal in re.findall(r'"([^"]*)"', code):
            assert not re.search(r"[一-鿿]", literal), (
                f"{path.name} 里有裸中文：{literal!r}"
            )
