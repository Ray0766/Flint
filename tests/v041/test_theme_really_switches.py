"""DARK-02：EYE-02 的「明暗两主题」从**量同一个东西**变成真判据。

## 这条洞的原形

`docs/blocked/EYE-02-TWO-THEMES-MEASURES-ONE.md` 记的是：K6-01 用
`check_fragment` 量入口按钮，两个主题量出**一位不差的同一组数**——

```
dark : color rgb(27,42,46)  background rgb(247,248,243)  96×29
light: color rgb(27,42,46)  background rgb(247,248,243)  96×29
```

而判据照样放行。它**不会误判**（两次都真的过线），但它**证不到**它字面上声称的
那件事：换主题之后仍然看得见。DARK-01 把暗色板做出来之后，这条洞第一次
**量得出来**——本卡把它关上。

## 四条判据

1. **前置断言**：受 `_ds` token 支配的元素，两主题量到的**颜色对必须不同**；
   两次相同即判红。归一到 RGB 之后比——否则 `#F7F8F3` 与 `rgb(247, 248, 243)`
   会被当成「不同」，那等于把假绿换了个写法留下来；
2. **阴性对照**：把暗色规则**临时摘掉**之后判据必须报红。摘的是内存里的一份
   CSS 副本与一份内联片段，产品文件一个字节不动——改产品文件造出来的红
   证明不了尺子有区分力，只证明了那次改动生效了；
3. **接进全局门**：`pytest -q` 直接跑得到本文件，且它对**磁盘上已录的真实取证**
   施加这条判据（F-11 的教训是不在门里的尺子等于没有）；
4. 关掉 `docs/blocked/EYE-02-TWO-THEMES-MEASURES-ONE.md`。

## 为什么默认开启

`check_fragment` 的新参数 `theme_sensitive` 默认 **True**：忘了打开时得到的是红，
不是绿。反过来默认关闭的话，本卡关上的洞会以「谁都没想起来传那个参数」的形式
原样回来——而那种回来是无声的。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

# pytest 由 `pythonpath = ["."]` 供仓根，`C:\pwenv` 的解释器直跑本文件时没有。
# 写在这里而不是只写进 `__main__`：两条路径要 import 到**同一个** `tools.visual_assert`。
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from tools import visual_assert as va
from tools.probe_evidence import require_probe_evidence

DS_ROOT = REPO / "web" / "public" / "_ds"
PROBE = REPO / ".ui-probe"
ARTIFACT = PROBE / "theme_switch.json"
BLOCKED = REPO / "docs" / "blocked" / "EYE-02-TWO-THEMES-MEASURES-ONE.md"

# ── 那组「两次量到一位不差」的观测，**从当前调色板现场取**（`PAL-02`）
#
# 改前这里冻着两个字面量：
#
#     FROZEN_FG = "rgb(27, 42, 46)"      # 明色 --ink  #1B2A2E
#     FROZEN_BG = "rgb(247, 248, 243)"   # 明色 --surface #F7F8F3
#
# **那两行是 `EYE-02` 那个洞的原形**（2026-08-04 实测：两个主题量到一位不差的
# 同一组数，而报告 `ok=True`），所以它们留在这段注释里当历史记录。
#
# 但把它们当成判据的**输入**，钉的是那一天的板：`PAL-01` 换板之后，
# 这组数与屏上任何一处都对不上了——判据仍然绿，因为它验的是「尺子会不会把
# 两次相同的观测判红」，而那与色号无关。绿得没错，**却在拿一组过期的数在验**。
#
# 改成从 `tokens/colors.css` 现场解析今天的明色 `--ink`/`--surface`：
# 守的仍是「两主题量到的颜色对 MUST 不同」这件事本身，
# 而喂给尺子的是**今天真的会出现在屏上的那一组**。
def _rgb_of(token: str) -> str:
    """当前明色板里那个 token 的 `rgb(...)` 写法（浏览器量到的就是这种）。"""
    block = re.search(r"^:root\{(.*?)\n\}", _colors_css(), re.DOTALL | re.MULTILINE)
    assert block, "colors.css 里没有 :root 块"
    value = dict(re.findall(r"(--[a-z0-9-]+)\s*:\s*([^;}]+)", block.group(1)))[token]
    r, g, b = va.parse_color(value.split("/*")[0].strip())
    return f"rgb({r}, {g}, {b})"


# 定义顺序：`_rgb_of` 依赖下面的 `_colors_css`，所以这两个常量在模块末尾赋值
# （见文件底部 `FROZEN_FG` / `FROZEN_BG` 的实际赋值）。
FROZEN_FG = ""
FROZEN_BG = ""


def _obs(theme: str, **over: object) -> va.VisualObservation:
    base = {
        "selector": ".trigger", "present": True, "width": 96.0, "height": 29.0,
        "color": FROZEN_FG, "background_color": FROZEN_BG, "theme": theme,
    }
    base.update(over)
    return va.VisualObservation(**base)  # type: ignore[arg-type]


def _bundle() -> Path:
    dirs = [p for p in DS_ROOT.iterdir() if p.is_dir()]
    assert len(dirs) == 1
    return dirs[0]


def _colors_css() -> str:
    return (_bundle() / "tokens" / "colors.css").read_text(encoding="utf-8")


# ───────────────────────── 一、前置断言：两次量到相同即判红（acceptance①）


def test_two_identical_measurements_are_red() -> None:
    """问题单里那一组数——一位不差——必须判红。

    此前它是绿的：三条老判据逐条都过（有尺寸、对比度 12.68 过线、两个主题都量到了），
    于是报告 ok=True。缺的是「这两次量的到底是不是两个东西」这一问。
    """
    verdict = va.judge_theme_switch({"dark": _obs("dark"), "light": _obs("light")})

    assert verdict.ok is False
    assert verdict.criterion == va.THEME_SWITCH
    assert FROZEN_BG in verdict.detail, "报红要把量到的那组值贴出来，否则读的人不知道红在哪"


def test_a_real_switch_is_let_through() -> None:
    """DARK-01 之后重量到的那一组——真的换了——必须放行。

    见谁都报红的尺子同样量不出东西：它只是把假绿换成了假红。
    """
    verdict = va.judge_theme_switch({
        "dark": _obs("dark", color="rgb(237, 238, 230)", background_color="rgb(21, 34, 37)"),
        "light": _obs("light"),
    })

    assert verdict.ok is True
    assert verdict.criterion == va.THEME_SWITCH


def test_the_same_color_written_two_ways_is_still_the_same_color() -> None:
    """`#F7F8F3` 与 `rgb(247, 248, 243)` 是同一个颜色——按字符串比会判成「换了」。

    那正是本卡要挡的假绿换个写法：判据必须归一到 RGB 之后再比。
    """
    verdict = va.judge_theme_switch({
        "dark": _obs("dark", background_color="#F7F8F3"),
        "light": _obs("light", background_color="rgb(247, 248, 243)"),
    })

    assert verdict.ok is False


def test_changing_only_the_background_counts_as_a_switch() -> None:
    """只有底色换了也算换：判据要的是「有区别」，不是「两项全换」。"""
    verdict = va.judge_theme_switch({
        "dark": _obs("dark", background_color="rgb(21, 34, 37)"),
        "light": _obs("light"),
    })

    assert verdict.ok is True


def test_a_size_only_difference_is_not_a_theme_switch() -> None:
    """尺寸抖了一像素而颜色一模一样：那不是主题在起作用，判红。

    调色板换的是颜色。把布局抖动当成「主题生效了」，就会把一个没有暗色规则的
    元素放行——本卡挡的就是这种放行。
    """
    verdict = va.judge_theme_switch({
        "dark": _obs("dark", width=97.0),
        "light": _obs("light"),
    })

    assert verdict.ok is False


def test_one_theme_alone_cannot_prove_a_switch() -> None:
    """只量到一个主题时报红，NEVER「没量到就算过」——少的那一半正是要证的那一半。

    **红的理由要点名缺了哪个主题**：只判「红了没有」的话，缺主题这一支被抽掉后，
    单份观测会掉进「两次量到同一组颜色」那一支，照样红——测试全绿而分支已经没了
    （变异考⑦ 实测过这个形状）。
    """
    verdict = va.judge_theme_switch({"dark": _obs("dark")})

    assert verdict.ok is False
    assert "缺" in verdict.detail and "light" in verdict.detail, (
        f"红的理由不是「缺一个主题」：{verdict.detail}")


def test_a_missing_element_is_red_with_its_own_message() -> None:
    """元素根本没渲染出来时，「颜色没变」是个无意义的结论——要红在找不到上。"""
    verdict = va.judge_theme_switch({
        "dark": _obs("dark", present=False, color="", background_color=""),
        "light": _obs("light"),
    })

    assert verdict.ok is False
    assert "找不到" in verdict.detail


def test_an_unparseable_color_is_red_not_guessed() -> None:
    """认不出的颜色 NEVER 猜：猜出来的「不同」是个看起来很像真的假数。"""
    verdict = va.judge_theme_switch({
        "dark": _obs("dark", background_color="chartreuse-ish"),
        "light": _obs("light"),
    })

    assert verdict.ok is False


# ───────────────────────── 二、接进 check_fragment 且默认开启（acceptance①③）


def _canned(dark: va.VisualObservation, light: va.VisualObservation) -> va.Measurer:
    table = {"dark": dark, "light": light}
    return lambda html, selector, theme: table[theme]


def test_check_fragment_enforces_the_switch_by_default() -> None:
    """**这一条就是回归**：老三条全过、两主题同值的那份观测，现在整体判红。

    不传任何新参数——默认就该拦住。传了才拦的话，本卡关上的洞会以
    「谁都没想起来传那个参数」的形式无声回来。
    """
    report = va.check_fragment(
        '<button class="trigger">锂电池回收</button>', ".trigger",
        measurer=_canned(_obs("dark"), _obs("light")),
    )

    assert report["ok"] is False
    failed = [v["criterion"] for v in report["verdicts"] if not v["ok"]]
    assert failed == [va.THEME_SWITCH], f"红的原因不止这一条，对照说明不了问题：{failed}"


def test_the_switch_verdict_is_reported_first() -> None:
    """它是**前置**断言：两次量的是不是两个东西，先于「看得见 / 看得清」回答。"""
    report = va.check_fragment(
        '<button class="trigger">锂电池回收</button>', ".trigger",
        measurer=_canned(
            _obs("dark", color="rgb(237, 238, 230)", background_color="rgb(21, 34, 37)"),
            _obs("light"),
        ),
    )

    assert report["verdicts"][0]["criterion"] == va.THEME_SWITCH


def test_turning_it_off_takes_an_explicit_argument_and_is_recorded() -> None:
    """确有不随主题变的元素（固定品牌色一类），可以关——但**关了要留在报告里**。

    不留痕的话，一份 ok=True 的报告读不出它是「验过了」还是「那条判据被关了」。
    """
    kwargs = {
        "measurer": _canned(_obs("dark"), _obs("light")),
        "theme_sensitive": False,
    }
    report = va.check_fragment(
        '<button class="trigger">锂电池回收</button>', ".trigger", **kwargs)  # type: ignore[arg-type]

    assert report["ok"] is True
    assert report["theme_sensitive"] is False
    assert va.THEME_SWITCH not in [v["criterion"] for v in report["verdicts"]]
    on = va.check_fragment(
        '<button class="trigger">锂电池回收</button>', ".trigger",
        measurer=_canned(_obs("dark"), _obs("light")))
    assert on["theme_sensitive"] is True, "开着的时候也要写进报告，两份报告才可比"


def test_the_old_three_criteria_still_run_alongside_it() -> None:
    """新判据是**加**一条，不是换掉那三条：0×0 仍然要被尺寸那条抓住。"""
    report = va.check_fragment(
        '<span class="trigger"></span>', ".trigger",
        measurer=_canned(
            _obs("dark", width=0.0, height=0.0, color="rgb(237, 238, 230)",
                 background_color="rgb(21, 34, 37)"),
            _obs("light", width=0.0, height=0.0),
        ),
    )

    criteria = {v["criterion"] for v in report["verdicts"] if not v["ok"]}
    assert "rendered-size" in criteria
    assert va.THEME_SWITCH not in criteria, "颜色确实换了，不该红在这一条上"


# ───────────────────────── 三、阴性对照：摘掉暗色规则必须报红（acceptance②）
#
# 摘的是**内存里的一份副本**：读真 `colors.css`，把暗色三块从字符串里删掉，
# 再按剩下的 `:root` 解析两个主题。产品文件一个字节不动——
# 改产品文件造出来的红只证明那次改动生效了，证明不了尺子有区分力。


def _block(css: str, selector: str) -> str:
    match = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", css)
    return match.group(1) if match else ""


def _tokens(block: str) -> dict[str, str]:
    return {n: v.strip() for n, v in re.findall(r"(--[a-z0-9-]+)\s*:\s*([^;]+);", block)}


def _resolve(tokens: dict[str, str], name: str) -> str:
    seen: set[str] = set()
    value = tokens[name]
    while value.startswith("var(") and name not in seen:
        seen.add(name)
        name = value[4:].split(")")[0].strip()
        value = tokens[name]
    return value


def _strip_dark_blocks(css: str) -> str:
    """把 `@media (prefers-color-scheme: dark)` 与 `[data-theme="dark"]` 两块删掉。"""
    start = css.find("@media (prefers-color-scheme: dark)")
    end = css.find('[data-theme="light"]')
    assert start != -1 and end > start, "暗色块的形状变了，这个对照要跟着改"
    return css[:start] + css[end:]


def _measurer_from_css(css: str) -> va.Measurer:
    """按一份 CSS 文本解析两个主题的颜色——暗色块在就取暗色，不在就落回 `:root`。"""
    light = _tokens(_block(css, ":root"))
    dark = {**light, **_tokens(_block(css, '[data-theme="dark"]'))}

    def measure(html: str, selector: str, theme: str) -> va.VisualObservation:
        table = dark if theme == "dark" else light
        return va.VisualObservation(
            selector=selector, present=True, width=96.0, height=29.0,
            color=_resolve(table, "--ink"), background_color=_resolve(table, "--surface"),
            theme=theme,
        )

    return measure


def test_the_real_palette_passes_the_new_criterion() -> None:
    """正例：拿真 `colors.css` 解析出来的两组值，判据放行。"""
    report = va.check_fragment(
        '<button class="trigger">锂电池回收</button>', ".trigger",
        measurer=_measurer_from_css(_colors_css()),
    )

    assert report["ok"] is True, [v["detail"] for v in report["verdicts"] if not v["ok"]]


def test_removing_the_dark_blocks_turns_the_criterion_red() -> None:
    """阴性对照：暗色块一摘，两个主题落回同一组 `:root` 值，判据必须报红。

    这条对照证的是**尺子有区分力**——DARK-01 之前的世界正是这个样子。
    """
    stripped = _strip_dark_blocks(_colors_css())
    report = va.check_fragment(
        '<button class="trigger">锂电池回收</button>', ".trigger",
        measurer=_measurer_from_css(stripped),
    )

    assert report["ok"] is False, "摘掉暗色规则之后判据仍然是绿的——它没有区分力"
    failed = [v["criterion"] for v in report["verdicts"] if not v["ok"]]
    assert failed == [va.THEME_SWITCH], f"红的原因不是主题没切，这个对照说明不了问题：{failed}"


def test_the_negative_control_changes_nothing_on_disk() -> None:
    """对照跑完，产品文件逐字节不变——红是内存里造出来的。"""
    before = _colors_css()
    _strip_dark_blocks(before)

    assert _colors_css() == before


# ───────────────────────── 四、接进全局门：判据施加到磁盘上已录的真实取证（acceptance③）


def _recorded_ds_reports() -> list[tuple[str, dict[str, object]]]:
    """磁盘上所有「带规则、且片段真的加载了 `_ds`」的取证报告。

    只取 `styled` 那一半：`unstyled` 是阴性对照，它本来就没有 `_ds` 规则在起作用，
    对它要求「主题切换」会造出一条永远红的假警报。
    """
    found: list[tuple[str, dict[str, object]]] = []
    for path in sorted(PROBE.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        for key, value in data.items():
            if not isinstance(value, dict) or "observations" not in value:
                continue
            if key != "styled":
                continue
            if "_ds" not in str(value.get("fragment", "")):
                continue
            found.append((f"{path.name}#{key}", value))
    return found


def test_there_is_recorded_evidence_to_judge() -> None:
    """判据要有真东西可判：一份都扫不到时报红，NEVER 空转成绿。"""
    require_probe_evidence(PROBE, "起栈后跑 scripts/ui_probe.py --tokens --json")
    assert _recorded_ds_reports(), f"{PROBE} 下没有可判的 _ds 取证"


def test_every_recorded_ds_element_really_switches_themes() -> None:
    """**这是本卡的门**：已录的每份 `_ds` 取证，逐份过新判据。

    磁盘上曾经躺着一份 `disputed_mark.json`，两个主题一位不差而 `ok=True`——
    那就是问题单说的假绿被**存了下来**。尺子补好而旧证据不重量，
    等于承认「以前那些绿不作数，但我们不查」。
    """
    stale = []
    for name, report in _recorded_ds_reports():
        by_theme = {
            theme: va.VisualObservation(**obs)  # type: ignore[arg-type]
            for theme, obs in report["observations"].items()  # type: ignore[union-attr]
        }
        verdict = va.judge_theme_switch(by_theme)
        if not verdict.ok:
            stale.append(f"{name}：{verdict.detail}")

    assert stale == [], "这些已录取证没有真的换主题（重跑取证或它本来就没被 _ds 上色）：" + \
        "；".join(stale)


def test_the_browser_level_negative_control_is_recorded() -> None:
    """真浏览器那一层的阴性对照也要留档：内联一份摘掉暗色块的 CSS，判据必须红。

    上面那条对照走的是注入驱动（判据面），这一条走的是 `C:\\pwenv` 的 playwright
    真量（量测面）。两层都要，因为它们坏的方式不一样。
    """
    require_probe_evidence(ARTIFACT, "用装了 playwright 的解释器直接跑本文件")
    assert ARTIFACT.exists(), (
        f"没有 {ARTIFACT.name}：用 C:\\pwenv\\Scripts\\python.exe 跑本文件生成")
    data = json.loads(ARTIFACT.read_text(encoding="utf-8"))

    assert data["schema"] == "theme-switch/1"
    assert data["with_dark"]["ok"] is True, [
        v["detail"] for v in data["with_dark"]["verdicts"] if not v["ok"]]
    assert data["without_dark"]["ok"] is False, "摘掉暗色块之后真浏览器里判据仍是绿的"
    failed = [v["criterion"] for v in data["without_dark"]["verdicts"] if not v["ok"]]
    assert failed == [va.THEME_SWITCH], f"红的原因不是主题没切：{failed}"


def test_the_two_recorded_runs_differ_only_by_the_dark_blocks() -> None:
    """两次真量的唯一变量就是那三块暗色声明——否则对照不成立。"""
    require_probe_evidence(ARTIFACT, "用装了 playwright 的解释器直接跑本文件")
    data = json.loads(ARTIFACT.read_text(encoding="utf-8"))

    assert data["with_dark"]["fragment_sha"] != data["without_dark"]["fragment_sha"]
    assert '[data-theme="dark"]' in data["with_dark"]["stylesheet_shape"]
    assert '[data-theme="dark"]' not in data["without_dark"]["stylesheet_shape"]


def test_this_file_needs_no_browser_to_run() -> None:
    """本文件恒在 `pytest -q` 里：判据面零 playwright 依赖，量测走注入驱动与已录产物。

    F-11 的教训是**不在门里的尺子等于没有**。真量那一层的产物由本文件的
    `__main__` 入口生成，判定那一层在门里逐次跑。

    判在 import 语句上，NEVER 判「正文里不许出现 playwright 这个词」——
    那会连注释里解释真量走哪个解释器的那句话一起禁掉。
    """
    import sys

    judged = Path(__file__).read_text(encoding="utf-8").split('if __name__ == "__main__"')[0]

    assert not re.search(r"^\s*(import|from)\s+playwright", judged, re.MULTILINE), (
        "判据面 import 了 playwright，它就进不了全局门")
    assert "playwright" not in sys.modules, "判据面这一趟把 playwright 拉进来了"


# ───────────────────────── 五、关掉那张问题单（acceptance④）


def test_the_blocked_doc_is_closed_with_a_banner() -> None:
    """问题单要关掉并写明裁决与日期。

    日期与卡号**直接钉在「已关闭」这个词后面**，NEVER 只判「关闭那一行里有个日期」——
    横幅正文里随手一句「owner 2026-08-04 裁决」就能把后者喂饱：去掉真正的关闭日期
    毫无反应（变异考⑭ 实测，本仓第二十二次同型）。
    """
    doc = BLOCKED.read_text(encoding="utf-8")
    banner = next((ln for ln in doc.splitlines()[:8] if "已关闭" in ln), "")

    assert banner, "顶部没有关闭横幅"
    assert re.search(r"已关闭\s*2026-08-04", banner), f"「已关闭」后面没跟关闭日期：{banner}"
    assert re.search(r"已关闭[^\n]{0,20}DARK-02", banner), f"关闭标记里没写由哪张卡解决：{banner}"


def test_the_original_report_is_kept_under_the_banner() -> None:
    """原文留着：删掉的话，「假绿是怎么被发现的」这段记录就没了。

    判的是**整段还在**，不是某个词还在：只钉一两个字符串的话，正文被截掉大半
    也照样绿（变异考⑯ 实测）。
    """
    doc = BLOCKED.read_text(encoding="utf-8")
    body = doc.split("原文原样保留在下面。", 1)[-1]

    assert "rgb(27,42,46)" in body, "问题单里那组实测值被删了"
    assert "同一组数" in body
    for heading in ("## 实测到的事", "## 为什么这值得立一张卡", "## 三条路（要 owner 选）",
                    "## 顺带记一条对照的形状"):
        assert heading in body, f"原文少了一节：{heading}"
    assert len(body.splitlines()) >= 40, f"原文只剩 {len(body.splitlines())} 行，被截掉了"


# ───────────────────────── 真量产物生成（用 C:\pwenv 的解释器跑本文件）

if __name__ == "__main__":  # pragma: no cover - 取证入口，pytest 不走这里
    import hashlib

    real_css = _colors_css()

    def fragment_of(css: str) -> str:
        """两份片段只差那段 CSS——写成一处才比得住。

        按钮的底色与字色**显式取 `_ds` 的 token**：不取的话浏览器给按钮一层
        不透明的 UA 默认灰，量到的就是 `rgb(240, 240, 240)`，两个主题当然一样，
        那时这份对照红在「按钮没被上色」而不是「暗色规则被摘了」。
        """
        return (
            f"<style>{css}</style>"
            '<div style="background:var(--bg-page);padding:20px">'
            '<button type="button" class="trigger" '
            'style="background:var(--surface);color:var(--ink);border:1px solid var(--rule);'
            'padding:6px 12px">锂电池回收</button>'
            "</div>"
        )

    out: dict[str, object] = {"schema": "theme-switch/1", "selector": ".trigger"}
    for key, css in (("with_dark", real_css), ("without_dark", _strip_dark_blocks(real_css))):
        html = fragment_of(css)
        report = va.check_fragment(html, ".trigger")
        report["fragment_sha"] = hashlib.sha256(html.encode()).hexdigest()[:16]
        report["stylesheet_shape"] = "".join(
            ln for ln in css.splitlines() if ln.strip().endswith("{") or ln.strip() == "}")
        out[key] = report

    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"with_dark.ok={out['with_dark']['ok']}  "  # type: ignore[index]
          f"without_dark.ok={out['without_dark']['ok']}")  # type: ignore[index]
    print(f"→ {ARTIFACT}")


def test_the_switch_ruler_bites_a_palette_whose_dark_paper_is_the_light_one() -> None:
    """**阴性对照（PAL-02）**：暗板的纸与明板同值 → 尺子 MUST 当场判红。

    `PAL-02` 把这两个常量从写死的字面量改成了**从当前板现场解析**。
    改判据之后要证的是它**还咬得住**：造一组「两个主题量到同一组数」的观测
    （正是 `EYE-02` 那个洞的形状），喂给同一把尺子。

    **改在内存里，NEVER 动真文件**。
    """
    same = _rgb_of("--paper")
    verdict = va.judge_theme_switch({
        "light": _obs("light", background_color=same),
        "dark": _obs("dark", background_color=same),
    })

    assert verdict.ok is False, "两个主题量到同一组数，而尺子放行了"
    assert same in verdict.detail, "报红没把量到的那组值贴出来"


# 模块加载完再赋值：`_rgb_of` 用到的 `_colors_css` 定义在上面那一段之后。
FROZEN_FG = _rgb_of("--ink")
FROZEN_BG = _rgb_of("--surface")
