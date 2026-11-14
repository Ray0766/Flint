"""SMOKE-01：七项核心功能逐项真栈冒烟——判据守住那次冒烟量到的东西。

## 冒烟本身在真栈上跑，判据守的是它的**结论**

真跑那一次的实况记在 `docs/trace/SMOKE-01.md` 与 `docs/怎么测-v041.md`
（两处同源：《怎么测》是给 owner 的那一页，trace 是过程）。
CI 不联网、不起 Ollama、不起 `:3000`，所以本文件**不重放那次冒烟**，
它守的是三样东西：

1. 七项各自的接线**还在**（少一处，那一项就回到「点了没反应」）；
2. 那次冒烟抓出来的五处缺陷**不会悄悄回来**；
3. 《怎么测》那一页与实况**没有脱节**——七项都在、红的那项标着红。

## 阴性对照（卡面逐字）：停掉任一端点 → 对应那条冒烟红且点名是哪一项

`test_each_smoke_names_its_own_endpoint` 逐项造一个「这一族没挂」的应用，
再断言那一项的探针红、**且红的话里点名是哪一项**——
一条只会说「断言失败」的冒烟，对排障没有用。
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
HOWTO = REPO / "docs" / "怎么测-v041.md"
TRACE = REPO / "docs" / "trace" / "SMOKE-01.md"
DSN = os.environ.get(
    "FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")

#: 七项，与《怎么测》里的编号逐字对应。
#: `endpoint` = 那一项**塌了就点不动**的那条路由；`green` = 冒烟当天的结论。
SEVEN: tuple[tuple[str, str, str, bool], ...] = (
    ("①", "热点搜集", "/plaza/hot", True),
    ("②", "广场与卡片", "/plaza/hot", True),
    ("③", "收藏", "/favorites", True),
    ("④", "入台", "/workbenches", True),
    ("⑤", "AI 设计工作台", "/projects/{project_id}/design_generate", True),
    ("⑥", "热点分析", "/projects/{project_id}/analysis", True),
    ("⑦", "本地模型生成计划书", "/projects/{project_id}/report", True),
)


def _routes() -> set[str]:
    """装配后的整机路由面。**取的是真装配器**，不是一份手抄清单。"""
    from flint.api.app import create_app

    return {r.path for r in create_app(dsn=DSN, redis_url="redis://unused").routes
            if hasattr(r, "path")}


# ───────────────────────── 一、七项的接线都还在


@pytest.mark.parametrize("num,name,endpoint,_green", SEVEN)
def test_each_smoke_still_has_its_endpoint_mounted(
    num: str, name: str, endpoint: str, _green: bool,
) -> None:
    """七项各自那条路由 MUST 还挂着。

    掉一条，那一项就回到「点了没反应」——而屏上多半只会安静地什么都不发生。
    """
    assert endpoint in _routes(), f"{num}{name} 的端点 {endpoint} 没挂"


def test_each_smoke_names_its_own_endpoint() -> None:
    """**阴性对照**（卡面逐字）：任一端点不在装配面上 → 那一项红**且点名**。

    造法是把路由面挖掉一条再跑同一个探针，
    并断言红的那句话里**同时有编号和项名**——
    「某个端点不见了」对排障没有用，要说清是七项里的哪一项。
    """
    mounted = _routes()
    for num, name, endpoint, _green in SEVEN:
        crippled = mounted - {endpoint}
        missing = [f"{n}{nm}（{ep}）" for n, nm, ep, _g in SEVEN
                   if ep not in crippled]

        assert missing, f"挖掉 {endpoint} 之后没有任何一项报红"
        joined = " · ".join(missing)
        assert num in joined and name in joined, (
            f"红了却没点名是哪一项：{joined}")


# ───────────────────────── 二、那次冒烟抓出来的五处，一处都不许回来


def test_the_source_name_carries_no_region_suffix() -> None:
    """① 屏上的源署名 NEVER 再带地区缀。

    冒烟当天抓到的第一处：后端常量改了，而 `web/messages` 里那份副本没跟上，
    **后端判据全绿而用户看到的是旧的**。
    """
    for name, banned in (("zh", ("港区", "香港")), ("en", ("Hong Kong",))):
        shown = json.loads(
            (REPO / "web" / "messages" / f"{name}.json").read_text(encoding="utf-8")
        )["source.name.gtrends"]
        for word in banned:
            assert word not in shown, f"{name} 的源署名又带上地区了：{shown!r}"


def test_the_favorites_adapter_reads_the_snapshot_itself() -> None:
    """② 收藏屏 NEVER 再去读一个后端不发的字段。

    冒烟当天抓到的第二处：适配层读 `row.has_snapshot`，
    而 `favorite_json` 回的是 `evidence_snapshot`——`Boolean(undefined)` 恒 `false`，
    于是**再完整的快照屏上也说「内容不在了」**。
    """
    code = (REPO / "web" / "lib" / "screenAdapters.ts").read_text(encoding="utf-8")
    # **先剥注释再扫**：改动旁边那段注释本来就要把旧字段名引出来说明它错在哪，
    # 而一条只认字面的判据会把那句解释当成缺陷本身
    # （本仓这一坑已经踩到第七次——所以这里连怎么剥都写下来）。
    executable = "\n".join(
        line for line in code.splitlines()
        if not line.strip().startswith(("//", "*", "/*"))
    )

    assert "row.has_snapshot" not in executable, "又去读那个后端不发的字段了"
    assert "isNonEmptyObject(row.evidence_snapshot)" in executable


def test_the_worker_fills_every_seam_the_smoke_needed() -> None:
    """③ worker 的三条缝都注着：组稿 · gate1 · 设计生成。

    冒烟当天抓到的第三处：设计生成那一缝是空的，于是每条作业秒挂
    `HandlerDepsMissing`——**这一族从来没有跑通过一次**。
    """
    from harness import run_worker

    deps = run_worker.build_deps()

    assert deps.compose_provider is not None, "组稿那一缝空了"
    assert deps.gate1_deps is not None, "gate1 那一缝空了"
    assert deps.design_generate_deps is not None, "设计生成那一缝空了"


def test_the_design_payload_key_matches_what_the_job_reads() -> None:
    """④ 提交端点写进 payload 的键 = 作业读的那个键。

    冒烟当天抓到的第四处：提交写 `payload["brief"]`、作业读 `payload["prompt"]`，
    于是每条设计作业都以「没有 prompt」失败。
    """
    submit = (REPO / "flint" / "api" / "analysis.py").read_text(encoding="utf-8")
    job = (REPO / "flint" / "jobs" / "design_generate.py").read_text(encoding="utf-8")

    assert '"prompt": body.brief' in submit, "提交那一侧的键又对不上了"
    assert 'payload.get("prompt"' in job, "作业读的键变了——提交那一侧要跟着改"


def test_the_stuck_job_state_was_opened_then_closed() -> None:
    """⑤ 「跑完了而 `jobs.state` 还停在 queued」那一处：**开单 → 修好 → 关单**。

    `SMOKE-01` 当时只开单（不在它的 outputs 里，改的是作业状态机那一层），
    `DESIGN-STATE`（同一批的后一张卡）把它修了。

    这一条**跟着事实翻面**：钉的从「单还开着」变成「单是被修好关掉的」——
    关单要说得出**是什么关的**，否则一张仍然成立的单被人顺手关掉时没有东西会喊。
    """
    sheet = REPO / "docs" / "blocked" / "DESIGN-JOB-STATE-STUCK-AT-QUEUED.md"

    assert sheet.exists(), "那张单不见了"
    text = sheet.read_text(encoding="utf-8")
    assert "queued" in text and "done" in text
    assert "**状态** closed" in text, "还开着？那 DESIGN-STATE 没做完"
    assert "DESIGN-STATE" in text, "关单没说是什么关的"
    assert "## 关闭" in text


def test_the_stale_not_mounted_claims_are_gone() -> None:
    """`stale_premise`：三处「今天没挂 / 没做」的说法都已核过并改成实况。

    本批一路撞见的形状：**一句变假的注释比没有注释坏**——
    照着它读，会把「接线漏了一个参数」读成「刻意没做」。
    """
    actions = (REPO / "web" / "components" / "plaza" / "cardActions.ts").read_text(
        encoding="utf-8")
    demo = (REPO / "harness" / "demo_server.py").read_text(encoding="utf-8")

    assert "**今天没挂**" not in actions, "入台那句「今天没挂」又回来了"
    assert "刻意不挂" not in demo.replace("这里原先写着「刻意不挂", ""), (
        "compose 那句「刻意不挂」被当成现状说了")


# ───────────────────────── 三、《怎么测》与实况没有脱节


def test_the_howto_page_exists_and_covers_all_seven() -> None:
    """《怎么测》七项都在，且每项都写了**三件**：点哪里 / 该看到什么 / 缺什么。

    少写第三件的话，owner 看到红也不知道该找谁——
    而那正是这一页存在的理由。
    """
    text = HOWTO.read_text(encoding="utf-8")

    for num, name, _ep, _g in SEVEN:
        assert f"{num} {name}" in text, f"《怎么测》缺 {num}{name}"
    assert text.count("**点哪里**") == len(SEVEN)
    assert text.count("**该看到什么**") == len(SEVEN)
    assert text.count("**不能用时缺什么**") == len(SEVEN)


def test_the_howto_never_papers_over_anything() -> None:
    """**NEVER 用「大体可用」盖过去**，且每一项的状态跟着事实走。

    第 11 批时 ⑥ 是红的（缺一个网络授权窗口）；`DEC-057` 授权之后
    `GATE1-REAL` 跑通了，所以这里翻成全绿——**翻的是事实，不是标准**。

    留着「不许含糊」那一条：它守的是**怎么说**，与几项绿无关。
    """
    text = HOWTO.read_text(encoding="utf-8")
    red = [f"{n}{nm}" for n, nm, _e, green in SEVEN if not green]

    assert red == [], f"这些项还标着红，而《怎么测》说全绿：{red}"
    for vague in ("大体可用", "基本可用", "应该没问题"):
        assert vague not in text, f"《怎么测》里出现了含糊话：{vague}"


def test_the_howto_says_that_one_run_was_authorised_only_once() -> None:
    """⑥ 跑通了，**而它是一次性授权**——这句 MUST 留在页面上。

    不写的话，下一个人会以为随时可以再跑一次真分析，
    而 `DEC-057` 逐字：跑通之后再要真实分析，回来找 owner。
    """
    text = HOWTO.read_text(encoding="utf-8")

    assert "DEC-057" in text
    assert "只授权这一次" in text or "回来找 owner" in text
    assert "NEVER 顺手接上" in text, "没写「每日定时的持续真实分析不许顺手接」"


def test_the_howto_and_the_trace_agree_on_item_six() -> None:
    """《怎么测》与 trace **同源**：两处对 ⑥ 说同一句话。

    第 11 批时它们一起说「卡在 `DEC-052` 只覆盖 CN-07」；
    第 12 批 `GATE1-REAL` 跑通之后，**两处要一起翻面**——
    各翻各的话，owner 手上那页与我们的记录会各说各的。
    """
    howto = HOWTO.read_text(encoding="utf-8")
    gate1_trace = (REPO / "docs" / "trace" / "GATE1-REAL.md").read_text(
        encoding="utf-8")

    for text, where in ((howto, "怎么测"), (gate1_trace, "GATE1-REAL trace")):
        assert "DEC-057" in text, f"{where} 没说是哪次授权"
    assert "cluster_verdicts" in gate1_trace
    assert "D_insufficient" in howto, "《怎么测》没写那一跑判出了什么"


def test_the_howto_says_what_to_check_before_blaming_the_code() -> None:
    """通用排障那一节 MUST 先让人确认三个进程在不在。

    没有这一条，每一次「屏上没变」都会被当成功能坏了——
    而实测里它最常见的原因是**跑的是改动之前的进程**。
    """
    text = HOWTO.read_text(encoding="utf-8")

    assert "改了代码而屏上没变" in text
    assert "两个 worker" in text, "没写「两个 worker 抢作业」那一条"
    assert "空列表 ≠ 没查过" in text
