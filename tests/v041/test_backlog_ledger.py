"""BL-12：待办清单总清账（四份来源合成一张表，每行五字段齐全）。

## 为什么要合成一张

积压散在四处：`docs/待办-优先级清单.md`（A~F 六组）、`docs/v0.4.1-候选清单.md`
（七项）、`docs/review/终检-v04.md`（八条新缺陷）、`tasks-v041-b2.json` 的 K1~K6/Z
与 `CLAUDE.md#S4` 的六条未决项。

四份各写各的时间点。**待办清单写于 2026-07-31，其中多条已被后续工作解决**
（B3/B4 当时就标了完成；A3/A4/A5/A6 本批刚做完；F5 的持久化前提 BL-06 已证明不成立）。
照抄任何一份，得到的都是一张过期的图。

## 每行五字段，缺一即红

`来源 | 一句话 | 现状（回源核实）| 卡在谁 | 本批覆盖`

- **现状**必须带依据（卡号 / 文件 / 命令），不是「已完成」三个字；
- **卡在谁**只有四种值：`—`（不卡）/ `owner` / `外部资源` / `红线`；
- 「做不了」的那些，卡在谁那一列**要能读成一句可执行的请求**，
  而不是「待定」（卡面 acceptance③ 原话）。
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LEDGER = REPO_ROOT / "docs" / "积压总账-v041.md"

# 五列的表头（写死：从文件里反推的话，把表头改坏也测不出来）
COLUMNS = ("来源", "一句话", "现状", "卡在谁", "本批覆盖")
BLOCKERS = ("—", "owner", "外部资源", "红线")
# 四份来源都要出现在总账里，一份不少
SOURCES = ("待办-优先级清单", "v0.4.1-候选清单", "终检-v04", "S4")


def _rows() -> list[list[str]]:
    """总账里的数据行（跳过表头与分隔行）。"""
    rows: list[list[str]] = []
    for line in LEDGER.read_text(encoding="utf-8").split("\n"):
        stripped = line.strip()
        if not stripped.startswith("|") or set(stripped) <= set("|-: "):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if len(cells) == len(COLUMNS) and cells[0] not in COLUMNS:
            rows.append(cells)
    return rows


def test_the_ledger_exists() -> None:
    assert LEDGER.exists(), "总账不在盘上"


def test_the_table_has_the_five_columns() -> None:
    """五列表头逐字对上——少一列，那一列的信息就整张表都没有。"""
    text = LEDGER.read_text(encoding="utf-8")

    # 找**同时含五个列名**的那一行：文件里还有一张三列的「来源一览」表，
    # 只按第一个列名找会找到它——判据要认的是这张表，不是任何一张表。
    header = next(
        line for line in text.split("\n")
        if line.strip().startswith("|") and all(col in line for col in COLUMNS)
    )
    cells = [c.strip() for c in header.strip().strip("|").split("|")]

    assert tuple(cells) == COLUMNS


def test_every_row_has_all_five_fields_filled() -> None:
    """acceptance④：每行四字段齐全，**空格子即红**。

    空格子最常出现在「卡在谁」那一列——而那正是最该有人读到的一列。
    """
    empty = [
        (row[0], COLUMNS[i])
        for row in _rows()
        for i in range(len(COLUMNS))
        if not row[i] or row[i] in ("", "待定", "TBD", "?")
    ]

    assert empty == [], f"这些格子是空的或写着「待定」：{empty}"


def test_the_status_column_carries_evidence() -> None:
    """acceptance④：现状字段**带依据**——卡号 / 文件路径 / 命令。

    「已完成」三个字不算依据：它要求读的人相信我。
    """
    weak = []
    for row in _rows():
        status = row[2]
        checkable = (
            re.search(r"[A-Z]{2,6}-\d{2}", status)                 # 卡号
            or re.search(r"[\w/]+\.(py|md|ts|tsx|yaml|json|mjs)", status)
            or re.search(r"`[^`]+`", status)                        # 表名/命令/端点
        )
        if not checkable:
            weak.append((row[0], status[:40]))

    assert weak == [], f"这些行的现状没给依据：{weak}"


@pytest.mark.parametrize("source", SOURCES)
def test_all_four_sources_are_represented(source: str) -> None:
    """四份来源一份不少——漏一份，那份里的积压就从账上消失了。"""
    text = LEDGER.read_text(encoding="utf-8")

    assert source in text, f"总账里没有这份来源：{source}"


def test_the_blocker_column_uses_the_closed_vocabulary() -> None:
    """卡在谁只有四种值：`—` / `owner` / `外部资源` / `红线`。

    闭集的作用是让「还有几件事卡在 owner」这个问题能被一眼数出来——
    自由文本写不出这个数。
    """
    bad = [(row[0], row[3]) for row in _rows() if row[3] not in BLOCKERS]

    assert bad == [], f"这些行的「卡在谁」不在闭集 {BLOCKERS} 里：{bad}"


def test_everything_stuck_on_the_owner_states_an_executable_request() -> None:
    """acceptance③：卡在 owner 的每一条 MUST 写清**要 owner 提供什么**。

    「待定」不是请求。一句可执行的请求长这样：
    「需要 12 份真实组稿的内容源」。
    """
    text = LEDGER.read_text(encoding="utf-8")
    section = text[text.index("## 卡在 owner"):] if "## 卡在 owner" in text else ""

    assert section, "总账里没有「卡在 owner」的请求清单"

    # 行首是 `A2 待办-优先级清单` 这种「编号 + 来源」，请求清单里用的是编号。
    # 判据取编号那一段——要求整串出现等于逼着请求清单抄一遍来源名。
    owner_ids = [row[0].split()[0] for row in _rows() if row[3] == "owner"]
    for key in owner_ids:
        assert key in section, f"{key} 卡在 owner，但请求清单里没有它"


def test_the_owner_requests_are_sentences_not_placeholders() -> None:
    """请求清单里每条都是一句话，且**不含**「待定 / 另议 / 以后再说」。"""
    text = LEDGER.read_text(encoding="utf-8")
    section = text[text.index("## 卡在 owner"):]
    section = section[: section.index("\n## ")] if "\n## " in section else section
    # 只判**编号条目那几行**，不判上面那段说明——说明里正写着「这一节 NEVER 出现
    # 『待定』『另议』」，连它一起判就是判据与留痕互相取消（本仓第十一次同型）。
    items = "\n".join(
        line for line in section.split("\n")
        if re.match(r"^\s*\d+\.", line) or line.startswith("   ")
    )

    assert items.strip(), "请求清单里一条编号条目都没有"
    for weasel in ("待定", "另议", "以后再说", "TBD"):
        assert weasel not in items, f"请求清单里出现了占位词：{weasel}"


def test_the_stale_rows_of_the_old_list_are_marked_stale() -> None:
    """acceptance②：待办清单写于 2026-07-31，其中多条已被后续工作解决。

    逐条核实过的证据：A3/A4/A5/A6 本批做完、F5 的持久化前提 BL-06 已证不成立。
    这四条在总账里必须**不是**「未做」。
    """
    by_key = {row[0]: row for row in _rows()}

    for key in ("A3", "A4", "A5", "A6", "F5"):
        matching = [k for k in by_key if k.startswith(key)]
        assert matching, f"总账里找不到 {key}"
        status = by_key[matching[0]][2]
        assert "未做" not in status, f"{key} 仍被标成未做——照抄了旧清单？"


def test_the_batch_coverage_column_points_at_real_cards() -> None:
    """「本批覆盖」写的卡号必须是 `tasks-v041-b2.json` 里真有的卡。

    写一个不存在的卡号，等于给了一个查不下去的线索。
    """
    import json

    with (REPO_ROOT / "docs" / "steward" / "tasks-v041-b2.json").open(
        encoding="utf-8-sig"
    ) as handle:
        known = {t["id"] for t in json.load(handle)["tasks"]}

    unknown: list[tuple[str, str]] = []
    for row in _rows():
        for card in re.findall(r"\b[A-Z]{2,6}-\d{2}(?:-\d{2})?\b", row[4]):
            if card not in known and not card.startswith(("Q-", "F-", "DEC-")):
                unknown.append((row[0], card))

    assert unknown == [], f"这些卡号在 tasks-v041-b2.json 里不存在：{unknown}"


def test_the_summary_counts_match_the_table() -> None:
    """顶部的一眼汇总数必须与表里数出来的一致——不一致就是两个真相。"""
    text = LEDGER.read_text(encoding="utf-8")
    rows = _rows()

    stated = re.search(r"共\s*(\d+)\s*行", text)
    assert stated, "顶部没写总行数"
    assert int(stated.group(1)) == len(rows), (
        f"顶部写 {stated.group(1)} 行，表里数出来 {len(rows)} 行"
    )

    stated_owner = re.search(r"卡在 owner\s*(\d+)\s*条", text)
    assert stated_owner, "顶部没写卡在 owner 的条数"
    assert int(stated_owner.group(1)) == len([r for r in rows if r[3] == "owner"])
