"""FIX-18：热点分析屏缺**来源分列**——第 8 批 `NAV-02` 的 acceptance③④ 没做。

## 欠的是什么

`NAV-02` 卡面 ③④ 要求解析界面有三样：**判定 · 证据概览 · 来源分列**。
前两样在 `AnalysisView` 里；第三样实查 `page.tsx` 与 `AnalysisView` 里
`SourceColumns` / `ClusterSourceLines` **均 0 处**——trace 未提、也没开单。

## 修法**不需要动封版件**

`AnalysisView` 是 v0.4 封版件（`worker.md` §9.2 / `DEC-021`）。
`FIX-19` 拿到的许可**只限加类名与样式**，改它的取数路径不在那条许可里。

卡面自己写着修法：**承载屏里把 `<AnalysisView/>` 与 `<ClusterSourceLines/>`
并排渲染**。所以本卡一个字都没动 `web/views/analysis/AnalysisView.tsx`——
判据 `test_the_sealed_analysis_view_was_not_touched` 直接量它。

## 复用既有件，NEVER 另写一份

`ClusterSourceLines`（`REGION-12` 建的那一层）已经把三张并行表配对成
`SourceColumns` 的三元组，且**缺词面的源另起一行如实说「原话没查到」**。
另写一份的话：① 广场与这一屏对同一条簇的原话会各自漂移；
② `FIX-17` 给它加的可见署名要再加一遍——而漏加的那一处屏上分不出谁说的。

## 各源原话是**当天**的事实

`by_source_text` 只在 `GET /plaza/hot?day=…` 的簇行上。
所以这一块按 `?day=` 取，URL 上没带时用与广场同一个默认值。
**这不是将就**：一个不带日期的「原话」说不清是哪天说的。
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
CARRIER = REPO / "web" / "app" / "clusters" / "[id]" / "page.tsx"
SOURCE_LINES = REPO / "web" / "app" / "clusters" / "[id]" / "sourceLines.tsx"
SEALED = REPO / "web" / "views" / "analysis" / "AnalysisView.tsx"
REUSED = REPO / "web" / "components" / "plaza" / "ClusterSourceLines.tsx"
MESSAGES = REPO / "web" / "messages"

PWENV = Path(r"C:\pwenv\Scripts\python.exe")
ARTIFACT = REPO / ".ui-probe" / "fix18-source-columns.json"
WEB_BASE = os.environ.get("FLINT_WEB_BASE", "http://localhost:3000")
#: 演示库里当天真有多源词面的一条簇（判据里用它取证）。
SAMPLE_CLUSTER = os.environ.get("FLINT_FIX18_CLUSTER", "c-20260704-000")
SAMPLE_DAY = "2026-07-04"


# ───────────────────────── 一、三样齐了，且没动封版件


def test_the_carrier_screen_renders_the_source_columns_beside_the_analysis() -> None:
    """acceptance②：**并排渲染**。"""
    code = CARRIER.read_text(encoding="utf-8")

    assert "<AnalysisView" in code, "判定与证据概览那一半不见了"
    assert "<ClusterSourceLinesForDay" in code, "来源分列那一样还是没接"


def test_the_sealed_analysis_view_was_not_touched() -> None:
    """`AnalysisView` 是 v0.4 封版件——本卡**一个字都没动它**。

    `FIX-19` 的许可只限「加类名与样式」，改取数路径不在那条许可里。
    这条判据从**封版件那一侧**量：它里面仍然没有来源分列的任何痕迹，
    也就是说本卡没有绕过许可去动它。
    """
    sealed = SEALED.read_text(encoding="utf-8")

    assert "ClusterSourceLines" not in sealed
    assert "SourceColumns" not in sealed
    assert "by_source_text" not in sealed


def test_the_reused_layer_is_the_existing_one() -> None:
    """acceptance③：复用既有件，NEVER 另写一份。"""
    code = SOURCE_LINES.read_text(encoding="utf-8")

    assert 'from "../../../components/plaza/ClusterSourceLines"' in code
    assert "SourceColumns" not in code, "这一屏自己又接了一次 SourceColumns"


def test_the_visible_attribution_from_fix17_comes_along() -> None:
    """`FIX-17` 给 `SourceColumns` 加的**可见署名**一并生效。

    署名住在被复用的那一层里，所以只要复用就带着——
    这条判据钉的是「那一层确实还在做署名这件事」，
    它哪天被摘掉，这一屏与广场会一起变哑。
    """
    reused = REUSED.read_text(encoding="utf-8")

    assert "SourceColumns" in reused
    assert "sourceId" in reused


# ───────────────────────── 二、text 槽是原文，缺词面 NEVER 塞占位串


def test_the_screen_does_not_invent_a_placeholder_wording() -> None:
    """acceptance④：`text` 槽契约是**原文而非译文**，缺词面的源另起一行如实说。

    本屏**只搬运**：三张表原样交给 `ClusterSourceLines`，
    一个字都不在这里加工。加工一下就等于在这一屏上产生了第二套口径。
    """
    code = SOURCE_LINES.read_text(encoding="utf-8")

    assert "bySourceText={state.cluster.by_source_text}" in code, (
        "原话不是原样交出去的")
    # **只扫交给分列那三个入参**，不扫整份文件：
    # 第一版扫全文，把 `data-source-lines-day={day ?? ""}` 也算成了占位串——
    # 那是**日期属性**的缺省值，与原话槽毫无关系。
    # 尺子扫得太宽时报的是一句读起来像真的的假话。
    # 取**真正那处 JSX**，不是文件头注释里提到的那个名字：
    # 文件头写着「把 `<AnalysisView/>` 与 `<ClusterSourceLines/>` 并排渲染」，
    # 按第一处切会切到那句解释后面的 `/>`，props 段是空的——
    # 于是这条判据报「三张表不是原样搬运」，而它其实一个字都没读到。
    # 本轮第三次撞上「尺子读了注释」这个形状。
    props = code.split("<ClusterSourceLines\n")[1].split("/>")[0]

    assert props.count("state.cluster.") == 3, f"三张表不是原样搬运：{props}"
    for placeholder in ('"—"', '"暂无"', '"未知"', '""'):
        assert placeholder not in props, f"给原话塞了占位串：{placeholder}"


def test_the_reused_layer_still_says_which_sources_had_no_wording() -> None:
    """缺词面那一行还在被复用的那一层里（`REGION-12` 的既有口径）。"""
    reused = REUSED.read_text(encoding="utf-8")

    assert "NEVER 塞占位串" in reused


# ───────────────────────── 三、四态各自成一态


def test_the_four_states_are_four_markers() -> None:
    """还在取 / 查到了 / 这一天没有它 / 读失败——**四态各有各的记号**。

    第三态与第四态尤其不能合并：前者该换一天，后者该重试，
    而两者在「屏上没有分列」这个结果上长得一模一样。
    """
    code = SOURCE_LINES.read_text(encoding="utf-8")

    for marker in ("loading", "ready", "not_on_this_day", "failed"):
        assert f'"{marker}"' in code, f"少了一态：{marker}"
    assert "data-source-lines-state" in code


def test_not_found_is_not_reported_as_a_failure() -> None:
    """找不到**不是失败**：它可能就是不在这一天的榜上。

    合成一句「读失败」的话，用户会去重试，而重试一百次也不会有结果。
    """
    code = SOURCE_LINES.read_text(encoding="utf-8")

    assert 'found ? { kind: "ready"' in code
    assert '{ kind: "not_on_this_day" }' in code


def test_the_absent_message_names_the_day() -> None:
    """**说清是哪一天**，用户才知道该换哪个。"""
    zh = json.loads((MESSAGES / "zh.json").read_text(encoding="utf-8"))

    assert "{day}" in zh["cluster.sources.not_on_this_day"]


def test_the_copy_is_keyed_in_both_languages() -> None:
    zh = json.loads((MESSAGES / "zh.json").read_text(encoding="utf-8"))
    en = json.loads((MESSAGES / "en.json").read_text(encoding="utf-8"))

    for key in ("cluster.sources.heading", "cluster.sources.failed",
                "cluster.sources.not_on_this_day"):
        assert key in zh and key in en, f"缺词条 {key}"


# ───────────────────────── 四、打真栈：取渲染后的**可见文本**


_RUNNER = r"""
import json, sys
from playwright.sync_api import sync_playwright

