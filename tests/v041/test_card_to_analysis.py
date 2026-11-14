"""NAV-02：点卡片主体 → 这个热点的分析界面。

## 改前的实况（本卡复核过）

`web/views/analysis/AnalysisView.tsx` 是 `HOTSPOT-03` 建的成品：四态齐全、只读、
复用 `viewsClient`。**全仓没有任何屏在用它**——唯一引用它的 `GraphOpenAnalysis`
是个抽屉组件，而那个抽屉自己也没有屏在用。

广场那边同时是断的：`PlazaCards` 早就有 `onSelectCluster` 入参，广场屏一直没往里传。
`PlazaCards.tsx` 里 `href` 出现 **0** 次。**点卡片什么都不会发生。**

> 建好的东西点不到，与没建长得一模一样。

## 呈现行为归 vitest 守

`web/__tests__/app/nav02.test.tsx`（本文件用 subprocess 把它跑进全局门）：
网络层 spy 数请求方法、四态互不冒充、点击排除区双断言、键盘可达。

这里守三件 vitest 够不着的事：**源码里不许出现写请求的形状**、
**判定归属不许被推断**、以及**屏在真浏览器里占了像素**。
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
SCREEN = WEB / "app" / "clusters" / "[id]" / "page.tsx"
PLAZA = WEB / "app" / "plaza" / "page.tsx"
CARDS = WEB / "components" / "plaza" / "PlazaCards.tsx"
STACK = WEB / "components" / "plaza" / "HotspotCardStack.tsx"
ACTIONS = WEB / "components" / "hotspot-card-actions" / "HotspotCardActions.tsx"
VIEW = WEB / "views" / "analysis" / "AnalysisView.tsx"
SPEC = WEB / "__tests__" / "app" / "nav02.test.tsx"
ZH = WEB / "messages" / "zh.json"
EN = WEB / "messages" / "en.json"
ARTIFACT = REPO / ".ui-probe" / "nav02_cluster_analysis.json"

PWENV = Path(r"C:\pwenv\Scripts\python.exe")
PLAZA_URL = "http://localhost:3000/plaza"


def _code_only(path: Path) -> str:
    """只看代码行。**注释里写着的路径不是一条路，写着的方法名不是一个请求。**

    本仓在「判据把说明问题的那句话当成问题本身」这一形状上栽过十二次，
    每一次的修法都是给引用一个位置，而不是把判据放宽。
    """
    text = re.sub(r"/\*[\s\S]*?\*/", "", path.read_text(encoding="utf-8"))
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("//")
    )


def _messages(path: Path) -> dict[str, str]:
    return json.loads(path.read_text(encoding="utf-8"))


# ───────────────────────── 一、屏在，且装的是那个成品


def test_the_carrier_screen_exists() -> None:
    assert SCREEN.exists(), "分析界面还是没有屏装它"


def test_the_screen_mounts_the_existing_view_instead_of_a_second_one() -> None:
    """`NEVER 为这一屏再写一遍分析视图`。

    写第二份的话，两处会各自漂移，而它们展示的是同一份判定——
    到时候用户从广场进去和从图上进去看到的判定不一样，谁也说不清哪个是真的。
    """
    code = _code_only(SCREEN)

    assert "AnalysisView" in code, "屏没装那个成品"
    assert "views/analysis/AnalysisView" in code
    # 复刻的痕迹：自己分四态、自己拼读端点。
    for tell in ("fetchVerdict", "fetchEvidenceCards", "analysis-verdict", "useState<Verdict"):
        assert tell not in code, f"承载屏自己复刻了分析视图的一部分：{tell}"


def test_the_view_is_no_longer_a_screenless_component() -> None:
    """这条判据守的是**这张卡解决的那件事**：成品终于有屏装它了。

    `NEVER 把它写成「AnalysisView 文件存在」`——改前它也存在，而屏上一次都没出现过。
    """
    users = [
        path for path in WEB.rglob("*.tsx")
        if "node_modules" not in path.parts and ".test." not in path.name
        and path != VIEW and "AnalysisView" in path.read_text(encoding="utf-8")
    ]
    screens = [p for p in users if p.parent.parts[-2:][0] == "app" or "app" in p.parts]

    assert screens, f"仍然没有屏在用它（引用它的只有 {[p.name for p in users]}）"


# ───────────────────────── 二、进入即渲染，**进入不触发**


def test_the_screen_never_writes(mutating_verbs: None = None) -> None:
    """打开一个热点的分析界面**只是查看**。

    顺手跑一次分析的代价有两笔，两笔都不可逆：
    ① 用户每点开一次就**付一次钱**；
    ② 同一个热点每次可能显示**不同的判定**——判定本身就不再可被引用。

    源码层判「有没有写的形状」，vitest 那边用网络层 spy 数**实际发出去的方法**。
    两层缺一不可：源码干净可能是把写请求藏在了别处，spy 绿可能是那条路没被走到。
    """
    code = _code_only(SCREEN)

    for verb in ('method: "POST"', 'method: "PUT"', 'method: "PATCH"',
                 'method: "DELETE"', "submitTopicAnalysis", "createCombo"):
        assert verb not in code, f"承载屏里有写请求的形状：{verb}"


def test_the_view_it_mounts_is_read_only_too() -> None:
    """屏干净不代表它装的东西干净——`AnalysisView` 本体也 NEVER 写。"""
    code = _code_only(VIEW)

    for verb in ('method: "POST"', 'method: "PUT"', 'method: "DELETE"'):
        assert verb not in code, f"AnalysisView 里有写请求：{verb}"


# ───────────────────────── 三、判定归属由调用方给出，NEVER 推断


def test_the_verdict_job_comes_from_the_url_not_from_the_cluster_id() -> None:
    """`NEVER 拿 cluster_id 拼一个 job id 去试`。

    `Job` 无 cluster 字段、`jobs` 表也无 `cluster_id`，这条对应关系今天**没有持久化真相**
    （`docs/blocked/HOTSPOT-03.md`）。拼一个去试，猜中的概率不高，
    而猜错时用户看到的是**另一个热点的判定**，并会把它引进计划书。

    **缺就是缺。**
    """
    code = _code_only(SCREEN)

    assert 'get("verdictJob")' in code, "判定归属不是从 URL 读的"
    # 拼 job id 的形状：把 cluster id 塞进一个 job 串。
    assert not re.search(r"job[-_]?\$\{|`job", code), "屏里在拼一个 job id"
    assert "clusterId}-" not in code and "${clusterId}_" not in code


def test_the_plaza_never_carries_its_verdict_job_onto_a_card() -> None:
    """广场 URL 上那个 `verdictJob` 是**调用方**手上的一条判定（`DEC-012`）。

    它不属于任何一张具体的卡——广场今天 154 张，那一条顶多是其中一张的。
    带过去等于替系统宣布「这个 job 就是这张卡的判定」。
    """
    code = _code_only(PLAZA)
    hop = re.search(r"onSelectCluster=\{[\s\S]*?\n\s*\}", code)

    assert hop, "广场没把 onSelectCluster 接上"
    assert "verdictJob" not in hop.group(0), "跳转时把 verdictJob 带上了"
    assert "/clusters/" in hop.group(0)


def test_the_route_is_a_literal_so_the_reachability_ruler_can_see_it() -> None:
    """路由写字面量，NEVER 藏进一个 `route()` 帮手。

    帮手会让 `NAV-01` 的可达性尺子看不见这条边——它读的是源码里的字面路径。
    看不见的后果不是沉默：尺子会报「图里有、源码里没有」，
    而那条红读起来像**图写错了**，实际是代码把路藏起来了。
    """
    from tools.check_reachability import _alias, app_routes, code_edges

    routes = set(app_routes())
    edges = {(src, _alias(dst, routes)) for src, dst in code_edges()}

    assert ("app/plaza/page.tsx", "/clusters/[id]") in edges, (
        "可达性尺子看不见广场 → 分析屏这条边")


# ───────────────────────── 四、点击排除区不倒（HOTSPOT-02）


def test_the_action_area_still_stops_the_card_from_navigating() -> None:
    """卡片主体成了跳转入口之后，这条比以前更要紧。

    不挡住冒泡的话，点「收藏」会**既收藏又跳走**——用户按了一下，屏没了。
    """
    code = _code_only(ACTIONS)

    assert "stopPropagation" in code, "点击排除区没了"
    # 挂在容器上而不是逐个按钮挂：逐个挂的话，将来多一个按钮而有人忘了挂，那一个就会漏。
    assert code.count("stopPropagation") == 1


def test_the_card_body_is_reachable_by_keyboard() -> None:
    """这一下点击**现在真的会跳屏**了，所以它不能只有鼠标能用。

    改前 `onSelectCluster` 没人传，点下去什么都不发生——那时没有键盘可达的问题。
    接上之后就有了：键盘用户走到卡上会**过不去**。
    """
    grid = _code_only(CARDS)
    stack = _code_only(STACK)

    assert 'role={onSelectCluster ? "link" : undefined}' in grid
    assert "onKeyDown" in grid and "preventDefault" in grid
    assert "e.target !== e.currentTarget" in grid, (
        "少了这一句：在动作按钮上按回车会既收藏又跳走——stopPropagation 拦的是 click")
    assert 'e.key === "Enter"' in stack, "堆叠上方向键能翻，却没有一个键能进去"


# ───────────────────────── 五、文案与 vitest 一起进全局门


def test_the_new_copy_is_keyed_in_both_languages() -> None:
    zh, en = _messages(ZH), _messages(EN)

    for key in ("cluster.analysis.title", "cluster.analysis.meta",
                "cluster.analysis.loading"):
        assert key in zh, f"zh 缺 {key}"
        assert key in en, f"en 缺 {key}"
        assert zh[key] != en[key], f"{key} 中英同文——有一侧没翻"


def test_no_hardcoded_chinese_on_the_new_screen() -> None:
    for literal in re.findall(r'"([^"]*)"', _code_only(SCREEN)):
        assert not re.search(r"[一-鿿]", literal), f"屏上有裸中文：{literal!r}"


def test_the_front_end_spec_runs_green() -> None:
    """把 vitest 那一组拉进全局门——**NEVER 只在开发时手跑一次**。

    网络层 spy、四态、点击排除区双断言都在那边，只有它跑到了，
    「零写请求」才是量出来的而不是看出来的。
    """
    done = subprocess.run(
        ["npx", "vitest", "run", "__tests__/app/nav02.test.tsx"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=WEB, shell=True, timeout=900, check=False)

    assert done.returncode == 0, (done.stdout or "")[-3000:] + (done.stderr or "")[-1500:]


# ───────────────────────── 六、运行时：这一屏真的占了像素


_RUNNER = r"""
import json, sys
from playwright.sync_api import sync_playwright

