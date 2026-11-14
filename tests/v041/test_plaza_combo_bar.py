"""PLZ-COMBO-01：广场 Combo 栏补 v4 多出来的两样（假设输入 + 三态提示）。

## 改前实况（本卡 NEVER 重写这条栏）

`plaza-combo-bar` **已经存在**（`PlazaCards.tsx`），已有已选计数、建组合按钮、
`need_two` 提示。v4 比现网多的只有两样：

1. **假设输入框进同一条栏**——选卡与写假设是同一件事的两半；
2. **三态提示**（v4 第 524 行 `comboMsg`）：`还需 N 张卡` → `关联假设必填` → `就绪 · 生成 5~8 个候选主题`。

本卡只补这两样（外加上限 5 的说明）。

## 这一屏选的是**热点簇**，而端点吃的是**证据卡**

`PlazaCards.tsx` 与 `app/combo/page.tsx` 都写明过这条分界：
`POST /projects/combo` 的 `card_ids` 是**证据卡** id，一个热点底下可能有好几张。
所以这条栏的按钮**仍然只是跳到 `/combo?clusters=…`**，
**NEVER 把簇 id 当 `card_ids` 发出去**——那些 id 在 `evidence_cards` 里一条都查不到，
而屏上会显示成一次正常的失败。本文件为此单列一条判据。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
WEB = REPO / "web"
CARDS = WEB / "components" / "plaza" / "PlazaCards.tsx"
PLAZA_PAGE = WEB / "app" / "plaza" / "page.tsx"
MESSAGES = WEB / "messages"
DESIGN = REPO / "前端设计" / "应用前端设计需求" / "design-handoff" / "Flint v4.dc.html"
TOPIC_CLIENT = WEB / "lib" / "topicClient.ts"
BACKEND_RULE = REPO / "flint" / "topic" / "create.py"


def _zh() -> dict[str, str]:
    return json.loads((MESSAGES / "zh.json").read_text(encoding="utf-8"))


def _code() -> str:
    return CARDS.read_text(encoding="utf-8")


def _stripped() -> str:
    return re.sub(r"/\*.*?\*/|//[^\n]*", "", _code(), flags=re.DOTALL)


# ═════════════════ 一、四态各说各的（v4 那条 `comboMsg`）


@pytest.mark.parametrize(("state", "key"), (
    ("empty", "plaza.combo.empty_hint"),
    ("need_more", "plaza.combo.need_n"),
    ("need_hypothesis", "plaza.combo.need_hypothesis"),
    ("ready", "plaza.combo.ready"),
))
def test_each_of_the_four_states_has_its_own_marker_and_wording(
    state: str, key: str,
) -> None:
    """四态**逐个** parametrize：缺一种即红。

    合并任意两态，用户就不知道自己卡在哪一步——
    而这条栏的全部作用就是回答「现在还差什么」。
    """
    code = _code()
    zh = _zh()

    assert f'"{state}"' in code, f"少了 `{state}` 这一态"
    assert key in code, f"`{state}` 那一态没有自己的文案（{key}）"
    assert zh[key].strip(), f"{key} 是空串"


def test_the_four_sentences_are_four_different_sentences() -> None:
    """四句话互不相同——两句一样等于两态合并了。"""
    zh = _zh()
    lines = [zh[k] for k in ("plaza.combo.empty_hint", "plaza.combo.need_n",
                             "plaza.combo.need_hypothesis", "plaza.combo.ready")]

    assert len(set(lines)) == 4, f"四句里有两句一样：{lines}"


def test_the_wording_comes_from_the_design_file_verbatim() -> None:
    """三句照 v4 逐字（判准取自设计稿原文，NEVER 在判据里抄一份）。"""
    src = DESIGN.read_text(encoding="utf-8")
    zh = _zh()

    assert zh["plaza.combo.need_hypothesis"] in src
    assert zh["plaza.combo.ready"] in src
    # 「还需 N 张卡」在 v4 里是拼出来的（`'还需 ' + (2 - n) + ' 张卡'`），
    # 所以比的是它的两头。
    assert "还需 " in src and " 张卡" in src
    assert "加入 2~5" in src, "空态那句在设计稿里找不到"


def test_the_missing_count_is_computed_from_the_selection_not_hardcoded() -> None:
    """「还需 N 张」里那个 N == `COMBO_MIN - 已选`，NEVER 写死一个 1。

    写死的话，一张没选与选了一张会印同一句——而这两态该做的事不同。
    """
    stripped = _stripped()

    assert "2 - selected.length" in stripped, "N 不是算出来的"
    assert 'plaza.combo.need_n", { n: String(' in stripped


# ═════════════════ 二、按钮的可点性与三态同源


def test_the_button_needs_both_enough_cards_and_a_non_blank_hypothesis() -> None:
    """`disabled` 在「选中数不足」与「假设空白」两种情形下都为真。

    **上限不在这一屏判**——见下一条。
    """
    stripped = _stripped()

    assert "selected.length >= 2" in stripped
    assert "hypothesisFilled" in stripped
    assert "disabled={!canBuild}" in stripped


def test_a_hypothesis_of_only_spaces_still_counts_as_empty() -> None:
    """**阴性对照**：填一个空格仍然不可点——前端与后端同 `strip()` 口径。

    各判各的话，屏上说「就绪」而服务端当场拒（`EMPTY_HYPOTHESIS`）。
    """
    stripped = _stripped()

    assert "hypothesis.trim() !== \"\"" in stripped, "空白判据不是 trim 口径"
    backend = BACKEND_RULE.read_text(encoding="utf-8")
    assert "strip()" in backend, "后端那一侧不是 strip 口径了——两边要一起看"


def test_the_upper_bound_is_never_re_judged_on_the_plaza() -> None:
    """**上限 NEVER 在广场判**（`ENTRY-04` 的既有纪律，本卡照它执行）。

    `2~5` 数的是**证据卡**，而这一屏选的是**热点**——两者不是同一个计数。
    在这里判一次的话，用户选了 6 个热点会被拦下，
    而那 6 个热点底下可能一共只有 3 张证据卡。

    卡面 acceptance⑤ 要「上限 5 在屏上说得出」，与既有那条**互相矛盾**
    （而且与同一张卡的 acceptance② 也矛盾）。按既有纪律执行并开单：
    `docs/blocked/PLAZA-UPPER-BOUND-CONTRADICTS-ENTRY-04.md`。
    这条判据钉的就是「按既有纪律执行」这件事——照卡面做会当场打红两条既有判据。
    """
    ticket = REPO / "docs" / "blocked" / "PLAZA-UPPER-BOUND-CONTRADICTS-ENTRY-04.md"

    # 剥注释再扫：解释「为什么不在广场判」的那段注释里正好点名了这两个名字，
    # 而一把读注释的尺子会把那句解释当成违规——既有那条判据也是这么写的。
    stripped = _stripped()
    assert "COMBO_MAX" not in stripped, "广场又把上限判了一次"
    assert "comboCountValid" not in stripped
    assert ticket.exists(), "矛盾没开单"
    body = ticket.read_text(encoding="utf-8")
    assert "acceptance⑤" in body and "ENTRY-04" in body


# ═════════════════ 三、簇 id **NEVER** 当 card_ids 发出去


def test_the_button_still_goes_through_the_clusters_route() -> None:
    """提交仍走 `?clusters=` 那条既有路到 `/combo` 屏选证据卡。

    这一屏选的是**热点簇**，而 `POST /projects/combo` 吃的是**证据卡** id——
    一个热点底下可能有好几张。直接发出去的话，那些 id 在 `evidence_cards` 里
    一条都查不到，而屏上会显示成一次正常的失败。
    """
    page = PLAZA_PAGE.read_text(encoding="utf-8")

    assert "/combo?clusters=" in page, "建组合不再走 `?clusters=` 那条路"
    stripped = _stripped()
    assert "card_ids" not in stripped, "广场这一屏出现了 `card_ids`"
    assert "projects/combo" not in stripped, "广场这一屏直接打了 combo 端点"


def test_the_typed_hypothesis_is_handed_to_the_caller() -> None:
    """输入的假设**交给调用方**（`onBuildCombo(hypothesis)`）。

    今天广场那一屏还没把它带进 `/combo` 的地址（那一步在别的卡的 outputs 里），
    所以用户到那一屏仍要再打一遍——**这条缝先留出来并写明它今天到哪为止**，
    NEVER 假装它已经接上了。
    """
    code = _code()

    assert "onBuildCombo?.(hypothesis.trim())" in code
    assert "onBuildCombo?: (hypothesis: string) => void" in code
    assert "还要再打一遍" in code or "再打一遍" in code, "没写明这条缝今天到哪为止"


# ═════════════════ 四、既有的那三样一个字没动


def test_the_bar_kept_its_count_and_build_button() -> None:
    """已选计数与建组合按钮**原样还在**——本卡是补两样，不是重写这条栏。"""
    code = _code()

    for hook in ("plaza-combo-bar", "plaza-combo-count", "plaza-combo-build",
                 "data-selected-count"):
        assert hook in code, f"既有取证钩子丢了：{hook}"


def test_the_bar_is_still_outside_the_three_empty_states() -> None:
    """计数条仍在三态分支**之上**：切到没有卡的区时它不能消失。

    消失的话，屏上说「没有」而用户手里还握着两张——
    看不见与清空了在用户那里是同一件事（`ENTRY-04` 的既有理由）。
    """
    code = _code()
    bar = code.index("plaza-combo-bar")
    out_of_scope = code.index("plaza-out-of-scope")

    assert bar < out_of_scope, "计数条掉进了三态分支里面"


def test_colors_stay_on_tokens() -> None:
    """裸色值 0（`DEC-060` 的单一颜色来源）。"""
    stripped = _stripped()

    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", stripped), "组件里出现了裸色值"
