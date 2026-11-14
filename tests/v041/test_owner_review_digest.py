"""HYG-02 · 第 2 批 owner_review 卡的复核摘要——38 张压着没人看。

## 为什么要这份摘要

第 2 批 89 张卡里有 38 张 `owner_review=true`。每张的 trace 里都写着
「请 owner 看这几处」，**加起来 21 万字**。owner 要看完才知道哪些还等着他，
而实际上其中一大半已经被后来的裁决覆盖掉了。

摘要把每张压成一行：**卡号 · 一句话结论 · owner 要看的那个具体点 · trace 锚点**，
并逐条标出**哪些已被 `DEC-031/032/033` 覆盖**——让 owner 只看剩下的。

## 卡面写 37，机器真相是 38

`tasks-v041-b2.json` 里 `owner_review == true` 的是 **38** 张
（37 张有 trace，`NET-03` 按 `DEC-033①` 记 `skipped_by_owner`、从没写过 trace）。
摘要按**机器真相**收 38 行——卡面 acceptance③ 要的正是集合逐字相等，
少收一张就等于替 owner 决定那张不用看。

## 判据判什么

1. **集合逐字相等**（acceptance③）：多一张少一张都红；
2. **每行四样齐全**，且 trace 锚点**在盘上真解析得到**——
   指向一个不存在的文件的锚点，比没有锚点更坏：它看起来是有出处的；
3. **标了「已覆盖」的必须点名是哪条裁决**，且那条裁决在 `DECISIONS-v04.md` 里真存在；
4. **NEVER 替 owner 下结论**（acceptance④）：摘要里不许出现
   「不必看 / 无需确认 / 已替 owner 决定」这类话。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DIGEST = REPO / "docs" / "owner复核摘要-v041.md"
TASKS = REPO / "docs" / "steward" / "tasks-v041-b2.json"
DECISIONS = REPO / "DECISIONS-v04.md"
TRACE = REPO / "docs" / "trace"
# 一行的形状：| 卡号 | 结论 | 要看的点 | trace 锚点 | 覆盖 |
_ROW = re.compile(r"^\|\s*`([A-Z][A-Z0-9]*-\d+)`\s*\|(.+)\|\s*$", re.MULTILINE)
_ANCHOR = re.compile(r"`(docs/trace/[A-Za-z0-9\-]+\.md)(#[^`]*)?`")
_DEC = re.compile(r"`(DEC-\d+)`")
NEVER_SAY = ("不必看", "无需确认", "已替 owner", "替 owner 决定", "owner 不用看")
# 已被裁决覆盖的**就是这十张**（`DEC-032` 十一张 UI 里的九张 + `UI-09`/`UI-11` 在内、
# `DEC-033` 的 `NET-03`）。判**等值**而不是判「至少有一张」：
# 本卡实测的变异③把 26 行一次性翻成「已覆盖」，而「至少有一张仍待看」照样绿——
# 因为 `UI-01`/`UI-02` 那两行的「部分覆盖…余 3 条待看」把非空对照喂饱了。
# 多一张要有人来这里说明是哪条裁决覆盖的，少一张说明有裁决被撤了。
COVERED = {
    "NET-03", "UI-03", "UI-04", "UI-05", "UI-06",
    "UI-07", "UI-08", "UI-09", "UI-10", "UI-11",
}


def _digest() -> str:
    return DIGEST.read_text(encoding="utf-8")


def _rows() -> dict[str, str]:
    return {m.group(1): m.group(2) for m in _ROW.finditer(_digest())}


def _owner_review_ids() -> set[str]:
    tasks = json.loads(TASKS.read_text(encoding="utf-8-sig"))["tasks"]
    return {t["id"] for t in tasks if t.get("owner_review")}


# ───────────────────────── acceptance③：机读守着不漂移


def test_the_card_set_is_word_for_word_the_machine_truth() -> None:
    """摘要里的卡号集合 == `tasks-v041-b2.json` 里 `owner_review=true` 的集合。

    少收一张，就等于**替 owner 决定那张不用看**；
    多收一张，owner 会去看一张本来不需要他的卡。
    """
    listed, truth = set(_rows()), _owner_review_ids()

    assert listed == truth, (
        f"多出：{sorted(listed - truth)}；漏掉：{sorted(truth - listed)}"
    )
    assert len(truth) == 38, f"第 2 批的 owner_review 卡是 {len(truth)} 张，不是 38"


def test_every_row_carries_all_four_fields() -> None:
    """每行四样：结论 · 要看的点 · trace 锚点 · 覆盖状态。缺一样判红。"""
    thin: list[str] = []
    for card, rest in _rows().items():
        cells = [c.strip() for c in rest.split("|")]
        if len([c for c in cells if c]) < 4:
            thin.append(f"{card}（只有 {len([c for c in cells if c])} 格）")

    assert thin == [], f"这些行没写全：{thin}"


def test_every_trace_anchor_resolves_on_disk() -> None:
    """锚点指到的文件**必须在盘上**。

    指向一个不存在的文件的锚点，比没有锚点更坏：**它看起来是有出处的**。
    """
    missing = [
        m.group(1) for m in _ANCHOR.finditer(_digest())
        if not (REPO / m.group(1)).exists()
    ]

    assert missing == [], f"这些 trace 锚点不在盘上：{sorted(set(missing))}"


def test_the_one_card_without_a_trace_says_so() -> None:
    """`NET-03` 从没写过 trace（`DEC-033①` 记 `skipped_by_owner`）——摘要要**说出来**。

    给它编一个 trace 锚点，或者干脆不收它，都是把一件已知的事藏起来。
    """
    row = _rows()["NET-03"]

    # **三样都要**：没有 trace、为什么没有（skipped_by_owner）、依据哪条裁决。
    # 少一样，这一行读起来就像一张正常结案的卡——而它从来没有被执行过。
    for token in ("无 trace", "skipped_by_owner", "DEC-033"):
        assert token in row, f"NET-03 那行没说清（缺 {token}）：{row}"


# ───────────────────────── acceptance②：已被裁决覆盖的逐条标出


def test_covered_rows_name_a_decision_that_really_exists() -> None:
    """标了覆盖的行 MUST 点名裁决号，且那条裁决在 `DECISIONS-v04.md` 里真存在。"""
    decisions = DECISIONS.read_text(encoding="utf-8")
    named = {m.group(1) for m in _DEC.finditer(_digest())}

    assert named, "一条裁决都没点名——那 DEC-031/032/033 覆盖了什么？"
    for dec in sorted(named):
        assert f"## {dec}" in decisions or f"### {dec}" in decisions or \
               f"**{dec}" in decisions or f"`{dec}`" in decisions, (
            f"{dec} 在 DECISIONS-v04.md 里找不到"
        )


def test_both_covered_and_open_rows_exist() -> None:
    """**非空对照**：覆盖与仍待看两类都要有实例。

    没有这条，「全部标成已覆盖」也能让上面几条全绿——
    而那正是把 38 张一次性抹掉的做法。
    """
    rows = _rows()
    covered = {c for c, r in rows.items() if "已覆盖" in r}
    still = {c for c, r in rows.items() if "已覆盖" not in r}

    assert covered == COVERED, (
        f"覆盖名单变了：多出 {sorted(covered - COVERED)}、少了 {sorted(COVERED - covered)}"
    )
    assert still, "全被覆盖了？那 owner 一张都不用看，这份摘要就没有存在的必要"
    assert all("待看" in rows[c] for c in still), (
        f"这些行既没标已覆盖、也没说仍待看：{sorted(c for c in still if '待看' not in rows[c])}"
    )


# ───────────────────────── acceptance④：NEVER 替 owner 下结论


def test_the_digest_never_decides_for_the_owner() -> None:
    """摘要只陈述与指路。

    「不必看」这三个字一旦写进去，就等于替 owner 做了一次筛选——
    而 owner 看不到被筛掉的是什么。
    """
    text = _digest()
    said = [word for word in NEVER_SAY if word in text]

    assert said == [], f"摘要里替 owner 下了结论：{said}"


def test_every_open_row_says_what_the_decision_is() -> None:
    """仍待看的每一行都要写清**要 owner 定的是什么**，NEVER 只写「待定」。

    「待定」是把问题原样退回去；一行摘要的价值全在那句「定什么」上。
    """
    vague: list[str] = []
    for card, rest in _rows().items():
        if "待看" not in rest:
            continue
        point = rest.split("|")[1].strip() if rest.count("|") >= 1 else ""
        if len(point) < 8 or point in {"待定", "—", "-"}:
            vague.append(f"{card}：{point!r}")

    assert vague == [], f"这些行只写了「待定」：{vague}"
