"""GAUGE-12：逐屏组件对照 —— 本仓**第一把正向尺子**。

## 这批返工的根因就是没有这把尺子

全仓此前的判据都是**禁止性**的：NEVER 空转 / NEVER 空态冒充 / NEVER 硬编码。
它们挡得住做错，**挡不住没做**。

广场屏那四条 `EYE-03` 判据（HTTP 200 · 零控制台报错 · 无横向溢出 · 两主题截图）
**全绿**，而那一屏是个 `ul/li`、全文件零 `className`——它就是这么过去的。
**一屏「什么都没做」在禁止性判据下永远是干净的：它没有错误可犯。**

## 三层各判各的

| 层 | 判什么 | 失败时说明什么 |
|---|---|---|
| 声明 | 每屏 MUST 用到的组件与 MUST 有样式的类名（`assets/screen_composition.json`） | 名单少一项 = 那一屏可以悄悄退化 |
| 运行时 | 组件**被真渲染**（DOM + 宽高）、类名**真有样式**（计算样式 ≠ 裸元素） | 「文件存在」不算 |
| 阴性对照 | 把任一屏的卡片换回无样式列表 → 尺子 MUST 报红并指出缺哪个 | 尺子认不出坏的，它给的绿说明不了任何事 |

## 为什么观测与判据分成两个文件

`tools/check_screen_composition.mjs` 在 node 侧跑，**没有 DOM**。
所以它消费一份观测产物，观测由本文件用 `C:\\pwenv` 的 playwright 落下。
这与本仓既有的 `check_design_constraints.mjs`（静态）+ `ui_probe.py`（运行时）
是同一套分工：**判据在那边，眼睛在这边**。
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
CHECKER = REPO / "tools" / "check_screen_composition.mjs"
DECLARATION = REPO / "assets" / "screen_composition.json"
OBSERVED = REPO / ".ui-probe" / "screen_composition.json"

PWENV = Path(r"C:\pwenv\Scripts\python.exe")

EXIT_OK = 0
EXIT_VIOLATIONS = 1
EXIT_NO_OBSERVATION = 2


def _node() -> str:
    found = shutil.which("node")
    if found is None:
        pytest.skip("本机没有 node")
    return found


def _run_checker(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [_node(), str(CHECKER), *args],
        capture_output=True, text=True, encoding="utf-8", cwd=REPO, check=False,
    )


# 观测跑器：逐屏取 DOM 与计算样式。
# **零样式的判法与 `DS-02` 那把尺子同源**：拿一个裸元素当基线，逐条比 19 项计算值，
# 一样就是「类名在、样式没有」——改前的广场屏正是这个样子。
_RUNNER = r"""
import json, sys
from playwright.sync_api import sync_playwright

decl_path, out = sys.argv[1], sys.argv[2]
declaration = json.load(open(decl_path, encoding="utf-8"))
screens = []
with sync_playwright() as p:
    b = p.chromium.launch()
    page = b.new_page(viewport={"width": 1440, "height": 900})
    for screen in declaration["screens"]:
        try:
            page.goto(screen["url"], wait_until="networkidle", timeout=60000)
        except Exception as exc:
            screens.append({"route": screen["route"], "error": str(exc)[:200]})
            continue
        page.wait_for_timeout(1200)
        got = page.evaluate(
            '''([components, styled]) => {
                const bare = document.createElement('div');
                document.body.appendChild(bare);
                const bs = getComputedStyle(bare);
                const props = ['backgroundColor','backgroundImage','borderTopWidth',
                  'borderTopColor','borderTopLeftRadius','boxShadow','paddingTop',
                  'paddingLeft','display','justifyContent','fontSize','fontWeight',
                  'color','fontFamily','fontVariantNumeric','overflow','marginTop',
                  'lineHeight','height'];
                const outC = {};
                for (const sel of components) {
                    const el = document.querySelector(sel);
                    if (!el) { outC[sel] = {present: false, width: 0, height: 0}; continue; }
                    const r = el.getBoundingClientRect();
                    outC[sel] = {present: true, width: r.width, height: r.height};
                }
                const outS = {};
                for (const cls of styled) {
                    const el = document.querySelector('.' + cls);
                    if (!el) { outS[cls] = {present: false, differsFromBare: false}; continue; }
                    const cs = getComputedStyle(el);
                    let differs = false;
                    for (const k of props) if (cs[k] !== bs[k]) differs = true;
                    outS[cls] = {present: true, differsFromBare: differs};
                }
                bare.remove();
                return {components: outC, styled: outS};
            }''', [screen.get("components", []), screen.get("styled", [])])
        screens.append({"route": screen["route"], **got})
    b.close()
