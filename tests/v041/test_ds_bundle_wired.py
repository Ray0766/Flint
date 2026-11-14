"""DS-01：`_ds_bundle.js` 从未被加载——`StickerTag` 与 `StatusMark` 一直在盘上没人用。

## 改前的实况（本卡开工时逐条核过）

- `web/app/layout.tsx` 只 `<link>` 了 `_ds/…/styles.css`。**CSS 那一半接了，JS 这一半没接**
  （`FB-01` 做的是前者）。
- `_ds_bundle.js` 里有 15 个组件，其中 `StickerTag`（贴纸标签）与 `StatusMark`（八态状态标记）
  是热点卡片顶行左右两枚的原件。全仓 grep 这两个名字 → **零引用**。
- 于是「素材没用上」这件事有了机械根因：不是没人想用，是**运行时根本没有这两个函数**。

## 判据为什么不是「script 标签在不在」

一条 `<script src="/_ds/…/_ds_bundle.js">` 可以在 DOM 里而组件仍然拿不到：

1. 路径里的哈希段随导出包变，**写错的路径静默 404**，页面照样渲染、只是没有组件
   （`F-09` 的形状，`FB-01` 已经被这一形状咬过一次，故本卡照抄它的路径判据）；
2. bundle 用的是 `React.createElement` 的**浏览器全局写法**，`window.React` 没被喂上去时
   它自己的 `try/catch` 会把错误吞进 `__errors`，**页面不报错、组件不存在**；
3. bundle 到位了，而 Flint 侧另写了一份「长得差不多」的替身——那时候接线是绿的，
   屏上却仍然不是设计系统的东西。

所以这份验收分三层，逐层都能独立判红：

| 层 | 判什么 | 失败时说明什么 |
|---|---|---|
| 源码层 | 接线在、路径解析得到真文件、bundle 没进构建面 | 接错了 |
| 契约层 | 封装的属性名与 bundle 里的函数签名**逐字相等**（机器比对，NEVER 手抄） | 封装漂了 |
| 运行时层 | 真浏览器里取 `StatusMark` / `StickerTag` 的计算样式，与 `_ds` token 声明值逐条相等 | 没生效 |

运行时那一层的产物是 `.ui-probe/ds_components.json`，由本文件里的 playwright 小跑器
（`C:\\pwenv` 的解释器，NEVER 进项目依赖）对着真起的前端落下。
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
WEB = REPO / "web"
LAYOUT = WEB / "app" / "layout.tsx"
SHELL = WEB / "components" / "shell"
DS_ROOT = WEB / "public" / "_ds"
ARTIFACT = REPO / ".ui-probe" / "ds_components.json"

PWENV = Path(r"C:\pwenv\Scripts\python.exe")
FRONTEND = "http://localhost:3000/plaza"

# 本卡接的两个组件。名字来自 `_ds_manifest.json` 的 components 表，NEVER 手写一份清单。
WIRED = ("StatusMark", "StickerTag")


def _bundle_dir() -> Path:
    dirs = [p for p in DS_ROOT.iterdir() if p.is_dir()]
    assert len(dirs) == 1, f"_ds 下应当只有一个包目录，实际 {[d.name for d in dirs]}"
    return dirs[0]


def _code_only(text: str) -> str:
    """剥块注释与行注释再扫。

    `FB-01` 在这里栽过：判据扫到了**解释判据的那段注释**，
    于是「为什么不能这么写」被读成「他就是这么写的」。
    """
    text = re.sub(r"/\*[\s\S]*?\*/", "", text)
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("//")
    )


def _shell_sources() -> str:
    return "\n".join(
        _code_only(p.read_text(encoding="utf-8")) for p in sorted(SHELL.rglob("*.ts*"))
    )


def _wiring() -> str:
    """接线面 = layout + shell。bundle 是全站件，接线只会落在这两处之一。"""
    return _code_only(LAYOUT.read_text(encoding="utf-8")) + "\n" + _shell_sources()


def _declared_colors() -> dict[str, str]:
    text = (_bundle_dir() / "tokens" / "colors.css").read_text(encoding="utf-8")
    return {
        m.group(1): m.group(2).split("/*")[0].strip()
        for m in re.finditer(r"(--[\w-]+)\s*:\s*([^;]+);", text)
    }


def _hex_to_rgb(value: str) -> str:
    """`#EDEEE6` → `rgb(237, 238, 230)`：浏览器把颜色一律回成 rgb()。"""
    h = value.lstrip("#")
    assert len(h) == 6, f"不是六位十六进制色：{value}"
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgb({r}, {g}, {b})"


def _ds_props(component: str) -> set[str]:
    """从 bundle 源码里解析 `function X({a, b = 1, c})` 的属性名。

    **这是本文件唯一的属性真相**。手抄一份清单的话，`_ds` 改了签名而清单没改，
    判据会继续绿——那正是「封装漂了」最容易溜过去的形状。
    """
    src = (_bundle_dir() / "_ds_bundle.js").read_text(encoding="utf-8")
    m = re.search(rf"function {component}\(\{{([^}}]*)\}}\)", src)
    assert m, f"bundle 里找不到 function {component}(…)"
    return {
        part.split("=")[0].strip()
        for part in m.group(1).split(",")
        if part.strip()
    }


# ───────────────────────── 一、源码层：接线真的在，而且指向真文件


def test_the_layout_wires_the_javascript_half_of_the_design_system() -> None:
    """改前这里只有 CSS 那一半。接上 JS 这一半，两个组件才在运行时存在。"""
    wired = _wiring()

    assert "_ds_bundle.js" in wired, (
        "全站接线里没有 _ds_bundle.js —— StickerTag 与 StatusMark 在运行时不存在"
    )


def test_the_bundle_path_resolves_to_a_file_that_exists() -> None:
    """写错的路径静默 404，页面照样渲染、只是没有组件（F-09 的形状）。"""
    refs = re.findall(r"/_ds/([^\"')\s]+\.js)", _wiring())

    assert refs, "接线里没有指向 _ds 的脚本引用"
    for ref in refs:
        assert (DS_ROOT / ref).exists(), f"引用了不存在的脚本：/_ds/{ref}"


def test_the_namespace_in_the_wiring_matches_the_one_the_bundle_writes() -> None:
    """bundle 把自己挂在 `window.<namespace>` 上。名字对不上 = 永远取不到组件。"""
    declared = json.loads((_bundle_dir() / "_ds_manifest.json").read_text(encoding="utf-8"))
    namespace = declared["namespace"]

    assert namespace in _wiring(), f"接线里没有 bundle 的命名空间 {namespace}"


def test_the_bundle_never_enters_the_build_surface() -> None:
    """NEVER 新增依赖：bundle 走 public/ 按 URL 取，NEVER 被 import 进构建面。"""
    sources = "\n".join(
        _code_only(p.read_text(encoding="utf-8"))
        for p in WEB.rglob("*.ts*")
        if "node_modules" not in p.parts and "public" not in p.parts
    )

    assert not re.search(r"(import|require)[^\n]*_ds_bundle", sources), (
        "bundle 被 import 进了构建面——它是供应商资产，只走 URL"
    )
    pkg = json.loads((WEB / "package.json").read_text(encoding="utf-8"))
    assert "framer-motion" not in pkg["dependencies"]
    assert "lucide-react" not in pkg["dependencies"]
    assert "tailwindcss" not in {**pkg["dependencies"], **pkg["devDependencies"]}


# ───────────────────────── 二、契约层：封装是 _ds 的封装，不是替身


def test_both_components_have_a_flint_wrapper() -> None:
    for name in WIRED:
        hits = [p for p in SHELL.rglob("*.tsx") if name in p.read_text(encoding="utf-8")]
        assert hits, f"{name} 在 shell/ 里没有任何封装——组件仍然全仓零引用"


@pytest.mark.parametrize("component", WIRED)
def test_the_wrapper_props_match_the_ds_signature_verbatim(component: str) -> None:
    """属性名与 `_ds` 逐字对齐：**两边都从源码解析**，NEVER 拿手抄的清单比。"""
    expected = _ds_props(component)
    wrapper = SHELL / f"Ds{component}.tsx"
    assert wrapper.exists(), f"缺 {wrapper.name}"

    code = _code_only(wrapper.read_text(encoding="utf-8"))
    m = re.search(r"export function Ds\w+\(\{([^}]*)\}", code)
    assert m, f"{wrapper.name} 里没有解构式的属性表"
    got = {part.split("=")[0].strip() for part in m.group(1).split(",") if part.strip()}

    assert got == expected, (
        f"{component} 封装的属性 {sorted(got)} 与 _ds 的 {sorted(expected)} 对不上"
    )


@pytest.mark.parametrize("component", WIRED)
def test_the_wrapper_is_a_delegate_not_a_visual_replica(component: str) -> None:
    """替身会把 `_ds` 的视觉常量抄一份过来。抄了就判红。

    抄一份的坏处不是「重复代码」——是**两份视觉从此各自漂移**，
    而屏上看不出哪一份才是设计系统。
    """
    code = _code_only((SHELL / f"Ds{component}.tsx").read_text(encoding="utf-8"))

    for tell in ("--indigo-soft", "--sulfur-soft", "--moss-soft", "--rust-soft",
                 "square-hollow", "borderRadius", "boxShadow", "rotate("):
        assert tell not in code, f"Ds{component}.tsx 里抄了 _ds 的视觉常量 {tell!r}"


def test_the_wrapper_never_falls_back_to_a_look_alike() -> None:
    """bundle 没到位时只交出文字内容，NEVER 画一个像 `_ds` 的东西顶上。

    顶上去的那一版会在慢网下被截图、被当成设计系统的样子——
    而它谁也不是。
    """
    for component in WIRED:
        code = _code_only((SHELL / f"Ds{component}.tsx").read_text(encoding="utf-8"))
        assert "data-ds-pending" in code, (
            f"Ds{component}.tsx 没有把「bundle 还没到」这一态标出来"
        )
        assert "style={{" not in code, f"Ds{component}.tsx 自己画了样式"


# ───────────────────────── 三、A4 规则：名单少一条即红


def _scan(root: Path) -> dict[str, object]:
    node = shutil.which("node")
    if node is None:
        pytest.skip("本机没有 node")
    # encoding 必须显式给：本机控制台是 GBK，尺子的输出里有中文，
    # 不给就在 subprocess 的读线程里抛 UnicodeDecodeError，报出来的却是「测试失败」。
    out = subprocess.run(
        [node, str(REPO / "tools" / "check_design_constraints.mjs"),
         str(root), "--json"],
        capture_output=True, text=True, encoding="utf-8", cwd=REPO, check=False,
    )
    return json.loads(out.stdout)


def test_the_a4_rule_has_a_subject_and_is_not_excused() -> None:
    """`StatusMark` 落地后 A4 NEVER 回到「无可量对象」名单。

    `UIX-03` 已经把豁免语撤了（`tests/v041/test_status_mark.py`），本条守的是**不回潮**：
    名单里再出现 A4，说明有人把对象弄没了又把豁免加了回来。
    """
    report = _scan(Path("web"))

    assert report["findings"] == [], f"技术约束清单有违规：{report['findings']}"
    assert report["applied"]["A4"] > 0, "A4 一个文件都没落到——规则是瞎的"
    assert "A4" not in [row["id"] for row in report["noSubject"]], (
        "A4 又回到了「无可量对象」名单"
    )
    assert "A4" not in report["blind"]


def test_the_a4_delegation_escape_is_narrow(tmp_path: Path) -> None:
    """**阴性对照**：本卡给 A4 开的那道口子只认「把记号交给 `_ds`」这一句。

    没有这一条，那道口子就是一句「我用了设计系统」的自我声明——
    谁都可以在文件里提一嘴 `_ds` 然后接着只用颜色画状态。
    """
    fake = tmp_path / "components" / "StatusMark.tsx"
    fake.parent.mkdir(parents=True)
    # 用了设计系统的**另一个**组件，状态标记仍然自己用颜色画 → 必须红。
    fake.write_text(
        'import { useDsComponent } from "./dsBundle";\n'
        "export function StatusMark({ state }: { state: string }) {\n"
        '  const Tag = useDsComponent("StickerTag");\n'
        '  const tone = state === "failed" ? "red" : "green";\n'
        "  return <span className={`mark mark--${tone}`}>{Tag ? 1 : 2}</span>;\n"
        "}\n",
        encoding="utf-8")

    findings = [f for f in _scan(tmp_path)["findings"] if f["rule"] == "A4"]

    assert findings, "只提了一句 _ds 就放行——那道口子太宽了"


# ───────────────────────── 四、运行时层：真浏览器里的计算样式


# 真跑器：在真起的前端页面里，用 bundle 自己产出的 style 对象铺一个真元素，
# 再取计算样式。**样式值来自 _ds 的函数返回，不是手抄的字面量**——
# 手抄的话，_ds 改了颜色而判据继续绿，那正是本卡要防的事。
_RUNNER = r"""
import json, sys
from playwright.sync_api import sync_playwright

