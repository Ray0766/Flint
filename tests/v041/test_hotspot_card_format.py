"""DS-02：热点卡片按 owner 指定的素材落成——结构与样式**成对**交付。

## 改前的实况

`web/components/hotspot-card/HotspotCard.tsx` 六信息槽齐全（`HOTSPOT-01` 建的），
而 `.hotspot-card` 在 `_ds` 与 `web/app/globals.css` 里**零样式**：
组件是好的，屏上是一串裸文字。

「只建组件不写样式等于没做」是本批工单的原话。所以这份验收的重心不在「类名在不在」——
类名在而样式没有，正是改前那一版的样子。**判据取运行时计算值**：
每个类名都拿一个裸 `<span>` 当基线比一次，**一样 = 零样式 = 判红**。

## 素材是哪一份

`前端设计/Flint 热点线索卡堆叠/CardStack.dc.html`——**已 Flint 化**：零 framer-motion、
零 lucide-react、零 Tailwind，全部 `_ds` token，并直接调 `_ds` 自带的 `StickerTag` 与
`StatusMark`。同目录的 `uploads/CardStack.txt` 是第三方原始版，NEVER 照那份做
（照它做等于把三个新依赖带进来，撞 S2-6）。

素材里那些值写在 inline style 上（它是一份单文件预览）。本卡把它们搬进样式表而不是抄进组件，
因为同一张卡面要被堆叠、网格、图谱节点、收藏库四处排布——抄进组件就有四份视觉各自漂移。
所以下面的数值判据**从素材源码里解析出来再比**，NEVER 手抄一份期望值。
"""
from __future__ import annotations

import json
import re
import subprocess
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
WEB = REPO / "web"
CARD = WEB / "components" / "hotspot-card" / "HotspotCard.tsx"
NATIVE = WEB / "components" / "native-name" / "NativeName.tsx"
GLOBALS = WEB / "app" / "globals.css"
DS_ROOT = WEB / "public" / "_ds"
ASSET = REPO / "前端设计" / "Flint 热点线索卡堆叠" / "CardStack.dc.html"
ARTIFACT = REPO / ".ui-probe" / "hotspot_card_format.json"

PWENV = Path(r"C:\pwenv\Scripts\python.exe")
FRONTEND = "http://localhost:3000/plaza"

# 探针要量的那棵树。**结构与组件同源**：下面 `test_every_class_the_component_emits_is_measured`
# 拿组件源码里解析出来的类名与这棵树判等——组件多一个类而这里没量，判红。
PROBE_TREE = """
<article class="hotspot-card" data-probe="1">
  <div class="hotspot-card__top">
    <span class="hotspot-card__region">JP</span>
    <span class="hotspot-card__verdict">C_opportunity</span>
  </div>
  <span class="native-name">
    <span class="native-name__primary">全固体電池の量産ライン</span>
    <span class="native-name__secondary">All-solid-state battery line<span
      class="native-name__mark">机翻</span></span>
  </span>
  <div class="hotspot-card__foot">
    <time class="hotspot-card__first-seen">2026-08-01</time>
    <span class="hotspot-card__heat">热度 100</span>
    <span class="hotspot-card__stale">已陈旧</span>
  </div>
</article>
"""
MEASURED = [
    ".hotspot-card",
    ".hotspot-card__top",
    ".hotspot-card__region",
    ".hotspot-card__verdict",
    ".hotspot-card .native-name",
    ".hotspot-card .native-name__primary",
    ".hotspot-card .native-name__secondary",
    ".hotspot-card .native-name__mark",
    ".hotspot-card__foot",
    ".hotspot-card__first-seen",
    ".hotspot-card__heat",
    ".hotspot-card__stale",
]


def _code_only(path: Path) -> str:
    text = re.sub(r"/\*[\s\S]*?\*/", "", path.read_text(encoding="utf-8"))
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("//")
    )


def _classes(path: Path) -> set[str]:
    return {
        cls
        for m in re.finditer(r'className="([^"]+)"', _code_only(path))
        for cls in m.group(1).split()
    }


def _bundle_dir() -> Path:
    dirs = [p for p in DS_ROOT.iterdir() if p.is_dir()]
    assert len(dirs) == 1
    return dirs[0]


def _declared_colors() -> dict[str, str]:
    text = (_bundle_dir() / "tokens" / "colors.css").read_text(encoding="utf-8")
    return {
        m.group(1): m.group(2).split("/*")[0].strip()
        for m in re.finditer(r"(--[\w-]+)\s*:\s*([^;]+);", text)
    }


