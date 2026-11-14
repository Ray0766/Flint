"""BL-11：问题单总清账（Q-001~Q-010 逐条**回源核实**，不是照抄旧状态）。

## 这份文件为什么会变成没人敢信的东西

`docs/v0.4-问题单.md` 是按时间往下追加的：每条 Q 写下时的现象、当时的裁决、
当时的状态。**问题解决了、前提变了，旧段落还在原地**——BL-06 就撞上过一次
（Q-009/Q-010 写着「DB 无 topics 表」，而四张表早就建好了）。

读到一句过期的话，下一个人会去建第二套落库路径。所以本卡做两件事：

1. **逐条回源核实**（查文件行号 / 查表 / 跑命令），按三类标注：
   **已解决**（给依据）· **仍未解决且卡在谁** · **前提已变**；
2. 用这份测试把「每条 Q 必须有状态字 + 依据字」钉住——
   **防止下次又变成一份没人敢信的旧文件**。

## NEVER 为了让清单好看而改状态

卡面第四条原话。卡在 owner 的就写卡在 owner——把它写成「已解决」，
owner 就再也不会被提醒那件事还等着他。
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LEDGER = REPO_ROOT / "docs" / "v0.4-问题单.md"

QUESTIONS = tuple(f"Q-{n:03d}" for n in range(1, 11))

# 三类标注的词面（`STATUS_WORDS`）与依据标记（`EVIDENCE_MARK`）都写死在这里：
# 从文件里反推的话，把文件写坏也测不出来。
STATUS_WORDS = ("已解决", "仍未解决", "前提已变")
EVIDENCE_MARK = "**依据**"
BLOCKER_MARK = "**卡在**"


def _sections() -> dict[str, str]:
    """按 `## Q-0XX` 切段。每段到下一个 `## ` 为止。"""
    text = LEDGER.read_text(encoding="utf-8")
    out: dict[str, str] = {}
    for qid in QUESTIONS:
        match = re.search(rf"^## {qid}\b.*$", text, re.MULTILINE)
        if match is None:
            continue
        rest = text[match.start():]
        nxt = re.search(r"^## ", rest[3:], re.MULTILINE)
        out[qid] = rest[: nxt.start() + 3] if nxt else rest
    return out


# ───────────────────────── 十条都在


@pytest.mark.parametrize("qid", QUESTIONS)
def test_every_question_has_a_section(qid: str) -> None:
    """Q-001~Q-010 一条不少——少一条就意味着有个问题从账上消失了。"""
    assert qid in _sections(), f"{qid} 在问题单里找不到"


# ───────────────────────── 每条有状态字（acceptance③）


@pytest.mark.parametrize("qid", QUESTIONS)
def test_every_question_carries_a_current_status(qid: str) -> None:
    """每条 Q 必须有**三类之一**的现状标注（@2026-08-04 这一轮核出来的）。"""
    section = _sections()[qid]
    hits = [word for word in STATUS_WORDS if word in section]

    assert hits, f"{qid} 没有现状标注（三类之一：{STATUS_WORDS}）"


@pytest.mark.parametrize("qid", QUESTIONS)
def test_every_question_carries_evidence(qid: str) -> None:
    """acceptance①：每条给依据——文件行号 / 表名 / 端点 / 命令输出。

    只写状态不给依据，下一个人没法自己复核，只能选择相信——
    而问题单正是因为「相信一句过期的话」才需要这张卡。
    """
    section = _sections()[qid]

    assert EVIDENCE_MARK in section, f"{qid} 没写依据"


@pytest.mark.parametrize("qid", QUESTIONS)
def test_the_evidence_is_checkable_not_a_feeling(qid: str) -> None:
    """依据必须是**可复核**的东西：文件路径 / 表名 / 端点 / 命令。

    「已核实」三个字不算依据——它要求读的人相信我。
    """
    section = _sections()[qid]
    evidence = section[section.index(EVIDENCE_MARK):][:600]
    checkable = (
        re.search(r"[\w/]+\.(py|md|ts|tsx|yaml|json)", evidence)
        or re.search(r"`[a-z_]+`\s*表", evidence)
        or re.search(r"(GET|POST) /", evidence)
        or "$ " in evidence
        or re.search(r"\bnpm\b|\bpytest\b|\bdocker\b", evidence)
    )

    assert checkable, f"{qid} 的依据不可复核：{evidence[:120]}"


# ───────────────────────── 未解决的要写卡在谁（acceptance②④）


@pytest.mark.parametrize("qid", QUESTIONS)
def test_an_unresolved_question_names_who_it_is_stuck_on(qid: str) -> None:
    """**仍未解决**的每条都要写清卡在谁（owner 输入 / 红线 / 外部资源）。

    不写的话，「未解决」就成了一句没有下一步的话——而它本该是一个请求。
    """
    section = _sections()[qid]
    if "仍未解决" not in section:
        return

    assert BLOCKER_MARK in section, f"{qid} 仍未解决却没写卡在谁"


def test_at_least_one_question_is_still_unresolved() -> None:
    """**NEVER 为了让清单好看而全标已解决**（卡面第四条）。

    这一条是反向的：真有卡在 owner 的事，清单上就该看得见。
    今天 Q-004（生产口径验证需 owner 供给）仍在等——它一旦被标成已解决，
    owner 就再也不会被提醒。
    """
    sections = _sections()
    unresolved = [qid for qid, body in sections.items() if "仍未解决" in body]

    assert unresolved, "十条全标已解决——回源核实过吗？"


def test_the_premise_changed_class_is_used_where_it_applies() -> None:
    """**前提已变**这一类真的被用上了（Q-005 的「本机无 node」已不成立）。

    把它并进「已解决」会丢掉一个重要区别：问题不是被解决的，是**不再成立**——
    而那意味着当初的处置方案也不必再执行。
    """
    sections = _sections()
    changed = [qid for qid, body in sections.items() if "前提已变" in body]

    assert changed, "没有一条标成前提已变——而 Q-005/009/010 的前提确实变了"


# ───────────────────────── 现状与真件对得上（回源核实，不是照抄）


def test_q005_premise_is_really_void_node_exists_now() -> None:
    """Q-005 写的是「本机无 node/npm」——**今天 node 与 npm 都在**。

    这一条不查文件，查**机器**：文件说什么不算数。
    """
    import shutil

    assert shutil.which("node"), "node 不在，Q-005 的前提还成立"
    assert shutil.which("npm"), "npm 不在，Q-005 的前提还成立"


def test_q001_premise_is_really_void_docker_exists_now() -> None:
    """Q-001 写的是「本机无 docker」——同样查机器。"""
    import shutil

    assert shutil.which("docker"), "docker 不在，Q-001 的前提还成立"


def test_q009_and_q010_point_at_bl06() -> None:
    """Q-009/Q-010 的核实出处是 BL-06（那张卡逐条查了表、INSERT、端点）。"""
    sections = _sections()

    for qid in ("Q-009", "Q-010"):
        assert "BL-06" in sections[qid], f"{qid} 没写核实出处"


def test_the_ledger_has_a_summary_table_at_the_top() -> None:
    """总清账要有一张**一眼可扫**的三类汇总表。

    十条散在四百行里，没有汇总表的话，「现在到底卡着几件事」要读全文才知道。
    """
    text = LEDGER.read_text(encoding="utf-8")
    head = text[: text.index("## Q-") if "## Q-" in text else len(text)]

    assert "总清账" in head
    for qid in QUESTIONS:
        assert qid in head, f"汇总表里缺 {qid}"