url, out = sys.argv[1], sys.argv[2]
MEASURE = [
    ("StatusMark", {"status": "verified"}),
    ("StatusMark", {"status": "blocking"}),
    ("StatusMark", {"status": "speculative"}),
    ("StickerTag", {"tone": "indigo", "children": "x"}),
    ("StickerTag", {"tone": "paper", "children": "x"}),
]
with sync_playwright() as p:
    b = p.chromium.launch()
    page = b.new_page(viewport={"width": 1440, "height": 900})
    page.goto(url, wait_until="networkidle", timeout=60000)
    page.wait_for_function(
        "() => { const ns = window.FlintDesignSystem_8fd95b;"
        " return !!(ns && ns.StatusMark && ns.StickerTag); }", timeout=30000)
    rows = []
    for name, props in MEASURE:
        rows.append(page.evaluate(
            '''([name, props]) => {
                const ns = window.FlintDesignSystem_8fd95b;
                const el = ns[name](props);            // _ds 的函数，真调一次
                const host = document.createElement('span');
                Object.assign(host.style, el.props.style);
                document.body.appendChild(host);
                const cs = getComputedStyle(host);
                // 非颜色载体也量：A4 说的「灰度打印下还分得出来」靠的就是这几样。
                const kids = [].concat(el.props.children || []);
                const marked = kids.find(
                    (k) => k && k.props && typeof k.props.kind === 'string');
                const out = {
                  component: name, props,
                  color: cs.color, backgroundColor: cs.backgroundColor,
                  borderTopColor: cs.borderTopColor, borderRadius: cs.borderTopLeftRadius,
                  fontFamily: cs.fontFamily,
                  borderTopStyle: cs.borderTopStyle,
                  backgroundImage: cs.backgroundImage === 'none' ? '' : 'set',
                  markKind: marked ? marked.props.kind : '',
                };
                host.remove();
                return out;
            }''', [name, props]))
    live = page.evaluate(
        '''() => {
            // 量的是 _ds 自己那一层，不是 Flint 封装的外壳 span：
            // 外壳没有样式，量它等于量了个寂寞。
            const host = document.querySelector(
                '[data-ds-component="StickerTag"] > *');
            if (!host) return null;
            const r = host.getBoundingClientRect();
            const cs = getComputedStyle(host);
            return {width: r.width, height: r.height,
                    borderRadius: cs.borderTopLeftRadius, fontFamily: cs.fontFamily,
                    backgroundColor: cs.backgroundColor};
        }''')
    errs = page.evaluate(
        "() => (window.FlintDesignSystem_8fd95b.__errors || []).map(e => e.path)")
    b.close()
