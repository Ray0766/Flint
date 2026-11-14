"""WB-05：章节导航 + 逐章检查项（五套模板的章节表照蓝本逐字）。

## 一处定义他处引用：章节表**由 yaml 生成**，不是手抄

工单原话：「章节表 MUST 与 `assets/templates/*.yaml` 对齐 …… NEVER 在前端
另建一份章节清单」。而前端今天**没有运行时的路**去读那五个 yaml
（全仓没有任何端点回报告模板；`/design/templates` 是设计台那一族，不是这个）。

所以走派生：`tools/gen_section_tables.py` 从 yaml 生成
`web/lib/sectionTables.generated.ts`，本文件用 `--check` 钉住它是最新的。
手抄的话，两处会在某次改模板之后分叉，而症状是
「章节导航里有一章，正文里永远没有它」——屏上看不出是抄错了还是没生成。

## 蓝本与 yaml 实测**对得上**（所以没有开单）

acceptance③ 说「两处对不上时停下开单」。逐字比过了：五套 × 每章的
`id / share% / 字数区间 / 检查问句` 与蓝本 `const TPLS` 表**逐字相同**。
蓝本自己那行注释也这么写着：「章节表来自附件 assets/templates/*.yaml」。

**只有显示名不在 yaml 里**（yaml 没有中文名/英文名这两格）。
它是界面文案 → 走 `messages/{zh,en}.json` 的 `wb.section.<模板>.<章节>`，
与全站同一套 i18n（两份词典的对称判据因此管得到它）。
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from tools.probe_evidence import require_probe_evidence

REPO = Path(__file__).resolve().parents[2]
PROBE = REPO / ".ui-probe" / "wb"
REPORT = PROBE / "sections.json"
PWENV = Path(r"C:\pwenv\Scripts\python.exe")

WEB = REPO / "web"
NAV = WEB / "components" / "workbench" / "WorkbenchSections.tsx"
GENERATED = WEB / "lib" / "sectionTables.generated.ts"
GENERATOR = REPO / "tools" / "gen_section_tables.py"
TEMPLATES = REPO / "assets" / "templates"
BLUEPRINT = REPO / "前端设计" / "ai工作台" / "Flint 设计台 v3.dc.html"
MESSAGES = WEB / "messages"
PROBE_TOOL = REPO / "tools" / "ui_probe_wb_sections.py"

FIVE = ("generic", "startup", "engineering", "grant", "thesis")

_INPUTS = (NAV, GENERATED, WEB / "app" / "workbench" / "page.tsx",
           WEB / "app" / "globals.css", PROBE_TOOL)


def _inputs_stamp() -> str:
    import hashlib

    h = hashlib.sha256()
    for path in _INPUTS:
        h.update(path.read_bytes() if path.exists() else b"")
    return h.hexdigest()[:16]


def _report() -> dict[str, object]:
    if REPORT.exists():
        cached = json.loads(REPORT.read_text(encoding="utf-8"))
        if cached.get("inputs_stamp") == _inputs_stamp():
            return dict(cached)
        REPORT.unlink()
    if not PWENV.exists():
        pytest.skip(f"本机没有 {PWENV}（playwright 恒在项目外）")
    PROBE.mkdir(parents=True, exist_ok=True)
    done = subprocess.run(
        [str(PWENV), str(PROBE_TOOL)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=REPO, check=False)
    if done.returncode != 0 or not REPORT.exists():
        pytest.skip(f"真栈没起或探针跑不动：{(done.stderr or done.stdout)[-600:]}")
    got = json.loads(REPORT.read_text(encoding="utf-8"))
    got["inputs_stamp"] = _inputs_stamp()
    REPORT.write_text(json.dumps(got, ensure_ascii=False, indent=1), encoding="utf-8")
    return dict(got)


# ═════════════════ 蓝本那张表（逐字解析出来，NEVER 在这里抄一遍）


def _blueprint_tables() -> dict[str, list[tuple[str, int, str, str]]]:
    """从蓝本 HTML 里把 `const TPLS` 那张表解析出来。

    **判准取自蓝本原文**——在这里手抄一份的话，判的是我抄得对不对。
    """
    src = BLUEPRINT.read_text(encoding="utf-8")
    block = src[src.index("const TPLS = {"):]
    block = block[:block.index("\n};") + 3]
    out: dict[str, list[tuple[str, int, str, str]]] = {}
    for match in re.finditer(
        r"(\w+): \{ zh: '[^']+', en: '[^']+', secs: \[(.*?)\] \}", block, re.DOTALL
    ):
        rows = re.findall(
            r"\['([a-z_]+)', '([^']+)', '([^']+)', (\d+), '([^']+)', '([^']+)'\]",
            match.group(2))
        out[match.group(1)] = [
            (sid, int(share), words, check) for sid, _zh, _en, share, words, check in rows
        ]
    return out


def _yaml_tables() -> dict[str, list[tuple[str, int, str, str]]]:
    out: dict[str, list[tuple[str, int, str, str]]] = {}
    for template_id in FIVE:
        payload = yaml.safe_load(
            (TEMPLATES / f"{template_id}.yaml").read_text(encoding="utf-8"))
        out[template_id] = [
            (
                str(s["section_id"]),
                round(float(s["ratio"]["share"]) * 100),
                f"{int(s['ratio']['min_words'])}–{int(s['ratio']['max_words'])}",
                str(s["check_questions"][0]),
            )
            for s in payload["sections"]
        ]
    return out


def _diff(
    left: dict[str, list[tuple[str, int, str, str]]],
    right: dict[str, list[tuple[str, int, str, str]]],
) -> list[str]:
    """两张表的差异**逐条点名是哪一套的哪一章**。

    只回一个 `True/False` 的话，对不上时下一个人要自己去找是哪一行——
    而那正是这条判据本来该替他做的事。
    """
    problems: list[str] = []
    for template_id in sorted(set(left) | set(right)):
        a, b = left.get(template_id, []), right.get(template_id, [])
        if len(a) != len(b):
            problems.append(f"{template_id}: 章数 {len(a)} vs {len(b)}")
            continue
        for row_a, row_b in zip(a, b, strict=True):
            if row_a != row_b:
                problems.append(f"{template_id}/{row_a[0]}: {row_a} vs {row_b}")
    return problems


# ═════════════════ 一、三处**同一张表**：蓝本 == yaml == 前端那份


@pytest.mark.parametrize("template_id", FIVE)
def test_the_yaml_matches_the_blueprint_table(template_id: str) -> None:
    """**五套各断言一次**：yaml 与蓝本那张表逐字相同（id / 占比 / 字数区间 / 检查问句）。"""
    problems = _diff(
        {template_id: _yaml_tables()[template_id]},
        {template_id: _blueprint_tables()[template_id]},
    )

    assert problems == [], problems


def test_the_diff_names_which_template_and_which_section() -> None:
    """**阴性对照**：改掉一章 → 判据红，且**点名是哪一套的哪一章**。

    这条判的是上面那条判据本身有没有用：一个只会说「不一样」的比较器，
    对不上的那天没人知道该去改哪一行。
    """
    good = _yaml_tables()
    broken = {k: list(v) for k, v in good.items()}
    sid, share, words, _check = broken["thesis"][2]
    broken["thesis"][2] = (sid, share, words, "被改过的检查问句")

    problems = _diff(good, broken)

    assert len(problems) == 1, problems
    assert problems[0].startswith("thesis/method"), problems[0]


def test_the_frontend_table_is_generated_from_the_yaml_and_is_fresh() -> None:
    """前端那份是**生成**的，且是最新的（生成器 `--check` 退 0）。"""
    done = subprocess.run(
        [sys.executable, str(GENERATOR), "--check"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=REPO, check=False)

    assert done.returncode == 0, f"{done.stdout}{done.stderr}"
    head = GENERATED.read_text(encoding="utf-8")[:400]
    assert "NEVER 手改" in head, "生成物没写明它是生成的"


def test_nobody_hand_wrote_a_second_section_list_in_the_frontend() -> None:
    """章节导航自己**不含**任何章节 id 字面量——它读的是那份生成物。"""
    code = NAV.read_text(encoding="utf-8")
    stripped = re.sub(r"/\*.*?\*/|//[^\n]*", "", code, flags=re.DOTALL)

    assert "SECTION_TABLES" in code, "没读那份生成物"
    assert "wb.check." in code, "检查问句没走词典（它由同一个生成器从 yaml 写入）"
    for sid in ("summary", "opportunity", "one_liner", "significance", "related_work"):
        assert sid not in stripped, f"导航里手写了章节 id：{sid}"


# ═════════════════ 二、显示名照蓝本逐字（两份词典对称）


@pytest.mark.parametrize("template_id", FIVE)
def test_the_display_names_come_from_the_blueprint_verbatim(template_id: str) -> None:
    """中文名/英文名**逐字**照蓝本，且按模板分键。

    按模板分键不是多余：同一个 `timeline` 在基金申请里叫「时间表」、
    在论文开题里叫「时间线」（蓝本原文）。压成一个键的话，
    其中一套会显示另一套的名字，而屏上看不出来。
    """
    src = BLUEPRINT.read_text(encoding="utf-8")
    block = src[src.index("const TPLS = {"):]
    block = block[:block.index("\n};") + 3]
    match = re.search(
        rf"{template_id}: \{{ zh: '[^']+', en: '[^']+', secs: \[(.*?)\] \}}", block, re.DOTALL)
    assert match is not None
    rows = re.findall(
        r"\['([a-z_]+)', '([^']+)', '([^']+)', \d+, '[^']+', '[^']+'\]", match.group(1))
    zh = json.loads((MESSAGES / "zh.json").read_text(encoding="utf-8"))
    en = json.loads((MESSAGES / "en.json").read_text(encoding="utf-8"))

    for sid, zh_name, en_name in rows:
        key = f"wb.section.{template_id}.{sid}"
        assert zh.get(key) == zh_name, f"{key}: 词典里是 {zh.get(key)}，蓝本是 {zh_name}"
        assert en.get(key) == en_name, f"{key}: 词典里是 {en.get(key)}，蓝本是 {en_name}"


def test_the_two_names_of_timeline_did_not_collapse_into_one() -> None:
    """那条差点被压掉的：`grant/timeline` 与 `thesis/timeline` 显示名不同。"""
    zh = json.loads((MESSAGES / "zh.json").read_text(encoding="utf-8"))

    assert zh["wb.section.grant.timeline"] == "时间表"
    assert zh["wb.section.thesis.timeline"] == "时间线"


# ═════════════════ 三、屏上（真栈实测）


@pytest.mark.parametrize("template_id", FIVE)
def test_each_template_shows_exactly_its_own_sections(template_id: str) -> None:
    """**五套各断言一次**：切到这一套，屏上的章节数与章名与蓝本表逐字相同。"""
    shot = _report()["templates"][template_id]  # type: ignore[index,call-overload]
    wanted = _blueprint_tables()[template_id]

    assert list(shot["ids"]) == [row[0] for row in wanted], (
        f"{template_id} 屏上是 {shot['ids']}，蓝本是 {[r[0] for r in wanted]}")
    # 名字**按这一套自己的表取**。第一版拿整块 `TPLS` 扫成一个扁平字典，
    # 于是 `timeline` 的两个名字（基金申请「时间表」/ 论文开题「时间线」）
    # 被压成后写的那一个——屏上是对的，红的是判据自己。
    zh = json.loads((MESSAGES / "zh.json").read_text(encoding="utf-8"))
    assert list(shot["names"]) == [
        zh[f"wb.section.{template_id}.{row[0]}"] for row in wanted
    ], f"{template_id} 屏上的章名对不上：{shot['names']}"


def test_the_nav_is_sticky_and_as_wide_as_the_blueprint() -> None:
    """蓝本：`position:sticky; width:138px`。"""
    m = _report()["geometry"]

    assert m["position"] == "sticky", m["position"]
    assert abs(float(m["width"]) - 138) <= 1, f"导航宽 {m['width']}，蓝本 138"


def test_clicking_a_section_moves_the_document_to_it() -> None:
    """点章节**真的跳到那一章**（量的是滚动位置变了，且那一章到了视口里）。"""
    m = _report()["jump"]

    assert m["scrolled"], f"点了没动：{m}"
    assert m["targetInView"], f"跳完那一章不在视口里：{m}"


def test_a_section_the_document_does_not_have_says_so() -> None:
    """正文里没有的那些章**说得出「还没有」**，且它们的跳转键是禁用的。

    不说的话，用户点一个跳不动的章名，会以为界面坏了。
    """
    m = _report()["absent"]

    assert int(m["count"]) > 0, "这一份产物竟然每一章都齐了——换一份缺章的来验这条"
    assert m["everyAbsentSaysSo"], "有章缺着却什么都没说"
    assert m["everyAbsentJumpDisabled"], "缺着的章，跳转键还能点"


def test_the_check_verdict_comes_from_the_backend_or_says_it_has_none() -> None:
    """「是否满足」**只能从后端来**；拿不到就显示「还没有判定」，NEVER 显示「通过」。

    今天 `GET /deliverables/{id}/quality` 是 503（那一族没配后端），
    所以每一章都是「还没有判定」——判据两个方向各钉一次：
    屏上那句话是「还没有判定」，且**请求真的发出去过**。
    """
    m = _report()["verdicts"]

    assert m["asked"], "屏上说「还没有判定」，而根本没去问过后端"
    assert int(m["unknown"]) > 0
    assert int(m["pass"]) == 0, "后端没给判定，屏上却说通过了"
    assert m["unknownWording"], "「还没有判定」那句话没在屏上"


def test_every_section_shows_its_check_question_verbatim() -> None:
    """每一章旁边**照模板原文**写着它的检查问句（屏上 == yaml == 蓝本）。"""
    shot = _report()["templates"]["generic"]  # type: ignore[index,call-overload]
    wanted = [row[3] for row in _blueprint_tables()["generic"]]
    zh = json.loads((MESSAGES / "zh.json").read_text(encoding="utf-8"))

    assert list(shot["checks"]) == wanted, f"屏上 {shot['checks']}"
    # 词典里那一份也是同一句：生成器写的，判据在这里再核一次落点。
    assert [zh[f"wb.check.generic.{row[0]}"] for row in _yaml_tables()["generic"]] == wanted


@pytest.mark.parametrize("theme", ("light", "dark"))
def test_the_screenshot_is_on_disk(theme: str) -> None:
    require_probe_evidence(REPORT, "起栈后跑 tools/ui_probe_wb_sections.py")
    matches = list(PROBE.glob(f"workbench-sections-*-{theme}.png"))

    assert matches, f"缺这一张：{theme}"
    assert matches[0].stat().st_size > 10_000, (
        f"{matches[0].name} 只有 {matches[0].stat().st_size} 字节")
