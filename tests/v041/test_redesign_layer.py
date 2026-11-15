"""REDESIGN-01：新设计层（`web/app/redesign.css`）自己的几条纪律。

owner 2026-11-14 要的是「从 0 重新设计」。新设计是压在 `globals.css` 之上的一整层：
新 token、侧边导航外壳、各屏组件。这一层长什么样是设计决定，判据不管；
判据管的是**它出了错而屏上看不出来**的那几种情形。

| 守什么 | 不守的话 |
|---|---|
| 它排在 `globals.css` 之后 | 顺序一倒，整层被旧样式盖回去，屏上是新旧混杂的一团 |
| 这一层里一个色值都没有 | 颜色只有一个来源（`_ds/tokens/colors.css`）；写在这里的色值换主题时不跟着翻 |
| 暗色两条通道取值相同 | 「跟随系统」与「手动选暗色」长得不一样，而两者本该是同一套 |
| 新板的文字对比度 | 好看而读不清 |
| 覆盖的 token 名字都对得上 | 拼错一个字母的 token 什么都不覆盖，也不报错 |
| 窄屏标签的字是视觉隐藏 | `display: none` 会让链接在读屏里没有名字 |
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
LAYER = REPO / "web" / "app" / "redesign.css"
LAYOUT = REPO / "web" / "app" / "layout.tsx"
DS_TOKENS = (REPO / "web" / "public" / "_ds"
             / "flint-design-system-8fd95ba3-cf31-49b6-b9d8-c863f3dc2724" / "tokens")
GLOBALS = REPO / "web" / "app" / "globals.css"
COLORS = DS_TOKENS / "colors.css"

# 这一层新引入的 token（`_ds` 与 `globals.css` 里都没有的）。写在这里是为了让下面那条
# 「名字都对得上」的判据分得清「新加的」与「拼错的」。
NEW_TOKENS = {"--nav-w", "--bar-h", "--tabbar-h", "--tab-count"}

COLOUR = re.compile(r"#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(")


def _css() -> str:
    return LAYER.read_text(encoding="utf-8")


def _strip_comments(css: str) -> str:
    return re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)


def _block(css: str, selector: str) -> dict[str, str]:
    """某个选择器那一块里的 `--token: value`。选择器逐字匹配，取它后面第一对花括号。"""
    start = css.index(selector)
    body = css[css.index("{", start) + 1:css.index("}", start)]
    return {m.group(1): m.group(2).strip()
            for m in re.finditer(r"(--[\w-]+)\s*:\s*([^;]+);", body)}


def _luminance(hex_colour: str) -> float:
    value = hex_colour.lstrip("#")
    channels = [int(value[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast(a: str, b: str) -> float:
    hi, lo = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


# ───────────────────────── 一、它真的接上了，而且排在后面


def test_the_layer_is_imported_after_the_old_stylesheet() -> None:
    source = LAYOUT.read_text(encoding="utf-8")
    old, new = source.find('import "./globals.css"'), source.find('import "./redesign.css"')

    assert old != -1 and new != -1, "两份样式里有一份没接进根布局"
    assert new > old, "新设计层排在了旧样式之前——整层会被盖回去"


# ───────────────────────── 二、这一层里一个色值都没有


def test_the_layer_holds_no_colour_at_all() -> None:
    """新板的色值在 `_ds/tokens/colors.css`。这里出现一个，颜色就有了第二个来源。"""
    found = [m.group(0) for m in COLOUR.finditer(_strip_comments(_css()))]

    assert COLOUR.search("color: #fff"), "扫描面自证：这条正则认得出色值"
    assert found == [], f"新设计层里出现了裸色值：{found[:5]}"


# ───────────────────────── 三、暗色两条通道同值


def _colour_blocks() -> dict[str, list[dict[str, str]]]:
    """`colors.css` 里的四块：明色两块（缺省 + 手动选明），暗色两块（跟随系统 + 手动选暗）。"""
    css = _strip_comments(COLORS.read_text(encoding="utf-8"))
    out: dict[str, list[dict[str, str]]] = {"light": [], "dark": []}
    for m in re.finditer(r"(@media[^{]*\{\s*)?(:root|\[data-theme=\"(?:dark|light)\"\])\s*\{([^}]*)\}", css):
        dark = bool(m.group(1)) or "dark" in m.group(2)
        tokens = {t.group(1): t.group(2).strip()
                  for t in re.finditer(r"(--[\w-]+)\s*:\s*([^;]+);", m.group(3))}
        out["dark" if dark else "light"].append(tokens)
    return out


def test_the_palette_file_has_two_blocks_per_theme() -> None:
    blocks = _colour_blocks()

    assert len(blocks["light"]) == 2 and len(blocks["dark"]) == 2, (
        {k: len(v) for k, v in blocks.items()})


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_the_two_channels_of_a_theme_carry_the_same_palette(theme: str) -> None:
    """「跟随系统」与「手动选」本该是同一套颜色。只比调色板那 19 个 token——
    药丸条那几行两块之间本来就按需出现，不在这条里。"""
    first, second = _colour_blocks()[theme]
    names = {fg for fg, _bg in PAIRS} | {bg for _fg, bg in PAIRS}
    differ = sorted(n for n in names if first.get(n) != second.get(n))

    assert differ == [], f"[{theme}] 两条通道这几个 token 取值不同：{differ}"


# ───────────────────────── 四、文字对比度（WCAG 2.1，正文级 4.5）


PAIRS = [
    ("--ink", "--surface"), ("--ink", "--paper"), ("--ink", "--paper-2"),
    ("--ink-2", "--surface"), ("--ink-2", "--paper"), ("--ink-2", "--paper-2"),
    ("--ink-3", "--surface"), ("--ink-3", "--paper"), ("--ink-3", "--paper-2"),
    ("--indigo", "--surface"), ("--indigo", "--paper"), ("--indigo", "--sulfur-soft"),
    ("--on-accent", "--sulfur"), ("--ink", "--sulfur-soft"), ("--ink", "--ochre-soft"),
    ("--moss", "--moss-soft"), ("--moss", "--surface"),
    ("--ochre", "--ochre-soft"), ("--ochre", "--surface"),
    ("--rust", "--rust-soft"), ("--rust", "--surface"),
]


def _palette(theme: str) -> dict[str, str]:
    return _colour_blocks()[theme][0]


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_text_on_its_background_is_readable(theme: str) -> None:
    palette = _palette(theme)
    weak = [
        (fg, bg, round(_contrast(palette[fg], palette[bg]), 2))
        for fg, bg in PAIRS if _contrast(palette[fg], palette[bg]) < 4.5
    ]

    assert weak == [], f"[{theme}] 这几对不到 4.5：{weak}"


def test_the_contrast_ruler_can_fail() -> None:
    """阴性对照：尺子自己量得出「读不清」。没有这条，上面两条可能只是算式恒大于 4.5。"""
    assert _contrast("#f0f1f4", "#ff8a47") < 4.5, "浅字压橙底本该不及格"
    assert _contrast("#000000", "#ffffff") > 20


# ───────────────────────── 五、覆盖的 token 名字都对得上


def test_every_overridden_token_exists_or_is_declared_new() -> None:
    known = set(NEW_TOKENS)
    for path in [*sorted(DS_TOKENS.glob("*.css")), GLOBALS]:
        known |= set(re.findall(r"(--[\w-]+)\s*:", path.read_text(encoding="utf-8")))
    declared = set(_block(_strip_comments(_css()), ":root:root {"))

    unknown = sorted(declared - known)
    assert unknown == [], f"这几个 token 在 `_ds` 与 globals.css 里都找不到（拼错了？）：{unknown}"
    assert NEW_TOKENS <= declared, f"登记为新增的 token 没有定义：{sorted(NEW_TOKENS - declared)}"


def test_every_token_the_layer_reads_is_defined_somewhere() -> None:
    """反方向：这一层 `var(--x)` 读到的每个名字都有定义。读一个没定义的 token，那条声明静静失效。"""
    known = set(NEW_TOKENS)
    for path in [*sorted(DS_TOKENS.glob("*.css")), GLOBALS]:
        known |= set(re.findall(r"(--[\w-]+)\s*:", path.read_text(encoding="utf-8")))
    read = set(re.findall(r"var\((--[\w-]+)", _strip_comments(_css())))

    assert read, "扫描面自证：这一层应当读得到 token"
    assert sorted(read - known) == [], f"读了没定义的 token：{sorted(read - known)}"


# ───────────────────────── 六、退役的两样真的不显示；窄屏标签读得到


def test_the_retired_pieces_are_hidden_and_labels_stay_readable() -> None:
    css = _strip_comments(_css())

    retired = re.search(
        r"\.anime-nav__glow,\s*\.anime-nav__mascot\s*\{\s*display:\s*none;", css)
    assert retired, "发光块与吉祥物没有被收起来"

    label_rules = re.findall(r"\.anime-nav__label\s*\{([^}]*)\}", css)
    assert label_rules, "扫描面自证：找不到导航标签的规则"
    assert not [r for r in label_rules if re.search(r"display:\s*none", r)], (
        "导航标签用了 display: none——读屏里那条链接就没有名字了")
    assert any("clip-path" in r for r in label_rules), "窄屏下标签没有做成视觉隐藏"


def test_placeholder_text_takes_its_colour_from_the_palette() -> None:
    """`REDESIGN-04`：输入框的提示语 NEVER 留给浏览器的默认灰。

    暗色下量到的现象：模板工具那个输入框的提示语是 `rgb(117, 117, 117)`——Chrome 的默认值，
    不是本仓任何一个 token。它在亮色的白底上是 4.6，在暗色的 `--surface` 上是 4.0，不到 4.5。
    默认灰不随主题变，所以两个主题里总有一个不达标。

    这一层给所有提示语一条通用规则，取 `--ink-3`：那个 token 对 `--surface` / `--paper` /
    `--paper-2` 的对比度由 `test_text_on_its_background_is_readable` 在两个主题下守着。
    """
    # 要的是**通用**那一条：选择器整行就是 `::placeholder`。某个具体输入框自己的
    # `…textarea::placeholder` 不算——它只管那一个框，别的框照旧落回默认灰。
    rule = re.search(r"(?m)^::placeholder\s*\{([^}]*)\}", _strip_comments(_css()))
    assert rule, "设计层没有通用的 ::placeholder 规则，提示语会落回浏览器默认灰"
    block = {m.group(1): m.group(2).strip()
             for m in re.finditer(r"([\w-]+)\s*:\s*([^;]+);", rule.group(1))}

    assert block.get("color") == "var(--ink-3)", f"提示语的颜色不是 --ink-3：{block}"
    # 火狐给提示语叠了一层半透明；不写这一行，同一个 token 在火狐里会更淡。
    assert block.get("opacity") == "1"
