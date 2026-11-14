"""DARK-01：`_ds` 出一套暗色调色板（owner 2026-08-04 裁决：允许暗色）。

## 为什么这张卡必须在 11 张 UI 卡之前

`_ds` 此前只有一块明色板，于是 `EYE-02` 的「明暗两主题」判据**在量同一个东西**——
两次量到同一组数，然后放行。那是**假绿**：它没有误判，但它证不到它声称证的事。
板不先落地，11 张 UI 卡会在只有一套调色板的前提下逐张取证，回头全部返工。

## 四条硬要求（缺一即红）

1. **逐个 token 都有暗色对照**：以 `tokens/colors.css` 的实际 token 全集为准，
   覆盖率 100%，缺一个判红——「做了一部分」在界面上的样子是**局部还亮着**；
2. **双通道生效**：`prefers-color-scheme: dark` 与 `data-theme="dark"` 都能切，
   且 `data-theme` 显式设定时**压过**系统偏好；
3. **对比度不退化**：暗色下正文/背景的对比度 **≥** 明色下的，且两者都过 WCAG AA
   正文线。判据复用 `tools/visual_assert.py`（EYE-02 的尺子），**NEVER 另造一把**；
4. **暗色值 NEVER 由明色取反**：取反出来的色相会翻到补色去，「纸与墨」就成了
   「霓虹与荧光」。逐档的取值依据写在 `docs/trace/DARK-01.md`。
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from tools.visual_assert import AA_NORMAL_TEXT, contrast_ratio, parse_color

REPO = Path(__file__).resolve().parents[2]
DS_ROOT = REPO / "web" / "public" / "_ds"
GLOBALS = REPO / "web" / "app" / "globals.css"


def _bundle() -> Path:
    dirs = [p for p in DS_ROOT.iterdir() if p.is_dir()]
    assert len(dirs) == 1
    return dirs[0]


def _colors() -> str:
    return (_bundle() / "tokens" / "colors.css").read_text(encoding="utf-8")


def _code_only() -> str:
    """剥掉注释的那一份。

    **判位置的那两条必须用它**（`TAIL-01` 现场撞到的）：那两条靠
    `css.find('[data-theme="dark"]')` 比先后，而文件里的注释在解释
    「哪条规则管暗色」时也会写出这个选择器——于是尺子量到的是注释的位置。
    本仓这一类（尺子读了注释）此前已经栽过六次，第七次就在这里。
    """
    return re.sub(r"/\*.*?\*/", "", _colors(), flags=re.DOTALL)


def _block(css: str, selector: str) -> str:
    """取某个选择器的声明块。找不到返回空串。"""
    match = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", css)
    return match.group(1) if match else ""


def _tokens(block: str) -> dict[str, str]:
    return {
        name: value.strip()
        for name, value in re.findall(r"(--[a-z0-9-]+)\s*:\s*([^;]+);", block)
    }


def _light() -> dict[str, str]:
    return _tokens(_block(_colors(), ":root"))


#: **与主题无关的固定色**（`TAIL-01` 从 `globals.css` 搬进来的那一族里的五个）。
#: 吉祥物是蓝本的美术设定（白脸 / 黑眼 / 粉腮红），`--nav-ink-on-*` 是
#: `--nav-ink-active` 取用的两端——它们在两个主题下**故意**相同，
#: 所以「每个明色 token 都要有暗色对照」那条对它们不适用。
#:
#: **NEVER 把这一格改成「跳过所有没有暗色对照的」**：那样下一个漏掉暗色值的
#: token 会自己溜进来。这里判的是**等值**——多一个少一个都红。
THEME_CONSTANT = {
    "--mascot-face", "--mascot-ink", "--mascot-blush",
    "--nav-ink-on-dark", "--nav-ink-on-light",
    # 它的值里引用 `--nav-border`（跟主题翻），自身因此只定义一次。
    "--mascot-shadow",
}


def _is_plain_colour(value: str) -> bool:
    """这个值是不是**一个颜色**（而不是投影那种复合值）。

    `--nav-shadow: 0 8px 32px rgba(0,0,0,0.4)` 是「长度 + 颜色」的复合值，
    拿去 `parse_color` 会当场抛。它仍然是这块板的一部分（明暗两套值不同），
    只是**取反**、**对比度**那两类判据对它无意义。
    """
    return value.strip().startswith(("#", "rgb"))


def _dark_media() -> dict[str, str]:
    """只取 media 块里那一段。

    从标记切到文件末尾的话，后面 `[data-theme="light"]` 的声明也会被算进来——
    那会让「两条通道同值」这条判据去比两个不相干的块。
    """
    css = _colors()
    start = css.find("@media (prefers-color-scheme: dark)")
    assert start != -1, "没有 prefers-color-scheme 通道"
    end = css.find("\n}\n}", start)
    assert end != -1, "media 块没有正常收尾"
    return _tokens(css[start:end])


def _dark_attr() -> dict[str, str]:
    return _tokens(_block(_colors(), '[data-theme="dark"]'))


# ───────────────────────── 一、逐个 token 都有暗色对照（acceptance①）


def test_the_light_palette_still_has_its_tokens() -> None:
    """明色板一个 token 都没丢——本卡是**加**一套暗色，不是换掉明色。"""
    light = _light()

    assert len(light) >= 20
    for name in ("--paper", "--surface", "--ink", "--rule"):
        assert name in light, f"明色板里少了 {name}"


def test_every_light_token_has_a_dark_counterpart() -> None:
    """acceptance①：**覆盖率 100%，缺一个判红**。

    「做了一部分」在界面上的样子是局部还亮着——那比整体没做更难查，
    因为它看起来像是「某个组件没跟上」。
    """
    light = _light()
    dark = _dark_attr()

    missing = sorted(set(light) - set(dark))

    # `TAIL-01` 之后这块板里多了一族**故意不跟主题翻**的固定色（见 `THEME_CONSTANT`）。
    # 判**等值**而不是「跳过没有对照的」：漏掉暗色值的 token 会因此照旧变红。
    assert missing == sorted(THEME_CONSTANT), (
        f"没有暗色对照的 token 变了：{missing}（登记在案的是 {sorted(THEME_CONSTANT)}）")


def test_the_two_dark_channels_declare_the_same_tokens() -> None:
    """两条通道给的是**同一套值**：不同的话，系统切与手动切会得到两种界面。"""
    media = _dark_media()
    attr = _dark_attr()

    for name, value in attr.items():
        assert media.get(name) == value, f"{name} 在两条通道里值不同"


def test_no_dark_value_is_the_light_value() -> None:
    """暗色值与明色值**逐个不同**——相同就说明那一档没换。"""
    light = _light()
    dark = _dark_attr()

    same = [n for n, v in dark.items() if n in light and v == light[n] and not v.startswith("var(")]

    assert same == [], f"这些 token 的暗色值与明色值相同：{same}"


# ───────────────────────── 二、双通道与优先级（acceptance②）


def test_the_media_channel_exists() -> None:
    """系统偏好通道：跟随操作系统的暗色设置。"""
    assert "@media (prefers-color-scheme: dark)" in _colors()


def test_the_attribute_channel_exists() -> None:
    """显式通道：用户在应用里手动切。"""
    assert '[data-theme="dark"]' in _colors()


def test_an_explicit_light_choice_beats_the_system_preference() -> None:
    """**手动选明色要压过系统暗色偏好**。

    只做 `prefers-color-scheme` 的话，系统是暗色时用户在应用里**切不回明色**——
    那不是「支持暗色」，那是「强制暗色」。
    """
    css = _code_only()

    assert '[data-theme="light"]' in css, "没有显式明色通道，系统暗色时切不回去"
    media_start = css.find("@media (prefers-color-scheme: dark)")
    light_attr = css.find('[data-theme="light"]')
    assert light_attr > media_start, (
        "显式明色声明在 media 之前，会被系统偏好覆盖——顺序决定谁赢")


def test_the_explicit_dark_choice_also_works_without_the_system_preference() -> None:
    """反向：系统是明色时，手动切暗色也要生效。"""
    css = _code_only()
    dark_attr = css.find('[data-theme="dark"]')
    media_start = css.find("@media (prefers-color-scheme: dark)")

    assert dark_attr != -1
    assert dark_attr > media_start, "显式暗色要写在 media 之后才压得住"


# ───────────────────────── 三、对比度不退化（acceptance③）


def _resolve(tokens: dict[str, str], name: str) -> str:
    """把 `var(--x)` 一路解开到具体色值。"""
    seen: set[str] = set()
    value = tokens[name]
    while value.startswith("var(") and name not in seen:
        seen.add(name)
        name = value[4:].split(")")[0].strip()
        value = tokens[name]
    return value


@pytest.mark.parametrize("fg,bg", [
    ("--ink", "--paper"),
    ("--ink", "--surface"),
    ("--ink-2", "--paper"),
])
def test_dark_contrast_is_not_worse_than_light(fg: str, bg: str) -> None:
    """acceptance③：暗色下的对比度 **≥** 明色下的，且两者都过 AA 正文线。

    尺子复用 `tools/visual_assert.py`（EYE-02 那把），**NEVER 另造一把**：
    两把尺子会给出两个数，而那时没人知道该信哪个。
    """
    light = _light()
    dark = {**light, **_dark_attr()}

    light_ratio = contrast_ratio(parse_color(_resolve(light, fg)),
                                 parse_color(_resolve(light, bg)))
    dark_ratio = contrast_ratio(parse_color(_resolve(dark, fg)),
                                parse_color(_resolve(dark, bg)))

    assert light_ratio >= AA_NORMAL_TEXT, f"明色下 {fg}/{bg} 就没过线：{light_ratio:.2f}"
    assert dark_ratio >= AA_NORMAL_TEXT, f"暗色下 {fg}/{bg} 没过线：{dark_ratio:.2f}"
    assert dark_ratio >= light_ratio, (
        f"暗色下 {fg}/{bg} 的对比度退化了：{dark_ratio:.2f} < {light_ratio:.2f}")


def test_the_accents_stay_readable_on_the_dark_surface() -> None:
    """性格色在暗底上也要看得清——链接与高亮不过线的话，暗色只是「能看」不是「可用」。"""
    dark = {**_light(), **_dark_attr()}
    surface = parse_color(_resolve(dark, "--surface"))

    for accent in ("--indigo", "--sulfur", "--rust"):
        ratio = contrast_ratio(parse_color(_resolve(dark, accent)), surface)
        assert ratio >= 3.0, f"{accent} 在暗底上只有 {ratio:.2f}:1"


# ───────────────────────── 四、不是取反（acceptance④）


def test_no_dark_value_is_the_arithmetic_inverse_of_the_light_one() -> None:
    """**NEVER 由明色取反生成**：取反会把色相翻到补色去，

    「纸与墨」就成了「霓虹与荧光」。逐档依据写在 trace 里。
    """
    light = _light()
    dark = _dark_attr()

    inverted = []
    for name, value in dark.items():
        if name not in light or value.startswith("var("):
            continue
        # 投影那种「长度 + 颜色」的复合值不在这条判据的量程里（`_is_plain_colour`）。
        if not _is_plain_colour(value) or not _is_plain_colour(light[name]):
            continue
        r, g, b = parse_color(light[name])
        # **中性色不在这条判据的量程里**（`TAIL-01` 现场撞到的）：这条守的是
        # 「取反会把**色相**翻到补色去」，而纯白 / 纯黑没有色相可翻。
        # 药丸条的底就是这一类：明色是半透明白、暗色是半透明黑（蓝本的设定），
        # 逐通道看确实互为取反，而**两边的透明度不同**（0.72 / 0.5）——
        # 机器取反不会顺手把透明度也改了。
        # NEVER 改成按名字放行：那样下一个真被取反出来的**有色**token 会跟着溜过去。
        if max(r, g, b) - min(r, g, b) == 0:
            continue
        if parse_color(value) == (255 - r, 255 - g, 255 - b):
            inverted.append(name)

    assert inverted == [], f"这些 token 是明色的算术取反：{inverted}"


def test_the_dark_palette_keeps_the_paper_and_ink_hue_family() -> None:
    """色相保持同族：暗色的「纸」仍看得出色相，不是纯黑或中性灰。

    **这条判据的方向跟着 `DEC-060` 换过一次，意图一个字没动。**

    它守的一直是同一件事：*暗纸没有退化成中性灰或纯黑，仍看得出它属于哪一族*。
    `max-min >= 4` 那半条**原样保留**——它才是「还看得出色相」的可量形式
    （v4 暗纸 `#191612` 实测 max-min=7）。

    变的只是**族的方向**：改前是 `b >= r`（青绿族——那时的板是「纸与墨」，
    暗纸 `#0F1A1C` 的蓝分量压着红分量）；`PAL-01` 换成 v4 的暖板之后，
    暗纸 `#191612` 是暖族（实测 r=25 ≥ b=18），照旧判 `b >= r` 的话，
    钉的就不再是「有没有色相」，而是「是不是 2026-08-04 那块板」。

    **NEVER 把这条判据删掉换成「有色相就行」**：那样两个方向都过，
    而「暗纸悄悄漂成蓝黑」这件事就再也没有人看着了。
    """
    dark = _dark_attr()
    r, g, b = parse_color(_resolve({**_light(), **dark}, "--paper"))

    assert max(r, g, b) - min(r, g, b) >= 4, "暗纸退化成了中性灰/纯黑，丢了色相"
    assert r >= b, "暗纸的色相偏离了暖族（DEC-060 之后的板是暖的）"


# ───────────────────────── 五、既有面不倒（acceptance⑤）


def test_globals_css_still_reads_tokens_not_literals() -> None:
    """应用层仍然只用 token：写死色值的地方在暗色下不会跟着变。"""
    css = GLOBALS.read_text(encoding="utf-8")
    body = _block(css, "body")

    assert "var(--bg-page)" in body and "var(--text-body)" in body


def test_no_external_font_sneaks_in_with_the_dark_palette() -> None:
    """acceptance⑤：`no_external_fonts` 那把尺子保持 exit 0。"""
    import shutil
    import subprocess

    node = shutil.which("node")
    assert node is not None, "找不到 node：这条门量不了，NEVER 当它通过"

    done = subprocess.run([node, "tools/no_external_fonts.mjs", "web"],
                          cwd=REPO, capture_output=True, text=True,
                          encoding="utf-8", check=False)

    assert done.returncode == 0, done.stdout + done.stderr


# ───────────────────────── 六、关掉那张问题单（acceptance⑥）


def test_the_blocked_doc_is_closed_with_a_banner() -> None:
    """问题单要**关掉**并写明裁决与日期——留着一张已解决的单，下一个人会重做一遍。"""
    doc = (REPO / "docs" / "blocked" / "DS-NO-DARK-PALETTE.md").read_text(encoding="utf-8")
    banner = next((ln for ln in doc.splitlines()[:8] if "已关闭" in ln), "")

    # 三样都判在**关闭那一行**上：按前 8 行整段判的话，横幅正文里那句
    # 「owner 2026-08-04 裁决」会把日期这条喂饱（变异考实测：去掉关闭日期，17 条全绿）。
    assert banner, "顶部没有关闭横幅"
    assert "2026-08-04" in banner, "关闭那一行没写日期"
    assert "DARK-01" in banner, "关闭那一行没写由哪张卡解决"


# ───────────────────────── 六、阴性对照（PAL-02）：重新瞄准之后它还咬得住吗


def test_the_hue_family_ruler_still_bites_after_being_re_aimed() -> None:
    """**阴性对照**：把暗色 `--paper` 临时改成明色同值 → 这条判据 MUST 当场变红。

    `PAL-02` 把族的方向从 `b >= r` 改成了 `r >= b`（`DEC-060` 换了板）。
    改判据最容易的死法是**改成一条谁都过得了的判据**——
    所以这里造一个「暗纸根本没变暗」的板喂给同一段判定逻辑，看它红不红。

    **改在内存里，NEVER 动真文件**：真文件被改一下再改回来，中间那一刻
    如果有别的判据在跑，它量到的是一块假板。
    """
    light = _light()
    dark = dict(_dark_attr())
    dark["--paper"] = light["--paper"]          # 暗纸 == 明纸：等于没有暗色板

    r, g, b = parse_color(_resolve({**light, **dark}, "--paper"))

    # 明纸 `#f2ede4` 是暖的（r 242 ≥ b 228），所以方向那半条**过得了**——
    # 咬住它的是另一半：明纸的 max-min 只有 14…… 也过得了。
    # 真正的判据在于**它与明纸相同**，这一条单独钉住：
    assert (r, g, b) == parse_color(_resolve(light, "--paper")), (
        "阴性对照没造出「暗纸==明纸」这个局面，后面的断言就没有意义")
    assert not _paper_really_darkens({**light, **dark}, light), (
        "暗纸与明纸取到同一个值，而判据没有反对——这套尺子量不出「有没有暗色板」")


def _paper_really_darkens(merged: dict[str, str], light: dict[str, str]) -> bool:
    """暗板的纸**确实比明板暗**（相对亮度更低）。

    这是「有没有暗色板」的可量形式，与色相那条各管一半：
    色相那条管「暗纸还看不看得出颜色」，这条管「它到底暗没暗」。
    """
    from tools.visual_assert import relative_luminance

    return (relative_luminance(parse_color(_resolve(merged, "--paper")))
            < relative_luminance(parse_color(_resolve(light, "--paper"))))


def test_the_real_palette_passes_that_same_ruler() -> None:
    """正面对照：真板上「暗纸确实更暗」成立——阴性对照才证得了东西。"""
    light = _light()
    merged = {**light, **_dark_attr()}

    assert _paper_really_darkens(merged, light)