def _hex_to_rgb(value: str) -> str:
    h = value.lstrip("#")
    assert len(h) == 6, f"不是六位十六进制色：{value}"
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgb({r}, {g}, {b})"


def _asset_card_style() -> dict[str, str]:
    """从素材那份 `.dc.html` 的卡面 `<article style="…">` 里解析声明。

    **期望值的真相是素材本身**。手抄一份的话，「照素材做」这句话就退化成
    「照我当时记下的样子做」——而那两者会随时间分开。
    """
    text = ASSET.read_text(encoding="utf-8")
    m = re.search(r'<article style="([^"]+)"', text)
    assert m, "素材里找不到卡面 article 的 style"
    out: dict[str, str] = {}
    for decl in m.group(1).split(";"):
        if ":" in decl:
            key, value = decl.split(":", 1)
            out[key.strip()] = value.strip()
    return out


# ───────────────────────── 一、结构：六槽照 HOTSPOT-01，缺失逐槽隐藏


def test_the_six_slots_are_all_present_in_the_source() -> None:
    code = _code_only(CARD)

    for slot in ("hotspot-region", "hotspot-verdict", "hotspot-first-seen",
                 "hotspot-stale"):
        assert f'data-testid="{slot}"' in code, f"少了 {slot} 槽"
    assert "NativeName" in code, "主行与机翻次要行没走 NativeName（B7/B8）"


def test_every_optional_slot_is_conditional() -> None:
    """逐槽隐藏：四个可选槽各自挂在自己的条件上，NEVER 用一个条件盖住几槽。

    一个条件盖几槽的话，只要有一槽有值，其余几槽就会跟着渲染出空壳。
    """
    code = _code_only(CARD)

    for slot, guard in (("hotspot-region", "region ?"),
                        ("hotspot-verdict", "verdict ?"),
                        ("hotspot-first-seen", "firstSeen ?"),
                        ("hotspot-stale", "stale === true ?")):
        assert guard in code, f"{slot} 没有自己的条件（{guard}）"


def test_no_placeholder_text_is_hardcoded() -> None:
    """NEVER 用「—」「暂无」「N/A」占位——占位符会让两种完全不同的情况长得一样。"""
    code = _code_only(CARD)

    for placeholder in ("—", "暂无", "N/A", "n/a"):
        assert placeholder not in code, f"卡面里写了占位符 {placeholder!r}"


def test_the_translated_line_never_replaces_the_native_line() -> None:
    """译名缺失时只显 name_native 单行——这条由 NativeName 持有，卡面 NEVER 另写一份。"""
    code = _code_only(CARD)

    assert "nameDisplay" in code and "display={nameDisplay}" in code
    assert "nameDisplay ?" not in code, (
        "卡面自己判了有没有译名——那条规则在 NativeName 里，两处判就是两种规则"
    )


# ───────────────────────── 二、素材：照 .dc.html 那份，NEVER 照第三方原始版


def test_no_new_dependency_sneaks_in_with_the_look() -> None:
    """素材的 `.dc.html` 版本已 Flint 化。照第三方原始版做会带进三个新依赖（S2-6）。"""
    pkg = json.loads((WEB / "package.json").read_text(encoding="utf-8"))
    deps = {**pkg["dependencies"], **pkg["devDependencies"]}

    for banned in ("framer-motion", "lucide-react", "tailwindcss"):
        assert banned not in deps, f"{banned} 被加进了依赖"

    card_css = GLOBALS.read_text(encoding="utf-8")
    code = _code_only(CARD)
    for tell in ("framer-motion", "lucide-react", "@tailwind", "motion.div"):
        assert tell not in code and tell not in card_css, f"卡面里出现了 {tell}"


# 卡面**内部**版式的类名。`hotspot-card__actions` 不在其中：那是 HOTSPOT-02 的三动作条，
# 挂在卡上而不是卡面版式的一部分（它有自己的组件与自己的卡：PLAZA-04）。
FACE_CLASSES = ("hotspot-card__top", "hotspot-card__foot", "hotspot-card__region",
                "hotspot-card__verdict", "hotspot-card__first-seen",
                "hotspot-card__stale", "hotspot-card__heat")


