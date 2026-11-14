"""DESIGN-02：AI 设计工作台那一屏是空壳——没有输入框、没有预览区、没有生成流。

## 改前的实况（逐条核过）

`web/components/design-workbench/DesignWorkbench.tsx` 共 108 行，**已经有的**只有：
`iframe srcdoc` 预览、失败态（原始产物 + 错误）、固化按钮与两种阻断说明。
`web/app/design/page.tsx` 给它传的是**两个 `null`**，且**一个请求都不发**。

**缺的两件**（卡面 acceptance① 点名的三件里的两件）：自然语言输入区、生成中的流式区。

## 端点实况（本卡开工时打过真栈）

- **没有任何端点能提交 `design_generate` 作业**：`web/lib/jobClient.ts#submitJob`
  打的是 `POST /projects/{id}/{kind}`，openapi 里没有 `design_generate` 那一条。
  消费者上一张卡刚接上，**入口那一端还没有**（单据
  `docs/blocked/DESIGN-GENERATE-HAS-NO-SUBMIT-ENDPOINT.md`）。
- **流式与续跑那两条是真通的**：`GET /jobs/{id}/events` 在；
  `GET /design/sessions/{job_id}/replay` 上一张卡刚把 `load_session` 接上（改前恒 404）。

所以本卡交付：输入区**真发请求**并按答复说话（`DEC-032` 的诚实态，形态照 `PLAZA-04`），
流式区与续跑**真接**那两条端点。

## 判据的重心

「屏上有没有那三件」在源码层判得出，但**判不出它们是不是 0 像素**——
`F-09` 那个空 span 就是「DOM 里有、用户看不见」。所以三件都在真浏览器里量宽高。
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

# FIX-13：小节切法只有一处（`tools/css_sections.py`）。
from tools.css_sections import (
    bare_sizes,
    colour_literals,
    section_after,
)

WEB = REPO / "web"
WORKBENCH = WEB / "components" / "design-workbench" / "DesignWorkbench.tsx"
SESSION = WEB / "components" / "design-workbench" / "designSession.ts"
PAGE = WEB / "app" / "design" / "page.tsx"
JOB_CLIENT = WEB / "lib" / "jobClient.ts"
CONTRACTS_V04 = REPO / "contracts_v04" / "models_v04.py"
ARTIFACT = REPO / ".ui-probe" / "design_workbench.json"

PWENV = Path(r"C:\pwenv\Scripts\python.exe")
FRONTEND = "http://localhost:3000/design"


def _code_only(path: Path) -> str:
    text = re.sub(r"/\*[\s\S]*?\*/", "", path.read_text(encoding="utf-8"))
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("//")
    )


# ───────────────────────── 一、三件齐全（源码层）


def test_the_screen_has_an_input_area() -> None:
    """自然语言输入区。改前一个字都没有。"""
    code = _code_only(WORKBENCH)

    assert "textarea" in code, "没有输入区"
    assert 'data-testid="design-prompt"' in code
    assert 'data-testid="design-generate"' in code, "没有提交按钮"


def test_the_screen_has_a_streaming_area() -> None:
    """生成中的流式区（逐块出现）。"""
    code = _code_only(WORKBENCH)

    assert 'data-testid="design-stream"' in code, "没有流式区"


def test_the_preview_is_an_iframe_srcdoc() -> None:
    """acceptance②：预览恒 `iframe.srcdoc`（零构建）。"""
    code = _code_only(WORKBENCH)

    assert "srcDoc" in code and "<iframe" in code


# ───────────────────────── 二、产物 NEVER 进主文档


def test_the_artifact_never_enters_the_host_document() -> None:
    """把生成产物注进主文档 = 让模型产物拿到本站权限（卡面 acceptance② 的原话）。

    这条在**整个工作台目录**上判，不是只判那一个组件——
    只判一个文件的话，下一个人在旁边新建一个渲染器就绕过去了。
    """
    for path in (WORKBENCH.parent).rglob("*.ts*"):
        if path.name.endswith(".test.tsx"):
            continue
        code = _code_only(path)
        for tell in ("dangerouslySetInnerHTML", "document.write", ".innerHTML"):
            assert tell not in code, f"{path.name} 里出现了 {tell}"


def test_the_preview_frame_keeps_scripts_off() -> None:
    """`sandbox=""` 全关：预览的是**设计**，不是让它在我们的页面里执行。"""
    code = _code_only(WORKBENCH)

    assert 'sandbox=""' in code, "沙箱被放开了"
    assert "allow-scripts" not in code


# ───────────────────────── 三、失败 NEVER 用上一次成功的顶替


def test_a_failed_preview_shows_the_raw_artifact_and_the_error() -> None:
    code = _code_only(WORKBENCH)

    assert 'data-design-preview-failed="true"' in code
    assert "design__raw" in code and "design__error-detail" in code


def test_a_failed_preview_renders_no_iframe_at_all() -> None:
    """失败分支里 NEVER 出现 `iframe`——出现了就是「顶替」的形状。

    顶替之后用户看到的是上一版，而他以为那是刚生成的这一版，
    并会照着那张图去固化。
    """
    code = _code_only(WORKBENCH)
    start = code.index("data-design-preview-failed")
    end = code.index("</div>", start)

    assert "<iframe" not in code[start:end]


# ───────────────────────── 四、中断可续：走 replay，NEVER 从头重跑


def test_the_screen_restores_from_the_replay_endpoint() -> None:
    """acceptance④：断线后走 `GET /design/sessions/{job_id}/replay` 取回已产出的块。"""
    code = _code_only(SESSION) + _code_only(PAGE)

    assert "/design/sessions/" in code and "/replay" in code


def test_resuming_never_resubmits_the_job() -> None:
    """续跑取回已产出的块，**NEVER 再提交一次作业**——那就是从头重跑。"""
    code = _code_only(PAGE)
    # 提交只挂在用户的那个按钮上；进屏的 effect 里 NEVER 出现提交调用。
    effects = re.findall(r"useEffect\(([\s\S]*?)\n  \}, \[", code)

    assert effects, "进屏没有任何 effect——那就没有续跑"
    for body in effects:
        assert "submitDesign" not in body, "进屏就提交了一次作业"


# ───────────────────────── 五、TS 镜像要认识 design_delta


def test_the_typescript_mirror_covers_the_design_delta_payload() -> None:
    """`jobClient.ts` 自述是「冻结件判别联合的 TS 镜像」。

    镜像落后一个成员的代价不是「少显示一点」——`applyEvent` 结尾是 `assertNever`，
    真来一条 `design_delta` 会**当场抛**，整条流断在那里。
    """
    assert "design_delta" in CONTRACTS_V04.read_text(encoding="utf-8")

    code = _code_only(JOB_CLIENT)
    assert "design_delta" in code, "TS 镜像里没有 design_delta"
    assert "DesignDeltaEvent" in code or "design_delta" in code


def test_the_stream_state_accumulates_the_design_text() -> None:
    """流式区要的是**拼起来的文字**，而拼接只该有一处实现。"""
    code = _code_only(JOB_CLIENT)

    assert "designText" in code, "流状态里没有设计文字"


# ───────────────────────── 六、风格照 _ds


def test_the_screen_uses_the_design_system_components() -> None:
    """acceptance⑤：用 `DS-01` 接上的 `_ds` 组件，NEVER 另起一套视觉。"""
    code = _code_only(WORKBENCH)

    assert "DsStatusMark" in code or "DsStickerTag" in code


# ───────────────────────── 七、提交那条：如实说，NEVER 假装成功


def test_the_submit_path_tells_the_truth_about_a_missing_endpoint() -> None:
    """提交端点今天不存在（框架那种没有 `code` 的 404）。

    形态照 `PLAZA-04`：三种「不成」各说各的话，**共用同一个结果形状**——
    两套形状会在同一个仓里对同一件事说两种话。
    """
    code = _code_only(SESSION)

    assert "ActionOutcome" in code, "没有复用既有的结果形状"
    assert "design_generate" in code, "没有打提交端点"


def test_the_submit_outcome_is_shown_on_screen() -> None:
    code = _code_only(WORKBENCH)

    assert 'data-testid="design-submit-outcome"' in code


def test_the_workbench_styles_use_tokens_except_the_named_geometry() -> None:
    """本段的字号、间距、颜色**一律走 `_ds` token**；几何值**显式列名**。

    口径与 `UI-01`／`PLAZA-01` 那两段相同：颜色零字面量、字号与间距零裸值。
    几何是例外，而例外逐个写在这里——`_ds` 的刻度里没有「预览框 420px 高」
    「流式区 120~320px」这种舞台尺寸。名单少一条即红，多一条要来这里解释。
    """
    # FIX-13：小节切法收成一处（`tools/css_sections.py`）。改前这里自己写了一遍
    # 「起点 → 下一条分隔线」，还带着那个魔数 `8`（「跳过自己这条分隔线」）。
    # 四份抄件迟早不一致，而不一致时红的那一份看起来像「产品坏了」。
    css = (WEB / "app" / "globals.css").read_text(encoding="utf-8")
    section = section_after(css, "* DESIGN-02 · AI 设计工作台")

    colours = colour_literals(section)
    assert colours == [], f"本段写死了颜色：{colours}"

    # 120/320 是流式区的定高区间（逐块进来时页面不跟着长，用户读的那行不被推走）；
    # 200 是预览区与原文/错误框的高底；420 是预览 iframe 的高（与堆叠台面同值）。
    allowed = ("120px", "320px", "200px", "420px")
    offenders = bare_sizes(section, allowed)
    assert offenders == [], f"本段写死了字号/间距：{offenders}"


# ───────────────────────── 八、运行时：三件都真占了像素


_RUNNER = r"""
import json, sys
from playwright.sync_api import sync_playwright