out, plaza_url = sys.argv[1], sys.argv[2]
got = {}
with sync_playwright() as p:
    b = p.chromium.launch()
    page = b.new_page(viewport={"width": 1440, "height": 900})
    errs = []
    writes = []
    page.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
    page.on("request", lambda r: writes.append(r.method + " " + r.url)
            if r.method not in ("GET", "HEAD") else None)

    page.goto(plaza_url, wait_until="networkidle", timeout=60000)
    page.wait_for_selector(".plaza-grid__item[data-cluster-id]", timeout=30000)
    writes.clear()                      # 广场自己的请求不算在分析屏头上
    page.click(".plaza-grid__item[data-cluster-id]")
    page.wait_for_url("**/clusters/**", timeout=30000)
    page.wait_for_selector("[data-testid='analysis-view']", timeout=30000)
    page.wait_for_timeout(1200)

    def box(sel):
        el = page.query_selector(sel)
        r = el.bounding_box() if el else None
        return {"width": r["width"], "height": r["height"]} if r else None

    got["url"] = page.url
    got["view"] = box("[data-testid='analysis-view']")
    got["verdict_heading"] = box("[data-testid='analysis-verdict-heading']")
    got["evidence_heading"] = box("[data-testid='analysis-evidence-heading']")
    got["writes_after_open"] = writes
    got["console_errors"] = errs
    page.screenshot(path=".ui-probe/nav02-cluster-analysis.png", full_page=True)
    b.close()
