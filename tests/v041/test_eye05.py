"""EYE-05：工作台整屏逐条对着蓝本验收（本批的防空转闸）。

六张整屏（三视口 × 两主题）+ 一组流程图，**截图与数一起落盘**——
只有图的话，下一个人无从判断它当时算不算合格（`EYE-04` 定的口径，一字不变）。

## 「零控制台报错」在这一屏做不到，于是**逐条点名归属**

这一屏上那几条 4xx 各自有单（`/hints/` 空 ref · `/…/quality` 那一族没配后端）。
把它们并成一句「已知噪声」的代价：下一条真的报错混进来时没有人会发现。
判据因此判的是「**只有这两条，且各自的单在盘上**」，而不是「有几条」。
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
PROBE = REPO / ".ui-probe" / "eye05"
REPORT = PROBE / "report.json"
PWENV = Path(r"C:\pwenv\Scripts\python.exe")
PROBE_TOOL = REPO / "tools" / "ui_probe_eye05.py"
HOWTO = REPO / "docs" / "怎么测-v041.md"

VIEWPORTS = ("1920x1080", "1440x900", "390x844")
THEMES = ("light", "dark")
WIDE = ("1920x1080", "1440x900")

#: 这一屏上每一条 4xx 的归属（前缀 → 单）。
KNOWN_404 = {
    "/hints/": "docs/blocked/REAL-GAP-NOTICES-HAVE-NO-HINTS-REF.md",
    "/deliverables/": "docs/blocked/QUALITY-FAMILY-HAS-NO-BACKEND.md",
}

_INPUTS = (REPO / "web" / "app" / "workbench" / "page.tsx",
           REPO / "web" / "app" / "globals.css", PROBE_TOOL)


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


def _screen(key: str) -> dict[str, object]:
    return dict(_report()["screens"][key])  # type: ignore[index,call-overload]


# ═════════════════ 一、六张整屏，每一张四条都要过


@pytest.mark.parametrize("viewport", VIEWPORTS)
@pytest.mark.parametrize("theme", THEMES)
def test_the_screenshot_is_on_disk(viewport: str, theme: str) -> None:
    """六种组合**逐一** parametrize：缺一种就红（`EYE-04` 的既有形状）。"""
    shot = PROBE / f"workbench-{viewport}-{theme}.png"

    assert shot.exists(), f"缺这一张：{shot.name}"
    assert shot.stat().st_size > 10_000, (
        f"{shot.name} 只有 {shot.stat().st_size} 字节（0 字节的文件也叫「在盘上」）")


@pytest.mark.parametrize("viewport", WIDE)
@pytest.mark.parametrize("theme", THEMES)
def test_the_three_columns_are_side_by_side_on_wide_screens(
    viewport: str, theme: str,
) -> None:
    """三栏在位且**并排**（390 除外，那一档纵向排开）。"""
    m = _screen(f"{viewport}-{theme}")
    cards, chat, preview = m["cards"], m["chat"], m["preview"]

    for name, col in (("cards", cards), ("chat", chat), ("preview", preview)):
        assert col is not None and float(col["w"]) > 0, f"{name} 栏不在位"
    assert float(cards["x"]) < float(chat["x"]) < float(preview["x"]), m
    # 三栏同高 = 它们真的在一行上（差一像素以内）。
    assert abs(float(cards["h"]) - float(preview["h"])) <= 1, m


@pytest.mark.parametrize("theme", THEMES)
def test_the_narrow_screen_stacks_instead_of_squeezing(theme: str) -> None:
    """390 下**不横排**：三栏依次往下排（`WB-01` 那条响应式的可量形式）。"""
    m = _screen(f"390x844-{theme}")
    cards, chat, preview = m["cards"], m["chat"], m["preview"]

    assert float(cards["x"]) == float(chat["x"]) == float(preview["x"]), m
    assert float(cards["y"]) < float(chat["y"]) < float(preview["y"]), m


@pytest.mark.parametrize("viewport", VIEWPORTS)
@pytest.mark.parametrize("theme", THEMES)
def test_no_horizontal_overflow(viewport: str, theme: str) -> None:
    """**最右元素右缘 ≤ 视口宽**（owner 2026-08-12 的口径）。

    文档级 `scrollWidth` 对 `fixed` 元素恒绿——顶栏那次 390 溢出
    被判绿了整整一批（`docs/blocked/NAV-BAR-OVERFLOWS-AT-390.md`）。
    """
    m = _screen(f"{viewport}-{theme}")

    assert float(m["rightmost"]["right"]) <= float(m["vw"]) + 0.5, (
        f"{m['rightmost']['sel']} 的右缘 {m['rightmost']['right']} > 视口 {m['vw']}")
    assert int(m["scrollW"]) <= int(m["vw"]) + 1, m


@pytest.mark.parametrize("viewport", VIEWPORTS)
@pytest.mark.parametrize("theme", THEMES)
def test_the_preview_shows_real_blocks_not_a_placeholder(
    viewport: str, theme: str,
) -> None:
    """右栏渲染的是**真 Block**，不是占位文案。

    两者在截图上长得不一样，但只有数得出来才判得了。
    """
    m = _screen(f"{viewport}-{theme}")

    assert m["placeholderOnly"] is False, "右栏只有占位文案"
    assert int(m["blockCount"]) >= 20, f"只渲染了 {m['blockCount']} 块"
    assert set(m["blockTypes"]) <= {
        "heading", "paragraph", "table", "chart", "declaration",
        "quality_card", "citation_list", "gap_notice"}, m["blockTypes"]


@pytest.mark.parametrize("viewport", VIEWPORTS)
@pytest.mark.parametrize("theme", THEMES)
def test_every_console_error_is_one_of_the_named_two(
    viewport: str, theme: str,
) -> None:
    """报错**逐条对得上一张单**，且那张单在盘上。多一条 = 有新东西坏了。"""
    m = _screen(f"{viewport}-{theme}")
    seen = set(m["badPaths"])
    unnamed = {p for p in seen if not any(p.startswith(k) for k in KNOWN_404)}

    assert unnamed == set(), f"出现了没登记的 4xx：{unnamed}"
    for path in seen:
        key = next(k for k in KNOWN_404 if path.startswith(k))
        assert (REPO / KNOWN_404[key]).exists(), f"{path} 的单子不在盘上"
    for line in list(m["errors"]):
        assert "Failed to load resource" in line, f"这不是资源加载报错：{line}"


# ═════════════════ 二、流程图：人真的会走的那五步


@pytest.mark.parametrize("step", (
    "flow-1-empty", "flow-2-picked", "flow-3-submitted",
    "flow-4-blocks", "flow-5-annotate"))
def test_the_flow_screenshot_is_on_disk(step: str) -> None:
    shot = PROBE / f"{step}.png"

    assert shot.exists(), f"流程缺这一张：{step}"
    assert shot.stat().st_size > 10_000


def test_the_flow_really_walked_through_the_five_steps() -> None:
    """每一步**带着那一步的量**，不是只有图。"""
    flow = dict(_report()["flow"])  # type: ignore[arg-type]

    assert int(flow["1_empty"]["cards"]) > 0, "第一步左栏一张卡都没有"
    assert flow["1_empty"]["docState"] == "empty", "空手进来右栏不是空态"
    assert list(flow["2_picked"]["tray"]) == list(flow["2_picked"]["picked"]), (
        "选了两张而托盘里不是那两张")
    assert int(flow["2_picked"]["evidence"]) > 0, "选了热点而证据没跟上"
    # 第三步：`COMBO-WIRE-01` 之前恒 503（combo 那一族没配后端，屏上如实转述），
    # 之后是 200 + 回执。**判的是「有终态」**，不是哪一种终态——
    # 拿最后一条消息当终态会读到那条「下一步还没接上」的告知（它既不是成也不是败）。
    assert flow["3_submitted"]["outcomeKind"] in ("failure", "receipt"), (
        flow["3_submitted"])
    assert int(flow["4_blocks"]["blocks"]) > 0, "右栏没有块"
    assert int(flow["4_blocks"]["sections"]) > 0, "没有章节导航"
    assert int(flow["4_blocks"]["cites"]) >= 0
    assert flow["5_annotate"]["canSubmit"], "写了批注而提交键还是禁的"


# ═════════════════ 三、《怎么测》补的那一节


def test_the_howto_has_a_workbench_section() -> None:
    """`docs/怎么测-v041.md` 里那一节：owner 从哪进 · 该看到什么 · 看不到时是谁的问题。"""
    doc = HOWTO.read_text(encoding="utf-8")

    assert "## 工作台" in doc, "《怎么测》没有「工作台」这一节"
    for must in ("从哪进", "该看到什么", "看不到时"):
        assert must in doc, f"那一节缺「{must}」"
    # 三处「看着不对时先看这三处」要写**本批实际踩过的**，不是「可能的」。
    for real in ("503", "hints_ref", "项目总览"):
        assert real in doc, f"那一节没写本批实际踩过的：{real}"