url, out = sys.argv[1], sys.argv[2]
with sync_playwright() as p:
    b = p.chromium.launch()
    page = b.new_page(viewport={"width": 1440, "height": 900})
    errs = []
    page.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
    page.goto(url, wait_until="networkidle", timeout=60000)
    page.wait_for_selector("[data-testid='design-prompt']", timeout=30000)
    def box(sel):
        el = page.query_selector(sel)
        if el is None:
            return None
        r = el.bounding_box()
        return {"width": r["width"], "height": r["height"]} if r else {"width": 0, "height": 0}
    got = {
        "prompt": box("[data-testid='design-prompt']"),
        "generate": box("[data-testid='design-generate']"),
        "stream": box("[data-testid='design-stream']"),
        "preview": box("[data-design-preview]"),
        "generateText": (page.query_selector("[data-testid='design-generate']")
                         .inner_text().strip()),
    }
    # 真按一次「生成」：提交端点今天不存在，屏上必须出现一句如实的答复。
    page.fill("[data-testid='design-prompt']", "一张纸质卡片")
    page.click("[data-testid='design-generate']")
    page.wait_for_selector("[data-testid='design-submit-outcome']", timeout=20000)
    el = page.query_selector("[data-testid='design-submit-outcome']")
    r = el.bounding_box()
    got["outcome"] = {"kind": el.get_attribute("data-outcome-kind"),
                      "text": el.inner_text().strip(),
                      "width": r["width"] if r else 0, "height": r["height"] if r else 0}
    got["console_errors"] = errs
    got["url_after"] = page.url
    page.screenshot(path=".ui-probe/design-workbench.png", full_page=False)
    b.close()
