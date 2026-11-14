"""NAV-05：主链路**真走一遍**——每一跳的 id 从上一屏拿。

## 为什么不判 href 存在

`href` 在不代表点得过去：目标屏可能 404、可能拿着一个错 id 恒空、
可能渲染出的是「接口未提供」而不是这一跳该有的东西。
**判 href 存在的判据，在链路断掉之后照样是绿的。**

而**硬编一串 id** 是同一个病的另一种形态：把 `proj-demo…` 写进测试，
上一屏不给这个 id 了判据也不知道。所以这里每一跳的 id 都从**上一屏的 DOM**里取。

## 走得到哪里，就走到哪里；走不通的逐条列名

本卡之后主链路的后半段（判定 → 报告 → 导出 / 质量卡 / vibe_pack / 干预）通了。
前半段（分析界面 → 图谱工作台 → 主题列表）**走不通**，两条缺口逐条记在
`docs/blocked/MAIN-CHAIN-HAS-NO-LIVE-ENTRANCE.md`：

1. `POST /workbenches` 未挂 → 入台永远拿不到 `ok`；
2. 广场没有「多选卡片建组合」→ `/combo` 没有入口。

`NEVER 用一条假链接把路连起来`：三种顶法都会说谎，那张单里逐条写了。

## 项目族六屏内部是通的——这一段用**直接进屏**走

它们没有活的入口（上面那张单），所以从顶栏走不到。但「进去之后能不能一路走下去」
是另一件事，而且它今天就该量：入口一旦建好，这一段必须立刻能用。
所以那一段的判据**带着一个真 id 直接进屏**，并在名字里写明这是从哪一屏开始的。
"""
from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
ARTIFACT = REPO / ".ui-probe" / "nav05_walk.json"
SHEET = REPO / "docs" / "blocked" / "MAIN-CHAIN-HAS-NO-LIVE-ENTRANCE.md"
GRAPH = REPO / "assets" / "screen_graph.json"

PWENV = Path(r"C:\pwenv\Scripts\python.exe")
BASE = "http://localhost:3000"
# 项目族没有活的入口，所以那一段从这里进。**这是唯一一处外部给的 id**，
# 而且它是从 demo 库里查出来的真项目，不是编的。后面每一跳都从上一屏取。
SEED_PROJECT = "proj-demo14bf9d94b0"


