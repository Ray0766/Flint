"""SPEC-01：`DEC-036` 落地——主题名称三元组，改规格不动冻结件。

## 事情是什么

规格 `docs/前端功能说明-v2.md#2.4`（主题列表 + 选主题）逐字写着：

> 名称三元组上屏：主行 `name_native`，机翻译名为**次要行**，译名带机翻标记。

而冻结件 `contracts/models.py#Topic` 的全部字段是
`topic_id / seed_id / one_liner / target_user_tag / form_factor_tag /
why_now / keyword_mapping / embedding`——**它本来就没有名称**。

热点簇确实有（`contracts_v04#Cluster` 的 `name_native` / `name_lang` /
`name_display`，`HotspotCard` 正在用）。那句话大概率是从簇那边抄过来的。

owner 2026-08-08 裁：**改规格，不动冻结件**（`DEC-036`）。给 `Topic` 加两个没人产出的
字段，只会让屏上出现一个「永远没有译名的三元组」——那看起来像翻译服务坏了，
而真相是这个实体从来就没有名称。

## 本文件最值钱的一条不是「那句话改了」

是**下一次抄错会被当场拦住**：规格里凡提名称三元组的行，
MUST 点名是哪个实体，且那个实体在冻结件里 MUST 真有那两个字段。

只判「#2.4 那一行没了」的话，同一句话抄到 #2.6 上照样绿。
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SPEC = REPO / "docs" / "前端功能说明-v2.md"
CONTRACTS = REPO / "contracts" / "models.py"
CONTRACTS_V04 = REPO / "contracts_v04" / "models_v04.py"
SHEET = REPO / "docs" / "blocked" / "TOPIC-HAS-NO-NAME-TRIPLE.md"
DECISIONS = REPO / "DECISIONS-v04.md"
B5_TASKS = REPO / "docs" / "steward" / "tasks-v041-b5.json"

# 名称三元组的两个真字段。**取自冻结件的写法，NEVER 只判「名称」二字**。
TRIPLE_FIELDS = ("name_native", "name_display")
# 规格里提到它的两种写法。任一出现，那一行就要点名实体。
MENTIONS = ("名称三元组", "`name_native`")


def _spec_lines() -> list[tuple[int, str]]:
    """规格里**在做主张**的行。

    引述块（`> …`）里且点着某条 `DEC-` 的行**不算主张**：它记的是「原先写的是什么、
    为什么作废」。不剥掉的话，判据会把**解释问题的那句话**当成问题本身——
    本仓栽过多次（`docs/blocked/SCANNERS-DO-NOT-STRIP-COMMENTS.md`）。

    为什么不是「凡 `>` 都跳过」：那就成了一条谁都能用的逃生口
    （把主张塞进引述块即可绕过）。要求同一行点着裁决号，
    等于要求**每一次豁免都有出处**。
    """
    out: list[tuple[int, str]] = []
    for no, line in enumerate(SPEC.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.lstrip()
        if stripped.startswith(">") and re.search(r"DEC-\d{3}", stripped):
            continue
        out.append((no, line))
    return out


def _entity_fields(name: str) -> set[str] | None:
    """从两份冻结件里取某个实体声明的字段名。找不到这个类 → None。"""
    for path in (CONTRACTS_V04, CONTRACTS):
        text = path.read_text(encoding="utf-8")
        match = re.search(rf"^class {name}[:(]", text, re.MULTILINE)
        if match is None:
            continue
        body = text[match.end():]
        nxt = re.search(r"\n(?:@dataclass|class |[A-Za-z_]+ = )", body)
        body = body if nxt is None else body[: nxt.start()]
        return set(re.findall(r"^\s{4}([a-z_][a-z0-9_]*)\s*:", body, re.MULTILINE))
    return None


def _entities_named_on(line: str) -> list[str]:
    """这一行用反引号点了名的冻结件实体。"""
    return [
        token for token in re.findall(r"`([A-Z][A-Za-z0-9_]*)`", line)
        if _entity_fields(token) is not None
    ]


# ───────────────────────── 一、那句话对主题不再成立


def test_the_topic_screen_no_longer_claims_a_name_triple() -> None:
    """#2.4 那一段与屏总表那一行，都不再说主题有名称三元组。"""
    text = SPEC.read_text(encoding="utf-8")
    claims = {line for _, line in _spec_lines()}
    section = [
        line for line in
        text[text.index("### 2.4 "):text.index("### 2.5 ")].splitlines()
        if line in claims                       # 作废引述块不算主张（见 `_spec_lines`）
    ]
    table_row = next(ln for ln in claims if ln.startswith("| 2.4 |"))

    for where, body in (("#2.4 正文", "\n".join(section)), ("屏总表 2.4 行", table_row)):
        for mention in MENTIONS:
            assert mention not in body, f"{where}还写着主题有名称三元组（{mention}）"