open(out, "w", encoding="utf-8").write(
    json.dumps({"schema": "screen-composition/1", "screens": screens},
               ensure_ascii=False, indent=1))
"""


def _declaration_stamp(declaration: Path) -> str:
    """声明文件的内容指纹——取证量的是「声明里点名的那些东西」。"""
    import hashlib

    return hashlib.sha256(declaration.read_bytes()).hexdigest()[:16]


def _observe(declaration: Path = DECLARATION, out: Path = OBSERVED) -> dict[str, object]:
    """取这份真浏览器取证；**声明变了就重拍**。

    改前只判 `out.exists()`：拍过一次就永远用那一份。
    于是 `WB-01` 往声明里加了 `/workbench` 之后，取证里没有它，
    尺子报「声明了这一屏，取证里却没有它」——**而屏是好的，是照片旧了**。

    同一天在 `test_shell_nav.py` 逮到的是这个毛病更坏的一面：
    那份缓存是药丸条之前录的，于是**一条真实的溢出被一路判绿**
    （单据 `docs/blocked/NAV-BAR-OVERFLOWS-AT-390.md`）。

    **这个指纹只盖声明，不盖屏本身**：改一个组件的类名不会让它重拍。
    那一半还没修——上面那张单的末节写着它，是下一批的活。
    """
    if out.exists():
        cached = json.loads(out.read_text(encoding="utf-8"))
        if cached.get("declaration_stamp") == _declaration_stamp(declaration):
            return dict(cached)
        out.unlink()
    if not PWENV.exists():
        pytest.skip(f"本机没有 {PWENV}（playwright 恒在项目外，NEVER 进项目依赖）")
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        runner = Path(tmp) / "screen_composition_runner.py"
        runner.write_text(_RUNNER, encoding="utf-8")
        done = subprocess.run(
            [str(PWENV), str(runner), str(declaration), str(out)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=REPO, check=False,
        )
    if done.returncode != 0:
        pytest.skip(f"前端没起或探针跑不动：{done.stderr[-500:]}")
    got = json.loads(out.read_text(encoding="utf-8"))
    # 指纹在**拍完之后**盖：拍之前盖的话，探针失败会留下一份
    # 「指纹对得上而内容是旧的」缓存，比没有缓存更坏。
    got["declaration_stamp"] = _declaration_stamp(declaration)
    out.write_text(json.dumps(got, ensure_ascii=False, indent=1), encoding="utf-8")
    return dict(got)


# ───────────────────────── 一、声明本身要立得住


def test_the_declaration_covers_the_screens_this_batch_touched() -> None:
    """名单少一项 = 那一屏可以悄悄退化回结构化文本。

    owner 指认的两屏（广场、设计工作台）**必须**在册——它们是本批的由来。
    """
    declaration = json.loads(DECLARATION.read_text(encoding="utf-8"))
    routes = {s["route"] for s in declaration["screens"]}

    assert "/plaza" in routes and "/design" in routes
    for screen in declaration["screens"]:
        assert screen.get("components"), f"{screen['route']} 一个组件都没声明"
        assert screen.get("why"), f"{screen['route']} 没写为什么在册"


def test_the_declaration_covers_every_screen_on_disk() -> None:
    """**GAUGE-15 的核心判据**：屏数与 `web/app/**/page.tsx` 对齐，NEVER 靠人记。

    `GAUGE-12` 建这份声明时只铺了 7 屏（本批动过的那几张）。
    其余 15 屏**只有禁止性判据守着**——而禁止性判据挡得住做错、挡不住没做，
    它们可以悄悄退化回结构化文本而没人拦。那正是广场屏当初过关的方式。

    判**等值**：新增一屏没声明就红，删掉一屏而声明还留着也红。
    靠人记的话，下一张新屏又会是没人量的那一张。
    """
    from tools.check_reachability import app_routes

    declaration = json.loads(DECLARATION.read_text(encoding="utf-8"))
    declared = {s["route"] for s in declaration["screens"]}
    on_disk = set(app_routes())

    assert declared == on_disk, (
        f"没声明的屏：{sorted(on_disk - declared)}；"
        f"声明了却不存在的屏：{sorted(declared - on_disk)}")


def test_every_declared_url_matches_its_route() -> None:
    """动态段填的是**真样例 id**，且填在对的位置。

    填错位置的话，探针会去看另一屏——那时报出来的红指向本屏，而屏本身是好的。
    这与 `fe_smoke.py` 文件头警告的「探针给错地址」是同一件事。
    """
    declaration = json.loads(DECLARATION.read_text(encoding="utf-8"))

    for screen in declaration["screens"]:
        route, url = screen["route"], screen["url"]
        path = url.split("localhost:3000", 1)[1]
        assert len(path.split("/")) == len(route.split("/")), (
            f"{route} 的 url 段数对不上：{url}")
        for want, got in zip(route.split("/"), path.split("/"), strict=True):
            if want.startswith("["):
                assert got and not got.startswith("["), f"{route} 的动态段没填：{url}"
            else:
                assert want == got, f"{route} 与 {url} 对不上"


def test_every_declared_screen_has_at_least_one_styled_class() -> None:
    """只声明组件不声明样式 = 又回到「类名在就算做过」。

    ## `GAUGE-15` 之后开了一个口子，而它比原来更严

    铺满 23 屏时撞上一屏**真的一个带样式的类名都没有**：`/clusters/[id]`
    装的 `AnalysisView` 全组件零 `className`（v0.4 已 verified，
    `DEC-021` 要求停下报 owner）。

    那时只有三条路：

    | 做法 | 后果 |
    |---|---|
    | 随手填一个别处的类名 | 报告变绿，**而那一屏没有变好**——正是这把尺子要治的病 |
    | 不给它写声明 | 它从这把尺子上**消失**，而消失与「查过了没问题」长得一样 |
    | 写空 + 指一张开着的单 | 报告上是显式的一行「这一屏没有样式，单在这儿」 |

    所以 `styled: []` **只在写了 `styled_none_because` 时允许**，
    而下一条判据要求那句话指向的单据真的存在、且还开着。
    """
    declaration = json.loads(DECLARATION.read_text(encoding="utf-8"))

    for screen in declaration["screens"]:
        if screen.get("styled"):
            continue
        assert screen.get("styled_none_because"), (
            f"{screen['route']} 一个 MUST 有样式的类名都没声明，也没说为什么")


def test_a_screen_without_styling_must_name_an_open_sheet() -> None:
    """写空的那几屏，逐条要有一张**开着的**单。

    没有这一条，`styled_none_because` 就成了一句可以随便写的话——
    而那正是 `exempt` 那条纪律防的东西（`NEVER 把「还没做」写成一个理由顶掉红`）。
    """
    declaration = json.loads(DECLARATION.read_text(encoding="utf-8"))
    blank = [s for s in declaration["screens"] if not s.get("styled")]

    # 改前这里钉的是 `len(blank) == 1`——写它的时候 `/clusters/[id]` 是唯一一屏。
    # `FIX-19` 给那一屏加上类名与样式之后 `blank` 空了，它必红——
    # **红的是「今天恰好有一屏是空的」这个事实过去了，不是纪律没了**。
    #
    # 改成**上限**：写空的屏 NEVER 增加。零条时这条判据仍然成立且仍然有意义
    # （多出一屏写空的，它当场红），而不必每次有屏毕业就回来改一个数。
    assert len(blank) <= 1, f"写空的屏多了：{[s['route'] for s in blank]}"
    for screen in blank:
        why = screen["styled_none_because"]
        hit = re.search(r"docs/blocked/[A-Z0-9-]+\.md", why)
        assert hit, f"{screen['route']} 没指出是哪张单：{why}"
        sheet = REPO / hit.group(0)
        assert sheet.exists(), f"{screen['route']} 的单不在：{hit.group(0)}"
        assert sheet.read_text(encoding="utf-8").splitlines()[2].startswith(
            "**状态** open"), f"{screen['route']} 挂的单已经关了"


# ───────────────────────── 二、真屏上零违规


def test_the_real_screens_satisfy_the_declaration() -> None:
    _observe()
    done = _run_checker()

    assert done.returncode == EXIT_OK, done.stdout


def test_no_declared_component_is_zero_size() -> None:
    """`F-09` 的形状：DOM 里有、宽高是 0，用户什么都看不见。"""
    observed = _observe()

    for screen in observed["screens"]:
        for selector, row in (screen.get("components") or {}).items():
            assert row["present"], f"{screen['route']} 没有 {selector}"
            assert row["width"] > 0 and row["height"] > 0, (
                f"{screen['route']} 的 {selector} 占 0 像素")


def test_no_declared_class_is_left_unstyled() -> None:
    """**这条就是「挡得住没做」的那一条**：类名在而计算样式与裸元素逐条相同。"""
    observed = _observe()

    for screen in observed["screens"]:
        for cls, row in (screen.get("styled") or {}).items():
            assert row["present"], f"{screen['route']} 没有 .{cls}"
            assert row["differsFromBare"], f"{screen['route']} 的 .{cls} 零样式"


# ───────────────────────── 三、阴性对照：尺子认得出坏的


def test_a_screen_that_lost_its_cards_is_reported(tmp_path: Path) -> None:
    """把广场的卡片换回无样式列表 → 尺子 MUST 报红**并指出缺哪个组件**。

    没有这一条，「0 处违规」可能只是因为尺子什么都没查。
    """
    declaration = json.loads(DECLARATION.read_text(encoding="utf-8"))
    observed = _observe()
    broken = json.loads(json.dumps(observed))
    for screen in broken["screens"]:
        if screen["route"] == "/plaza":
            screen["components"]["[data-testid='hotspot-card']"] = {
                "present": False, "width": 0, "height": 0}
            screen["styled"]["hotspot-card"] = {"present": True, "differsFromBare": False}

    decl_file = tmp_path / "decl.json"
    obs_file = tmp_path / "obs.json"
    decl_file.write_text(json.dumps(declaration, ensure_ascii=False), encoding="utf-8")
    obs_file.write_text(json.dumps(broken, ensure_ascii=False), encoding="utf-8")

    done = _run_checker("--declaration", str(decl_file), "--observed", str(obs_file),
                        "--json")

    assert done.returncode == EXIT_VIOLATIONS
    kinds = {f["kind"] for f in json.loads(done.stdout)["findings"]}
    subjects = {f["subject"] for f in json.loads(done.stdout)["findings"]}
    assert "missing_component" in kinds, "卡片没了却没报「缺组件」"
    assert "unstyled_class" in kinds, "零样式却没报出来"
    assert "[data-testid='hotspot-card']" in subjects, "报了红却没指出缺哪个"


def test_a_bare_element_anywhere_is_named_with_its_screen(tmp_path: Path) -> None:
    """**卡上点名的阴性对照**：把**任一屏**的组件换成无样式裸元素，
    尺子 MUST 报红**并点名是哪一屏缺哪一项**。

    上一条只试了广场。铺满 23 屏之后，「任一屏」这三个字才有分量——
    只在一屏上验过的尺子，证明不了它在另外 22 屏上也睁着眼。
    """
    declaration = json.loads(DECLARATION.read_text(encoding="utf-8"))
    observed = _observe()
    broken = json.loads(json.dumps(observed))

    # 挑一屏**不是**广场的：本批新铺进来的那一批才是没被验过的部分。
    victim = "/settings/locale"
    hurt = next(s for s in broken["screens"] if s["route"] == victim)
    first_component = next(iter(hurt["components"]))
    first_class = next(iter(hurt["styled"]))
    hurt["components"][first_component] = {"present": False, "width": 0, "height": 0}
    hurt["styled"][first_class] = {"present": True, "differsFromBare": False}

    decl_file = tmp_path / "decl.json"
    obs_file = tmp_path / "obs.json"
    decl_file.write_text(json.dumps(declaration, ensure_ascii=False), encoding="utf-8")
    obs_file.write_text(json.dumps(broken, ensure_ascii=False), encoding="utf-8")

    done = _run_checker("--declaration", str(decl_file), "--observed", str(obs_file),
                        "--json")

    assert done.returncode == EXIT_VIOLATIONS
    findings = json.loads(done.stdout)["findings"]
    named = [f for f in findings if f.get("route") == victim]
    assert named, f"报了红却没点名是哪一屏：{findings}"
    subjects = {f["subject"] for f in named}
    assert first_component in subjects, f"没点名缺哪一项：{subjects}"
    # 零样式那条报的是选择器形态（`.locale`），组件那条报的是原样选择器——
    # 判据照它实际报出来的样子判，NEVER 反过来要求尺子迁就判据的写法。
    assert f".{first_class}" in subjects, f"零样式那一项没点名：{subjects}"


def test_a_screen_that_was_never_probed_is_reported(tmp_path: Path) -> None:
    """**没量过的屏不算做过。** 取证里缺一屏 = 那一屏可以随便退化而没人知道。"""
    declaration = json.loads(DECLARATION.read_text(encoding="utf-8"))
    observed = _observe()
    trimmed = {"schema": observed["schema"],
               "screens": [s for s in observed["screens"] if s["route"] != "/design"]}

    decl_file = tmp_path / "decl.json"
    obs_file = tmp_path / "obs.json"
    decl_file.write_text(json.dumps(declaration, ensure_ascii=False), encoding="utf-8")
    obs_file.write_text(json.dumps(trimmed, ensure_ascii=False), encoding="utf-8")

    done = _run_checker("--declaration", str(decl_file), "--observed", str(obs_file),
                        "--json")

    assert done.returncode == EXIT_VIOLATIONS
    assert "not_probed" in {f["kind"] for f in json.loads(done.stdout)["findings"]}


def test_a_missing_observation_is_not_the_same_as_a_violation(tmp_path: Path) -> None:
    """两件事的修法完全不同：一个是去做界面，一个是去跑取证。

    退出码因此分开（`2` 与 `1`）——共用一个的话，人会照着错的那条去修。
    """
    done = _run_checker("--observed", str(tmp_path / "nope.json"))

    assert done.returncode == EXIT_NO_OBSERVATION
    assert "去跑取证" in done.stdout or "取证" in done.stdout


# ───────────────────────── 四、接进全局门（F-11 的教训）


def test_this_ruler_runs_inside_pytest_q() -> None:
    """**不在门里的尺子等于没有**（`F-11`：两把尺子一红一绿，红的那把没人跑）。

    判的是 pytest 的默认收集面收不收得到本文件——而不是读源码找 `skipif`。
    """
    import sys

    done = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q",
         "-k", "the_real_screens_satisfy_the_declaration"],
        cwd=REPO, capture_output=True, text=True, encoding="utf-8", check=False)

    assert done.returncode == 0, done.stdout[-400:]
    assert "test_the_real_screens_satisfy_the_declaration" in done.stdout