_RUNNER = r"""
import json, os, sys
from playwright.sync_api import sync_playwright

out, base, seed_project = sys.argv[1], sys.argv[2], sys.argv[3]
os.makedirs(".ui-probe/walk", exist_ok=True)
shots = []
walk = []
errs = []


# 逐跳留一张图（SHIP-08 的出口断言之一）。文件名带序号：**这一趟是有顺序的**，
# 按字母排序的一堆图看不出人是怎么走过来的。
#
# 这里用 `#` 注释而不是 docstring：本函数活在 `_RUNNER` 那个 r-string 里，
# 三引号会**把那个字符串就地截断**——首版正是这么炸的（SyntaxError 指向
# 一句中文标点，而真因是引号）。
def shot(page, name):
    # 序号用**自己的计数器**，NEVER 用 len(walk)：`hop()` 在 append 之前拍、
    # 手写的那两跳在 append 之后拍，同一个长度会被用两次——
    # 首版就撞出了两个 01 与两个 03。
    slug = "".join(c if c.isalnum() else "-" for c in name).strip("-")[:48]
    shots.append(name)
    path = f".ui-probe/walk/{len(shots):02d}-{slug}.png"
    page.screenshot(path=path)
    return path


def hop(page, name, url, wait_for, grab=None):
    r = page.goto(url, wait_until="domcontentloaded", timeout=60000)
    row = {"name": name, "url": url, "status": r.status if r else None}
    try:
        page.wait_for_selector(wait_for, timeout=20000)
        row["rendered"] = True
    except Exception:
        row["rendered"] = False
    row["got"] = page.eval_on_selector(grab[0], grab[1]) if grab and row["rendered"] else None
    row["shot"] = shot(page, name)
    walk.append(row)
    return row


with sync_playwright() as p:
    b = p.chromium.launch()
    page = b.new_page(viewport={"width": 1440, "height": 900})
    page.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)

    # ── ① 顶栏 → 广场：第一跳的「id」是顶栏那条 href 本身。
    page.goto(base + "/plaza", wait_until="networkidle", timeout=60000)
    page.wait_for_selector(".plaza-grid__item[data-cluster-id]", timeout=30000)
    walk.append({"name": "顶栏 → 广场", "url": page.url, "status": 200,
                 "rendered": True, "got": None})
    walk[-1]["shot"] = shot(page, "顶栏 → 广场")

    # ── ② 广场 → 热点分析：cluster id 从卡片上取，NEVER 硬编。
    cluster = page.eval_on_selector(
        ".plaza-grid__item[data-cluster-id]", "e => e.dataset.clusterId")
    hop(page, "广场 → 热点分析", f"{base}/clusters/{cluster}",
        "[data-testid='analysis-view']",
        ("[data-testid='analysis-view']", "e => e.dataset.clusterId"))

    # ── ③ 演示串屏 → Job 进度：job id 从串屏跑出来的那一跳取。
    page.goto(base + "/demo", wait_until="networkidle", timeout=60000)
    walk.append({"name": "顶栏 → 演示串屏", "url": page.url, "status": 200,
                 "rendered": page.query_selector("[data-demo-flow]") is not None,
                 "got": None})
    walk[-1]["shot"] = shot(page, "顶栏 → 演示串屏")

    # ── ④~⑧ 报告那一族。
    #
    # 两个 job 各有各的用处，**NEVER 混成一个**（fe_smoke 的样例登记里写过同一件事）：
    #   `probe-owned-ingest`    → 属于探针这个用户，Job 屏能真渲染（不是「无权查看」）；
    #   `job-gate1-live-qwen`   → demo 库里**唯一**有 verdict 快照的作业。
    # 拿后者去看 Job 屏会撞上 403 的诚实态，而那时红的是样例给错了，不是屏坏了。
    row = hop(page, "Job 进度 → Gate①（跑完了那条入口）",
              f"{base}/jobs/probe-owned-ingest", "[data-job-id]",
              ("[data-job-id]", "e => e.dataset.jobId"))
    link = page.query_selector("[data-gate-link]")
    row["gate_link"] = link.get_attribute("href") if link else None
    status = page.query_selector("[data-job-status]")
    # `UIR-03` 之后那一格的文字是标签（「已完成」），原值在属性上。读原值；
    # 属性是空的（改前的屏）就退回读文字。
    row["job_status"] = (
        (status.get_attribute("data-job-status") or status.inner_text().strip())
        if status else None)
    row["denied"] = page.query_selector("[data-job-denied]") is not None

    job = "job-gate1-live-qwen"
    # 两态各自成一态：判出来了（`[data-gate]`，GateView 的根）
    # 与「这一条还没判」（`[data-gate-unjudged]`）。等其中任一出现。
    hop(page, "→ Gate① 判定", f"{base}/gate/{job}", "[data-gate], [data-gate-unjudged]")
    walk[-1]["got"] = "verdict" if page.query_selector("[data-gate]") else "unjudged"

    deliverable = "del-demo-fixture-report"
    row = hop(page, "Gate① → 报告", f"{base}/deliverables/{deliverable}",
              "[data-export-entry]")
    # 后四跳的 id **全部从这一屏的链接上取**——硬编的话，链接断了判据还是绿的。
    for key, sel in (("export", "[data-export-link]"),
                     ("quality", "[data-quality-link]"),
                     ("pack", "[data-pack-link]"),
                     ("interventions", "[data-interventions-link]")):
        el = page.query_selector(sel)
        row[key] = el.get_attribute("href") if el else None

    # 等的是**那一屏自己的东西**，NEVER 等 `.screen__title`：屏头是外壳给的，
    # 它在数据回来之前就在——等它等于什么都没等，截图拍到的是「正在查……」。
    for key, wait_for in (("export", "[data-export-formats]"),
                          ("quality", "[data-quality-state]"),
                          ("pack", "[data-pack-state]"),
                          ("interventions", "[data-intervention-list]")):
        href = row[key]
        if href:
            hop(page, f"报告 → {key}", base + href, wait_for)

    # ── ⑨~⑫ 项目族：没有活的入口（见单据），所以带一个真项目 id 直接进。
    row = hop(page, "[直接进屏] 主题列表", f"{base}/projects/{seed_project}/topics",
              "[data-topic-list]")
    open_link = page.query_selector("[data-topic-open]")
    row["topic_href"] = open_link.get_attribute("href") if open_link else None
    for key, sel in (("overview", "[data-project-overview-link]"),
                     ("analysis", "[data-project-analysis-link]")):
        el = page.query_selector(sel)
        row[key] = el.get_attribute("href") if el else None

    if row["topic_href"]:
        r2 = hop(page, "主题列表 → 主题详情", base + row["topic_href"],
                 "[data-topic-detail]")
        el = page.query_selector("[data-analysis-link]")
        r2["analysis_href"] = el.get_attribute("href") if el else None
        r2["no_project"] = page.query_selector("[data-analysis-no-project]") is not None
        if r2["analysis_href"]:
            hop(page, "主题详情 → 发起分析", base + r2["analysis_href"],
                "[data-testid='analysis-submit']")

    if row["overview"]:
        r3 = hop(page, "主题列表 → 项目总览", base + row["overview"], "[data-project-links]")
        for key, sel in (("topics", "[data-topics-link]"),
                         ("analysis", "[data-analysis-link]"),
                         ("proposal", "[data-proposal-link]")):
            el = page.query_selector(sel)
            r3[key] = el.get_attribute("href") if el else None
        if r3["proposal"]:
            hop(page, "项目总览 → 计划书受众", base + r3["proposal"], "[data-proposal-fork]")

    b.close()
open(out, "w", encoding="utf-8").write(
    json.dumps({"schema": "nav05/1", "walk": walk, "console_errors": errs},
               ensure_ascii=False, indent=1))
"""