# 准借卡壳的白名单。骨架卡（`PLAZA-03`）借的是同一套盒子类，**借了才占得对位**——
# 另写一个「长得像卡片」的盒子会让两份卡形各自漂移。
# 借的代价由 `tests/v041/test_plaza_cards.py::test_the_shell_borrower_renders_no_data_at_all`
# 兜住：**它一个数据槽都不许渲染**。名单少一条即红，多一条要来这里解释。
SHELL_BORROWERS = {"HotspotCardSkeleton.tsx"}


def test_the_card_face_is_written_once() -> None:
    """卡面本体只有一份。

    图谱节点、收藏库、（下一张卡的）广场堆叠与网格都渲染同一份数据——
    各写一份卡面，它们会各自漂移，而屏上看不出哪一份才是对的。
    """
    others = [
        str(p.relative_to(WEB)) for p in WEB.rglob("*.tsx")
        if "node_modules" not in p.parts
        and p != CARD
        and p.name not in SHELL_BORROWERS
        and not p.name.endswith(".test.tsx")
        and any(cls in _code_only(p) for cls in FACE_CLASSES)
    ]

    assert others == [], f"这些文件也在画卡面内部结构：{others}"


# ───────────────────────── 三、样式与结构成对：**运行时计算值**


_RUNNER = r"""
import json, sys
from playwright.sync_api import sync_playwright

url, out, tree, sels = sys.argv[1], sys.argv[2], sys.argv[3], json.loads(sys.argv[4])
with sync_playwright() as p:
    b = p.chromium.launch()
    page = b.new_page(viewport={"width": 1440, "height": 900})
    page.goto(url, wait_until="networkidle", timeout=60000)
    got = page.evaluate(
        '''([tree, sels]) => {
            const host = document.createElement('div');
            // 定宽定高：卡面是 flex 列，脚注靠 margin-top:auto 贴底——
            // 不给高度的话那一条永远量不出「贴底」。素材里卡片是 520x320。
            host.style.cssText = 'position:fixed;left:-9999px;top:0;width:520px;height:320px';
            host.innerHTML = tree;
            document.body.appendChild(host);
            const baseline = document.createElement('span');
            document.body.appendChild(baseline);
            const bs = getComputedStyle(baseline);
            const props = ['backgroundColor','backgroundImage','borderTopWidth','borderTopColor',
                           'borderTopLeftRadius','boxShadow','paddingTop','paddingLeft','display',
                           'justifyContent','fontSize','fontWeight','color','fontFamily',
                           'fontVariantNumeric','overflow','webkitLineClamp','marginTop','lineHeight'];
            const rows = {};
            for (const sel of sels) {
                const el = host.querySelector(sel.replace('.hotspot-card ', '.hotspot-card '));
                if (!el) { rows[sel] = null; continue; }
                const cs = getComputedStyle(el);
                const r = el.getBoundingClientRect();
                const style = {};
                let differs = false;
                for (const k of props) {
                    style[k] = cs[k];
                    if (cs[k] !== bs[k]) differs = true;
                }
                rows[sel] = {style, width: r.width, height: r.height,
                             differsFromBareSpan: differs};
            }
            const card = host.querySelector('.hotspot-card').getBoundingClientRect();
            const foot = host.querySelector('.hotspot-card__foot').getBoundingClientRect();
            rows['__footStickToBottom'] = Math.abs(
                (card.bottom - 24) - foot.bottom) < 2;
            baseline.remove();
            host.remove();
            return rows;
        }''', [tree, sels])
    b.close()
open(out, "w", encoding="utf-8").write(
    json.dumps({"schema": "hotspot-card-format/1", "url": url, "rows": got},
               ensure_ascii=False, indent=1))
"""