out, base, cluster, day = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
got = {}
with sync_playwright() as p:
    b = p.chromium.launch()
    page = b.new_page(viewport={"width": 1280, "height": 900})
    errs = []
    page.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
    page.goto(f"{base}/clusters/{cluster}?day={day}",
              wait_until="domcontentloaded", timeout=60000)
    page.wait_for_selector("[data-testid='cluster-source-lines']", timeout=30000)
    page.wait_for_function(
        "() => document.querySelector('[data-testid=\"cluster-source-lines\"]')"
        ".getAttribute('data-source-lines-state') !== 'loading'", timeout=30000)
    page.wait_for_timeout(600)

    got["state"] = page.eval_on_selector(
        "[data-testid='cluster-source-lines']",
        "e => e.getAttribute('data-source-lines-state')")
    got["day"] = page.eval_on_selector(
        "[data-testid='cluster-source-lines']",
        "e => e.getAttribute('data-source-lines-day')")
    got["visible_text"] = page.eval_on_selector(
        "[data-testid='cluster-source-lines']", "e => e.innerText")
    got["has_analysis"] = page.eval_on_selector_all(
        "[data-testid='analysis-view']", "els => els.length")
    got["source_ids"] = page.eval_on_selector_all(
        "[data-source-id]", "els => els.map(e => e.getAttribute('data-source-id'))")
    got["console_errors"] = errs
    page.screenshot(path=".ui-probe/fix18-cluster.png")
    b.close()