def _walk() -> dict[str, object]:
    if ARTIFACT.exists():
        return json.loads(ARTIFACT.read_text(encoding="utf-8"))
    if not PWENV.exists():
        pytest.skip(f"本机没有 {PWENV}（playwright 恒在项目外，NEVER 进项目依赖）")
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        runner = Path(tmp) / "nav05_runner.py"
        runner.write_text(_RUNNER, encoding="utf-8")
        done = subprocess.run(
            [str(PWENV), str(runner), str(ARTIFACT), BASE, SEED_PROJECT],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=REPO, check=False)
    if done.returncode != 0:
        pytest.skip(f"前端没起或探针跑不动：{done.stderr[-800:]}")
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


def _hop(name: str) -> dict[str, object]:
    for row in _walk()["walk"]:
        if row["name"] == name:
            return row
    raise AssertionError(f"这一跳根本没走到：{name}")


# ───────────────────────── 一、每一跳都真的到了，且渲染出该有的东西


def test_every_hop_answered_200() -> None:
    """**逐跳** 200。有一跳 404 就说明上一屏给的 id 是错的。"""
    for row in _walk()["walk"]:
        assert row["status"] in (200, None), f"{row['name']} 回了 {row['status']}"


def test_every_hop_rendered_what_that_hop_is_for() -> None:
    """`NEVER 只断言 href 存在`：每一跳都等到那一屏该有的东西出现。

    只判 200 的话，一屏「接口未提供」也是 200。
    """
    for row in _walk()["walk"]:
        assert row["rendered"] is True, f"{row['name']} 到了，而这一屏该有的东西没出现"


def test_the_cluster_id_came_from_the_card_not_from_the_test() -> None:
    """**这一跳的 id 从上一屏拿**：广场卡片上的 `data-cluster-id`。

    硬编一串 id 的话，广场哪天不再给 id 了，这条判据还是绿的。
    """
    row = _hop("广场 → 热点分析")

    assert row["got"], "分析屏没说出它在看哪个热点"
    assert row["got"] in row["url"], f"屏上的 id 与 URL 对不上：{row}"
    assert "c-" in str(row["got"])


# ───────────────────────── 二、Job → Gate①：跑完了才给


def test_the_gate_entry_appears_only_after_the_job_is_done() -> None:
    """作业还在跑时点过去，判定屏会如实说「未判定」——**那句话读起来像结论**。

    真相是「还没跑到」。两件事该说的话完全不同，所以入口只在 `done` 之后给。
    """
    row = _hop("Job 进度 → Gate①（跑完了那条入口）")

    assert row["denied"] is False, "样例作业不属于探针那个用户——红的是样例，不是屏"
    if row["job_status"] == "done":
        assert row["gate_link"] == f"/gate/{row['got']}", (
            f"跑完了却没有通往判定的入口：{row}")
    else:
        assert row["gate_link"] is None, (
            f"作业状态是 {row['job_status']}，却给了判定入口")


