"""TRIAGE-02：剩余「已装配未调用」逐条判。

**NEVER 靠人记**：这张表与尺子的实况**双向一致**——
表里每一条都在尺子的输出里，尺子输出的每一条都在表里。
数字对不上时红。
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TABLE = REPO / "docs" / "端点分诊-v041-triage02.md"


def _unused() -> set[str]:
    done = subprocess.run(
        [sys.executable, str(REPO / "tools" / "check_fe_be_parity.py"), "--json"],
        capture_output=True, text=True, encoding="utf-8", cwd=REPO, check=False)
    report = json.loads(done.stdout)
    return {f["subject"] for f in report["findings"]
            if f["kind"] == "backend_unused_by_frontend"}


def _listed() -> set[str]:
    """表里点名的端点。**只认表行**（以 `|` 开头的那些）。

    第一版扫的是全文的反引号路径，于是正文里提到的**屏**路径
    （`/design`、`/share/[token]`）也被当成了端点——判据当场红，**而它是对的**：
    那两个不是端点。**把它们从正则里排掉是错的修法**（那等于给提取器开后门）；
    正确的修法是让每一条端点都住在表行里，提取器只看表行。
    """
    rows = [ln for ln in TABLE.read_text(encoding="utf-8").splitlines()
            if ln.startswith("| `/")]
    return {m for row in rows for m in re.findall(r"`(/[^`]+)`", row)}


def test_the_table_and_the_ruler_agree_both_ways() -> None:
    """acceptance③：**双向一致**。

    只判一个方向的话：表里多写几条没人管的，或者尺子多报几条表里没有的，
    都能绿——而两种都是「这张表不再是实况」。
    """
    listed, unused = _listed(), _unused()

    assert listed - unused == set(), f"表里有尺子没报的：{sorted(listed - unused)}"
    assert unused - listed == set(), f"尺子报了而表里没有：{sorted(unused - listed)}"


def test_every_line_is_judged_into_exactly_one_of_two_classes() -> None:
    """每一条落进**甲（这一版要接）**或**乙（这一版明确不接）**，不能两头都不在。"""
    text = TABLE.read_text(encoding="utf-8")
    jia = text[text.index("## 甲"): text.index("## 乙")]
    yi = text[text.index("## 乙"): text.index("## 数字对账")]

    for endpoint in _unused():
        in_jia = f"`{endpoint}`" in jia
        in_yi = f"`{endpoint}`" in yi
        assert in_jia != in_yi, f"{endpoint} 落进了两类或一类都没落"


def test_the_ones_to_wire_carry_a_card_number() -> None:
    """甲那一类**要给卡号**——没有卡号的「要接」与「以后再说」没有区别。"""
    text = TABLE.read_text(encoding="utf-8")
    jia = text[text.index("## 甲"): text.index("## 乙")]

    rows = [ln for ln in jia.splitlines() if ln.startswith("| `/")]
    assert rows, "甲类一条都没有"
    for row in rows:
        assert re.search(r"`B\d+-[A-Z-]+`", row), f"这一行没有卡号：{row}"


def test_the_ones_not_to_wire_say_which_specific_thing_they_wait_for() -> None:
    """乙那一类 **NEVER 写「以后再说」**，要说清等的是哪一件具体的事。"""
    text = TABLE.read_text(encoding="utf-8")
    yi = text[text.index("## 乙"): text.index("## 数字对账")]

    assert "以后再说" not in yi
    # 四个小节各自说清等什么。
    assert yi.count("等的那一件具体的事") >= 3
    assert "不再写死" in yi or "改成真取数" in yi


def test_no_endpoint_was_excluded_to_make_the_number_smaller() -> None:
    """acceptance⑤：**NEVER 用「把它从尺子里排掉」让数字变小**。

    与 `ENTRY-05` 那条「豁免名单只许有 `/share/[token]`」是同一条纪律。
    这里判的是：这张表里**一条排除都没有**——15 条全部逐条判过。
    （原本 16 条；`WB-05` 把 `/deliverables/{}/quality` 接上之后尺子不再报它，
    表与判据一起减一——**只改一处就是让两处各说各的**。）
    """
    listed = _listed()

    assert len(listed) == len(_unused()) == 15, (len(listed), len(_unused()))
    text = TABLE.read_text(encoding="utf-8")
    assert "排除" in text and "一条排除都没有" in text