open(out, "w", encoding="utf-8").write(
    json.dumps({"schema": "nav02/1", **got}, ensure_ascii=False, indent=1))
"""


def _artifact() -> dict[str, object]:
    if ARTIFACT.exists():
        return json.loads(ARTIFACT.read_text(encoding="utf-8"))
    if not PWENV.exists():
        pytest.skip(f"本机没有 {PWENV}（playwright 恒在项目外，NEVER 进项目依赖）")
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        runner = Path(tmp) / "nav02_runner.py"
        runner.write_text(_RUNNER, encoding="utf-8")
        done = subprocess.run(
            [str(PWENV), str(runner), str(ARTIFACT), PLAZA_URL],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=REPO, check=False)
    if done.returncode != 0:
        pytest.skip(f"前端没起或探针跑不动：{done.stderr[-600:]}")
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


def test_clicking_a_real_card_lands_on_the_analysis_screen() -> None:
    """**真点一下**。源码层判得出「接上了」，判不出「点下去到底去了哪」。"""
    got = _artifact()

    assert "/clusters/" in str(got["url"]), f"点完落在了 {got['url']}"
    assert "verdictJob" not in str(got["url"]), "跳转把 verdictJob 带过去了"


def test_the_analysis_screen_occupies_pixels() -> None:
    """`F-09` 那个占 0 像素的争议记号是同一形状：DOM 里有、用户看不见。"""
    got = _artifact()

    for name in ("view", "verdict_heading", "evidence_heading"):
        box = got[name]
        assert box is not None, f"{name} 不在屏上"
        assert box["width"] > 20 and box["height"] > 10, f"{name} 几乎没有面积：{box}"


def test_opening_it_in_a_real_browser_writes_nothing() -> None:
    """网络层 spy 的真浏览器版：打开这一屏，**一个非 GET 请求都不许有**。"""
    got = _artifact()

    assert got["writes_after_open"] == [], got["writes_after_open"]


def test_the_screen_is_clean() -> None:
    got = _artifact()

    assert got["console_errors"] == [], got["console_errors"]