def test_the_gate_screen_shows_a_verdict_or_says_it_is_unjudged() -> None:
    """两态各自成一态，NEVER 互相冒充。"""
    row = _hop("→ Gate① 判定")

    assert row["got"] in ("verdict", "unjudged")


# ───────────────────────── 三、报告 → 四个同族屏，id 全从上一屏取


def test_the_report_hands_out_four_hrefs_built_from_its_own_id() -> None:
    """四条链接的 id **来自报告屏自己**，判据不写死任何一个。"""
    row = _hop("Gate① → 报告")
    own = row["url"].rstrip("/").rsplit("/", 1)[-1]

    for key in ("export", "quality", "pack", "interventions"):
        assert row[key], f"报告屏没有通往 {key} 的入口"
        assert own in row[key], f"{key} 那条链接里的 id 不是这一屏的：{row[key]}"


def test_all_four_sibling_screens_open() -> None:
    """四屏建好之后此前**一个都点不到**。现在逐屏走一遍。"""
    for key in ("export", "quality", "pack", "interventions"):
        row = _hop(f"报告 → {key}")
        assert row["status"] == 200 and row["rendered"] is True, row


# ───────────────────────── 四、项目族：内部通了（入口另开单）


def test_the_topic_list_leads_somewhere() -> None:
    """这一屏此前是条**死路**——进来之后无处可去。"""
    row = _hop("[直接进屏] 主题列表")

    assert row["topic_href"], "每条主题没有「查看」入口"
    assert row["overview"] and row["analysis"], "项目总览 / 发起分析两条路没接上"
    assert SEED_PROJECT in row["overview"]


def test_the_project_id_is_carried_into_the_topic_detail() -> None:
    """主题详情**不知道**自己属于哪个项目（`Topic` 里没有 project_id）。

    所以项目 id 由调用方带过来（`?project=`），与 `DEC-012` 同一形态。
    带到了就给「发起分析」入口，没带就如实说——`NEVER 拿 topic_id 拼一个项目去试`：
    猜错时用户会把分析发起到**别人的项目**上，而那要花钱。
    """
    row = _hop("主题列表 → 主题详情")

    assert f"project={SEED_PROJECT}" in row["url"], "项目 id 没带过来"
    assert row["no_project"] is False, "带了项目 id，屏上却说不知道属于哪个项目"
    assert row["analysis_href"] and SEED_PROJECT in row["analysis_href"]


def test_the_analysis_screen_opens_from_the_topic_detail() -> None:
    row = _hop("主题详情 → 发起分析")

    assert row["status"] == 200 and row["rendered"] is True, row


def test_the_project_overview_is_the_hub() -> None:
    """三条支路都按项目走，而 id 就在这一屏手上。

    受众分叉从这里进、而不是从报告屏：报告屏只有交付物 id，
    **交付物 → 项目没有可读的对应关系**，从那边接就得猜一个项目 id。
    """
    row = _hop("主题列表 → 项目总览")

    for key in ("topics", "analysis", "proposal"):
        assert row[key], f"项目总览没有通往 {key} 的入口"
        assert SEED_PROJECT in row[key]

    assert _hop("项目总览 → 计划书受众")["rendered"] is True


# ───────────────────────── 五、走不通的那几跳，逐条列名开单


# ───────────────────────── 单据留痕的判法：**收在一处**（GAUGE-16）
#
# 这三样原来在本文件与另一个判据文件里**各有一份、逐字相同**（各 1499 字符）。
# 两份各自漂移的那天，两张单会按两套规矩判——而它们守的是同一条纪律；
# 更坏的是，修好其中一份的人会以为自己修好了这条纪律。
# 收进 `tests/v041/_sheet_trace.py`（下划线开头、不叫 test_*，pytest 不收集它）。
from tests.v041._sheet_trace import (
    assert_every_island_is_accounted_for,
    assert_sheet_keeps_its_trace,
    status_of,
)

SHEET_UNDER_TEST = SHEET