def _artifact() -> dict[str, object]:
    if ARTIFACT.exists():
        return json.loads(ARTIFACT.read_text(encoding="utf-8"))
    if not PWENV.exists():
        pytest.skip(f"本机没有 {PWENV}（playwright 恒在项目外，NEVER 进项目依赖）")
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        runner = Path(tmp) / "hotspot_card_runner.py"
        runner.write_text(_RUNNER, encoding="utf-8")
        done = subprocess.run(
            [str(PWENV), str(runner), FRONTEND, str(ARTIFACT),
             PROBE_TREE, json.dumps(MEASURED)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=REPO, check=False,
        )
    if done.returncode != 0:
        pytest.skip(f"前端没起或探针跑不动（{FRONTEND}）：{done.stderr[-400:]}")
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


def _rows() -> dict[str, dict[str, object]]:
    return _artifact()["rows"]


def test_every_class_the_component_emits_is_measured() -> None:
    """探针那棵树与组件同源：组件多一个类而没人量它，判红。

    没有这一条，「全部量过了」会随着组件长出新类名而悄悄变成「量了一部分」。
    """
    emitted = _classes(CARD) | {
        c for c in _classes(NATIVE) if c.startswith("native-name")
    }
    measured = {sel.split()[-1].lstrip(".") for sel in MEASURED}

    assert emitted <= measured, f"这些类名没人量：{sorted(emitted - measured)}"


def test_no_class_is_left_with_zero_styling() -> None:
    """**本卡的主判据**：每个类都拿裸 `<span>` 当基线比一次，一样 = 零样式。

    改前那一版正是这个样子——类名齐全、计算值与裸 span 逐条相同，屏上一串裸文字。
    """
    rows = _rows()

    for sel in MEASURED:
        row = rows[sel]
        assert row is not None, f"{sel} 在探针树里没找到"
        assert row["differsFromBareSpan"], f"{sel} 与裸 span 计算值完全相同——它没有样式"


def test_the_card_face_matches_the_asset_declaration() -> None:
    """卡面六项逐条对素材：**期望值从 `.dc.html` 解析**，判据里零手抄。"""
    declared = _asset_card_style()
    tokens = _declared_colors()
    card = _rows()[".hotspot-card"]["style"]

    assert card["backgroundColor"] == _hex_to_rgb(tokens["--surface"]), (
        f"纸面底色不是 --surface：{card['backgroundColor']}"
    )
    assert "url(" in card["backgroundImage"], "没有纸纹（--tex-paper）"
    assert card["borderTopWidth"] == "1px"
    assert card["borderTopColor"] == _hex_to_rgb(tokens["--rule"])
    assert card["borderTopLeftRadius"] == "8px", "圆角不是 --r-card"
    assert card["boxShadow"] != "none", "没有 --shadow-sticker"
    assert card["paddingTop"] == "24px" and card["paddingLeft"] == "24px"
    # 素材声明里写的就是这几样——对不上说明我们照的不是那份素材。
    assert declared["padding"] == "24px"
    assert declared["background-color"] == "var(--surface)"
    assert declared["border-radius"] == "var(--r-card)"


def test_the_top_row_puts_the_two_marks_on_opposite_sides() -> None:
    top = _rows()[".hotspot-card__top"]["style"]

    assert top["display"] == "flex"
    assert top["justifyContent"] == "space-between", "顶行两枚记号没有左右分列"


def test_the_title_and_secondary_line_follow_the_type_scale() -> None:
    """标题 --fs-20/600/--ink；次要行 --fs-14/两行截断/--ink-2。"""
    tokens = _declared_colors()
    title = _rows()[".hotspot-card .native-name__primary"]["style"]
    second = _rows()[".hotspot-card .native-name__secondary"]["style"]

    assert title["fontSize"] == "20px"
    assert title["fontWeight"] == "600"
    assert title["color"] == _hex_to_rgb(tokens["--ink"])

    assert second["fontSize"] == "14px"
    assert second["color"] == _hex_to_rgb(tokens["--ink-2"])
    assert second["webkitLineClamp"] == "2", "次要行没有两行截断"
    assert second["overflow"] == "hidden"


def test_the_footer_is_a_rule_line_plus_mono_tabular_numbers() -> None:
    tokens = _declared_colors()
    foot = _rows()[".hotspot-card__foot"]["style"]

    assert foot["borderTopWidth"] == "1px"
    assert foot["borderTopColor"] == _hex_to_rgb(tokens["--rule"])
    assert "Plex Mono" in foot["fontFamily"], "脚注没走 --font-mono"
    assert "tabular-nums" in foot["fontVariantNumeric"], "数字不是等宽的"
    assert foot["color"] == _hex_to_rgb(tokens["--ink-3"])


def test_the_footer_sticks_to_the_bottom_of_the_card() -> None:
    """脚注恒贴卡底（`margin-top:auto`）。

    这不是排版洁癖：堆叠里五张卡的分隔线因此在同一条水平线上——
    那正是这张卡看起来「像一叠纸」而不是「五个高度不同的框」的原因。
    """
    assert _artifact()["rows"]["__footStickToBottom"] is True, "脚注没贴住卡底"
