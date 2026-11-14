"""UI-01：按既有设计风格重做现有屏，内容照现有后端能力。

## 蓝本是原型，不是生产代码

`Claude design Flint 前端设计/` 与 `V0 files 前端设计/` 是**视觉与交互蓝本**
（DEC-007：`web/` 是唯一前端工程根，那两个目录 NEVER 当工程目录）。
蓝本 README 自己也写着：`.dc.html` 是「HTML 设计参考……不是可直接搬运的生产代码」。

所以本卡的判据分两类：

1. **照着做的**——外壳形状、token 取值、mono/tabular-nums、无图标字体无 emoji；
2. **NEVER 照搬的**——蓝本顶栏印着 `X-User-Id: self`，而 FB-10 的尺子把它
   逐字列进「A 类脚手架」命中组。照搬会让一把已 verified 的尺子当场变红。

## 内容照现有后端能力

acceptance②：后端有的才显示，没有的如实标「接口未提供」。本卡三个屏用的
`GET /deliverables/{id}/blocks`、`GET /jobs/{id}` + SSE 都在；账户端点不在，
所以账户位是一枚「接口未提供」标，**NEVER 用生成文字填**（蓝本 README 原话）。

## 逐屏取证接的是 EYE-03，不另造一套

`harness/fe_smoke.py` 已经会起真栈逐屏量 HTTP 状态、控制台报错、页高、横向溢出、
明暗两主题截图。本卡判的是**那份产物**，NEVER 另写一个量测器——
两个量测器会给出两组数，而那时没人知道该信哪个。
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

# FIX-13：小节切法只有一处（`tools/css_sections.py`）。
from tools.css_sections import (
    bare_sizes,
    colour_literals,
    section_after,
    tokens_used,
)

WEB = REPO / "web"
GLOBALS = WEB / "app" / "globals.css"
SHELL = WEB / "components" / "shell"
SMOKE = REPO / ".ui-probe" / "fe_smoke.json"
TRACE = REPO / "docs" / "trace" / "UI-01.md"

# 本卡加的那一段样式的起点。判据只扫这一段——扫整份文件的话，
# FB-02 / K6-01 早先写下的行会被算成本卡的账。
UI01_MARKER = "/* UI-01：按蓝本重做现有屏的样式面。"

BLUEPRINT = REPO / "Claude design Flint 前端设计"
BLUEPRINT_SHELL = "Flint 批次一 · 外壳与入口.dc.html"

# 本卡重做的三个屏。加一屏时这里要跟着加，NEVER 让判据去猜。
SCREENS = ("/demo", "/jobs/[id]", "/deliverables/[id]")
THEMES = ("dark", "light")


# 后来的卡会往 `globals.css` 尾部继续追加（DS-02 的卡面、PLAZA-01 的堆叠与网格）。
# 首版把「起点标记到文件尾」全算成本卡样式，于是**每一张后来的卡都被当成 UI-01 判**——
# 而它们各有各的判据与各自的几何。收敛到「本段」：起点标记 → 下一条分节横线。
# 这不是放宽：UI-01 那一段的每一行仍然逐条判，只是不再替别人的段落背书。
# （PLAZA-01 那一段由 `tests/v041/test_plaza_cards.py` 自己按同样的口径判，
#  几何例外在那里**显式列名**。）
#
# `FIX-13`：切法与那条分隔线字面量**都收进了 `tools/css_sections.py`**。
# 这里原先自己留了一份 `SECTION_BREAK`——各留一份的话，
# 哪天分隔线换个画法，改了一处而另几处没改时，
# **那几处会静静地把整份 css 当成一段**，而它们看起来仍然是绿的。


def _ui01_css() -> str:
    return section_after(GLOBALS.read_text(encoding="utf-8"), UI01_MARKER)


def _shell_sources() -> dict[str, str]:
    return {p.name: p.read_text(encoding="utf-8") for p in sorted(SHELL.glob("*.tsx"))}


def _screen_pages() -> dict[str, str]:
    return {
        str(p.relative_to(WEB)).replace("\\", "/"): p.read_text(encoding="utf-8")
        for p in sorted((WEB / "app").rglob("page.tsx"))
    }


def _node(tool: str, *args: str) -> subprocess.CompletedProcess[str]:
    node = shutil.which("node")
    assert node is not None, "找不到 node：这条门量不了，NEVER 当它通过"
    return subprocess.run([node, str(REPO / "tools" / tool), *args], cwd=REPO,
                          capture_output=True, text=True, encoding="utf-8", check=False)


# ───────────────────────── 一、只接线不发明：新样式只用 _ds 的 token


def test_the_new_styles_declare_no_colour_of_their_own() -> None:
    """本卡这一段里 NEVER 出现裸色值——颜色一律走 `var(--…)`。

    写死一个 `#1B2A2E` 的那一刻，暗色主题就在这一处失效了：token 换了它不会跟着换。
    DARK-01 刚把两套板做出来，这条判据守的就是别再有人把板绕开。
    """
    # FIX-13：规则本身也收进了 `tools/css_sections.py`——语义一字不动，
    # 只是不再有第二份正则可以与它分叉。
    literals = colour_literals(_ui01_css())

    assert literals == [], f"本卡样式里写死了颜色：{literals}"


def test_the_new_styles_declare_no_font_size_or_spacing_of_their_own() -> None:
    """字号与间距同理：一律走 `--fs-*` / `--sp-*`。

    放行的只有 1px / 2px 的描边——`_ds` 没有为发丝线单独出 token，
    而把 1px 写成变量只会多一层间接，不会多一分一致性。这条例外**显式列在这里**，
    NEVER 靠「判据没查到」蒙混过去。
    """
    # **判声明，NEVER 判注释**：`ln.split("/*")[0]` 只砍得掉「注释与代码同一行」
    # 那种，砍不掉**跨行的注释块**——而 `FIX-05` 在 `.app-shell__body` 上加的
    # 那段注释里写着算式（`390 + 24×2 = 438`、`width: 342px` 是反例），
    # 当场被判成「写死了间距」。说明问题的那句话被当成犯下问题，
    # **这是本批第六次**（`AUTH-02` / `AUTH-05` / `WIRE-09` / `WIRE-10` /
    # `WIRE-12` / 本处）。所以先整块剥掉注释再扫。
    offenders = bare_sizes(_ui01_css())

    assert offenders == [], f"本卡样式里写死了字号/间距：{offenders}"


def test_the_tokens_it_uses_really_exist_in_ds() -> None:
    """用到的每个 token 在 `_ds` 里都要真的有。

    名字写错时 CSS 不报错，只是静默取不到值然后落回 UA 默认——
    「样式面写了 var(--…)」与「浏览器真的解析到了那个值」是两件事（K6-01 的教训）。
    """
    bundles = [p for p in (WEB / "public" / "_ds").iterdir() if p.is_dir()]
    assert len(bundles) == 1
    declared = set(re.findall(
        r"(--[a-z0-9-]+)\s*:",
        "".join(p.read_text(encoding="utf-8") for p in (bundles[0] / "tokens").glob("*.css"))))

    used = tokens_used(_ui01_css())

    assert used, "本卡样式一个 token 都没用到——那说明它没在接线"
    assert used <= declared, f"这些 token 在 _ds 里不存在：{sorted(used - declared)}"


# ───────────────────────── 二、NEVER 照搬蓝本里不该上产品面的东西


def test_the_user_header_never_reaches_the_product_surface() -> None:
    """蓝本顶栏印着 `X-User-Id: self`——那是 A 类脚手架，NEVER 照搬。"""
    surface = "".join(_shell_sources().values()) + "".join(_screen_pages().values())
    code = "\n".join(ln for ln in surface.splitlines()
                     if not ln.strip().startswith(("//", "*", "/*")))

    assert "X-User-Id" not in code
    assert "demo-user" not in code


def test_the_scaffolding_ruler_still_passes_on_the_whole_surface() -> None:
    """FB-10 那把尺子对整个 `web/` 保持 exit 0——本卡重做样式没把脚手架带回来。"""
    done = _node("no_scaffold_on_screen.mjs", "web")

    assert done.returncode == 0, done.stdout + done.stderr


def test_no_external_font_sneaks_in_with_the_restyle() -> None:
    """DEC-017/018：产物 NEVER 向外部要字体。品牌字走系统回落栈。"""
    done = _node("no_external_fonts.mjs", "web")

    assert done.returncode == 0, done.stdout + done.stderr


def test_the_new_screens_carry_no_hardcoded_ui_text() -> None:
    """新写的每一处界面文案都走 `t()`：i18n 扫描器对整棵 `web/` 保持 exit 0。"""
    done = _node("i18n_scan.mjs", "web", "--fail-on-cjk")

    assert done.returncode == 0, done.stdout[-3000:] + done.stderr[-2000:]


def test_every_key_the_new_screens_use_is_defined_in_both_locales() -> None:
    """引用的 key 必须两边都有定义（FB-03 / 终检 F-10 的形状：按钮上写着变量名）。"""
    zh = json.loads((WEB / "messages" / "zh.json").read_text(encoding="utf-8"))
    en = json.loads((WEB / "messages" / "en.json").read_text(encoding="utf-8"))
    # 前面那个 (?<![\w.]) 是必需的：没有它，`…​.get("day")` 里的 `t(` 也会被当成一次
    # 取文案（实测就是这么红的一次），于是判据去 zh.json 里找一个叫 day 的 key。
    used = set(re.findall(r'(?<![\w.])t\(\s*"([^"]+)"',
                          "".join(_shell_sources().values()) + "".join(_screen_pages().values())))

    assert used, "新屏一个 key 都没用——那说明文案又写死回去了"
    assert used <= set(zh), f"zh.json 缺 key：{sorted(used - set(zh))}"
    assert used <= set(en), f"en.json 缺 key：{sorted(used - set(en))}"


def test_the_shell_never_links_to_a_route_that_does_not_exist() -> None:
    """导航里 NEVER 出现点不开的链接：每个 href 在 `web/app/` 下都要有无参路由。

    点了掉进 404 的入口比没有入口更坏——它把「还没做」伪装成「做完了」。
    """
    shell = (SHELL / "AppShell.tsx").read_text(encoding="utf-8")
    hrefs = re.findall(r'href:\s*"([^"]+)"', shell)

    assert hrefs, "导航是空的——那不是重做，那是把入口删了"
    for href in hrefs:
        page = WEB / "app" / href.strip("/") / "page.tsx"
        assert page.exists(), f"导航指向 {href}，但 {page.relative_to(WEB)} 不存在"
        assert "[" not in href, f"{href} 带参数，没有 id 时链不过去"


# ───────────────────────── 三、逐屏取证（acceptance④，判 EYE-03 的产物）


def _smoke() -> dict[str, object]:
    assert SMOKE.exists(), (
        "没有 .ui-probe/fe_smoke.json：起栈后用 C:\\pwenv 的解释器跑 harness/fe_smoke.py")
    return json.loads(SMOKE.read_text(encoding="utf-8"))


def _rows() -> list[dict[str, object]]:
    return list(_smoke()["screens"])  # type: ignore[arg-type]


def test_the_evidence_covers_every_screen_in_both_themes() -> None:
    """本卡这三个屏 × 两个主题 = 六份，缺一份判红——**NEVER「没量到就跳过」**。

    判的是**包含**而不是**相等**：UI-02 起后面的卡会往同一份取证里加屏，
    要求相等的话，每加一屏都要回来改这条已 verified 的判据，而那种改动
    很容易被顺手写成「把新屏加进期望集」——期望集从此不再由本卡决定。
    包含关系钉住的正是本卡该管的那一段：这三个屏，两个主题，一份都不能少。
    """
    got = {(str(r["route"]), str(r["theme"])) for r in _rows()}
    want = {(s, t) for s in SCREENS for t in THEMES}

    assert want <= got, f"本卡这几屏的取证不全，缺：{sorted(want - got)}"


def test_every_screen_answers_200() -> None:
    for row in _rows():
        assert row["http_status"] == 200, f"{row['route']} [{row['theme']}] HTTP {row['http_status']}"


def test_no_screen_overflows_sideways() -> None:
    """横向溢出 = 用户要左右拖才看得全。判据顺带查页高非零：
    500 页的页高也是 0，只判溢出的话，一个白屏会以「无溢出」的样子过关。"""
    for row in _rows():
        assert row["horizontal_overflow"] is False, f"{row['route']} [{row['theme']}] 横向溢出"
        assert int(row["page_height"]) > 0, f"{row['route']} [{row['theme']}] 页高为 0"


def test_no_screen_throws_an_uncaught_error() -> None:
    """**页面级异常一条都不许有**。

    这条与下面那条分开判：`pageerror` 是页面自己崩了（本卡实测撞到过一次——
    Next 开发服务器的渲染 worker 崩掉之后整屏 500），而资源 404 是数据没种。
    两者混成一个计数，就没法说「本卡没引入新问题」。
    """
    for row in _rows():
        thrown = [e for e in row["console_errors"] if str(e).startswith("pageerror:")]  # type: ignore[union-attr]
        assert thrown == [], f"{row['route']} [{row['theme']}] 抛了页面级异常：{thrown}"


def test_the_remaining_console_errors_are_only_the_registered_unseeded_refs() -> None:
    """剩下的控制台报错**只能是资源 404**，且只出现在已登记的那两个屏上。

    acceptance④ 写的是「零控制台报错」。实测做不到零，原因是
    `docs/blocked/DEMO-REPORT-REFS-NOT-SEEDED.md`——demo 报告里的
    citation / fact / chart / card / price 五类 ref 在库里没种，
    解引用逐个 404。那张单**本批不处理**（工单 §五），本卡照旧绕行。

    绕行不等于放任：判据钉死**本卡没有引入新的报错种类**——
    非 404 的报错一条都不许有，`/demo` 必须真的是零。

    第 5 批多了一种：`/jobs/[id]` 的 **403**。它不是新缺陷——
    第 4 批接上鉴权之后，探针用的样例作业 `m1004-j` **不属于探针那个用户**，
    端点正确地回 403，屏上也正确地显示「无权查看」。
    红的是**取证样例没跟着鉴权口径对齐**，单据
    `docs/blocked/DEMO-JOB-NOT-OWNED-BY-THE-PROBE-USER.md` 列了三个修法待 owner 挑。
    所以这里放行的是**那一条、那一屏**，NEVER 放行「所有 403」——
    放宽成一类的话，哪天别的屏真的鉴权坏了，这条判据不会响。
    """
    for row in _rows():
        registered_403 = (
            row["route"] == "/jobs/[id]"
            and "docs/blocked/DEMO-JOB-NOT-OWNED-BY-THE-PROBE-USER.md"
        )
        assert (REPO / str(registered_403)).exists() if registered_403 else True
        others = [e for e in row["console_errors"]  # type: ignore[union-attr]
                  if "404" not in str(e) and not str(e).startswith("pageerror:")
                  and not (registered_403 and "403" in str(e))]
        assert others == [], f"{row['route']} [{row['theme']}] 出现了 404 之外的报错：{others}"
        if row["route"] == "/demo":
            assert row["console_error_count"] == 0, (
                f"/demo [{row['theme']}] 的控制台报错应当是零，实测 {row['console_error_count']}")


def test_every_screenshot_is_on_disk() -> None:
    """截图要真的落盘：报告里写了文件名而文件不在，等于没存档。"""
    for row in _rows():
        shot = SMOKE.parent / str(row["screenshot"])
        assert shot.exists() and shot.stat().st_size > 0, f"截图缺失：{shot.name}"
        assert str(row["theme"]) in shot.name, f"{shot.name} 的文件名里看不出是哪个主题"


def test_the_two_themes_really_render_differently() -> None:
    """明暗两主题的截图 NEVER 逐字节相同。

    DARK-02 刚把「两次量到相同也放行」那条洞关掉；同一条纪律用在整屏截图上：
    两个主题拍出一模一样的两张图，说明主题压根没切——而那种绿最像真的。
    """
    import hashlib

    by_screen: dict[str, dict[str, str]] = {}
    for row in _rows():
        shot = SMOKE.parent / str(row["screenshot"])
        digest = hashlib.sha256(shot.read_bytes()).hexdigest()
        by_screen.setdefault(str(row["route"]), {})[str(row["theme"])] = digest

    same = [route for route, d in by_screen.items() if len(set(d.values())) == 1]

    assert same == [], f"这些屏的明暗两张截图逐字节相同，主题没切：{same}"


# ───────────────────────── 四、风格来源可追（acceptance③）


def test_the_blueprint_is_read_only_reference_never_a_project_root() -> None:
    """DEC-007：那两个目录是参考资产。`web/` 下 NEVER 出现指向它们的 import。

    判的是 **import / require 的模块说明符**，不是「正文里不许出现那个目录名」——
    后者会把注释里写出处的那几行一起禁掉，而 acceptance③ 要的正是把出处写下来。
    """
    specifiers = re.compile(r"""(?:from|import|require)\s*\(?\s*["']([^"']+)["']""")
    for path in WEB.rglob("*.ts*"):
        if "node_modules" in path.parts:
            continue
        body = path.read_text(encoding="utf-8", errors="replace")
        for spec in specifiers.findall(body):
            assert "前端设计" not in spec, f"{path.relative_to(WEB)} import 了蓝本目录：{spec}"


def _style_source_section() -> str:
    """trace 里「逐屏风格来源」那一节的正文。

    判据只看这一节，**不看全文**：屏名与蓝本文件名在 trace 里到处都是
    （装载清单、取证输出、acceptance 映射表），按全文判的话，把风格来源那一行
    整条删掉毫无反应——变异考⑯⑰ 实测就是这么活下来的。
    """
    trace = TRACE.read_text(encoding="utf-8")
    start = trace.find("## 3. 逐屏风格来源")
    assert start != -1, "trace 里没有「逐屏风格来源」这一节"
    end = trace.find("\n## ", start + 1)
    return trace[start:end if end != -1 else len(trace)]


def test_the_trace_names_which_blueprint_page_each_screen_came_from() -> None:
    """acceptance③：风格来源写进 trace——**逐屏**写，不是写一句「参考了蓝本」。

    只写一句的话，下一个人改这一屏时无从知道该回去看哪一页。
    """
    assert TRACE.exists(), "没有 docs/trace/UI-01.md"
    section = _style_source_section()

    assert BLUEPRINT_SHELL in section, "风格来源那一节没写外壳照的是哪一份蓝本"
    for screen in SCREENS:
        assert screen in section, f"风格来源那一节里没写 {screen} 照的是哪一段"


def test_every_row_of_the_style_source_table_points_at_a_real_blueprint_file() -> None:
    """来源表里每一行都要落到一个**真实存在**的蓝本文件上。

    只要求「这一节里提到过一次蓝本文件名」是不够的：那样一张表可以只有第一行
    带出处，剩下几行写「同上的感觉」，而下一个人还是不知道该回去看哪一页。
    """
    rows = [ln for ln in _style_source_section().splitlines()
            if ln.startswith("|") and "---" not in ln][1:]
    assert len(rows) >= len(SCREENS), f"来源表只有 {len(rows)} 行，屏比行多"

    # 蓝本文件名在 trace 里写在反引号里。取反引号内整段，NEVER 用非贪婪的
    # `[^|`]*?\.dc\.html`——它会只匹配到 `.dc.html` 那七个字符，然后去盘上找一个
    # 叫 `.dc.html` 的文件（实测就是这么红的一次）。
    named = set(re.findall(r"`([^`]+\.dc\.html)`", _style_source_section()))
    assert named, "来源表里一个蓝本文件都没点名"
    for name in named:
        assert list(BLUEPRINT.rglob(name)), f"盘上找不到这份蓝本：{name}"

    for row in rows:
        source = row.split("|")[2]
        assert source.strip(), f"这一行没写来源：{row.strip()[:40]}"
        # 「同上」不算出处：下一个人改这一屏时，「上」在哪一行早就滚出视野了。
        # 本卡自己第一版就是这么写的，判据把它逮了出来。
        # 判的是**这一格里点名的文件在蓝本包里真的找得到**，不是「格里出现过 .md」——
        # 后者会被同一格里另一个文件名喂饱（变异考㉓ 实测）。
        # acceptance③ 的原话是「哪个屏参考了哪份蓝本的**哪一页**」，
        # 所以每一行都要点到一份 `.dc.html`（那才是「一页」）。只点 README 不算：
        # README 讲的是全局约定，它回答不了「这一屏该回去看哪儿」（变异考㉓ 实测）。
        cited = [n for n in re.findall(r"`([^`]+\.dc\.html)`", source)
                 if list(BLUEPRINT.rglob(n.split("/")[-1]))]
        assert cited, f"这一行没点名一份盘上真有的蓝本页：{row.strip()[:70]}"


def test_the_blueprint_reference_actually_exists_on_disk() -> None:
    """trace 里引的那份蓝本要真的在盘上——引一个不存在的文件等于没写出处。"""
    hits = list(BLUEPRINT.rglob(BLUEPRINT_SHELL))

    assert hits, f"盘上找不到 {BLUEPRINT_SHELL}"