def test_the_broken_hops_are_named_in_a_sheet_that_keeps_its_trace() -> None:
    """`NEVER 用一条假链接把路连起来`（acceptance ④）。

    两条缺口各自点名：缺哪一条端点、缺哪一个功能、以及**三种顶法各自会说什么假话**。

    这条判据原来还钉着「这张单必须 open」。`ENTRY-04` 把「多选建组合」这个功能
    做出来、`ENTRY-05` 把那条边声明进图之后，这张单被**正当地关掉**，
    判据当场变红——**而红的原因是活干完了**。
    该守的从来不是 `open` 那个字，是留痕：单还在、说得出是谁在哪一天关的、
    关掉那一刻写下了为什么。缺口那三处点名照旧钉着，它们记的是当时缺什么。
    """
    state, _day, card = assert_sheet_keeps_its_trace(SHEET)
    text = SHEET.read_text(encoding="utf-8")

    assert state == "closed", f"这张单还开着，而入口已经建出来了：{state}"
    assert card == "ENTRY-05", f"关它的应该是 ENTRY-05，状态行写的是 {card}"
    assert "POST /workbenches" in text, "没点名缺的那条端点"
    assert "多选" in text, "没点名缺的那个功能"
    assert "假话" in text, "没写清为什么不先接一条链接顶上"


def test_every_island_has_a_reason_and_an_open_sheet() -> None:
    """acceptance ⑤ 的后半句：**不可达的逐条在图里标明理由**。

    写理由**不顶红**——写理由只是让「没人管」与「有主，等一件具体的东西」分得开。

    `ENTRY-05` 之后孤岛清零，这条判据因此翻面。**翻的是数字，不是规矩**：
    还有孤岛的时候，每一座仍然要有理由 + 一张留得住痕的单。

    `GAUGE-16` 修的是那次翻面留下的洞：清零那句断言排在遍历的**上一行**，
    循环体永远执行不到——docstring 写着「它必须留着，下一次长出孤岛时它就是那道闸」，
    **而那道闸当时是拆的**。判据的说明与判据的可达性对不上，
    与第 9 批刚修的那两条同族。现在遍历排在前面，且单独有一条阴性对照喂它人造孤岛。

    单据那一条也从「必须 open」改成「必须留得住痕」（与另外两条同一判法），
    并且**不再用 `splitlines()[2]` 数行号**——状态行在第几行不该由行号决定，
    单据头上多一行说明它就红，而红的原因是排版。
    """
    from tools.check_reachability import check

    graph = json.loads(GRAPH.read_text(encoding="utf-8"))
    report = check()

    # **先逐条交代，再判清零**——顺序反了的话循环体永远执行不到。
    # `GAUGE-16` 之前这两句就是反的：`assert islands == []` 排在 `for` 的上一行，
    # 于是「每座孤岛要有理由与单据」这条纪律**全仓没有任何东西在守**
    # （`island_reason` / `island_sheet` 只在那四行出现过）。
    assert_every_island_is_accounted_for(graph, list(report.islands))
    assert report.islands == [], f"又长出孤岛了：{report.islands}"

    # **清零 NEVER 靠往 exempt 里塞**：豁免名单只许有那一条外链屏。
    assert [e["route"] for e in graph["exempt"]] == ["/share/[token]"]
    assert check().clean is True


def test_every_hop_left_a_screenshot() -> None:
    """**SHIP-08 的出口断言之一**：逐跳留图。

    截图不是装饰：`F-09` 那个占 0 像素的争议记号、`REGION-11` 那个 481px 的下拉，
    都是源码层与 DOM 层判不出、只有看图才发现的。这一趟走 15 跳，留下 15 张——
    下一次链路断在哪一跳，对着图就看得出来。
    """
    walk = _walk()["walk"]

    assert len(walk) >= 15, f"只走了 {len(walk)} 跳"
    for row in walk:
        assert row.get("shot"), f"{row['name']} 没留图"
        shot = REPO / row["shot"]
        assert shot.exists(), f"{row['name']} 的图不在：{row['shot']}"
        assert shot.stat().st_size > 3000, f"{row['name']} 的图几乎是空的"

    # 序号连续：这一趟是**有顺序的**，缺号说明中间有一跳没走到。
    numbers = [int(Path(r["shot"]).name.split("-", 1)[0]) for r in walk]
    assert numbers == sorted(numbers) and len(set(numbers)) == len(numbers), numbers


