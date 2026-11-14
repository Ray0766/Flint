"""HYG-01 · 单据状态机读化 + 关闭三张根因已消失的陈旧单。

## 为什么要一行机读的状态

改前 33 张单里，「这张还开着吗」只能靠**读全文猜**：

- 4 张把「已关闭」写在 H1 标题的括号里；
- 14 张写成正文里的引用块横幅，格式各不相同；
- 15 张什么都没写——**「没关」与「忘了写」长得一模一样**；
- 1 张（`K1-02-SOURCE-CONTRACTS-MISSING`）正文里出现「已关闭」三个字，
  说的却是 **reddit 的自助注册已关闭**——单子本身还开着。
  按字符串搜「已关闭」来数单子，会把它数成已解决。

所以每张单顶部一行：

```
**状态** open
**状态** closed · 2026-08-05 · `FIX-02`
**状态** historical · 2026-08-02 · 历史留存
```

三态，机器读得懂，缺了判红。

## 关闭者可以是卡，也可以是 owner 裁决

实测五张单（`CLAUDE-S3-LAG` / `DESIGN-21-FONTS` / `HOTSPOT-03` /
`REGION-06-AXIS-WORDING` / `SCHEMA-05-FROZEN-WORDING`）是被 **owner 裁决**
关掉的（`DEC-012` / `DEC-018` / `DEC-019`），不是被某张卡修掉的。
所以关闭者的形状是 `卡号 或 DEC 号`——只认卡号的话，
这五张要么填不出来，要么被人随手编一个卡号填上。

## acceptance④：NEVER 凭印象关单

三张单的根因**逐条实跑**过，命令与输出贴在 `docs/trace/HYG-01.md` §2，
并抄进各自单子的关闭段。这个文件的
`test_the_three_stale_sheets_carry_their_evidence` 判的就是那几行证据在不在。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BLOCKED = REPO / "docs" / "blocked"
HEAD_LINES = 8
STATES = ("open", "closed", "historical")
_STATE = re.compile(r"^\*\*状态\*\*\s+(\w+)(.*)$", re.MULTILINE)
_DATE = re.compile(r"(20\d\d-\d\d-\d\d)")
# 卡号（`FIX-02`）或 owner 裁决号（`DEC-019`）。两者都是**真实存在的东西**；
# 只认卡号的话，那五张被裁决关掉的单要么填不出来、要么被人随手编一个卡号。
#: 关闭者：卡号或 `DEC` 号。**形状是 `字母-数字`**。
#: 本批起有几张卡的名字不带数字（`FAV-SNAPSHOT` / `REGION-CN-HK`），
#: 它们关单时 MUST 同时写上授权它的 `DEC` 号——那本来也是更准的说法：
#: 关掉一张单的是**裁决**，卡只是执行它的那一步。
_CLOSER = re.compile(r"`?([A-Z][A-Z0-9]*-\d+[a-z]?)`?")
STALE_THREE = {
    "I18N-01": '"next-intl": "4.13.4"',
    "I18N-FRONTEND-GROUP": '"next-intl": "4.13.4"',
    "V0-PROMPTS-LOCK": "9 passed",
}
HISTORICAL = {"CONCURRENT-WORKER-COLLISION", "SUMMARY"}


@dataclass(frozen=True)
class Sheet:
    name: str
    state: str
    rest: str
    text: str


def _sheets() -> list[Sheet]:
    found: list[Sheet] = []
    for path in sorted(BLOCKED.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        head = "\n".join(text.splitlines()[:HEAD_LINES])
        match = _STATE.search(head)
        found.append(Sheet(
            name=path.stem,
            state=match.group(1) if match else "",
            rest=match.group(2) if match else "",
            text=text,
        ))
    return found


# ───────────────────────── acceptance③：状态机读化


def test_every_sheet_declares_its_state_in_its_head() -> None:
    """每张单顶部 MUST 有 `**状态**` 一行，取值在三态之内。**缺标记判红。**

    改前 15 张什么都没写——而「没关」与「忘了写」长得一模一样。
    """
    missing = [s.name for s in _sheets() if not s.state]
    unknown = [f"{s.name}={s.state}" for s in _sheets()
               if s.state and s.state not in STATES]

    assert missing == [], f"这些单没写状态：{missing}"
    assert unknown == [], f"状态取值不在 {STATES} 之内：{unknown}"


def test_closed_sheets_carry_a_date_and_the_thing_that_closed_them() -> None:
    """`closed` MUST 带日期与关闭者（卡号或 `DEC` 号）。

    只写「已关闭」的那张单，回头没人说得出它是**什么时候、被什么**关掉的——
    于是下一个人只能重新查一遍根因。
    """
    bad: list[str] = []
    for sheet in _sheets():
        if sheet.state != "closed":
            continue
        if not _DATE.search(sheet.rest):
            bad.append(f"{sheet.name}：没有日期")
        elif not _CLOSER.search(_DATE.sub("", sheet.rest)):
            bad.append(f"{sheet.name}：没有关闭者")

    assert bad == [], f"这些 closed 单缺证据：{bad}"


def test_both_open_and_closed_actually_occur() -> None:
    """**非空对照**：三态里至少 open 与 closed 各有实例。

    没有这条，「全部标成 closed」也能让上面两条全绿——
    而那正是把一堆没解决的问题一次性抹掉的做法。
    """
    states = [s.state for s in _sheets()]

    assert states.count("open") > 0, "一张开着的单都没有？那清单本身可疑"
    assert states.count("closed") > 0
    assert len(states) >= 30, f"单子只剩 {len(states)} 张——有人删单了"


def test_the_reddit_sentence_is_not_mistaken_for_a_closed_sheet() -> None:
    """`K1-02` 正文里的「已关闭」说的是 **reddit 的自助注册**，不是这张单。

    按字符串搜「已关闭」来数单子，会把它数成已解决——
    **这正是要一行机读状态的原因**。这条判据把那个坑钉住。
    """
    k1 = next(s for s in _sheets() if s.name == "K1-02-SOURCE-CONTRACTS-MISSING")

    assert k1.state == "open", "K1-02 的根因（拿不到数据源令牌）没有消失"
    assert "已关闭" in k1.text, "那句 reddit 的话不在了——这条判据的前提变了"


# ───────────────────────── acceptance①：三张陈旧单，逐条实跑后关闭


def test_the_three_stale_sheets_are_closed_by_this_card() -> None:
    for name in STALE_THREE:
        sheet = next(s for s in _sheets() if s.name == name)

        assert sheet.state == "closed", f"{name} 还没关"
        assert "HYG-01" in sheet.rest, f"{name} 没写是谁关的"


def test_the_three_stale_sheets_carry_their_evidence() -> None:
    """**NEVER 凭印象关单**（卡面 acceptance④）：关闭段里要有实跑的输出。

    「根因消失了」这句话本身不是证据；`"next-intl": "4.13.4"` 与 `9 passed` 是。
    """
    for name, evidence in STALE_THREE.items():
        sheet = next(s for s in _sheets() if s.name == name)

        assert evidence in sheet.text, f"{name} 的关闭段里没有实跑输出：{evidence}"


# ───────────────────────── acceptance②：历史留存的两张


def test_the_historical_sheets_are_marked_and_banner_ed() -> None:
    """`CONCURRENT-WORKER-COLLISION` 与 `SUMMARY` 标历史留存 + 醒目横幅。

    它们记的是**当时**的状况。被当成当前状态引用的那天，
    读的人会照着一份过期的地图走——而地图上没有任何字说它过期了。
    """
    for name in sorted(HISTORICAL):
        sheet = next(s for s in _sheets() if s.name == name)

        assert sheet.state == "historical", f"{name} 没标历史留存"
        # 横幅要**在顶部**——写在第 80 行的警告，读的人已经读完了才看到。
        head = sheet.text.splitlines()[:HEAD_LINES + 6]
        assert any("历史留存" in ln for ln in head), f"{name} 的横幅不在顶部"
        # **判整句，NEVER 判两个分散的词。** 本卡实测的变异⑤把两处横幅都改软了，
        # 而 `"NEVER" in text and "当前状态" in text` 照样绿——
        # 那两个词在正文别处各自出现过。判据要判**同一行**里两者同在。
        banner = [ln for ln in head if "NEVER" in ln and "当前状态" in ln]
        assert banner, f"{name} 顶部没有那句横幅：NEVER 把它当作当前状态引用"