open(out, "w", encoding="utf-8").write(json.dumps(
    {"schema": "ds-components/1", "url": url, "measured": rows,
     "live_sticker_tag": live, "bundle_errors": errs},
    ensure_ascii=False, indent=1))
"""


def _artifact() -> dict[str, object]:
    if ARTIFACT.exists():
        return json.loads(ARTIFACT.read_text(encoding="utf-8"))
    if not PWENV.exists():
        pytest.skip(f"本机没有 {PWENV}（playwright 恒在项目外，NEVER 进项目依赖）")
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    # 跑器落在临时目录，NEVER 落进仓里：它是 playwright 环境的代码，
    # 而 playwright 恒在项目外（`C:\pwenv`）。落进仓里会被 ruff 与 mypy 当成项目代码扫，
    # 报出来的红说的是「另一个解释器里的脚本不合本仓的规矩」——一句没用的话。
    with tempfile.TemporaryDirectory() as tmp:
        runner = Path(tmp) / "ds_components_runner.py"
        runner.write_text(_RUNNER, encoding="utf-8")
        done = subprocess.run(
            [str(PWENV), str(runner), FRONTEND, str(ARTIFACT)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=REPO, check=False,
        )
    if done.returncode != 0:
        pytest.skip(f"前端没起或探针跑不动（{FRONTEND}）：{done.stderr[-400:]}")
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


def test_the_bundle_loads_without_swallowing_a_component() -> None:
    """bundle 每个组件都裹在自己的 try/catch 里——出错时它**静静地不存在**。"""
    report = _artifact()

    assert report["bundle_errors"] == [], (
        f"bundle 里有组件加载失败：{report['bundle_errors']}"
    )


def test_the_status_mark_computes_to_the_declared_ds_tokens() -> None:
    """真渲染一次 `StatusMark`，取计算样式，与 `_ds` 的 token 声明逐条相等。"""
    declared = _declared_colors()
    rows = {
        (r["component"], json.dumps(r["props"], sort_keys=True)): r
        for r in _artifact()["measured"]
    }

    verified = rows[("StatusMark", json.dumps({"status": "verified"}, sort_keys=True))]
    assert verified["color"] == _hex_to_rgb(declared["--indigo"]), (
        f"verified 态取到 {verified['color']}，_ds 声明 --indigo={declared['--indigo']}"
    )
    assert verified["borderTopColor"] == _hex_to_rgb(declared["--indigo"])

    blocking = rows[("StatusMark", json.dumps({"status": "blocking"}, sort_keys=True))]
    assert blocking["color"] == _hex_to_rgb(declared["--rust"]), (
        "blocking 态没取到 --rust —— 八态在运行时没分开"
    )
    assert blocking["color"] != verified["color"], "两态取到同一个颜色 = 样式没生效"
    assert "Plex Mono" in verified["fontFamily"], "状态标记没走 --font-mono"


def test_the_status_mark_carries_a_non_colour_difference_at_runtime() -> None:
    """A4 的那句话在运行时被量出来：**八态互相区分靠的不只是颜色**。

    这一条是 `Ds StatusMark.tsx` 能在 A4 下过关的**唯一理由**：那个封装自己一行视觉都不写，
    非颜色载体全在 `_ds` 那边。载体到底在不在，源码扫描器看不见——只能在浏览器里量。
    量的是三样互不相同的东西：边框笔法、底纹有无、记号形状。
    """
    rows = {
        r["props"]["status"]: r
        for r in _artifact()["measured"] if r["component"] == "StatusMark"
    }
    verified, blocking, speculative = (
        rows["verified"], rows["blocking"], rows["speculative"])

    assert {verified["borderTopStyle"], blocking["borderTopStyle"],
            speculative["borderTopStyle"]} >= {"solid", "double", "dashed"}, (
        f"三态的边框笔法没分开：{[r['borderTopStyle'] for r in rows.values()]}"
    )
    kinds = {r["markKind"] for r in rows.values()}
    assert len(kinds) == len(rows), f"记号形状有重复：{kinds}"
    assert "" not in kinds, "有的状态一个记号都没有——灰度下它只剩颜色"


def test_the_sticker_tag_computes_to_the_declared_ds_tokens() -> None:
    rows = {
        (r["component"], r["props"]["tone"]): r
        for r in _artifact()["measured"] if r["component"] == "StickerTag"
    }
    declared = _declared_colors()

    indigo = rows[("StickerTag", "indigo")]
    paper = rows[("StickerTag", "paper")]
    assert indigo["backgroundColor"] == _hex_to_rgb(declared["--indigo-soft"])
    assert paper["backgroundColor"] == _hex_to_rgb(declared["--paper-2"])
    assert indigo["borderRadius"] == "999px", "贴纸标签的 --r-tag 没生效"


def test_a_sticker_tag_is_actually_on_screen_with_size() -> None:
    """接上了、也真的占了像素。

    `F-09` 量的正是这一件事的反面：DOM 里有、宽高是 0，屏上什么都没有。
    """
    live = _artifact()["live_sticker_tag"]

    assert live is not None, "真屏上一个 StickerTag 都没有——组件接了但没人用"
    assert live["width"] > 0 and live["height"] > 0, f"StickerTag 占 0 像素：{live}"
    assert live["borderRadius"] == "999px"
    assert "Plex Mono" in live["fontFamily"]


if __name__ == "__main__":  # pragma: no cover - 手跑取证用
    sys.exit(pytest.main([__file__, "-q"]))