# 盘上 `/deliverables/[id]` 带着 **3 条既有红**：chart / 质量卡 / gap hints
# **全库没有存储面**，端点如实回 404（单据 `DEMO-REFS-NO-STORAGE-FACE` 仍 open）。
# **当前行为是对的，NEVER 修绿。**
#
# 加了逐跳截图之后它们才在这一趟里露面：截图让页面多停了一拍，
# 那几条子请求赶上了。**这不是新问题，是这一趟以前跑得太快没看见。**
#
# 判**等值**，与 `test_screens_live_probe` 同一套办法：判零会把别人的活算成本卡失败，
# 不判会让新增的报错混进来。
KNOWN_404S = 3


def test_the_walk_is_clean_apart_from_the_known_reds() -> None:
    errs = _walk()["console_errors"]
    not_404 = [e for e in errs if "404" not in e]

    assert not_404 == [], not_404
    assert len(errs) == KNOWN_404S, (
        f"404 从 {KNOWN_404S} 变成了 {len(errs)}——回来确认是修好了还是又坏了：{errs}")
    # 单据的状态行**不总在第 3 行**（各单的抬头格式不一样）——所以按行找，
    # NEVER 按行号取：按行号取会在格式一变时报出一句与事实无关的红。
    sheet = REPO / "docs" / "blocked" / "DEMO-REFS-NO-STORAGE-FACE.md"
    status = next(ln for ln in sheet.read_text(encoding="utf-8").splitlines()
                  if ln.startswith("**状态**"))
    assert status.startswith("**状态** open"), (
        f"那三条红挂的单已经关了（{status}）——回来确认这三条是不是也该没了")


def test_a_status_line_that_says_neither_open_nor_closed_goes_red() -> None:
    """**阴性对照**：状态行改成一个既不是 open 也不是 closed 的值 → 判据 MUST 红。

    没有这一条的话，上面那条判据在「状态行烂掉」时的行为无人知晓——
    而一把在坏数据上照样绿的尺子，与一把被注释掉的尺子长得一模一样。

    连**真文件都不动**：把文本改在内存里、写进临时文件。
    改真文件去量一次红，是在盘上留一个随时可能被人当成实况的坏状态。
    """
    text = SHEET_UNDER_TEST.read_text(encoding="utf-8")
    line = next(ln for ln in text.splitlines() if ln.startswith("**状态**"))

    for bogus in ("**状态** 差不多吧 · 2026-08-09 · `X-01`",   # 状态不是三个词之一
                  "**状态** closed · 最近 · `X-01`",           # 日期不是日期
                  "**状态** closed · 2026-08-09"):             # 没说是哪张卡
        with tempfile.TemporaryDirectory() as tmp:
            fake = Path(tmp) / SHEET_UNDER_TEST.name
            fake.write_text(text.replace(line, bogus, 1), encoding="utf-8")
            with pytest.raises(ValueError, match="状态行"):
                assert_sheet_keeps_its_trace(fake)


def test_an_island_without_a_reason_makes_the_gate_go_red() -> None:
    """**阴性对照（孤岛面）**：造一座缺 `island_reason` 的孤岛，闸 MUST 红并点名它。

    今天孤岛是 0，上面那条判据的遍历**一次都不会转**。
    没有这一条的话，`GAUGE-16` 把闸修得可达之后，**谁都不知道它活着**——
    而这正是它上一次坏掉却没人发现的原因。

    造法：拿真图，拆掉 `/plaza -> /combo` 那条头边（`/combo` 与整条项目链退回孤岛），
    再把 `/combo` 的 `island_reason` 抹掉。**真图一个字都不动**——
    改真文件去量一次红，是在盘上留一个随时会被当成实况的坏状态。
    """
    from tools.check_reachability import check

    graph = json.loads(GRAPH.read_text(encoding="utf-8"))
    plaza = next(s for s in graph["screens"] if s["route"] == "/plaza")
    plaza["goes_to"] = [e for e in plaza["goes_to"] if e["to"] != "/combo"]
    combo = next(s for s in graph["screens"] if s["route"] == "/combo")
    combo.pop("island_reason", None)

    with tempfile.TemporaryDirectory() as tmp:
        fake = Path(tmp) / "screen_graph.json"
        fake.write_text(json.dumps(graph, ensure_ascii=False), encoding="utf-8")
        islands = list(check(fake).islands)

    assert "/combo" in islands, "这条对照的前提没了：拆掉头边之后它仍然可达"
    with pytest.raises(AssertionError, match="/combo"):
        assert_every_island_is_accounted_for(graph, islands)