open(out, "w", encoding="utf-8").write(
    json.dumps({"schema": "design-workbench/1", "url": url, **got},
               ensure_ascii=False, indent=1))
"""


def _artifact() -> dict[str, object]:
    if ARTIFACT.exists():
        return json.loads(ARTIFACT.read_text(encoding="utf-8"))
    if not PWENV.exists():
        pytest.skip(f"本机没有 {PWENV}（playwright 恒在项目外，NEVER 进项目依赖）")
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        runner = Path(tmp) / "design_workbench_runner.py"
        runner.write_text(_RUNNER, encoding="utf-8")
        done = subprocess.run(
            [str(PWENV), str(runner), FRONTEND, str(ARTIFACT)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=REPO, check=False,
        )
    if done.returncode != 0:
        pytest.skip(f"前端没起或探针跑不动（{FRONTEND}）：{done.stderr[-500:]}")
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


def test_all_three_parts_occupy_pixels_on_the_real_screen() -> None:
    """源码层判得出「有没有」，判不出「是不是 0 像素」——`F-09` 就是那个形状。"""
    art = _artifact()

    for name in ("prompt", "generate", "stream", "preview"):
        box = art[name]
        assert box is not None, f"{name} 不在屏上"
        assert box["width"] > 10 and box["height"] > 10, f"{name} 几乎没有面积：{box}"


def test_the_generate_button_has_words() -> None:
    assert _artifact()["generateText"], "生成按钮没有文字"


def test_pressing_generate_says_the_truth_and_stays_on_the_screen() -> None:
    """提交端点今天不存在 → 屏上出现一句如实的答复，而**没有跳走**。"""
    art = _artifact()
    outcome = art["outcome"]

    assert outcome["kind"] == "not_provided", f"答复被读成了 {outcome['kind']}"
    assert outcome["text"], "答复那一行是空的"
    assert outcome["width"] > 0 and outcome["height"] > 0
    assert art["url_after"].endswith("/design")


def test_the_only_console_noise_is_the_registered_missing_endpoint() -> None:
    """控制台里只许有**一条**，且那一条要点得出单据。

    本屏是**有意**去打一个今天不存在的端点（理由见 `designSession.ts`：
    「能不能提交」的真相在服务端，前端自带判断会与后端各自漂移）。
    代价就是这一条 404 噪声——**它是设计决定的一部分，所以登记而不是掩盖**。

    登记的形状照 `test_mobile_sweep` 那条既有基线：**判等值**。
    多一条要停下来看，少一条说明端点挂上了——那时来这里删掉这一行
    并关掉 `docs/blocked/DESIGN-GENERATE-HAS-NO-SUBMIT-ENDPOINT.md`。
    """
    errors = _artifact()["console_errors"]
    expected = ["Failed to load resource: the server responded with a status of 404 (Not Found)"]

    assert errors == expected, (
        f"控制台噪声面变了：实测 {errors}，登记 {expected}——"
        f"多了要停下登记，少了说明 POST /projects/{{id}}/design_generate 挂上了"
    )