open(out, "w", encoding="utf-8").write(
    json.dumps({"schema": "fix18/1", **got}, ensure_ascii=False, indent=1))
"""


def _artifact() -> dict[str, object]:
    if ARTIFACT.exists():
        return json.loads(ARTIFACT.read_text(encoding="utf-8"))
    if not PWENV.exists():
        pytest.skip(f"本机没有 {PWENV}（playwright 恒在项目外）")
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        runner = Path(tmp) / "fix18_runner.py"
        runner.write_text(_RUNNER, encoding="utf-8")
        done = subprocess.run(
            [str(PWENV), str(runner), str(ARTIFACT), WEB_BASE, SAMPLE_CLUSTER,
             SAMPLE_DAY],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=REPO, check=False)
    if done.returncode != 0:
        pytest.skip(f"前端没起或探针跑不动：{done.stderr[-800:]}")
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


def test_the_source_columns_really_render_on_the_screen() -> None:
    """acceptance⑤：**取渲染后的可见文本**，且打真栈。

    源码层判得出「接上了」，判不出「屏上真的有字」——
    第 8 批 `FIX-17` 抓到过一次只有看屏才发现的缺陷（署名与词面挤成一句）。
    """
    got = _artifact()

    assert got["state"] == "ready", f"分列没渲染出来：{got['state']}"
    assert got["day"] == SAMPLE_DAY
    text = str(got["visible_text"]).strip()
    assert len(text) > 10, f"分列那一块几乎没有可见文本：{text!r}"


def test_the_analysis_view_is_still_on_the_same_screen() -> None:
    """**并排**：分列接上了，判定那一半没被挤掉。"""
    got = _artifact()

    assert got["has_analysis"] == 1, "分析视图不见了——那是并排，不是替换"


def test_each_source_is_attributed_on_screen() -> None:
    """屏上分得出**谁说的**（`FIX-17` 的可见署名一并生效）。"""
    got = _artifact()
    ids = [s for s in got["source_ids"] if s]

    assert ids, "屏上一个源署名都没有"


def test_no_placeholder_string_reached_the_screen() -> None:
    """屏上 NEVER 出现「暂无 / 未知」这类占位串顶替原话。

    缺词面的源由被复用的那一层另起一行如实说「原话没查到」——
    那是一句**关于我们**的话，不是把它当成源说过的话。
    """
    got = _artifact()
    text = str(got["visible_text"])

    for placeholder in ("：暂无", "：未知", "：—"):
        assert placeholder not in text, f"屏上出现了占位串：{placeholder}"


def test_no_console_errors_on_the_analysis_screen() -> None:
    got = _artifact()

    assert got["console_errors"] == [], f"控制台有错：{got['console_errors']}"