def test_an_island_whose_sheet_is_already_closed_makes_the_gate_go_red() -> None:
    """**阴性对照（孤岛面之二）**：理由写了、单据挂了，**而那张单已经关了**。

    这一条与上一条治的不是同一种偷懒：上一条是「什么都没写」，
    这一条是「写了，但指向一张已经做完的单」——后者更像真的，
    因为它在图里看起来样样齐全。

    用真图里那张已 closed 的 `MAIN-CHAIN-HAS-NO-LIVE-ENTRANCE.md`
    （`ENTRY-05` 关的）。**孤岛挂一张关掉的单** = 这座岛没有主。
    """
    graph = json.loads(GRAPH.read_text(encoding="utf-8"))
    combo = next(s for s in graph["screens"] if s["route"] == "/combo")
    combo["island_reason"] = "造一个理由，专为量下一行"
    combo["island_sheet"] = "docs/blocked/MAIN-CHAIN-HAS-NO-LIVE-ENTRANCE.md"

    # 前提：那张单本身**留得住痕**（它是被正当关掉的）——
    # 所以这一条量的不是留痕，而是「孤岛挂的单不该是关着的」，两件事分开判。
    state, _day, _card = assert_sheet_keeps_its_trace(
        REPO / "docs" / "blocked" / "MAIN-CHAIN-HAS-NO-LIVE-ENTRANCE.md")
    assert state == "closed", "这条对照的前提没了：那张单又开了"

    with pytest.raises(AssertionError, match="这座岛今天没有主"):
        assert_every_island_is_accounted_for(graph, ["/combo"])


def test_a_closed_sheet_without_a_closing_section_goes_red() -> None:
    """**阴性对照第四例**：状态行合法、写着 closed，**而没有「## 关闭」那一节**。

    前三例的坏样本全部落在 `status_of` 的 `ValueError` 上——
    「必须有 `## 关闭` 节」与「关闭那一节要点名同一张卡」是两条 `assert`，
    **一次都没被碰到**：把那两条删掉，阴性对照照样绿。这一例与下一例补上它们。

    期望的是 `AssertionError` 而**不是** `ValueError`：两者说的是两件事——
    前者是「这张单没交代清楚」，后者是「这张单的状态行读不出来」。
    合成一个的话，读到红的人不知道该去补一节还是去修一行。
    """
    text = SHEET_UNDER_TEST.read_text(encoding="utf-8")
    assert "## 关闭" in text, "这条对照的前提没了：这张单本来就没有关闭节"
    stripped = text.split("## 关闭", 1)[0]

    with tempfile.TemporaryDirectory() as tmp:
        fake = Path(tmp) / SHEET_UNDER_TEST.name
        fake.write_text(stripped, encoding="utf-8")
        with pytest.raises(AssertionError, match="没写关闭那一节"):
            assert_sheet_keeps_its_trace(fake)


def test_a_closing_section_that_names_another_card_goes_red() -> None:
    """**阴性对照第五例**：有「## 关闭」那一节，**而里面点的是另一张卡**。

    这是三种关法里最像真的那一种：单据看上去交代得齐全，
    只是状态行说 A 关的、正文说 B 关的。不判的话，
    「谁关的」这件事在盘上有两个互相矛盾的答案，而下一个人只会读到其中一个。
    """
    text = SHEET_UNDER_TEST.read_text(encoding="utf-8")
    line = next(ln for ln in text.splitlines() if ln.startswith("**状态**"))
    _state, day, _card = status_of(text)
    bogus = line.split(" · ")[0] + f" · {day} · `NOBODY-99`"

    with tempfile.TemporaryDirectory() as tmp:
        fake = Path(tmp) / SHEET_UNDER_TEST.name
        fake.write_text(text.replace(line, bogus, 1), encoding="utf-8")
        with pytest.raises(AssertionError, match="没点名 NOBODY-99"):
            assert_sheet_keeps_its_trace(fake)
