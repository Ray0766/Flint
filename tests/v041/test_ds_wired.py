"""FB-01：设计系统接进应用——F-09 的根因。

## 根因

`web/app/layout.tsx` **零 CSS import**，`_ds` 那 7 个 CSS 文件躺在 `web/public/_ds/` 里
当静态资源，**从未被应用加载过**。于是 `.mark--disputed` 那个争议记号是个没有任何样式的
空行内元素，占 0 像素（终检 F-09）。EYE-03 把这件事量成了字节级证据：三屏的 dark 与 light
截图**逐字节相同**——主题开关什么都没改，因为根本没有样式可改。

## 口径收窄：`_ds` **只有一套明色**（acceptance② 的一半做不到）

卡面 acceptance② 要求「明暗两主题下取到的值**不同**」。回源核过，那个前提不成立：

- `_ds` 全目录 grep `prefers-color-scheme` / `data-theme` / `.dark` → **零命中**；
- `web/` 下（除 node_modules）同样零命中；
- `tokens/colors.css` 是一套「纸与墨」明色（`--paper:#EDEEE6` / `--ink:#1B2A2E`），没有暗色对照；
- 卡面点名的 `--background` 在 `_ds` 里**不存在**（那是 shadcn 的命名，`_ds` 用 `--paper`/`--surface`/`--ink`）。

造一套暗色调色板是**设计决定**，且要动供应商资产（终检 C6 把 `_ds` 按供应商资产对待），
NEVER 由一张接线卡自决。所以本卡做的是可做的那一半、并把做不到的那一半登记成问题单：

- **做**：token 在运行时真的生效（取计算值，与 `_ds` 里声明的逐条比对）；
- **不做**：明暗两套值不同 → `docs/blocked/DS-NO-DARK-PALETTE.md`。

## 为什么不只断言 import 语句

卡面原话「NEVER 只断言 import 语句存在」。一条 `import "./globals.css"` 可以存在而样式仍然
到不了页面（路径写错、被 Next 的 CSS 管线丢掉、`_ds` 的 `@import` 解析失败——三种都发生过）。
所以这里的判据是**浏览器里的计算值**：`.ui-probe/ds_tokens.json` 是真跑 `scripts/ui_probe.py
--tokens --json` 落下的，测试拿它与 `_ds/tokens/colors.css` 的声明逐条对。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
WEB = REPO / "web"
LAYOUT = WEB / "app" / "layout.tsx"
GLOBALS = WEB / "app" / "globals.css"
DS_ROOT = WEB / "public" / "_ds"
TOKENS_ARTIFACT = REPO / ".ui-probe" / "ds_tokens.json"

# 运行时必须取到真值的 token：既在 _ds/tokens/colors.css 里声明，**也在探针的观测面里**。
# 首版把 `--paper` 也列了进来，实测拿到空串——不是样式没生效，是 `scripts/ui_probe.py`
# 的 WATCH_TOKENS 根本没查它。那种红说的是「探针没量」，会被读成「样式坏了」，
# 所以下面单独有一条断言钉住「本清单必须是探针观测面的子集」。
LIVE_TOKENS = ("--surface", "--ink", "--ink-2", "--ink-3", "--rule")


def _bundle_dir() -> Path:
    dirs = [p for p in DS_ROOT.iterdir() if p.is_dir()]
    assert len(dirs) == 1, f"_ds 下应当只有一个包目录，实际 {[d.name for d in dirs]}"
    return dirs[0]


def _declared_colors() -> dict[str, str]:
    """从 `_ds/tokens/colors.css` 解析 `--name:value`。声明是真相，NEVER 手抄一份。"""
    text = (_bundle_dir() / "tokens" / "colors.css").read_text(encoding="utf-8")
    return {m.group(1): m.group(2).strip()
            for m in re.finditer(r"(--[\w-]+)\s*:\s*([^;]+);", text)}


# ───────────────────────── acceptance①：真的接上了


def test_the_layout_loads_the_design_system() -> None:
    """`layout.tsx` 加载 `_ds` 的样式——改前它零 CSS import，这正是 F-09 的根因。"""
    layout = LAYOUT.read_text(encoding="utf-8")

    assert "globals.css" in layout, "layout 没有加载任何应用样式表"
    assert GLOBALS.exists(), "globals.css 不在"
    assert "_ds" in layout, "layout 没有把 _ds 接进来"


def _code_only(text: str) -> str:
    """剥掉块注释再扫。

    首版直接扫原文，被自己的注释咬了一口：`globals.css` 的注释里逐字写着那条
    `@import url("/_ds/…/styles.css")`（说明为什么不能那样写），带省略号，
    于是断言报「引用了不存在的样式表」。**判据要落在代码层，不是落在解释代码的话上**
    ——否则它只会逼后人把病史从注释里抹掉（与 GAUGE-06 撞上的是同一类问题）。
    """
    return re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)


def test_the_stylesheet_path_points_at_a_file_that_exists() -> None:
    """接线里写的路径必须真解析得到文件——写错的路径静默 404，页面照样渲染（无样式）。"""
    wired = _code_only(LAYOUT.read_text(encoding="utf-8"))
    wired += _code_only(GLOBALS.read_text(encoding="utf-8"))
    refs = re.findall(r"/_ds/([^\"')\s]+\.css)", wired)

    assert refs, "接线里没有指向 _ds 的样式表引用"
    for ref in refs:
        assert (DS_ROOT / ref).exists(), f"引用了不存在的样式表：/_ds/{ref}"


def test_the_bundle_barrel_pulls_every_token_file() -> None:
    """`styles.css` 是 6 个文件的桶——接了它就等于接了全部 token，不必逐个列。"""
    barrel = (_bundle_dir() / "styles.css").read_text(encoding="utf-8")
    imported = set(re.findall(r'@import url\("([^"]+)"\)', barrel))

    assert {"tokens/colors.css", "tokens/typography.css", "tokens/spacing.css",
            "tokens/texture.css", "tokens/base.css"} <= imported


# ───────────────────────── acceptance②（可做的那一半）：运行时真的生效


def _declared_by_theme() -> dict[str, dict[str, str]]:
    """明暗**各自**的声明。

    改前这里只有一份：`_declared_colors()` 拿一条正则扫全文件，
    后面的块覆盖前面的，最终留下的是最后那个 `[data-theme="light"]` 块——
    也就是**明色那一套**。于是暗色页的运行时取值也拿去和明色声明比。

    那条判据此前一直是绿的，而绿的理由是**产物本身是假的**：
    `PAL-03` 保下来的换板前那份 `ds_tokens.json` 里，
    dark 页记的是 `--surface #F7F8F3 / --ink #1B2A2E`——与 light 页一位不差。
    暗色主题那时根本没在那次取证里生效（`EYE-02` 那个洞的同一种形状），
    而「拿明色声明去比明色数值」当然过得了。

    改成明暗各比各的：`:root` 一套，`[data-theme="dark"]` 覆盖上去一套。
    意图一个字没动——仍是「浏览器里取到的计算值 == `_ds` 里声明的值」。
    """
    text = (_bundle_dir() / "tokens" / "colors.css").read_text(encoding="utf-8")
    root = re.search(r"^:root\{(.*?)\n\}", text, re.DOTALL | re.MULTILINE)
    dark = re.search(r'\[data-theme="dark"\]\{(.*?)\n\}', text, re.DOTALL)
    assert root and dark, "colors.css 里少了 :root 或 [data-theme=dark] 块"

    def decls(block: str) -> dict[str, str]:
        return {m.group(1): m.group(2).strip()
                for m in re.finditer(r"(--[\w-]+)\s*:\s*([^;]+);", block)}

    light = decls(root.group(1))
    return {"light": light, "dark": {**light, **decls(dark.group(1))}}


def _judge_live_tokens(report: dict[str, object]) -> list[str]:
    """把一份取证判一遍，回**逐条**的红。判定与读盘分开，阴性对照才做得了。"""
    by_theme = _declared_by_theme()
    problems: list[str] = []
    for page in [p for p in report["pages"] if p["tokens"]]:  # type: ignore[index]
        declared = by_theme[page["theme"]]
        for name in LIVE_TOKENS:
            got = page["tokens"].get(name, "")
            if not got:
                problems.append(f"[{page['theme']}] {name} 在浏览器里取不到值——样式没生效")
                continue
            wanted = declared[name].split("/*")[0].strip()
            if got.upper() != wanted.upper():
                problems.append(
                    f"[{page['theme']}] {name} 运行时 {got}，_ds 声明 {wanted}")
    return problems


def test_the_tokens_are_live_in_the_browser_with_the_declared_values() -> None:
    """浏览器里取到的计算值 == `_ds` 里声明的值（**明暗各比各的**）。

    产物由真跑落下（`scripts/ui_probe.py --tokens --json`，见 docs/trace/FB-01.md）。
    没有产物就 skip 并说明是什么没做——但上面几条源码判据恒跑，所以这份验收不会退化成空壳。

    `PAL-03` 把「拿明色声明比所有页」改成「明暗各比各的」，理由见 `_declared_by_theme()`。
    """
    if not TOKENS_ARTIFACT.exists():
        pytest.skip("本机没跑过真栈 token 取值：缺 .ui-probe/ds_tokens.json"
                    "（起栈 start-demo.ps1，再跑 ui_probe --tokens --json）")

    report = json.loads(TOKENS_ARTIFACT.read_text(encoding="utf-8"))
    assert [p for p in report["pages"] if p["tokens"]], "产物里没有任何 token 取值"

    assert _judge_live_tokens(report) == []


def test_the_re_aimed_judge_would_have_caught_the_old_fake_green() -> None:
    """**阴性对照**：换板前那份取证（dark 页记着明色的数）现在会被判红。

    这条是上一条的价值证明：改前的判据对那份产物是绿的，
    因为它拿明色声明去比明色数值——两边都是明色，当然过。
    """
    before = (REPO / ".ui-probe" / "palette" / "before" / "ds_tokens.json")
    if not before.exists():
        pytest.skip("换板前那份取证没留（PAL-03 才开始留）")

    problems = _judge_live_tokens(json.loads(before.read_text(encoding="utf-8")))

    assert problems, "换板前那份产物应当被判红——它的 dark 页记的是明色的数"
    assert any("dark" in line for line in problems), problems[:2]


def test_every_watched_token_is_actually_watched_by_the_probe() -> None:
    """本清单必须是探针观测面的子集，否则上一条会把「没量」报成「没生效」。"""
    from scripts.ui_probe import WATCH_TOKENS

    missing = sorted(set(LIVE_TOKENS) - set(WATCH_TOKENS))
    assert missing == [], f"这些 token 探针根本不查，断言它们等于自造一条假红：{missing}"

    declared = _declared_colors()
    assert set(LIVE_TOKENS) <= set(declared), "清单里有 _ds 没声明的 token"


def test_the_dark_palette_gap_stays_registered_until_the_ds_grows_one() -> None:
    """`_ds` 只有一套明色 → 「明暗两套值不同」做不到，必须有人认领。

    条件写成「`_ds` 里没有暗色声明」，所以 `_ds` 哪天真加了暗色，本条自动放行——
    NEVER 留一份修好之后还赖着的问题单。
    """
    ds_text = "\n".join(
        p.read_text(encoding="utf-8") for p in _bundle_dir().rglob("*.css")
    )
    has_dark = any(k in ds_text for k in ("prefers-color-scheme", "data-theme", ".dark"))
    if has_dark:
        return                                   # _ds 有暗色了，问题单可以撤

    doc = REPO / "docs" / "blocked" / "DS-NO-DARK-PALETTE.md"
    assert doc.exists(), "_ds 仍是单套明色，问题单却不在"
    assert "prefers-color-scheme" in doc.read_text(encoding="utf-8")


# ───────────────────────── acceptance③：不引入外部字体


def test_no_external_font_is_pulled_in_by_the_wiring() -> None:
    """DEC-017/018 继续有效：品牌字走系统回落栈，**零外部取用**。

    接线最容易顺手带进来的就是一条字体 CDN——那会让页面在无网环境下等一个超时，
    而 CI 恒不联网（S2-7）。
    """
    for path in (GLOBALS, LAYOUT):
        text = path.read_text(encoding="utf-8")
        assert "http://" not in text and "https://" not in text, f"{path.name} 里有外链"
        assert "fonts.googleapis" not in text and "next/font" not in text

    fonts_css = (_bundle_dir() / "fonts" / "fonts.css").read_text(encoding="utf-8")
    code = re.sub(r"/\*.*?\*/", "", fonts_css, flags=re.DOTALL)     # 注释里提到 @import 不算
    assert "@import" not in code, "_ds 的 fonts.css 里出现了 @import（DEC-018 已删过一次）"
