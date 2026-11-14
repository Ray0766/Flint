"""FB-02：争议记号对**视力用户**可见（终检 F-09）。

## F-09 原话

`BlockView.tsx` 的争议记号从 `⚠` 改成了 `<span data-testid="disputed-mark" className="mark mark--disputed" />`，
无障碍那一半做对了（`role="img"` + `aria-label` 取到真文案），**视觉那一半归零**：
`.mark--disputed` 全仓零 CSS，`web/` 下一个样式表都没有，`_ds` 根本没被应用加载 ——
那个 span 没有文字内容、没有任何样式，**占 0 像素**。
改之前用户看得见一个 `⚠`，改之后**什么都看不见**，而测试全绿
（`querySelector(...) !== null` 对一个不可见的空 span 照样通过）。

FB-01 把样式管线接通了；本卡给这个记号一份真样式，并用 EYE-02 的判据守住它。

## 记号形态照 `_ds` 的既有约定，NEVER 自己发明

`_ds/readme.md` 原话：「不用图标字体、不用 emoji、不引 CDN 图标库；识别物是『印记』：
小尺寸单色几何记号（实心方 = 事实、空心方 = 价格、括线 = 涉我、三角 = 阻塞、**斜纹方 = 争议**）」。
斜纹用 `_ds` 现成的 `--tex-hatch`（`tokens/texture.css` 里写着「划线底纹（争议）」），
**不新造任何颜色或图案**。

## 判据分三层

1. **样式面**（离线，恒跑）：规则存在、用的是 `_ds` 的 token、尺寸非零、无 emoji；
2. **像素面**（有产物则必验）：`.ui-probe/disputed_mark.json` 由真浏览器量出，
   用 EYE-02 的三条判据判（存在 + 渲染尺寸非零 + 对比度过线，明暗两主题）；
3. **阴性对照**（同一份产物里）：**把样式规则抽掉**的那次测量必须红——
   否则第 2 层证明不了是这份 CSS 让它可见的。

产物由本文件的 `__main__` 生成（用 `C:\\pwenv` 的解释器跑，命令见 docs/trace/FB-02.md），
所以它可复现，不是一次性手工结果。
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
GLOBALS = REPO / "web" / "app" / "globals.css"
DS_ROOT = REPO / "web" / "public" / "_ds"
ARTIFACT = REPO / ".ui-probe" / "disputed_mark.json"
MARK_SELECTOR = ".mark--disputed"

# emoji 与图标字体的形态。`_ds` readme 明确禁掉它们（各平台字形不同、颜色不受 token 控制、
# 读屏会把 ⚠ 读成「警告标志」而不是这套系统里的「争议」语义）。
BANNED_GLYPHS = ("⚠", "❗", "❕", "🔺", "🚩", "content: \"\\f", "FontAwesome", "Material Icons")


def _rule(css: str, selector: str) -> str:
    """取某条规则的声明块。找不到返回空串。"""
    match = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", css)
    return match.group(1) if match else ""


# ───────────────────────── ① 样式面（恒跑）


def test_the_disputed_mark_has_a_real_rule() -> None:
    """`.mark--disputed` 有真规则——改前它全仓零 CSS，那个 span 占 0 像素。"""
    body = _rule(GLOBALS.read_text(encoding="utf-8"), MARK_SELECTOR)

    assert body, f"{MARK_SELECTOR} 在 globals.css 里没有规则"
    assert re.search(r"\bwidth\s*:", body) and re.search(r"\bheight\s*:", body), (
        "记号没有显式宽高：它是空元素，行内默认就是 0×0"
    )
    assert "inline-block" in body, "行内元素设宽高不生效——必须是 inline-block 之类"


def test_the_mark_reuses_the_ds_hatch_token() -> None:
    """斜纹来自 `_ds` 的 `--tex-hatch`，NEVER 自己写一条 repeating-linear-gradient。

    自己写一条就等于在应用层复制了一份「争议长什么样」的真相；
    `_ds` 哪天改了斜纹角度或浓度，这里不会跟着变，两处从此各说各的。
    """
    body = _rule(GLOBALS.read_text(encoding="utf-8"), MARK_SELECTOR)

    assert "--tex-hatch" in body, "没有用 _ds 的争议斜纹 token"
    assert "repeating-linear-gradient" not in body, "应用层自己写了斜纹，绕过了 _ds"

    texture = (_bundle_dir() / "tokens" / "texture.css").read_text(encoding="utf-8")
    assert "--tex-hatch" in texture, "_ds 里没有这个 token（名字写错了？）"
    assert "争议" in texture, "_ds 的 --tex-hatch 不再是「争议」语义，本卡口径要跟着改"


def _bundle_dir() -> Path:
    dirs = [p for p in DS_ROOT.iterdir() if p.is_dir()]
    assert len(dirs) == 1
    return dirs[0]


def test_no_emoji_or_icon_font_sneaks_back_in() -> None:
    """acceptance②：NEVER 用 emoji 当图标（这正是 C4 那次改动要消灭的东西）。

    只扫**代码层**：注释里逐字写着「改之前用户看得见一个 ⚠」（说明这条规则替掉的是什么），
    扫原文会把「解释它」当成「用了它」。判据落在代码上，不落在解释代码的话上——
    本批第三次撞上同一类问题（GAUGE-06 的 hasattr 引文、FB-01 的 @import 引文）。
    """
    css = re.sub(r"/\*.*?\*/", "", GLOBALS.read_text(encoding="utf-8"), flags=re.DOTALL)

    for glyph in BANNED_GLYPHS:
        assert glyph not in css, f"globals.css 里出现了 {glyph!r}"


def test_the_confidence_viz_lint_still_passes() -> None:
    """`lint_no_confidence_viz.mjs` 保持 exit 0（acceptance② 点名）。

    node 缺席时红不跳过——一把会自己消失的尺子等于没有尺子（与 EYE-01 同一条口径）。
    """
    node = shutil.which("node")
    assert node is not None, "找不到 node：这条门量不了，NEVER 当它通过"

    done = subprocess.run([node, "tools/lint_no_confidence_viz.mjs", "web"],
                          cwd=REPO, capture_output=True, text=True,
                          encoding="utf-8", check=False)

    assert done.returncode == 0, done.stdout + done.stderr


# ───────────────────────── ②③ 像素面 + 阴性对照


def _report() -> dict:
    # 惰性 import：`C:\pwenv` 的解释器没有 pytest，而本文件的 `__main__` 取证入口要在那里跑。
    import pytest

    if not ARTIFACT.exists():
        pytest.skip("本机没跑过像素取证：缺 .ui-probe/disputed_mark.json"
                    "（跑法见本文件 __main__ 与 docs/trace/FB-02.md）")
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


def test_the_mark_is_visible_in_both_themes() -> None:
    """acceptance③：明暗两主题下「存在 + 尺寸非零 + 对比度过线」全过。"""
    styled = _report()["styled"]

    assert styled["ok"] is True, [v["detail"] for v in styled["verdicts"] if not v["ok"]]
    for theme in ("dark", "light"):
        obs = styled["observations"][theme]
        assert obs["present"] is True
        assert obs["width"] > 0 and obs["height"] > 0, f"[{theme}] 记号 0 像素"


def test_stripping_the_rule_makes_the_assertion_red() -> None:
    """阴性对照：把样式规则抽掉，上一条必须红——否则它证明不了是这份 CSS 让记号可见。

    与 GAUGE-03 那条「抽掉机制后必红」是同一个道理：**没验过强度的可见性断言，
    和 `querySelector(...) !== null` 是同一种东西**。
    """
    unstyled = _report()["unstyled"]

    assert unstyled["ok"] is False, "抽掉样式之后判据仍然是绿的"
    failed = [v for v in unstyled["verdicts"] if not v["ok"]]
    assert any(v["criterion"] == "rendered-size" for v in failed), (
        f"红的原因不是尺寸，这个对照说明不了问题：{[v['detail'] for v in failed]}"
    )


def test_the_two_runs_differ_only_by_the_rule() -> None:
    """两次测量的唯一变量就是那条规则——否则对照不成立。"""
    report = _report()

    assert report["schema"] == "disputed-mark/1"
    assert report["selector"] == MARK_SELECTOR
    assert report["styled"]["fragment_sha"] != report["unstyled"]["fragment_sha"]
    assert report["rule_under_test"] in report["styled"]["fragment"]
    assert report["rule_under_test"] not in report["unstyled"]["fragment"]


# ───────────────────────── 产物生成（用 C:\pwenv 的解释器跑本文件）

if __name__ == "__main__":  # pragma: no cover - 取证入口，pytest 不走这里
    import hashlib
    import sys

    sys.path.insert(0, str(REPO))
    from tools.visual_assert import check_fragment

    bundle = _bundle_dir().name
    css = GLOBALS.read_text(encoding="utf-8")
    rule_body = _rule(css, MARK_SELECTOR)
    rule = f"{MARK_SELECTOR} {{{rule_body}}}"

    # 片段用真 CSS：`_ds` 经 dev server 取（栈要在跑），应用层规则从 globals.css 原样读出。
    # NEVER 手抄一份样式进来——手抄的那份和线上跑的那份迟早不是同一个。
    base = (f'<link rel="stylesheet" href="http://localhost:3000/_ds/{bundle}/styles.css">'
            '<div style="background:var(--bg-page);padding:20px">'
            '<span class="mark mark--disputed" role="img" aria-label="争议"></span>'
            "</div>")
    styled_html = f"<style>{rule}</style>{base}"

    out = {"schema": "disputed-mark/1", "selector": MARK_SELECTOR, "rule_under_test": rule}
    for key, html in (("styled", styled_html), ("unstyled", base)):
        report = check_fragment(html, MARK_SELECTOR)
        report["fragment"] = html
        report["fragment_sha"] = hashlib.sha256(html.encode()).hexdigest()[:16]
        out[key] = report

    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"styled.ok={out['styled']['ok']}  unstyled.ok={out['unstyled']['ok']}")
    print(f"→ {ARTIFACT}")
