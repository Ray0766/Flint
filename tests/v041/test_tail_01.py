"""TAIL-01 · 清掉 steward 已答复的四张单（改名 / 关单 / 搬色号 / 认措辞）。

owner 要停约一周。这四张单**放着会在一周后变成「这是什么」**——
答复都已经在单子里了，落地就是一件事。

## 四张单各自落成什么

| 单 | 落地 |
|---|---|
| `WARN-TOKEN-NAME-CONTRADICTS-DEC-060` | `--warn` → **`--ochre`**（赭），值一个字不动；用途边界写死并各配一条判据 |
| `PLAZA-UPPER-BOUND-CONTRADICTS-ENTRY-04` | 关掉：**卡面错、既有纪律对**。`test_plaza_multiselect_combo.py` 一个字不动 |
| `NAV-MASCOT-COLOURS-ARE-A-SECOND-SOURCE` | 药丸条与吉祥物那 26 行搬进 `_ds/tokens/colors.css`，`globals.css` 只留 `var()` |
| `DEC-060-TEXT-IS-STEWARD-AUTHORED-OPTIONS` | 关掉：steward 认下措辞（`DECISIONS` append-only，既有条目 NEVER 重写） |

## 搬家这件事，判据判的是「**位置换了、值没变**」

搬前搬后各在**真浏览器**上量一次药丸条与吉祥物的 computed color
（`tools/ui_probe_nav_tokens.py` → `nav-before.json` / `nav-after.json`），
两份逐键相等才算搬对。**NEVER 借搬家顺手调色**——调色是另一件事，要单独看屏定。

## 赭色那一格：只落一个色号是不够的

`#a3701c` 在明色 `--surface` 上实测 **4.01**——够图形对比（3:1），不够正文（4.5）。
所以用途边界写死：只许用于图形 / 边框 / 图标 / 状态点，**NEVER 用作正文或链接文字**。
阴性对照把它挂到一段正文上，判据 MUST 红**并报出实测比值**。
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import pytest

from tools.probe_evidence import ONLY_ON_THE_ORIGINAL_MACHINE, require_probe_evidence

REPO = Path(__file__).resolve().parents[2]
DS = REPO / "web" / "public" / "_ds" / "flint-design-system-8fd95ba3-cf31-49b6-b9d8-c863f3dc2724"
COLORS = DS / "tokens" / "colors.css"
GLOBALS = REPO / "web" / "app" / "globals.css"
BLOCKED = REPO / "docs" / "blocked"
PROBE = REPO / ".ui-probe" / "tail01"
BEFORE = PROBE / "nav-before.json"
AFTER = PROBE / "nav-after.json"
PROBE_TOOL = REPO / "tools" / "ui_probe_nav_tokens.py"
PWENV = Path(r"C:\pwenv\Scripts\python.exe")
PLAZA_RULER = REPO / "tests" / "v041" / "test_plaza_multiselect_combo.py"

#: 搬家的那一族：药丸条 + 吉祥物。**名字一个都不改**——
#: 改名要把 `globals.css` 里每一处 `var()` 跟着改，而那就不再是「搬位置」了。
MOVED = (
    "--mascot-face", "--mascot-ink", "--mascot-blush", "--mascot-shadow",
    "--nav-ink-on-dark", "--nav-ink-on-light",
    "--nav-surface", "--nav-border", "--nav-shadow",
    "--nav-ink", "--nav-ink-active", "--nav-hover-bg",
)

#: `ENTRY-04` 那条纪律的量具**一个字不动**（单子答复逐字要求的）。
#: 它哪天真要改，先改这个指纹并在 trace 里说明为什么——
#: 而不是改完就走，那样「一个字不动」就没有人在守。
PLAZA_RULER_SHA = "0ec676bdf6186cb63a844c9b06afde63cba7fea736d1a0b02aa243185f9a6df5"


def _light_block() -> str:
    """`:root{…}` 那一段（明色）。"""
    text = COLORS.read_text(encoding="utf-8")
    return text.split(":root{", 1)[1].split("}", 1)[0]


def _dark_block() -> str:
    """`[data-theme="dark"]{…}` 那一段。"""
    text = COLORS.read_text(encoding="utf-8")
    return text.split('[data-theme="dark"]{', 1)[1].split("}", 1)[0]


def _token(block: str, name: str) -> str:
    found = re.search(rf"^{re.escape(name)}\s*:\s*([^;]+);", block, re.MULTILINE)
    assert found, f"{name} 不在这一段里"
    return found.group(1).strip()


def _hex(rgb: tuple[float, float, float]) -> str:
    return "#" + "".join(f"{round(c):02x}" for c in rgb)


def _composite(fg: tuple[int, int, int], alpha: float,
               bg: tuple[int, int, int]) -> str:
    """rgba 合成到不透明底上——`--rust-soft` / `--moss-soft` 同一条规则。"""
    return _hex(tuple(alpha * f + (1 - alpha) * b for f, b in zip(fg, bg)))


# ═════════════════ ① `--warn` 改名 `--ochre`，值一个字不动


# REDESIGN-01（`DEC-065`）：v5 把整板颜色换了，赭色这一族的取值也在其中。下面三条钉的是
# v4 那一版的具体数（`#a3701c` / `#c99a4a`、合成出来的两个 soft、明色实测 4.01）。
# 标出来、留着不删：赭色当初为什么只许做图形、那个 4.01 是怎么来的，记录还在。
# **「赭色 NEVER 画文字」这条规矩本身没有退役**——再往下那两条照常生效，v5 的样式照样守着。
superseded_by_v5 = pytest.mark.skip(
    reason="DEC-065 / REDESIGN-01：v4 调色板已被 v5 整板取代，这条钉的是 v4 赭色一族的取值与实测比值")


@superseded_by_v5
def test_the_amber_token_landed_under_a_material_name() -> None:
    """名字照本仓的**材料名**法（paper / ink / rule / indigo / sulfur / rust / moss）。

    `DEC-060` 把 `--warn` 逐字列进「NEVER 引进本仓」的 v4 记法里，
    而卡面要落的正是那个名字——两处矛盾，按单子答复取材料名 `--ochre`（赭）。
    """
    assert _token(_light_block(), "--ochre") == "#a3701c"
    assert _token(_dark_block(), "--ochre") == "#c99a4a"
    assert "v4 --warn" in COLORS.read_text(encoding="utf-8"), (
        "注释里没写它对应 v4 的哪个变量——那是换板留下的线索")


def test_the_forbidden_v4_name_did_not_sneak_in() -> None:
    """`--warn` 这个名字**一处定义都没有**（`DEC-060` 第一条）。

    判定义不判提及：注释里写「v4 --warn」是在记线索，那正是要留的东西。
    """
    guilty: list[str] = []
    for path in (REPO / "web").rglob("*.css"):
        if "node_modules" in path.parts or ".next" in path.parts:
            continue
        text = re.sub(r"/\*.*?\*/", "", path.read_text(encoding="utf-8"), flags=re.DOTALL)
        if re.search(r"^\s*--warn\s*:", text, re.MULTILINE):
            guilty.append(path.relative_to(REPO).as_posix())

    assert guilty == [], f"v4 的名字进来了：{guilty}"


@superseded_by_v5
def test_the_soft_shade_is_composited_not_picked() -> None:
    """soft 那一格是**算出来的**：v4 的 rgba 合成到同主题 `--paper` 上。

    随手挑一个色号的话，下一个人无从判断它是量出来的还是拍出来的
    （`--rust-soft` / `--moss-soft` 同一条规则，本仓既有口径）。
    """
    light = _composite((180, 130, 40), 0.14, (0xF2, 0xED, 0xE4))   # v4 rgba(180,130,40,.14)
    dark = _composite((200, 155, 75), 0.16, (0x19, 0x16, 0x12))    # v4 rgba(200,155,75,.16)

    assert light == "#e9deca", light
    assert dark == "#352b1b", dark
    assert _token(_light_block(), "--ochre-soft") == light
    assert _token(_dark_block(), "--ochre-soft") == dark


@superseded_by_v5
def test_the_ochre_is_good_for_graphics_and_not_for_text() -> None:
    """**用途边界是量出来的**：明色 `#a3701c` 在 `--surface` 上 4.01。

    够图形对比（3:1）**不够正文**（AA 4.5）。这条把那两个数各判一次——
    只落一个色号而不写边界的话，下一个人会拿它去写正文，
    而那一屏在浅色主题下就读不清了。
    """
    from tools.visual_assert import contrast_ratio, parse_color

    ratio = contrast_ratio(parse_color("#a3701c"),
                           parse_color(_token(_light_block(), "--surface")))

    assert 3.0 <= ratio < 4.5, f"实测 {ratio:.2f}——边界那句话要跟着重写"
    assert round(ratio, 2) == 4.01, f"实测 {ratio:.2f}，单子里记的是 4.01"
    # 暗色那一格反过来：它够正文线，所以边界只对明色说。
    dark_ratio = contrast_ratio(parse_color("#c99a4a"),
                                parse_color(_token(_dark_block(), "--surface")))
    assert dark_ratio >= 4.5, f"暗色实测 {dark_ratio:.2f}"


def _text_paints_with(css: str, token: str) -> list[str]:
    """找出**用这个 token 画文字**的声明（`color:` 那一类）。

    背景 / 边框 / 图标 / 状态点不在此列——那正是允许的用法。
    """
    stripped = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    return [
        line.strip()
        for line in stripped.splitlines()
        if re.search(rf"(^|[;{{\s])color\s*:\s*var\(\s*{re.escape(token)}\s*\)", line)
    ]


def test_no_rule_in_the_repo_paints_text_with_the_ochre() -> None:
    """全仓**没有一处**拿它画正文或链接文字。"""
    guilty: list[str] = []
    for path in (REPO / "web").rglob("*.css"):
        if "node_modules" in path.parts or ".next" in path.parts:
            continue
        for line in _text_paints_with(path.read_text(encoding="utf-8"), "--ochre"):
            guilty.append(f"{path.relative_to(REPO).as_posix()}: {line}")

    assert guilty == [], f"赭色被拿去画文字了（明色实测 4.01 < 4.5）：{guilty}"


def test_the_text_guard_actually_bites_and_reports_the_measured_ratio() -> None:
    """**阴性对照**：把它挂到一段正文上 → 判据 MUST 红，且报得出实测比值。

    改在内存里，NEVER 动真文件（第 9 批那条教训：判据读的不只是源码）。
    """
    from tools.visual_assert import contrast_ratio, parse_color

    mutated = ".screen__body { color: var(--ochre); font-size: 14px; }"

    caught = _text_paints_with(mutated, "--ochre")
    ratio = contrast_ratio(parse_color("#a3701c"),
                           parse_color(_token(_light_block(), "--surface")))

    assert caught, "把赭色挂到正文上都抓不住——这条判据在空转"
    assert ratio < 4.5, f"{ratio:.2f} 已经够正文线了，边界该重定"
    # 允许的用法不许被误伤：背景 / 边框 / 状态点照旧。
    assert _text_paints_with(
        ".dot { background: var(--ochre); border-color: var(--ochre); }", "--ochre") == []


# ═════════════════ ② 广场上限那张单：卡面错、既有纪律对


def test_the_plaza_ruler_was_not_touched() -> None:
    """`ENTRY-04` 那条判据**一个字没动**（单子答复逐字要求的）。"""
    got = hashlib.sha256(PLAZA_RULER.read_bytes()).hexdigest()

    assert got == PLAZA_RULER_SHA, (
        f"那把尺子被改了：{got}。真要改，先在 trace 里说明为什么，再改这个指纹")


def test_the_three_gating_hints_never_mention_an_upper_bound() -> None:
    """广场**三态提示**（还差几张 / 假设必填 / 就绪）只说下限，NEVER 说上限。

    `2~5` 数的是**证据卡**，广场选的是**热点**——一个热点底下可能有好几张卡。
    在广场说一个上限，用户会照着热点数去凑，而那个数与端点判的不是同一件事。

    **空态那一句不在这三态里**：它是 v4 设计稿的原文（「加入 2~5 张热点卡」），
    由 `test_plaza_combo_bar.py::test_the_wording_comes_from_the_design_file_verbatim`
    钉着照抄。改它是**文案**问题、且会与那条已 verified 的判据打架——
    本卡 `no_new_fronts`，故如实登记在单子的关闭节里，NEVER 顺手改。
    """
    messages = json.loads(
        (REPO / "web" / "messages" / "zh.json").read_text(encoding="utf-8"))
    gating = ("plaza.combo.need_n", "plaza.combo.need_hypothesis",
              "plaza.combo.ready")

    for key in gating:
        line = messages[key]
        for word in ("最多", "上限", "2~5"):
            assert word not in line, f"{key} 说了上限：{line}"


def test_the_plaza_screen_still_does_not_judge_the_upper_bound() -> None:
    """广场**代码层**一次都不判上限（`ENTRY-04` 的既有裁决，本卡维持）。

    与既有那条判据判的是同一件事，这里从**用途**这一侧再判一次：
    上限那句文案（`plaza.combo.at_max`）在这一屏一次都没被用到。
    """
    code = re.sub(r"/\*.*?\*/|//[^\n]*", "",
                  (REPO / "web" / "components" / "plaza" / "PlazaCards.tsx")
                  .read_text(encoding="utf-8"), flags=re.DOTALL)

    assert "plaza.combo.at_max" not in code, "广场用上了那句「一次最多」"
    assert "COMBO_MAX" not in code and "comboCountValid" not in code


# ═════════════════ ③ 药丸条与吉祥物：搬位置不搬值


def test_the_nav_and_mascot_colours_now_live_in_the_token_file() -> None:
    """那一族的定义**只在 `colors.css` 里**，`globals.css` 只剩 `var()`。"""
    tokens = COLORS.read_text(encoding="utf-8")
    styles = GLOBALS.read_text(encoding="utf-8")
    missing = [name for name in MOVED
               if not re.search(rf"^{re.escape(name)}\s*:", tokens, re.MULTILINE)]
    left_behind = [name for name in MOVED
                   if re.search(rf"^\s*{re.escape(name)}\s*:", styles, re.MULTILINE)]

    assert missing == [], f"这几个没搬过去：{missing}"
    assert left_behind == [], f"这几个还留在 globals.css 里定义着：{left_behind}"


def test_the_only_colour_literals_under_web_are_in_the_token_dir() -> None:
    """**全仓判据**：`web/` 下除 `_ds/tokens/` 之外没有颜色字面量。

    改前有 26 行（25 处定义 + 吉祥物那圈描边里的一个 `rgba`），
    全部集中在 `globals.css` 的药丸条那一段——它们是颜色的**第二个来源**，
    换板时不会跟着变，而屏上只显得「那条导航条与其余部分不是同一套颜色」。

    这条判据没有白名单：**白名单一开，下一个例外就有先例可循**。
    """
    skip = {"node_modules", ".next", "dist", "coverage", "__pycache__"}
    guilty: list[str] = []
    for path in sorted((REPO / "web").rglob("*")):
        if path.suffix not in (".css", ".ts", ".tsx") or any(
                part in skip for part in path.parts):
            continue
        if ".test." in path.name or ".spec." in path.name:
            continue
        if COLORS.parent in path.parents:            # `_ds/tokens/` 是唯一的家
            continue
        text = re.sub(r"/\*.*?\*/|//[^\n]*", "", path.read_text(encoding="utf-8"),
                      flags=re.DOTALL)
        for lineno, line in enumerate(text.splitlines(), start=1):
            if re.search(r"#[0-9a-fA-F]{6}\b", line) or re.search(
                    r"\brgba?\(\s*\d+", line):
                guilty.append(f"{path.relative_to(REPO).as_posix()}:{lineno}: "
                              f"{line.strip()[:70]}")

    assert guilty == [], f"`_ds/tokens/` 之外又有颜色字面量了：{guilty[:6]}"


def _nav_snapshot() -> tuple[dict[str, Any], dict[str, Any]]:
    """搬前那份是**开工前**拍的；搬后这份现拍（输入变了就重拍）。"""
    require_probe_evidence(BEFORE, ONLY_ON_THE_ORIGINAL_MACHINE)
    assert BEFORE.exists(), "缺搬家前那份取证——那是这条判据唯一的对照"
    stamp = hashlib.sha256(
        COLORS.read_bytes() + GLOBALS.read_bytes() + PROBE_TOOL.read_bytes()
    ).hexdigest()[:16]
    if AFTER.exists():
        cached = json.loads(AFTER.read_text(encoding="utf-8"))
        if cached.get("inputs_stamp") == stamp:
            return json.loads(BEFORE.read_text(encoding="utf-8")), dict(cached)
        AFTER.unlink()
    if not PWENV.exists():
        pytest.skip(f"本机没有 {PWENV}（playwright 恒在项目外）")
    with tempfile.TemporaryDirectory():
        done = subprocess.run(
            [str(PWENV), str(PROBE_TOOL), str(AFTER)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=REPO, check=False)
    if done.returncode != 0 or not AFTER.exists():
        pytest.skip(f"真栈没起或探针跑不动：{(done.stderr or done.stdout)[-600:]}")
    got = json.loads(AFTER.read_text(encoding="utf-8"))
    got["inputs_stamp"] = stamp
    AFTER.write_text(json.dumps(got, ensure_ascii=False, indent=1), encoding="utf-8")
    return json.loads(BEFORE.read_text(encoding="utf-8")), dict(got)


_COLOUR = re.compile(
    r"#[0-9a-fA-F]{3,8}\b|rgba?\([^)]*\)")


def _canon_colour(text: str) -> tuple[int, int, int, float]:
    """`#fff` / `#ffffffb8` / `rgb(255 255 255)` / `rgba(255, 255, 255, 0.72)`
    → 同一个四元组。**alpha 取两位小数**：`#ffffffb8` 是 184/255 = 0.7216，
    而它就是 `0.72` 被压出来的那个字节。"""
    text = text.strip()
    if text.startswith("#"):
        digits = text[1:]
        if len(digits) in (3, 4):
            digits = "".join(c * 2 for c in digits)
        parts = [int(digits[i:i + 2], 16) for i in range(0, len(digits), 2)]
        r, g, b = parts[:3]
        alpha = (parts[3] / 255) if len(parts) == 4 else 1.0
        return (r, g, b, round(alpha, 2))
    nums = re.findall(r"[\d.]+", text)
    r, g, b = (int(float(n)) for n in nums[:3])
    alpha = float(nums[3]) if len(nums) > 3 else 1.0
    return (r, g, b, round(alpha, 2))


def _canon(value: str) -> str:
    """把一串 CSS 值里的每个颜色都换成规范形，其余原样。

    **为什么不能逐字比 token 文本**（第一版判据就是那么写的，实测被它抓到）：
    `globals.css` 过 Next 的 CSS 管线，`rgba(255, 255, 255, 0.72)` 被压成
    `#ffffffb8`；而 `_ds/tokens/colors.css` 是 `web/public/` 下的**静态文件**，
    原样送到浏览器。于是搬家前后 11 个 token 的**文本**全都不同，
    而它们的**颜色**一个都没变——逐字比的话，量到的是两条管线的差别，不是搬家的差别。
    """
    return _COLOUR.sub(lambda m: str(_canon_colour(m.group(0))), value)


@pytest.mark.parametrize("theme", ("light", "dark"))
def test_moving_them_changed_no_computed_colour(theme: str) -> None:
    """**搬前搬后逐个相等**：两主题下药丸条与吉祥物身上真正生效的颜色。

    量两层：
    - **元素层**（`background-color` / `border-color` / `box-shadow` / `color`）
      判**逐字相同**——浏览器算出来的值，两条管线在这一层已经合流，
      它就是「屏上有没有变」的直接证据；
    - **token 层**判**颜色相同**（规范化后），理由见 `_canon`。
      只量元素层的话，「变量还在但没人读它了」会被判成通过。
    """
    before, after = _nav_snapshot()
    was, now = before[theme], after[theme]

    assert now["missing"] == [], f"这几个元素在屏上找不到了：{now['missing']}"
    for selector, props in was["elements"].items():
        for prop, value in props.items():
            assert now["elements"][selector][prop] == value, (
                f"[{theme}] {selector} 的 {prop}："
                f"搬前 {value} → 搬后 {now['elements'][selector][prop]}")
    for name, value in was["tokens"].items():
        assert _canon(now["tokens"].get(name, "")) == _canon(value), (
            f"[{theme}] {name}：搬前 {value} → 搬后 {now['tokens'].get(name)}")


def test_the_colour_comparison_is_not_blind_to_a_real_change() -> None:
    """**阴性对照**：规范化 NEVER 把「颜色真变了」也抹平。

    上一条把 token 层放宽成「颜色相同」，那就得证明它还咬得住——
    否则那条判据就成了「只要还是个颜色就算过」。
    """
    assert _canon("#ffffffb8") == _canon("rgba(255, 255, 255, 0.72)")
    assert _canon("#fff") == _canon("rgb(255 255 255)")
    assert _canon("#ffffffb8") != _canon("rgba(255, 255, 255, 0.5)"), "透明度变了没抓住"
    assert _canon("#fff") != _canon("rgb(254 255 255)"), "差一个色阶没抓住"
    assert _canon("0 6px 20px #1b2a2e1f") != _canon("0 8px 20px #1b2a2e1f"), (
        "投影的形状变了没抓住")


def test_the_after_shot_is_a_real_shot() -> None:
    """搬后那份取证不是空壳：两主题 × 13 个 token × 6 个元素都在。"""
    _before, after = _nav_snapshot()

    for theme in ("light", "dark"):
        assert len(after[theme]["tokens"]) >= 13, after[theme]["tokens"]
        assert len(after[theme]["elements"]) == 6, after[theme]["elements"]


# ═════════════════ ④ 四张单全部按新规矩关


@pytest.mark.parametrize("ticket", (
    "WARN-TOKEN-NAME-CONTRADICTS-DEC-060.md",
    "PLAZA-UPPER-BOUND-CONTRADICTS-ENTRY-04.md",
    "NAV-MASCOT-COLOURS-ARE-A-SECOND-SOURCE.md",
    "DEC-060-TEXT-IS-STEWARD-AUTHORED-OPTIONS.md",
))
def test_each_ticket_is_closed_by_the_new_rules(ticket: str) -> None:
    """状态行三样齐（状态 · 日期 · 卡号）+ `## 关闭` 那一节点名本卡。

    直接删掉单子的话，这段经过就没了；关掉而不点名的话，
    下一个人问「是谁在哪一天关的」没有答案。
    """
    text = (BLOCKED / ticket).read_text(encoding="utf-8")
    status = [ln for ln in text.splitlines() if ln.startswith("**状态**")]

    assert status, f"{ticket} 没有机读状态行"
    assert "closed" in status[0], status[0]
    assert "2026-08-12" in status[0], status[0]
    assert "TAIL-01" in status[0], status[0]
    assert re.search(r"^##\s*关闭", text, flags=re.MULTILINE), f"{ticket} 缺「## 关闭」"
    assert "TAIL-01" in text.split("## 关闭", 1)[1], f"{ticket} 关闭那节没点名本卡"


def test_the_plaza_ticket_says_the_card_was_wrong_not_the_discipline() -> None:
    """广场那张单要写清**是卡面错、既有纪律对**。

    只写「关了」的话，下一批出卡的人会照着同一条 acceptance 再写一次。
    """
    text = (BLOCKED / "PLAZA-UPPER-BOUND-CONTRADICTS-ENTRY-04.md").read_text(
        encoding="utf-8")
    closing = text.split("## 关闭", 1)[1]

    assert "卡面" in closing and "错" in closing
    assert "既有纪律" in closing


def test_the_wording_ticket_records_who_owns_the_text() -> None:
    """`DEC-060` 措辞那张单关掉时要说清：**steward 认下措辞**，条目一个字没改。

    `DECISIONS-v04.md` 是 append-only——回头改既有条目是本仓判过的死手
    （`DEC-056` 立的判例）。
    """
    text = (BLOCKED / "DEC-060-TEXT-IS-STEWARD-AUTHORED-OPTIONS.md").read_text(
        encoding="utf-8")
    closing = text.split("## 关闭", 1)[1]
    decisions = (REPO / "DECISIONS-v04.md").read_text(encoding="utf-8")

    assert "steward" in closing
    assert "append-only" in closing or "NEVER 重写" in closing
    assert "steward 拟的选项文本" in decisions, "DEC-060 条目里那句出处不见了"
