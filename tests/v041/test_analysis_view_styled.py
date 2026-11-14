"""FIX-19：`AnalysisView` 全组件零 `className`——**owner 已准动这个封版件**。

## 许可与它的边界（逐字）

> **`FIX-19` 已获 owner 明确许可动 v0.4 封版件 `AnalysisView.tsx`，
> 边界只限「加类名与样式」——NEVER 改判定语义、NEVER 动四态、NEVER 改既有判据。**
> （第 9 批工单 §5.3 的唯一例外条）

所以这份判据分两半，**第二半比第一半重要**：

1. 类名与样式**真的加上了**（`GAUGE-15` 那个 `styled: []` 变成实际类名）；
2. **除了类名什么都没动**——判定语义、四态分支、`data-*` 记号、取数，逐条还在。

第二半怎么量：把源码里所有 `className="…"` **剥掉**之后，
渲染段应当与改前**逐字相同**。这条判据不依赖任何人记得「我只加了类名」——
它直接量那句话是不是真的。

## 类名走 token，NEVER 写死颜色与字号

写死一个 `#333` 或 `14px` 的话，暗色主题下它不会跟着变——
而 `DARK-01` 的双通道正是靠 `_ds` 的 token 生效的（`UI-01` 三条判据的射程）。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
VIEW = REPO / "web" / "views" / "analysis" / "AnalysisView.tsx"
CSS = REPO / "web" / "app" / "globals.css"
DECLARATION = REPO / "assets" / "screen_composition.json"
TICKET = REPO / "docs" / "blocked" / "ANALYSIS-VIEW-HAS-NO-CLASSNAMES.md"

#: 改前那一段渲染体（`HOTSPOT-03` 的原文，逐字）。剥掉类名之后应当与它相同。
#: 写死在判据里而不是从 git 取：本仓不是 git 工作区，而「改前长什么样」
#: 正是这条判据唯一要比对的东西。
BEFORE_RENDER = """
    <section data-testid="analysis-view" data-cluster-id={clusterId}>
      <h2 data-testid="analysis-verdict-heading">{t("analysis.section.verdict")}</h2>
      {verdictState === "loading" ? (
        <p data-testid="analysis-verdict-loading">{t("analysis.verdict.loading")}</p>
      ) : null}
      {verdictState === "ready" && verdict ? (
        <div data-testid="analysis-verdict" data-verdict={verdict.verdict}>
          <span data-testid="analysis-verdict-code">{verdict.verdict}</span>
          <span data-testid="analysis-verdict-all-satisfied">
            {verdict.all_satisfied.join(" ")}
          </span>
          <span data-testid="analysis-verdict-citations">
            {t("analysis.verdict.citations", { count: verdict.key_citation_ids.length })}
          </span>
        </div>
      ) : null}
      {verdictState === "absent" ? (
        <p data-testid="analysis-verdict-unjudged">{t("analysis.verdict.unjudged")}</p>
      ) : null}
      {verdictState === "failed" ? (
        <p data-testid="analysis-verdict-error">{t("analysis.verdict.error")}</p>
      ) : null}

      <h2 data-testid="analysis-evidence-heading">{t("analysis.section.evidence")}</h2>
      {cardsState === "loading" ? (
        <p data-testid="analysis-evidence-loading">{t("analysis.evidence.loading")}</p>
      ) : null}
      {cardsState === "ready" ? (
        <ul data-testid="analysis-evidence">
          {cards.map((card) => (
            <li
              key={card.card_id}
              data-testid="analysis-evidence-card"
              data-card-id={card.card_id}
            >
              {t("analysis.evidence.counts", {
                keywords: card.keyword_ids.length,
                flags: card.flags.length,
                links: card.top_links.length,
              })}
            </li>
          ))}
        </ul>
      ) : null}
      {cardsState === "absent" ? (
        <p data-testid="analysis-evidence-empty">{t("analysis.evidence.empty")}</p>
      ) : null}
      {cardsState === "failed" ? (
        <p data-testid="analysis-evidence-error">{t("analysis.evidence.error")}</p>
      ) : null}
    </section>
