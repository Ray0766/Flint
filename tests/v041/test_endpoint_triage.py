"""GAUGE-11 · 33（实测 35）条端点逐条分诊，机读守着不漂移。

## 一句「不是缺陷」带过，等于把 35 条留给下一个人重查

`backend_unused_by_frontend` 从 `WIRE-11` 起就挂在对账器输出里，
每次收卡都写一句「不是判据」。写一次省十分钟，而下一个人要从头查 35 条。

## 分诊第一条结论：这 35 条里有 12 条**前端其实在调**

那个名字读起来是「后端有、前端没人用」，而 12 条是**尺子看不见**
（首段白名单 7 条 + 只扫 `web/lib/` 5 条）。
**修法完全相反**：真没人用 → 去接线；尺子没量到 → 去修尺子。

所以本判据里最要紧的一条是 `test_class_a_entries_really_are_called`——
A 类每一条都要**指得出调用点**，且那个文件里真有那条路径。
指不出来的话，这份分诊就是另一句没有依据的话。

## 判等值，不判「都分诊过了」

新增一个端点而没进表 → 红；表里写了一条对账器不再报的 → 也红
（说明它被接上了或退役了，两种都要有人回来确认）。
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DOC = REPO / "docs" / "端点分诊-v041.md"
TICKET = REPO / "docs" / "blocked" / "PARITY-BLIND-TO-PAGES-AND-UNLISTED-PREFIXES.md"
WEB = REPO / "web"
# 表格行形如 `| `/facts/{}` | `web/lib/derefClient.ts:17` |`
_ENDPOINT_CELL = re.compile(r"^\|\s*`(/[^`]+)`\s*\|")
_CALL_SITE = re.compile(r"`([\w./\[\]-]+\.tsx?):(\d+)`")


def _doc() -> str:
    return DOC.read_text(encoding="utf-8")


def _section(title: str) -> str:
    """取一节的正文（从 `## <title>` 到下一个 `## `）。"""
    text = _doc()
    start = text.index(f"## {title}")
    rest = text.find("\n## ", start + 1)
    return text[start: rest if rest != -1 else len(text)]


def _endpoints_in(section: str) -> list[str]:
    return [m.group(1) for line in section.splitlines()
            if (m := _ENDPOINT_CELL.match(line))]


def _reported() -> list[str]:
    """对账器**实跑**输出里的那一类。NEVER 读一份缓存下来的旧报告。"""
    done = subprocess.run(
        [sys.executable, str(REPO / "tools" / "check_fe_be_parity.py"), "--json"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=REPO, timeout=300, check=False)
    payload = json.loads(done.stdout[done.stdout.index("{"):])
    return sorted(f["subject"] for f in payload["findings"]
                  if f["kind"] == "backend_unused_by_frontend")


# GAUGE-14（v0.4.1 第 6 批）把对账器的两个盲区修掉了，于是本文件里
# 好几条判据的**前提过期**了——它们红的是自己描述的那个世界没了，不是产品出错：
#
# - **A 类整类消失**：那 14 条「尺子看不见」的端点现在被正确认出在调，
#   本来就不该在这张表上。三条按 A 类形状写的判据（等值/计数/不重复分类）
#   跟着去掉 A；`test_class_a_entries_really_are_called` 整条删除——
#   它守的是「A 类每条都指得出调用点」，而 A 类不存在了；
# - **盲区那张单已 closed**：`test_the_two_blind_spots_are_named_and_ticketed`
#   改判「单据关了，且表里记着是被谁修的」；
# - **条数 35 → 20**：卡面那个 33 与实测 35 的对照换成 32 → 20 的重算记录。
#
# **判据跟着事实走**——钉死一个过期的世界，只会让下一次真正的修复被判成错。


# ───────────────────────── acceptance②：机读守着不漂移


def test_the_triage_covers_exactly_what_the_checker_reports() -> None:
    """**判等值**：表里的端点集合 == 对账器实跑输出。

    多一条 = 表里写了一条不再被报的（接上了或退役了）；
    少一条 = 新增端点没分诊。**两种都要有人回来确认**，所以不判包含关系。
    """
    reported = set(_reported())
    triaged = {e for name in ("B · 屏在，但那一屏还写死或没接这条（11 条）",
                              "C · 屏还没建（4 条）")
               for e in _endpoints_in(_section(name))}

    assert reported, "对账器一条都没报：扫描面塌了，这条判据在空转"
    assert triaged == reported, (
        f"分诊表与实跑对不上。表里多出 {sorted(triaged - reported)}，"
        f"少了 {sorted(reported - triaged)}")


def test_the_counts_in_the_headings_match_the_rows() -> None:
    # `WB-05` 把 `/deliverables/{}/quality` 接上之后，B 类 12 → 11。
    # 标题里的数、表里的行、这里的期望值**三处一起改**——
    # 只改能让它变绿的那一处，就是把尺子改成量自己。
    """小标题里那个数与表里的行数一致。

    标题写 12 而表里只有 10 行时，读的人会以为自己看到了全部。
    """
    for name, expected in (("B · 屏在，但那一屏还写死或没接这条（11 条）", 11),
                           ("C · 屏还没建（4 条）", 4)):
        rows = _endpoints_in(_section(name))
        assert len(rows) == expected, f"{name[:1]} 类标题写 {expected}，实际 {len(rows)} 行"


def test_no_endpoint_is_triaged_into_two_classes() -> None:
    """一条端点只能进一类——进两类等于没分诊。"""
    seen: dict[str, str] = {}
    for name in ("B · 屏在，但那一屏还写死或没接这条（11 条）",
                 "C · 屏还没建（4 条）"):
        for endpoint in _endpoints_in(_section(name)):
            assert endpoint not in seen, (
                f"{endpoint} 同时进了 {seen[endpoint][:1]} 类与 {name[:1]} 类")
            seen[endpoint] = name


# ───────────────────────── A 类没有了（`GAUGE-14`）

# `test_class_a_entries_really_are_called` 在这里**整条删除**：
# 它守的是「A 类每条都指得出调用点」，而 A 类整类消失了
# （那 14 条现在被对账器正确认出在调，本来就不该在这张表上）。
# 留一条永远为真的判据比没有更坏——它占着位置，看起来像还有人在守这件事。


def test_the_two_blind_spots_are_named_and_ticketed() -> None:
    """两个盲区各有名字，且挂了一张仍 open 的单。

    改前这条判据要求那张单**仍然 open**——`GAUGE-14` 修完之后它红了，
    **红的是自己描述的那个世界没了**。

    名字仍然要留着：只写「尺子看不见」不够，**首段白名单**与
    **只扫 `web/lib/`** 是两处独立的洞，修一处另一处照样漏——
    下一个人得看得出当初漏的是哪两处。
    """
    text = _doc()

    assert "首段白名单" in text and "web/lib" in text
    assert TICKET.exists(), "盲区那张单不见了"
    head = "\n".join(TICKET.read_text(encoding="utf-8").splitlines()[:12])
    assert "**状态** closed" in head, "盲区修掉了，单据却还开着"
    assert "GAUGE-14" in text, "表里没记是被谁重算的"


# ───────────────────────── acceptance③：每一条都要有理由


def test_every_row_carries_a_reason_not_a_blanket_phrase() -> None:
    """**逐条写为什么**，NEVER 用一句话概括一整类。

    表里每一行至少三列（端点 / 去处 / 说明），且说明不许是这几个空话。
    """
    banned = ("多为内部用途", "内部使用", "无需上屏", "不是缺陷", "暂不处理")
    for name in ("B · 屏在，但那一屏还写死或没接这条（11 条）", "C · 屏还没建（4 条）"):
        section = _section(name)
        for line in section.splitlines():
            if not _ENDPOINT_CELL.match(line):
                continue
            cells = [c.strip() for c in line.strip("|").split("|")]
            assert len(cells) >= 3, f"这一行没写去处与说明：{line}"
            assert all(cells[1:]), f"这一行有空列：{line}"
            for phrase in banned:
                assert phrase not in line, f"用空话概括了：{phrase} —— {line}"


def test_the_retire_class_is_empty_and_says_why() -> None:
    """D 类为空，**并且写明为什么是空的**。

    「一条都没有」与「没查」长得一模一样——所以那一节要说清判退役的门槛
    （指得出被谁取代、或需求没了），以及为什么这 35 条一条都不满足。
    """
    section = _section("D · 该退役（0 条）")

    assert _endpoints_in(section) == []
    assert "结论" in section and "省略" in section
    assert "猜" in section, "没写清为什么不硬填一条"


# ───────────────────────── acceptance④：候选清单可用


def test_the_candidate_list_carries_a_screen_and_a_priority() -> None:
    """该上屏的那一类落成候选清单，**带屏名与优先级**。

    只列端点的话，下一批的人还要再查一遍「这条该上哪一屏」。
    """
    section = _section("该上屏的那一类：下一批候选清单（acceptance④）")
    rows = [line for line in section.splitlines()
            if line.startswith("| P") and "|" in line[2:]]

    assert len(rows) >= 8, f"候选清单只有 {len(rows)} 行"
    for line in rows:
        cells = [c.strip() for c in line.strip("|").split("|")]
        assert len(cells) >= 4, f"候选行缺列：{line}"
        assert re.fullmatch(r"P[1-4]", cells[0]), f"优先级不规范：{cells[0]}"
        assert cells[1] and cells[2] and cells[3], f"候选行有空列：{line}"


def test_the_checker_is_run_live_not_read_from_a_stale_report() -> None:
    """本文件的数据源是**实跑**，不是一份缓存下来的旧报告。

    读旧报告的话，端点面变了而报告没重跑时，上面那条等值判据会绿——
    而它绿在一份过期的事实上。
    """
    import ast

    source = Path(__file__).read_text(encoding="utf-8")
    assert "subprocess.run" in source and "check_fe_be_parity.py" in source

    # **判代码，NEVER 判注释**：第一版按整行扫「同时出现 read_text 与 json」，
    # 当场把上面这句解释性注释判成违规——说明问题的那句话被当成犯下问题。
    # **这是本批第七次**（AUTH-02 / AUTH-05 / WIRE-09 / WIRE-10 / WIRE-12 /
    # FIX-05 / 本处）。改成走 ast：只看真的把文件内容喂给 json 解析的那种调用。
    tree = ast.parse(source)
    offenders = [
        ast.unparse(node) for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and "json" in ast.unparse(node.func)
        and any("read_text" in ast.unparse(arg) for arg in node.args)
    ]

    assert offenders == [], f"在读一份缓存下来的报告：{offenders}"


def test_the_document_records_the_recount() -> None:
    """**数按实跑的来**，且换数时把前后都写下来。

    改前这条判的是「卡面写 33、实测 35」。`GAUGE-14` 修掉两个盲区之后
    条数变成 20，那两个数都过期了——**而这条判据的意图没变**：
    换了数就要留下换数的记录，否则少掉的那 12 条就没有名字。
    """
    text = _doc()

    assert "20" in text and "32" in text, "没记下重算前后的两个数"
    assert "实跑" in text or "实测" in text
    assert "GAUGE-14" in text
