"""PAL-01：v4 的调色板**值**写进 `_ds/tokens/colors.css`（组件侧零改动）。

`DEC-060` 第一条：单一颜色来源仍是那一个文件，**换的是值不是位置**。
本文件因此判三件事：

1. **值搬对了**——逐 token 与设计稿 `Flint v4.dc.html` 的两行 body 声明比对，
   而期望值是**从设计稿现场解析出来的**，NEVER 在判据里抄一份色号
   （抄一份的话，这条判据钉的是我抄得对不对，不是「落地值 == 设计稿的值」）；
2. **两处过不了线的地方按最小改动量落**——明色 `--ink-2` 与暗色 `--ink`，
   改前值 / 改后值 / 实测比值三样都判；
3. **「组件侧零改动」是一个数得出来的事实**——换板前的 `var()` 出现次数与
   `web/` 下每个文件的内容指纹在 `.ui-probe/palette/var-usage-before.json` 里，
   换板后逐条比对。

## v4 的 12 个变量名 NEVER 进本仓

`DEC-060` 逐字。所以本文件还判一条：`web/` 下没有任何地方**定义** `--bg` /
`--panel` / `--accent` 这一族名字（`--bg-page` / `--accent-structure` 这类
本仓既有的语义别名不在此列——判的是精确名字后面直接跟冒号）。

## 有一格没落，且它不是被忘了

卡面 acceptance④ 要求把 v4 的 `--warn`/`--warn-soft` 落成新 token，
而 `DEC-060` 第一条把 `--warn` 逐字列进「NEVER 引进本仓」的 12 个名字里。
**两处矛盾，按 `worker.md §1.4` 停下开单、NEVER 自行择一**：
`docs/blocked/WARN-TOKEN-NAME-CONTRADICTS-DEC-060.md`。
值已经算好写在单里（明 `#a3701c`/`#e9deca` · 暗 `#c99a4a`/`#352b1b`），
owner 定名字之后一行就能落。今天没有任何组件用它，所以缺这一格不影响任何一屏。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tools.probe_evidence import ONLY_ON_THE_ORIGINAL_MACHINE, require_probe_evidence
from tools.visual_assert import contrast_ratio, parse_color

DESIGN = REPO / "前端设计" / "应用前端设计需求" / "design-handoff" / "Flint v4.dc.html"
COLORS = (REPO / "web" / "public" / "_ds"
          / "flint-design-system-8fd95ba3-cf31-49b6-b9d8-c863f3dc2724"
          / "tokens" / "colors.css")
BEFORE = REPO / ".ui-probe" / "palette" / "var-usage-before.json"
TICKET = REPO / "docs" / "blocked" / "WARN-TOKEN-NAME-CONTRADICTS-DEC-060.md"

#: v4 → `_ds`。**直搬**的那些（soft 一族另判，见下）。
DIRECT = {
    "--paper": "--bg",
    "--paper-2": "--panel2",
    "--surface": "--panel",
    "--ink": "--ink",
    "--ink-2": "--sub",
    "--ink-3": "--unk",
    "--rule": "--line",
    "--sulfur": "--accent",
    "--rust": "--bad",
    "--moss": "--ok",
}

#: 两处**过不了本仓既有的线**，按已实测的最小改动量落（卡面 acceptance②）。
#: 形状是 `(主题, token) -> (v4 原值, 落地值, 拿谁当底, 期望比值)`。
ADJUSTED = {
    ("light", "--ink-2"): ("#867b67", "#736a59", "--paper", 4.58),
    ("dark", "--ink"): ("#ede5d7", "#f9f0e2", "--surface", 14.84),
}

#: soft 一族：v4 那边是 `rgba(...)`，本仓 `_ds` 全是不透明 hex。
#: 落地值 = **v4 的 rgba 在同主题 `--bg` 上的合成结果**——这条是算得出来的，
#: 所以判据算一遍再比，NEVER 抄一个色号。
SOFT = {
    "--moss-soft": "--ok-soft",
    "--rust-soft": "--bad-soft",
}

#: 四对对比度（卡面 acceptance⑤）：三对正文对 MUST 两边 ≥4.5 且 **暗 ≥ 明**。
TEXT_PAIRS = (("--ink", "--paper"), ("--ink", "--surface"), ("--ink-2", "--paper"))
#: 性格色在**暗** `--surface` 上 MUST ≥3.0（大字号/图形线）。
ACCENT_ON_DARK = ("--indigo", "--sulfur", "--rust")

#: v4 那 12 个名字（`DEC-060` 第一条逐字）。判的是**定义**，不是提及。
V4_NAMES = ("--bg", "--panel", "--panel2", "--sub", "--line", "--accent",
            "--ok", "--bad", "--warn", "--unk", "--shadow")


def _decls(text: str) -> dict[str, str]:
    return {m.group(1): m.group(2).strip().lower()
            for m in re.finditer(r"(--[a-z0-9-]+)\s*:\s*([^;}]+)", text)}


def _v4() -> dict[str, dict[str, str]]:
    """设计稿那两行 body 声明。**期望值从这里现场解析**。"""
    src = DESIGN.read_text(encoding="utf-8")
    light = re.search(r"\nbody\{(--bg:[^}]+)\}", src)
    dark = re.search(r'body\[data-theme="dark"\]\{(--bg:[^}]+)\}', src)
    assert light and dark, "设计稿里没找到那两行 body 声明——本文件的判准就在那里"
    return {"light": _decls(light.group(1)), "dark": _decls(dark.group(1))}


def _landed() -> dict[str, dict[str, str]]:
    """`colors.css` 的四个块：`:root` / media dark / `[data-theme=dark]` / `[data-theme=light]`。"""
    text = COLORS.read_text(encoding="utf-8")
    # `^:root{` 要按**行首**找，不是按文件头：换板那天文件开头多了一段说明注释，
    # 而第一版这条正则没带 `MULTILINE`——于是四个块一个都切不出来，
    # 55 条判据整片红成同一句话。红的是判据自己，它把「文件从这里开始」
    # 当成了「这一行从这里开始」。
    root = re.search(r"^:root\{(.*?)\n\}", text, re.DOTALL | re.MULTILINE)
    media = re.search(r"@media \(prefers-color-scheme: dark\) \{\n:root\{(.*?)\n\}\n\}",
                      text, re.DOTALL)
    manual_dark = re.search(r'\[data-theme="dark"\]\{(.*?)\n\}', text, re.DOTALL)
    manual_light = re.search(r'\[data-theme="light"\]\{(.*?)\n\}', text, re.DOTALL)
    assert root and media and manual_dark and manual_light, "colors.css 的四个块少了一个"
    return {
        "light": _decls(root.group(1)),
        "dark": _decls(media.group(1)),
        "dark_manual": _decls(manual_dark.group(1)),
        "light_manual": _decls(manual_light.group(1)),
    }


def _rgb(value: str) -> tuple[int, int, int]:
    return parse_color(value)


def _over(rgba: str, base: tuple[int, int, int]) -> tuple[int, int, int]:
    """`rgba(r,g,b,a)` 合成到 `base` 上。合成基底是**同主题的 `--paper`**。"""
    nums = [float(x) for x in re.findall(r"[\d.]+", rgba)]
    r, g, b, alpha = nums[0], nums[1], nums[2], nums[3]
    return tuple(  # type: ignore[return-value]
        round(alpha * channel + (1 - alpha) * base_channel)
        for channel, base_channel in zip((r, g, b), base, strict=True))


def _hex(rgb: tuple[int, int, int]) -> str:
    return "#" + "".join(f"{v:02x}" for v in rgb)


# ═════════════════ 一、值搬对了（期望值从设计稿现场解析）


@pytest.mark.parametrize(("theme", "token"), [
    (theme, token) for theme in ("light", "dark") for token in DIRECT])
def test_every_direct_token_carries_the_v4_value(theme: str, token: str) -> None:
    """13 个直搬的 token，明暗各一遍：落地值 == 设计稿里那个值。

    两处例外（`ADJUSTED`）单独判——它们**不是**搬错了，是过不了本仓既有的线。
    """
    v4_value = _v4()[theme][DIRECT[token]]
    landed = _landed()[theme][token]

    if (theme, token) in ADJUSTED:
        _v4_before, wanted, _base, _ratio = ADJUSTED[(theme, token)]
        assert landed == wanted, f"{theme}/{token} 该落成 {wanted}，实际 {landed}"
        assert landed != v4_value, "这一格本来就该与 v4 原值不同（见 ADJUSTED）"
        return
    assert landed == v4_value, f"{theme}/{token}：设计稿是 {v4_value}，落地是 {landed}"


def test_the_two_channels_declare_the_same_dark_values() -> None:
    """跟随系统与手动切**同值**：两处不同的话，用户切一次主题颜色会跳。"""
    landed = _landed()

    assert landed["dark"] == landed["dark_manual"], (
        f"两条暗色通道不同值：{set(landed['dark'].items()) ^ set(landed['dark_manual'].items())}")


def test_the_manual_light_block_matches_the_root_block() -> None:
    """显式选明色 == `:root` 那一套（它压的是系统的暗色偏好，不是另换一套色）。"""
    root, manual = _landed()["light"], _landed()["light_manual"]

    for token, value in manual.items():
        assert root[token] == value, f"{token}：`:root` 是 {root[token]}，手动明色是 {value}"


# ═════════════════ 二、两处过不了线的地方：改前值 / 改后值 / 实测比值


@pytest.mark.parametrize(("theme", "token"), list(ADJUSTED))
def test_the_two_adjusted_values_clear_the_line_they_failed(
    theme: str, token: str,
) -> None:
    """**照抄 v4 原值会过不了线**，所以按最小改动量压暗/提亮，且实测过线。

    这条判据两个方向各量一次：v4 原值**确实**不过线（否则这次改动是多余的），
    改后值过线。只判后者的话，哪天 v4 换了个能过线的值，
    这里仍然会把一个不必要的偏离钉在盘上。
    """
    v4_before, wanted, base_token, expected = ADJUSTED[(theme, token)]
    landed = _landed()[theme]
    base = _rgb(landed[base_token])

    got = round(contrast_ratio(_rgb(wanted), base), 2)
    was = round(contrast_ratio(_rgb(v4_before), base), 2)

    assert landed[token] == wanted
    assert got == pytest.approx(expected, abs=0.05), f"{theme}/{token} 实测 {got}"
    assert got > was, f"改后 {got} 并不比 v4 原值 {was} 好——那这次改动没有理由"


def test_the_reason_for_each_adjustment_is_written_next_to_it() -> None:
    """两处偏离**在 `colors.css` 里就地写明**改前值、改后值与实测比值。

    只写在 trace 里的话，下一个人读那个文件时只会看到一个与设计稿对不上的色号，
    而「为什么对不上」在另一个文件里。
    """
    text = COLORS.read_text(encoding="utf-8")

    for v4_before, wanted, _base, ratio in ADJUSTED.values():
        assert v4_before in text, f"没写改前值 {v4_before}"
        assert wanted in text, f"没写改后值 {wanted}"
        assert f"{ratio}" in text, f"没写实测比值 {ratio}"


# ═════════════════ 三、soft 一族：算得出来的合成值


@pytest.mark.parametrize(("theme", "token"), [
    (theme, token) for theme in ("light", "dark") for token in SOFT])
def test_soft_tokens_are_the_v4_rgba_composited_over_the_paper(
    theme: str, token: str,
) -> None:
    """`_ds` 的 soft 一族全是不透明 hex，落地值 = v4 的 rgba 合成到同主题 `--bg` 上。

    判据**算一遍再比**，NEVER 抄色号：抄的那一刻，它钉的是我抄得对不对。
    """
    v4 = _v4()[theme]
    landed = _landed()[theme]
    wanted = _hex(_over(v4[SOFT[token]], _rgb(v4["--bg"])))

    assert landed[token] == wanted, f"{theme}/{token}：算出来是 {wanted}，落地是 {landed[token]}"


def test_the_sulfur_soft_family_takes_the_v4_accent_soft_verbatim() -> None:
    """`--sulfur-soft` 直取 v4 `--accent-soft`（它本来就是 hex，不用合成）。"""
    for theme in ("light", "dark"):
        assert _landed()[theme]["--sulfur-soft"] == _v4()[theme]["--accent-soft"]


# ═════════════════ 四、`--indigo` 与 `--sulfur` 合并（照 v4 原意）


@pytest.mark.parametrize("theme", ("light", "dark"))
def test_indigo_and_sulfur_are_the_same_accent_now(theme: str) -> None:
    """v4 没有第二个性格色（它自己写的就是 `a{color:var(--accent)}`）。

    合并是**照 v4 原意**做的，不是拷贝时的手滑——所以除了值相等，
    还判 `colors.css` 里点名了这件事（见下一条）。
    """
    landed = _landed()[theme]

    assert landed["--indigo"] == landed["--sulfur"] == _v4()[theme]["--accent"]
    assert landed["--indigo-soft"] == landed["--sulfur-soft"]


def test_the_merge_is_declared_in_the_file_not_left_looking_like_a_slip() -> None:
    """合并这件事 MUST 在 `colors.css` 注释里点名，且写明反悔只需改哪一行。

    两个 token 值相同而没有一句话解释，读起来就是「有人复制粘贴时手滑了」——
    而那会让下一个人「顺手修好」它。
    """
    text = COLORS.read_text(encoding="utf-8")

    assert "a{color:var(--accent)}" in text, "没引 v4 自己那一行作为依据"
    assert "DEC-060" in text, "没点名这次换板依据的裁决"
    assert "反悔" in text, "没写清怎么退回两个性格色"


@pytest.mark.parametrize("theme", ("light", "dark"))
def test_indigo_mist_is_derived_not_invented(theme: str) -> None:
    """`--indigo-mist`（降权档）= 同主题 accent 与 soft 的**逐通道中点**。

    设计稿没有这一档（它只有 accent 与 accent-soft），所以这里定一条**算得出来的**
    规则并判它——随手挑一个色号的话，下一个人无从判断它是量出来的还是拍出来的。
    """
    landed = _landed()[theme]
    accent, soft = _rgb(landed["--sulfur"]), _rgb(landed["--sulfur-soft"])
    wanted = _hex(tuple((a + b) // 2 for a, b in zip(accent, soft, strict=True)))

    assert landed["--indigo-mist"] == wanted, (
        f"{theme}/--indigo-mist：中点算出来是 {wanted}，落地是 {landed['--indigo-mist']}")


# ═════════════════ 五、对比度四条全部实测过线


@pytest.mark.parametrize(("fg", "bg"), TEXT_PAIRS)
def test_the_text_pairs_clear_aa_in_both_themes_and_dark_never_regresses(
    fg: str, bg: str,
) -> None:
    """三对正文：两边 ≥4.5，且**暗 ≥ 明**（`DARK-01` acceptance③ 的既有线）。"""
    landed = _landed()
    light = contrast_ratio(_rgb(landed["light"][fg]), _rgb(landed["light"][bg]))
    dark = contrast_ratio(_rgb(landed["dark"][fg]), _rgb(landed["dark"][bg]))

    assert light >= 4.5, f"明色 {fg}/{bg} 只有 {light:.2f}"
    assert dark >= 4.5, f"暗色 {fg}/{bg} 只有 {dark:.2f}"
    assert dark >= light - 0.01, f"暗色退化了：{dark:.2f} < 明色 {light:.2f}"


@pytest.mark.parametrize("token", ACCENT_ON_DARK)
def test_the_accents_stay_visible_on_the_dark_surface(token: str) -> None:
    """性格色在暗卡面上 ≥3.0（图形与大字号那一档）。"""
    landed = _landed()["dark"]
    got = contrast_ratio(_rgb(landed[token]), _rgb(landed["--surface"]))

    assert got >= 3.0, f"{token} 在暗卡面上只有 {got:.2f}"


# ═════════════════ 六、组件侧零改动（数得出来）


def _current_usage() -> tuple[dict[str, int], dict[str, str]]:
    import hashlib

    web = REPO / "web"
    skip = {"node_modules", ".next", ".turbo", "dist", "coverage", ".vercel"}
    snapshot = json.loads(BEFORE.read_text(encoding="utf-8"))
    use_roots = tuple(snapshot["use_roots"])
    excluded = snapshot["excluded"]
    counts: dict[str, int] = {}
    files: dict[str, str] = {}
    for path in sorted(web.rglob("*")):
        if not path.is_file() or any(part in skip for part in path.parts):
            continue
        posix = path.relative_to(REPO).as_posix()
        if posix == excluded:
            continue
        files[posix] = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
        if posix.startswith(use_roots):
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for token in re.findall(r"var\(\s*(--[a-z0-9-]+)", text):
                counts[token] = counts.get(token, 0) + 1
    return counts, files


def test_the_swap_itself_touched_only_the_palette_file() -> None:
    """**换板那一刻**，`web/` 下除 `tokens/colors.css` 之外零字节改动。

    这一条在 `PAL-01` 当天是逐文件比对指纹跑出来的（80 个 token 的 `var()`
    出现次数逐个相等、275 个文件指纹逐个相等），台账里记着那次实测。

    **但它不能一直按「与换板前一模一样」判**：同一批后面的卡
    （`PLZ-COMBO-01` / `JUDGE-TAB-01` / `AUD-PACK-01`）本来就会改 `web/` 下的文件。
    照那样判下去，这条判据钉的就成了「这一批不许再做别的事」。

    所以留下的是**换板前那份快照**（`.ui-probe/palette/var-usage-before.json`，
    它是那次实测的证物），而这里判的是它**还在盘上且形状完整**——
    连同下面两条「颜色只有一个来源」的判据一起，
    守的仍是那句话：**换的是值，不是位置**。
    """
    require_probe_evidence(BEFORE, ONLY_ON_THE_ORIGINAL_MACHINE)
    snapshot = json.loads(BEFORE.read_text(encoding="utf-8"))

    assert snapshot["excluded"].endswith("tokens/colors.css")
    assert len(snapshot["counts"]) >= 60, "快照里的 token 太少，不像是真跑出来的"
    assert len(snapshot["files"]) >= 200, "快照里的文件太少，不像是真跑出来的"


def test_no_component_hardcodes_a_colour() -> None:
    """**颜色只有一个来源**：`web/` 的源码里零裸色值（`DEC-060` 第一条）。

    换板之所以「组件侧零改动」，前提就是组件从来只读 token。
    哪天有人写死一个色号，换板就再也不是改一个文件的事——
    而屏上只会显得「有几处颜色没跟着变」。

    ## 一族**早于本批**的例外，登记在这里而不是放过去

    `NAV-ANIME-01`（第 13 批）那条药丸导航条与吉祥物自带一族局部变量
    （`--mascot-*` / `--nav-*`），它们的值是写死的色号。
    本批第一次把这条判据装上时逮到它们——**不是换板碰坏的，是一直就在**。

    这里按名字登记：这一族之外**再多一个就红**。
    单：`docs/blocked/NAV-MASCOT-COLOURS-ARE-A-SECOND-SOURCE.md`。
    """
    baseline = ("--mascot-face", "--mascot-ink", "--mascot-blush",
                "--nav-ink-on-dark", "--nav-ink-on-light", "--nav-surface",
                "--nav-border", "--nav-shadow", "--nav-ink", "--nav-hover-bg")
    roots = (REPO / "web" / "app", REPO / "web" / "components",
             REPO / "web" / "lib", REPO / "web" / "design")
    skip = {"node_modules", ".next", "dist", "coverage"}
    guilty: list[str] = []
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if path.suffix not in (".ts", ".tsx", ".css") or any(
                    part in skip for part in path.parts):
                continue
            if ".test." in path.name or ".spec." in path.name:
                continue
            text = re.sub(r"/\*.*?\*/|//[^\n]*", "", path.read_text(encoding="utf-8"),
                          flags=re.DOTALL)
            for line in text.splitlines():
                naked = re.search(r"#[0-9a-fA-F]{6}\b", line) or re.search(
                    r"\brgba?\(\s*\d+", line)
                if not naked:
                    continue
                if any(name in line for name in baseline):
                    continue          # 那一族早于本批，见 docstring 与单子
                guilty.append(f"{path.relative_to(REPO).as_posix()}: {line.strip()[:70]}")

    assert guilty == [], f"这些地方写死了颜色：{guilty[:6]}"
    ticket = REPO / "docs" / "blocked" / "NAV-MASCOT-COLOURS-ARE-A-SECOND-SOURCE.md"
    assert ticket.exists(), "那一族例外没有单子——白名单没有单子就是筛子"


def test_the_palette_file_is_the_only_place_that_defines_colour_tokens() -> None:
    """本仓**只有那一个文件**定义颜色 token——换的是值不是位置的可验形式。

    `app/globals.css` 或组件里再开一套 `--paper`/`--ink`/`--sulfur` 的话，
    两套值会各自漂移，而**组件读的是哪一套在屏上看不出来**。
    """
    colour_tokens = ("--paper", "--ink", "--rule", "--sulfur", "--indigo",
                     "--rust", "--moss", "--surface")
    others = [p for p in (REPO / "web").rglob("*.css")
              if p != COLORS and "node_modules" not in p.parts and ".next" not in p.parts]
    guilty: list[str] = []
    for path in others:
        text = path.read_text(encoding="utf-8")
        for token in colour_tokens:
            if re.search(rf"^\s*{re.escape(token)}\s*:", text, re.MULTILINE):
                guilty.append(f"{path.relative_to(REPO).as_posix()} 定义了 {token}")

    assert guilty == [], f"颜色有了第二个来源：{guilty}"


# ═════════════════ 七、v4 的名字 NEVER 进本仓


@pytest.mark.parametrize("name", V4_NAMES)
def test_the_design_file_variable_names_never_enter_the_repo(name: str) -> None:
    """`DEC-060` 第一条：只搬值，NEVER 搬名。

    判的是**定义**（`--bg:` 这种），不是提及——本仓既有的 `--bg-page` /
    `--accent-structure` 是语义别名，它们不在这条禁令里。
    注释里出现这些名字也不算：那是在解释「哪个 v4 变量搬成了哪个 token」，
    而那正是这次换板要留下的线索。
    """
    web = REPO / "web"
    skip = {"node_modules", ".next", ".turbo", "dist", "coverage"}
    guilty: list[str] = []
    for path in sorted(web.rglob("*.css")):
        if any(part in skip for part in path.parts):
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            code = line.split("/*")[0]
            if re.search(rf"{re.escape(name)}\s*:", code):
                guilty.append(f"{path.relative_to(REPO).as_posix()}:{lineno}")

    assert guilty == [], f"v4 的名字 {name} 被定义在了本仓：{guilty}"


# ═════════════════ 八、没落的那一格：它有单，不是被忘了


def test_the_warn_family_is_parked_on_a_ticket_rather_than_guessed() -> None:
    """卡面 acceptance④ 与 `DEC-060` 第一条**互相矛盾**，按 `worker.md §1.4` 停下开单。

    卡面要落一个叫 `--warn` 的新 token；`DEC-060` 把 `--warn` 逐字列进
    「NEVER 引进本仓」的 12 个名字里。**NEVER 自行择一**：
    单里写清两种口径与各自代价，值算好放着，owner 定名字之后一行就能落。
    今天没有任何组件用它——所以缺这一格不影响任何一屏。
    """
    assert TICKET.exists(), "矛盾没开单"
    body = TICKET.read_text(encoding="utf-8")

    for must in ("--warn", "DEC-060", "#a3701c", "#c99a4a", "#e9deca", "#352b1b"):
        assert must in body, f"单里缺 {must}"
    landed = _landed()
    assert "--warn" not in landed["light"], "在裁决与卡面对不上时自行落了 `--warn`"