def test_the_topic_screen_still_says_what_it_does_show() -> None:
    """删掉一句 NEVER 等于留个空。

    #2.4 得说清主题屏**实际**显示什么，否则下一个人只会把那句话抄回来——
    他看到的是一段没有呈现规则的屏。
    """
    text = SPEC.read_text(encoding="utf-8")
    section = text[text.index("### 2.4 "):text.index("### 2.5 ")]

    assert "one_liner" in section, "#2.4 没说主题屏拿什么当标题"
    assert "DEC-036" in section, "#2.4 没写这句改动的出处，下一个人无从知道为什么"
    assert len(section.strip()) > 200, "#2.4 只剩一个标题"


# ───────────────────────── 二、机器守着不漂移（本卡最值钱的一条）


def test_every_name_triple_claim_names_a_real_entity() -> None:
    """规格里凡提名称三元组的行，MUST 点名实体。

    不点名的话，读的人只能从上下文猜是哪个实体——而 `#2.4` 那次抄错，
    正是因为「名称三元组」这句话可以脱离实体独立成立。
    """
    offenders = [
        (no, line) for no, line in _spec_lines()
        if any(m in line for m in MENTIONS) and not _entities_named_on(line)
    ]

    assert offenders == [], (
        "这些行提了名称三元组却没点名是哪个实体："
        + "；".join(f"第 {no} 行 {line.strip()[:40]}" for no, line in offenders)
    )


def test_every_named_entity_really_has_the_two_fields() -> None:
    """点了名还不够——那个实体在冻结件里 MUST 真有那两个字段。

    **这一条就是 `DEC-036` 的机器形态。** 下一次有人把这句话抄到
    一个没有名称的实体上，它当场红。
    """
    for no, line in _spec_lines():
        if not any(m in line for m in MENTIONS):
            continue
        for entity in _entities_named_on(line):
            fields = _entity_fields(entity)
            assert fields is not None
            missing = [f for f in TRIPLE_FIELDS if f not in fields]
            assert not missing, (
                f"第 {no} 行说 `{entity}` 有名称三元组，"
                f"而冻结件里它没有 {missing}——这正是 DEC-036 那次抄错"
            )


def test_the_ruler_would_really_catch_the_mistake_it_was_built_for() -> None:
    """**判据自己的阴性对照**：把那句话安到 `Topic` 上，上面那条必须红。

    没有这一条，`_entity_fields` 哪天解析不出字段（改了缩进、换了 dataclass 写法）
    就会让每个实体都「没有缺字段」，而它看起来仍然是绿的。
    """
    topic_fields = _entity_fields("Topic")
    cluster_fields = _entity_fields("Cluster")

    assert topic_fields, "解析不出 Topic 的字段——判据本身坏了"
    assert cluster_fields, "解析不出 Cluster 的字段——判据本身坏了"
    assert [f for f in TRIPLE_FIELDS if f not in topic_fields] == list(TRIPLE_FIELDS), (
        "Topic 竟然有名称三元组了？那 DEC-036 要重开"
    )
    assert [f for f in TRIPLE_FIELDS if f not in cluster_fields] == [], (
        "Cluster 没有名称三元组——那广场那张卡的主行是从哪来的"
    )


def test_the_frozen_contract_was_not_touched() -> None:
    """acceptance④：本卡改的是规格文字，`contracts/` 一个字都不动。

    判 `Topic` 的字段集**逐字相同**：加一个字段这里就红。
    """
    assert _entity_fields("Topic") == {
        "topic_id", "seed_id", "one_liner", "target_user_tag",
        "form_factor_tag", "why_now", "keyword_mapping", "embedding",
    }


# ───────────────────────── 三、同一句话的另外两处也跟着改


def test_the_batch_five_card_was_corrected_too() -> None:
    """`CHAIN-03` 卡面 acceptance② 抄的是同一句话。

    卡面留着旧话的话，下一个照卡做的人会把它再实现一遍——
    **而那张卡已经 verified，没人会再去看它的 trace**。
    """
    import json

    tasks = json.loads(B5_TASKS.read_text(encoding="utf-8-sig"))["tasks"]
    chain03 = next(t for t in tasks if t["id"] == "CHAIN-03")
    joined = " ".join(chain03["acceptance"])

    assert "名称三元组" not in joined, "CHAIN-03 卡面还写着名称三元组"
    assert "DEC-036" in joined, "卡面没写订正的出处"
    assert "one_liner" in joined, "订正后没说主题屏该显示什么"


def test_the_sheet_is_closed_by_the_decision_not_by_the_card() -> None:
    """关单的条件是**事情有了结论**，不是「那张卡跑完了」。

    所以先验结论在（`DEC-036` 在册且规格已订正），再验状态行。
    """
    assert "DEC-036" in DECISIONS.read_text(encoding="utf-8")

    text = SHEET.read_text(encoding="utf-8")
    state = next((ln for ln in text.splitlines()[:8] if ln.startswith("**状态**")), "")

    assert state.startswith("**状态** closed"), f"单据还开着：{state!r}"
    assert "DEC-036" in text, "单子里没写是被哪条裁决关的"
    assert "SPEC-01" in text, "单子里没写是哪张卡落的地"