"""


def _render_body(text: str) -> str:
    """组件的 JSX 返回段。

    **锚点取最后一个 `return (`**：文件里第一个出现在 `useEffect` 的清理函数上
    （`return () => { alive = false; };`），按它切会把整段 effect 也算进来，
    于是这条判据比对的是两段毫不相干的文本。
    """
    return text[text.rindex("  return ("):]


def _squash(text: str) -> str:
    """去掉所有空白——比对的是**结构与字面**，不是缩进。"""
    return re.sub(r"\s+", "", text)


# ───────────────────────── 一、类名与样式真的加上了


def test_the_view_now_has_class_names() -> None:
    """改前全文件 `className` 出现 **0 次**（单据原话）。"""
    code = VIEW.read_text(encoding="utf-8")

    assert code.count("className=") >= 10, (
        f"类名太少：{code.count('className=')}——那一屏还是拿不到样式")


def test_every_class_name_has_a_rule_in_the_stylesheet() -> None:
    """加了类名而没写样式 = **屏上还是什么都没有**。

    这是 `FB-01`/`F-09` 治过的同一个病：DOM 里有、屏幕上没有。
    """
    code = VIEW.read_text(encoding="utf-8")
    css = CSS.read_text(encoding="utf-8")

    names = {
        name
        for attr in re.findall(r'className="([^"]+)"', code)
        for name in attr.split()
    }
    assert names, "一个类名都没有"
    for name in sorted(names):
        assert f".{name}" in css, f"类名 {name} 在样式表里没有对应规则"


def test_the_styles_use_tokens_and_never_hardcode_colour_or_size() -> None:
    """acceptance③：走 `_ds` token，**NEVER 写死颜色与字号**。

    写死的话暗色主题下它不会跟着变，而 `DARK-01` 的双通道正是靠 token 生效的。
    """
    css = CSS.read_text(encoding="utf-8")
    # **只扫这一卡那一段**，NEVER 一路扫到文件尾。
    #
    # 改前写的是 `css[css.index("/* FIX-19"):]`——从本卡那段起**一直到末尾**。
    # 第 13 批把药丸条与吉祥物追加在后面之后，这条判据把
    # **蓝本逐字的几何**（头 40×40、眼 8×8、间距 12px）也圈了进来，
    # 而那些数正是「照蓝本做」的内容，不是「写死了尺寸」。
    #
    # 一条射程无限的判据，会在下一个人往文件尾追加任何东西时红——
    # 而红的原因与它自己守的那件事无关。
    start = css.index("/* FIX-19")
    nxt = css.find("\n/* ═", start)
    block = css[start:nxt] if nxt > start else css[start:]
    # **先剥 CSS 注释再扫**：那段注释里正好举了「写死一个 #333 或 14px」当反例，
    # 而一把读注释的尺子会把那个反例本身当成违规——
    # 红的是尺子自己。本轮第四次撞上这个形状。
    rules = re.sub(r"/\*.*?\*/", "", block, flags=re.DOTALL)

    assert "var(--" in rules
    assert re.search(r"#[0-9a-fA-F]{3,8}\b", rules) is None, "写死了颜色"
    assert re.search(r":\s*\d+(\.\d+)?px", rules.replace("1px", "")) is None, (
        "写死了尺寸（1px 边框除外——它是描边宽度，不是字号或间距）")


# ───────────────────────── 二、**除了类名什么都没动**（本卡的核心）


def test_stripping_the_class_names_gives_back_the_original_render() -> None:
    """**许可的边界是可量的**：剥掉所有 `className="…"` 之后，
    渲染段应当与改前**逐字相同**。

    这条判据不依赖任何人记得「我只加了类名」——它直接量那句话是不是真的。
    改了一个分支、动了一处 `data-*`、换了一句文案，都会让它红。
    """
    code = VIEW.read_text(encoding="utf-8")
    stripped = re.sub(r'\s*className="[^"]*"', "", _render_body(code))

    # 末尾那个收函数体的 `}` 不在比对范围内（`BEFORE_RENDER` 只到 `);`）。
    expected = _squash("  return (" + BEFORE_RENDER + "  );")

    assert _squash(stripped).rstrip("}") == expected, (
        "剥掉类名之后与改前对不上——本卡动了类名之外的东西")


def test_the_four_states_are_still_four_branches() -> None:
    """四态逻辑一个字没动（`loading` / `ready` / `absent` / `failed` 各两组）。"""
    code = VIEW.read_text(encoding="utf-8")

    for state in ("loading", "ready", "absent", "failed"):
        assert code.count(f'verdictState === "{state}"') == 1, f"判定那一族少了 {state}"
        assert code.count(f'cardsState === "{state}"') == 1, f"证据那一族少了 {state}"


def test_the_verdict_semantics_were_not_touched() -> None:
    """判定语义：四分类码原样显示、`all_satisfied` 原样拼、引用数原样数。

    **NEVER 按 `data-verdict` 上不同的颜色**——那会让 A/B/C/D 在屏上
    变成「好/坏」的暗示，而它们是四种并列的结论。
    """
    code = VIEW.read_text(encoding="utf-8")
    css = CSS.read_text(encoding="utf-8")

    assert "{verdict.verdict}" in code
    assert 'verdict.all_satisfied.join(" ")' in code
    assert "verdict.key_citation_ids.length" in code
    block = css[css.index("/* FIX-19"):]
    assert "data-verdict=" not in block, "样式按判定取值分了颜色——四类不是好坏"


def test_every_existing_marker_survived() -> None:
    """既有判据靠 `data-testid` / `data-verdict` / `data-card-id` 找元素。

    动掉任何一个，都会让**别人的判据**红——而那是「NEVER 改既有判据」的反面：
    不是去改它们，是别把它们脚下的地板抽走。
    """
    code = VIEW.read_text(encoding="utf-8")

    for marker in (
        'data-testid="analysis-view"', 'data-cluster-id={clusterId}',
        'data-testid="analysis-verdict"', 'data-verdict={verdict.verdict}',
        'data-testid="analysis-evidence"', 'data-card-id={card.card_id}',
        'data-testid="analysis-evidence-card"',
    ):
        assert marker in code, f"既有记号被动了：{marker}"


def test_no_data_fetching_changed() -> None:
    """取数一行没动——本卡是样式卡。"""
    code = VIEW.read_text(encoding="utf-8")

    assert "fetchEvidenceCards" in code and "fetchVerdict" in code
    assert code.count("useEffect(") == 1, "多出/少了一个 effect"


# ───────────────────────── 三、声明与单据跟着事实走


def test_the_gauge15_declaration_no_longer_says_styled_is_empty() -> None:
    """acceptance④：`GAUGE-15` 的声明里这一屏的 `styled` 从 `[]` 改成实际类名。

    不改的话，那把尺子会拿「声明为空」去对「屏上有样式」——**红的是声明过期了**。
    """
    data = json.loads(DECLARATION.read_text(encoding="utf-8"))
    screens = data["screens"] if isinstance(data, dict) and "screens" in data else data
    row = next(s for s in screens if s["route"] == "/clusters/[id]")

    assert row["styled"], "声明里这一屏仍然是 styled: []"
    assert "styled_none_because" not in row, (
        "「为什么没有样式」那句解释还在——它现在是假话")


def test_the_declared_class_names_are_the_real_ones() -> None:
    """声明里写的类名 MUST 是组件里真有的那些。

    **NEVER 随手填一个别处的类名顶上**——那会让这一屏看起来被量着，而它没有
    （声明里那句 `styled_none_because` 的原话）。
    """
    code = VIEW.read_text(encoding="utf-8")
    data = json.loads(DECLARATION.read_text(encoding="utf-8"))
    screens = data["screens"] if isinstance(data, dict) and "screens" in data else data
    row = next(s for s in screens if s["route"] == "/clusters/[id]")

    real = {
        name
        for attr in re.findall(r'className="([^"]+)"', code)
        for name in attr.split()
    }
    for declared in row["styled"]:
        assert declared.lstrip(".") in real, f"声明里那个类名组件里没有：{declared}"


def test_the_ticket_is_closed() -> None:
    """acceptance⑤：关闭 `docs/blocked/ANALYSIS-VIEW-HAS-NO-CLASSNAMES.md`。

    根因消失了单还开着的话，下一批的人会把同一件事再做一遍。
    """
    text = TICKET.read_text(encoding="utf-8")

    assert "**状态** closed" in text, "单还开着"
    assert "FIX-19" in text, "没写清是谁关的"
