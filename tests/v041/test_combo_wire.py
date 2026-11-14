"""COMBO-WIRE-01 · 把 combo 的 provider 插上（缝是留好的，只是没插）。

## 这张卡不是「缺功能」

`flint/api/app.py` 的 `create_app` 早就有 `combo_provider` / `combo_model` 两个参数，
`harness/demo_server.py` 自己的注释也写着怎么插——**全仓就是没有一个调用方传过它**。
于是 `POST /projects/combo` 在**所有**部署上都是 503，
owner 在工作台屏上按下「按你选的卡建项」撞见的就是这一幕
（`docs/blocked/COMBO-FAMILY-HAS-NO-PROVIDER-ANYWHERE.md`）。

## 三件事各有判据，且**一律正向**

1. **插上了**：demo 栈拿到的是真 `LocalProvider` + 真模型名，
   且它与组稿那一族读的是**同一处定义**（`harness/local_model.py`）——
   各造一份的话，「combo 用的是哪个模型」会有两个答案，
   而两个答案在屏上长得一模一样；
2. **那句 503 不再猜原因**：`FamilyNotConfigured` 原话硬写「迁移里没有对应的表」，
   对 combo 是假的（表全在，缺的是模型）。照那句去查迁移的人会白查一趟。
   改后默认不猜，构造方**知道真原因时才写**——两者该让人做的事完全不同；
3. **缝还在**：真去掉某一族的 provider → 仍然 503 且说得出是哪一族没配。
   那条缝的价值就在这里，NEVER 因为「现在插上了」就把它拆掉。

## 阴性对照与正向取证分开放

阴性对照（`test_a_family_without_a_provider_still_refuses_and_says_which`）
在进程内造一个没插 provider 的应用；正向取证在**真浏览器 · 真栈**上跑一遍
owner 撞到的那条路，逐屏落 `.ui-probe/combo_wire/`。
组件快照 NEVER 冒充整屏（本批 `positive_criteria`）。
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "start-demo.ps1"
HARNESS = REPO / "harness"
APP = REPO / "flint" / "api" / "app.py"
PROBE = REPO / ".ui-probe" / "combo_wire"
REPORT = PROBE / "e2e.json"
FINGERPRINT = PROBE / "web_fingerprint.json"
PROBE_TOOL = REPO / "tools" / "ui_probe_combo_wire.py"
PWENV = Path(r"C:\pwenv\Scripts\python.exe")
TICKET = REPO / "docs" / "blocked" / "COMBO-FAMILY-HAS-NO-PROVIDER-ANYWHERE.md"

DSN = os.environ.get(
    "FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")

#: 本批**明示**要改的 web 文件（`TAIL-01`：药丸条那 26 行色号搬进 token 层）。
#: 本卡自己对 web/ 的改动面是**空的**，这张白名单是给同批另一张卡留的门。
BATCH16_WEB_ALLOWLIST = {
    "web/app/globals.css",
    ("web/public/_ds/flint-design-system-"
     "8fd95ba3-cf31-49b6-b9d8-c863f3dc2724/tokens/colors.css"),
}


# ═════════════════ 一、插上了：真 provider + 一处定义


def test_the_demo_stack_hands_combo_a_real_provider() -> None:
    """demo 栈调 `create_app` 时**真的传了** `combo_provider` 与 `combo_model`。

    盯的是那一发调用本身（在真调用点上装个记录器），
    不是「源码里有没有出现 combo_provider 这个词」——
    出现在注释里也算数的话，这条判据从头到尾就是绿的（它此前正是这么绿着的）。
    """
    from flint.llm.local import LocalProvider
    from harness import demo_server

    seen: dict[str, Any] = {}
    real = demo_server.create_app

    def spy(dsn: str, **kwargs: Any) -> Any:
        seen.update(kwargs)
        seen["dsn"] = dsn
        return real(dsn, **kwargs)

    demo_server.create_app = spy            # type: ignore[assignment]
    try:
        demo_server.build_app()
    finally:
        demo_server.create_app = real       # type: ignore[assignment]

    assert isinstance(seen.get("combo_provider"), LocalProvider), (
        f"combo 那条缝还是空的：{seen.get('combo_provider')!r}")
    assert seen.get("combo_model"), "模型名没传：`model=\"unconfigured\"` 会一路进生成记录"
    assert seen["combo_model"] != "unconfigured"


def test_combo_and_the_composing_family_read_one_definition_of_the_model() -> None:
    """combo（API 进程）与组稿（worker 进程）读的是**同一处**模型定义。

    两处各写一份 `os.environ.get("FLINT_FREE_TIER_MODEL", …)` 的话，
    默认值哪天分了叉，「combo 用的是哪个模型」就有两个答案——
    而两个答案在屏上、在日志里长得一模一样。
    """
    from harness import demo_server, local_model, run_worker

    assert demo_server.build_local_provider is local_model.build_local_provider
    assert run_worker.build_local_provider is local_model.build_local_provider
    # combo 的模型名进的是端点的生成记录（`model=` 那一格），所以它也要是同一个。
    assert demo_server.MODEL is local_model.MODEL


def test_only_one_place_in_the_harness_reads_the_model_environment() -> None:
    """`harness/` 里读那两个环境变量的地方**只有一处**。

    判的是代码层（先剥注释与文档串），因为这一族的病正是
    「注释里写着怎么做，而没有人真的做」。
    """
    guilty: list[str] = []
    for path in sorted(HARNESS.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            args = [a for a in node.args if isinstance(a, ast.Constant)]
            if any(a.value in ("FLINT_FREE_TIER_MODEL", "FLINT_LOCAL_BASE_URL")
                   for a in args):
                guilty.append(f"{path.name}:{node.lineno}")

    assert sorted({g.split(":")[0] for g in guilty}) == ["local_model.py"], (
        f"读模型环境变量的地方不止一处：{guilty}")
    assert len(guilty) == 2, f"地址一处 + 模型名一处，实测 {guilty}"


def test_the_shared_provider_is_free_local_and_reads_no_api_key() -> None:
    """那个 provider 是**免费本地档**，且工厂那一路一个 key 都不读。

    付费开通是 owner 人审节点（S2-10）：这条把「本地」钉成可判的东西——
    provider 的地址与模型名逐字等于共享的那两个常量。
    key 那一半判**代码层**（先剥文档串）：说明这条禁令的那句话
    NEVER 被当成犯下禁令（本仓栽过四次）。
    """
    from harness.local_model import MODEL, OLLAMA, build_local_provider

    provider = build_local_provider()

    # `_base_url` 是 `LocalProvider` 自己 rstrip 之后存的那一份（私有，故直取）。
    assert provider._base_url == OLLAMA.rstrip("/")
    assert provider.model == MODEL
    tree = ast.parse((HARNESS / "local_model.py").read_text(encoding="utf-8"))
    docs = {
        id(node.body[0].value) for node in ast.walk(tree)
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef))
        and node.body and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
    }
    literals = [
        node.value for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
        and id(node) not in docs
    ]
    assert not [s for s in literals if "KEY" in s.upper()], literals


# ═════════════════ 二、那句 503 不再猜原因


def test_the_not_configured_message_no_longer_invents_a_cause() -> None:
    """默认那句话**不说原因**。

    改前它硬写「迁移里没有对应的表」——对 combo 是假的（表全在，缺的是模型），
    而 owner 屏上看到的就是这句。**NEVER 把「没配」和「表不存在」写成同一句话**：
    前者去配一个后端，后者去建一张表。
    """
    from flint.api.app import FamilyNotConfigured

    said = str(FamilyNotConfigured("combo"))

    assert "combo" in said, "连是哪一族都没说"
    assert "没配 ≠ 坏了" in said, "没配与坏了这条分界不能丢"
    for guess in ("迁移", "表"):
        assert guess not in said, f"默认那句话又猜了一个原因：{said}"


def test_a_caller_that_knows_the_real_reason_can_say_it() -> None:
    """知道真原因的构造方**可以**写进去，且它照原样出现在响应里。

    这是「不猜」的另一半：不猜不等于不说，
    说不出来的 503 会让人从头翻一遍装配代码。
    """
    from flint.api.app import FamilyNotConfigured

    said = str(FamilyNotConfigured("quality", reason="迁移里没有对应的表"))

    assert "迁移里没有对应的表" in said
    assert "quality" in said


def test_the_model_seam_says_it_is_the_model_that_is_missing() -> None:
    """模型那条缝抛出来的话说的是**模型没注**，不是别的。

    `combo` 与 `interventions` 两族缺的都是 provider；
    此前它们与「没有那张表」共用同一句话。
    """
    from flint.api.app import FamilyNotConfigured, _UnconfiguredProvider

    with pytest.raises(FamilyNotConfigured) as caught:
        _UnconfiguredProvider("combo").generate_structured("x", {}, 2)

    assert "provider" in str(caught.value) or "模型" in str(caught.value), caught.value
    assert "迁移" not in str(caught.value)


def test_no_string_in_the_app_glues_not_configured_to_a_missing_table() -> None:
    """全文件扫一遍：**没有任何一句**同时说「未配置」与「迁移/表」。

    这条守的是下一次——有人再往通用文案里塞一个具体原因时当场红。
    """
    tree = ast.parse(APP.read_text(encoding="utf-8"))
    docs = {
        id(node.body[0].value) for node in ast.walk(tree)
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef))
        and node.body and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
    }
    guilty = [
        f"{node.lineno}: {node.value}"
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
        and id(node) not in docs
        and "未配置" in node.value
        and ("迁移" in node.value or "没有对应的表" in node.value)
    ]

    assert guilty == [], f"通用文案里又硬套了一个具体原因：{guilty}"


# ═════════════════ 三、阴性对照：缝还在


@pytest.mark.compose
def test_a_family_without_a_provider_still_refuses_and_says_which() -> None:
    """**阴性对照**：真去掉 provider → 仍然 503，且**说得出是哪一族**。

    这条缝的价值就在这里：没配时回一个空结果的话，
    屏上读到的是「算过了，没组合出主题」，而真相是「根本没算」。
    """
    import asyncio

    import asyncpg
    from fastapi.testclient import TestClient

    from flint.api.app import create_app

    async def two_cards() -> list[str]:
        conn = await asyncpg.connect(DSN)
        try:
            rows = await conn.fetch(
                "SELECT card_id FROM evidence_cards ORDER BY card_id LIMIT 2")
            await conn.execute(
                "INSERT INTO users (user_id, email, display_name, created_at) "
                "VALUES ($1, $2, $3, now()) ON CONFLICT (user_id) DO NOTHING",
                "combowire-u", "u@combowire.invalid", "U")
        finally:
            await conn.close()
        return [r["card_id"] for r in rows]

    cards = asyncio.run(two_cards())
    assert len(cards) == 2, "测试库里没有证据卡，这条阴性对照会走不到模型那一步"

    with TestClient(create_app(DSN)) as client:          # 不注 combo_provider
        got = client.post(
            "/projects/combo",
            json={"card_ids": cards, "hypothesis": "把这一族的 provider 摘掉之后呢"},
            headers={"X-User-Id": "combowire-u"})

    assert got.status_code == 503, got.text
    body = got.json()
    assert body["family"] == "combo", body
    assert "combo" in body["message"], body
    assert "topics" not in body and "project_id" not in body, (
        f"拒绝里带了组合结果字段：{body}")


# ═════════════════ 四、启动脚本那句话现在是真的（核过，不是碰巧）


def test_the_start_script_promise_about_combo_is_backed_by_the_wiring() -> None:
    """`start-demo.ps1` 打印「combo/Gate 走免费本地 $Model」——**核一遍**。

    只断言那句话在脚本里没有意义：它此前一直在，而它是假的。
    这里判的是**链**：脚本把 `$Model` 写进后端进程的 `FLINT_FREE_TIER_MODEL`，
    而 combo 的模型名正是从那个变量来的。
    """
    script = SCRIPT.read_text(encoding="utf-8")
    line = [ln for ln in script.splitlines() if "combo/Gate" in ln]

    assert line, "那句承诺不见了（改了就该连同这条判据一起改）"
    assert "$env:FLINT_FREE_TIER_MODEL = '$Model'" in script, (
        "脚本没把模型名交给后端进程，那句承诺就又变成一句空话")
    shared = (HARNESS / "local_model.py").read_text(encoding="utf-8")
    assert "FLINT_FREE_TIER_MODEL" in shared, "combo 的模型名不是从那个变量来的"


# ═════════════════ 五、正向取证：真浏览器 · 真栈 · owner 撞到的那条路


def _inputs_stamp() -> str:
    h = hashlib.sha256()
    for path in (PROBE_TOOL, HARNESS / "demo_server.py", HARNESS / "local_model.py",
                 APP):
        h.update(path.read_bytes() if path.exists() else b"")
    return h.hexdigest()[:16]


def _report() -> dict[str, Any]:
    """取那份真栈取证；**输入变了就重拍**（读一份旧照片等于没有判据）。"""
    if REPORT.exists():
        cached = json.loads(REPORT.read_text(encoding="utf-8"))
        if cached.get("inputs_stamp") == _inputs_stamp():
            return dict(cached)
        REPORT.unlink()
    if not PWENV.exists():
        pytest.skip(f"本机没有 {PWENV}（playwright 恒在项目外，NEVER 进项目依赖）")
    PROBE.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory():
        done = subprocess.run(
            [str(PWENV), str(PROBE_TOOL)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=REPO, check=False)
    if done.returncode != 0 or not REPORT.exists():
        pytest.skip(f"真栈没起或探针跑不动：{(done.stderr or done.stdout)[-600:]}")
    got = json.loads(REPORT.read_text(encoding="utf-8"))
    got["inputs_stamp"] = _inputs_stamp()
    REPORT.write_text(json.dumps(got, ensure_ascii=False, indent=1), encoding="utf-8")
    return dict(got)


def test_three_picked_hotspots_show_up_in_this_rounds_tray() -> None:
    """选 3 张热点 → 左栏选中 3 条、中栏「本次组合」列的就是那 3 条。

    判的是**同一批 id**，不是「托盘里有三个东西」——
    托盘里列着别的热点在屏上看不出来。
    """
    m = _report()["pick"]

    assert len(m["picked"]) == 3, m
    assert list(m["trayClusters"]) == list(m["picked"]), (
        f"选的是 {m['picked']}，托盘里列的是 {m['trayClusters']}")
    assert m["evidenceCards"], "这三条热点底下一张证据卡都没取到"


def test_the_build_button_no_longer_answers_five_o_three() -> None:
    """**owner 撞到的那一下**：按「按你选的卡建项」不再 503。

    这条判的是那一发真请求的答复，不是屏上写了什么。
    """
    m = _report()["submit"]

    assert m["status"] == 200, (
        f"还是 {m['status']}：{m.get('serverMessage', '')[:200]}")
    assert m["projectId"], "回来了，但没有 project_id"
    assert len(m["topicIds"]) >= 1, f"没有主题：{m}"
    assert str(m["url"]).endswith("/projects/combo")


def test_the_screen_says_it_worked_and_stops_spinning() -> None:
    """屏上给的是回执、且**没有一处还在转**。

    `mark_failed` 那一族的病是「结束了屏上还在转」——两个方向各量一次。
    """
    m = _report()["submit"]

    assert m["pendingWhileWaiting"], "提交时屏上没有任何『在等』的表示"
    assert not m["pendingAfterAnswer"], "答复回来了，屏上还在转"
    assert m["terminalKind"] == "receipt", m["terminalKind"]


def test_the_topics_it_made_are_really_in_the_database() -> None:
    """回来的那几个 topic_id **在库里查得到**，且主题页把它们列出来了。

    只信响应体的话，一个只在内存里活过的 id 也会让这条绿。
    """
    m = _report()["topics"]

    assert m["screenTopicIds"], "主题页一条都没列出来"
    assert set(m["screenTopicIds"]) <= set(_report()["submit"]["topicIds"]), m
    assert m["inDatabase"] == len(m["screenTopicIds"]), (
        f"屏上 {len(m['screenTopicIds'])} 条，库里 {m['inDatabase']} 条")


def test_the_document_column_renders_real_blocks() -> None:
    """右栏渲染的是**真 Block**：块型全部落在冻结件那八枚里。

    右栏取的是一份真交付物（`?deliverable=`），
    NEVER 拿夹具冒充「你的计划书」（`DEC-012` 判死过同形的手）。
    """
    known = {"heading", "paragraph", "table", "chart", "declaration",
             "quality_card", "citation_list", "gap_notice"}
    m = _report()["doc"]

    assert m["blockCount"] > 0, "右栏一块都没有"
    assert set(m["blockTypes"]) <= known, f"冒出了冻结件没有的块型：{m['blockTypes']}"
    assert m["deliverableId"], "右栏没说自己在看哪一份"


@pytest.mark.parametrize(
    "shot", ("plaza", "picked", "typed", "receipt", "topics", "doc"))
def test_every_step_left_a_screenshot(shot: str) -> None:
    """逐屏留图：这条路上每一步都有一张，且不是空白图。"""
    matches = list(PROBE.glob(f"combo-{shot}-*.png"))

    assert matches, f"缺这一步的截图：{shot}"
    assert matches[0].stat().st_size > 10_000, (
        f"{matches[0].name} 只有 {matches[0].stat().st_size} 字节")


def test_the_walk_raised_no_application_error() -> None:
    """整条路**零应用报错**。

    浏览器给每一发 4xx/5xx 记的那条 `Failed to load resource` 不算——
    它是「某个端点如实拒绝了」的影子，单独一格逐条归属（下一条）。
    """
    m = _report()

    assert m["errors"] == [], f"有报错：{m['errors'][:2]}"


def test_every_refused_call_on_this_walk_belongs_to_a_ticket_that_is_still_open() -> None:
    """被拒的每一发**逐条点名归属**，且 combo 那一发不在其中。

    只数个数的话，九条 `Failed to load resource` 长得一模一样，
    而它们的归属可以是九张不同的单。这里按 URL 分派到两张**仍然 open** 的单：

    - `…/quality` 503 → `QUALITY-FAMILY-HAS-NO-BACKEND.md`（第 14 批开的）；
    - `/hints/` 404 → `REAL-GAP-NOTICES-HAVE-NO-HINTS-REF.md`
      （真 `gap_notice` 块的 `hints_ref` 是空的，于是 URL 拼出来就是 `/hints/`）。

    两张单哪天做掉了，这条会红——**红得对**：那时这一屏该是干净的。
    """
    known = {
        "/quality": "QUALITY-FAMILY-HAS-NO-BACKEND.md",
        "/hints/": "REAL-GAP-NOTICES-HAVE-NO-HINTS-REF.md",
    }
    refused = _report()["refusedCalls"]

    unattributed = [
        call for call in refused
        if not any(mark in str(call["url"]) for mark in known)
    ]
    assert unattributed == [], f"这几发拒绝没有归属：{unattributed}"
    assert not [c for c in refused if "/projects/combo" in str(c["url"])], (
        "combo 那一发又被拒了")
    for mark, ticket in known.items():
        if any(mark in str(c["url"]) for c in refused):
            text = (REPO / "docs" / "blocked" / ticket).read_text(encoding="utf-8")
            assert "**状态** open" in text, (
                f"{ticket} 关掉了，而它挂的那一发还在被拒——这条要重新归属")


# ═════════════════ 六、改动面：web/ 下零字节


def test_this_card_changed_nothing_under_web() -> None:
    """**数一遍**：`web/` 下 277 个文件，除本批明示的两个外逐字未变。

    指纹是本卡开工**前**拍的（改完再拍就是拿结论当证据）。
    白名单里那两个是同批 `TAIL-01` 明示要搬色号的文件——
    第三个文件变了，这条当场红。
    """
    recorded = json.loads(FINGERPRINT.read_text(encoding="utf-8"))["files"]
    changed: list[str] = []
    for rel, digest in recorded.items():
        path = REPO / rel
        if not path.exists():
            changed.append(f"{rel}（没了）")
            continue
        if hashlib.sha256(path.read_bytes()).hexdigest()[:16] != digest:
            changed.append(rel)

    assert len(recorded) == 277, f"指纹面塌了：只有 {len(recorded)} 个文件"
    assert set(changed) <= BATCH16_WEB_ALLOWLIST, (
        f"本批没打算改的 web 文件变了：{sorted(set(changed) - BATCH16_WEB_ALLOWLIST)}")


def test_the_ticket_is_closed_by_this_card() -> None:
    """那张单按新规矩关：状态行三样齐 + `## 关闭` 点名本卡。"""
    text = TICKET.read_text(encoding="utf-8")
    status = [ln for ln in text.splitlines() if ln.startswith("**状态**")]

    assert status, "没有机读状态行"
    assert "closed" in status[0], status[0]
    assert "2026-08-12" in status[0], status[0]
    assert "COMBO-WIRE-01" in status[0], status[0]
    assert re.search(r"^##\s*关闭", text, flags=re.MULTILINE), "缺「## 关闭」那一节"
    closing = text.split("## 关闭", 1)[1]
    assert "COMBO-WIRE-01" in closing, "关闭那一节没点名是哪张卡关的"
