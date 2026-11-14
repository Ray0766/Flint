"""WB-03-a：中栏对话区 + 提交（走既有 combo 客户端；生成链吃结构化 JSON）。

## 本卡为什么是 `-a`

`WB-03` 原卡要「提交 → 作业 done → `deliverables` 多出一条新的 → 右栏渲染它」。
读完链之后实测到**三处各自独立的断点**，三处都不在前端：

| 步 | 端点 | 今天的实况 | 单 |
|---|---|---|---|
| ① 建项 | `POST /projects/combo` | **503**：`combo_provider` 这条缝全仓没有调用方 | `COMBO-FAMILY-HAS-NO-PROVIDER-ANYWHERE.md` |
| ② 分析 | `POST /projects/{id}/analysis` | 作业一被消费就打**真实** github/arxiv；本批规则「NEVER 真实网络」 | `DEC-057`（窗口只授权过一次） |
| ③ 成文 | `POST /projects/{id}/report` | 要 `analysis_id`，而**没有一条从分析拿回它的路** | `ANALYSIS-ID-HAS-NO-PATH-FROM-AN-ANALYSIS.md` |

所以本卡（`-a`）做的是**今天做得完、也验得了**的那一半：中栏的形状、
真提交（真端点真答复）、真失败态、以及 `never_html_regex` 那条全仓判据。
端到端出真 Block 是 `WB-03-b`，它 blocked 在上面三条上。

## 判据一律正向

链那一段不判「没有正则」了事——**拿结构化 JSON 真跑一遍 `_parse_blocks`，
断言出来的是真 Block**；再把蓝本那套 HTML 原样喂进去，断言这条链
**吃不下它**（0 块）。禁止性的那条（全仓不许用正则抠 `<block`/`<part`）
是工单点名要的，留着，但它是**第三条**，不是唯一一条。
"""
from __future__ import annotations

import json
import re
import subprocess
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
PROBE = REPO / ".ui-probe" / "wb"
REPORT = PROBE / "generate.json"
PWENV = Path(r"C:\pwenv\Scripts\python.exe")

WEB = REPO / "web"
PAGE = WEB / "app" / "workbench" / "page.tsx"
CHAT = WEB / "components" / "workbench" / "WorkbenchChat.tsx"
COMPOSER = WEB / "components" / "workbench" / "WorkbenchComposer.tsx"
CHAIN_CLIENT = WEB / "components" / "chain" / "chainClient.ts"
MESSAGES = WEB / "messages" / "zh.json"
PROBE_TOOL = REPO / "tools" / "ui_probe_wb_generate.py"

#: 中栏这一屏的输入面。变了就重拍——**读一份旧照片的判据等于没有判据**
#: （`WB-01` 现场逮到的：药丸条换了之后那份缓存量的还是上一版屏）。
_INPUTS = (PAGE, CHAT, COMPOSER, WEB / "components" / "workbench" / "WorkbenchTray.tsx",
           WEB / "app" / "globals.css", PROBE_TOOL)


def _inputs_stamp() -> str:
    import hashlib

    h = hashlib.sha256()
    for path in _INPUTS:
        h.update(path.read_bytes() if path.exists() else b"")
    return h.hexdigest()[:16]


def _report() -> dict[str, object]:
    """取真浏览器真栈的那份取证；**输入变了就重拍**。"""
    if REPORT.exists():
        cached = json.loads(REPORT.read_text(encoding="utf-8"))
        if cached.get("inputs_stamp") == _inputs_stamp():
            return dict(cached)
        REPORT.unlink()          # 指纹对不上 = 这一屏改过了，这份照片作废
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
    # 指纹在**拍完之后**盖：拍之前盖的话，探针失败会留下一份
    # 「指纹对得上而内容是旧的」缓存——比没有缓存更坏。
    got["inputs_stamp"] = _inputs_stamp()
    REPORT.write_text(json.dumps(got, ensure_ascii=False, indent=1), encoding="utf-8")
    return dict(got)


# ═════════════════ 一、生成这条链吃的是结构化 JSON（正向，真跑）


def test_the_compose_chain_turns_structured_json_into_real_blocks() -> None:
    """**正向**：喂一份结构化 JSON 进 `_parse_blocks`，出来的是真 `Block`。

    这条判的是「本仓的链本来长什么样」，不是「本仓没有什么」。
    `never_html_regex` 那条规则要防的事，防得住的根据就在这里：
    这条链的入口是 `payload["blocks"]`，一个 `dict`。
    """
    from flint.compose.llm_generator import _parse_blocks
    from flint.domain.models import Block, SectionSpec

    spec = SectionSpec(section_id="summary", inputs=[], check_questions=[], charts=[])
    blocks = _parse_blocks(
        {"blocks": [
            {"type": "heading", "level": 2, "text": "摘要"},
            {"type": "paragraph", "text": "结论一句话", "fact_ids": ["f-1"]},
            {"type": "gap_notice", "hints_ref": "hints-1"},
        ]},
        spec, "del-probe")

    assert [b.type for b in blocks] == ["heading", "paragraph", "gap_notice"]
    assert all(isinstance(b, Block) for b in blocks)
    assert blocks[1].fact_ids == ["f-1"], "三通道那一格没有跟着结构化字段进来"
    assert [b.section_id for b in blocks] == ["summary"] * 3
    assert [b.author for b in blocks] == ["system"] * 3


def test_the_same_chain_cannot_be_fed_the_blueprints_html() -> None:
    """把蓝本那套 HTML 原样喂进去 → **0 块**，且不抛。

    蓝本（`Flint 设计台 v3.dc.html`）让模型直接吐
    `<part id=…><block type=…>…` 再用正则抠回来。本仓这条链**吃不下**它——
    这是结构上的吃不下，不是靠一条约定。
    """
    from flint.compose.llm_generator import _parse_blocks
    from flint.domain.models import SectionSpec

    spec = SectionSpec(section_id="summary", inputs=[], check_questions=[], charts=[])
    html = '<part id="summary"><block type="paragraph">结论一句话</block></part>'

    assert _parse_blocks({"blocks": html}, spec, "del-probe") == []
    assert _parse_blocks({"html": html}, spec, "del-probe") == []


def test_the_generator_asks_the_model_for_structure_not_free_text() -> None:
    """**正向**：生成器走的是 `generate_structured(…, BLOCK_SCHEMA)`。

    自由生成那条路（`generate`）在这里被调到就是走错了链——
    喂个一调用就抛的 provider 进去，抛了说明真的没人走那条路。
    """
    from flint.compose.llm_generator import BLOCK_SCHEMA, build_llm_generator
    from flint.domain.models import SectionSpec

    seen: dict[str, object] = {}

    class OnlyStructured:
        def generate(self, prompt: str, tools: object = None) -> object:
            raise AssertionError("组稿走了自由生成那条路")

        def generate_structured(
            self, prompt: str, schema: object, max_retries: int = 2,
        ) -> object:
            seen["schema"] = schema
            return {"blocks": [{"type": "heading", "level": 2, "text": "摘要"}]}

    spec = SectionSpec(section_id="summary", inputs=[], check_questions=[], charts=[])
    blocks = build_llm_generator(spec, "del-probe", OnlyStructured(), "prompt")([])

    assert [b.type for b in blocks] == ["heading"]
    assert seen["schema"] is BLOCK_SCHEMA, "要的不是那份块 schema"


def test_no_regex_pulls_blocks_out_of_model_output_anywhere_in_the_repo() -> None:
    """工单点名的那条：**全仓没有任何一处用正则从模型输出里抠 `<block` / `<part`**。

    这是本文件里唯一一条禁止性判据（工单要求它在）。它扫的是**代码层**：
    正则构造件与那两个记号出现在同一条语句里。
    """
    machinery = ("RegExp(", "re.compile", "re.search", "re.findall", "re.match",
                 ".match(", ".matchAll(", ".exec(")
    roots = (REPO / "flint", REPO / "web" / "app", REPO / "web" / "components",
             REPO / "web" / "lib", REPO / "harness", REPO / "tools")
    guilty: list[str] = []
    for root in roots:
        for path in root.rglob("*"):
            if path.suffix not in (".py", ".ts", ".tsx", ".mjs", ".js"):
                continue
            if "node_modules" in path.parts or "__pycache__" in path.parts:
                continue
            for lineno, line in enumerate(
                    path.read_text(encoding="utf-8").splitlines(), start=1):
                code = line.split("//")[0].split("#")[0]
                if "<block" not in code and "<part" not in code:
                    continue
                if any(bit in code for bit in machinery):
                    guilty.append(f"{path.relative_to(REPO)}:{lineno}")

    assert guilty == [], f"有人把蓝本那套正则解析搬进来了：{guilty}"


# ═════════════════ 二、中栏的形状照蓝本（真浏览器实测）


def test_the_message_area_takes_the_space_and_scrolls_inside_itself() -> None:
    """蓝本第 116 行：消息区 `flex:1` + 自己滚。

    量的是实况：那一层的 `overflow-y` 是 `auto`，且它塞满了输入区上方的空间。
    """
    m = _report()["shape"]

    assert m["messagesOverflowY"] in ("auto", "scroll"), m["messagesOverflowY"]
    assert float(m["messagesHeight"]) > 0
    # 消息区 + 底部区 ≈ 整栏：中间不该有一块没人认领的空白。
    assert abs(float(m["messagesHeight"]) + float(m["footHeight"])
               - float(m["chatHeight"])) <= 2, m


def test_the_input_area_is_pinned_below_the_messages() -> None:
    """蓝本第 137 行：输入区 `flex-shrink:0`，钉在底下不跟着滚。

    两个方向各量一次：位置在消息区**下方**，且消息区滚动之后它**没动**。
    """
    m = _report()["shape"]

    assert float(m["footTop"]) >= float(m["messagesBottom"]) - 1, m
    assert m["footTopAfterScroll"] == m["footTop"], (
        f"消息区一滚，输入区就跟着走了：{m['footTop']} → {m['footTopAfterScroll']}")


def test_the_tray_sits_between_the_messages_and_the_input() -> None:
    """蓝本第 126 行：「本次组合」在消息区与输入框**之间**。"""
    m = _report()["shape"]

    assert float(m["trayTop"]) >= float(m["messagesBottom"]) - 1, m
    assert float(m["trayBottom"]) <= float(m["inputTop"]) + 1, m


# ═════════════════ 三、提交走既有客户端与既有端点（复用，NEVER 另写）


def test_the_middle_column_reuses_the_existing_chain_client() -> None:
    """提交走 `chainClient#submitCombo`——`CHAIN-04` 已经写好的那一个。

    另写一份的代价不是重复代码：那个文件里写着「前端一句拒绝话都不写、
    把服务端的 message 原样带回屏上」这种与两条端点对过账的决定
    （`docs/blocked/EMPTY-HYPOTHESIS-TWO-CODES.md`），
    另写一份会把它们悄悄丢掉。
    """
    code = PAGE.read_text(encoding="utf-8")

    assert "submitCombo" in code and "chain/chainClient" in code
    stripped = re.sub(r"/\*.*?\*/|//[^\n]*", "", code, flags=re.DOTALL)
    assert "/projects/combo" not in stripped, "屏里自己拼了 combo 的 URL"
    assert "fetch(" not in stripped, "屏里自己发了请求（取数/提交都该走既有客户端）"


def test_the_card_ids_come_from_the_evidence_cards_themselves() -> None:
    """`card_ids` 取自**取回来的那份证据卡**，NEVER 由簇 id 拼。

    `card-20260810-c-20260810-000` 这个形状看着就是「日期 + 簇 id」，
    拼一个出来在今天的数据上大概率能对上——**而对上的那次不会有人发现它是拼的**，
    直到某个簇底下有第二张证据卡。
    （同形先例：`web/app/combo/page.tsx:34-41` 拦下过同一只手。）
    """
    code = "".join(p.read_text(encoding="utf-8")
                   for p in (PAGE, CHAT, COMPOSER) if p.exists())
    stripped = re.sub(r"/\*.*?\*/|//[^\n]*", "", code, flags=re.DOTALL)

    assert "`card-" not in stripped and '"card-' not in stripped, "屏里拼了证据卡 id"
    assert "card_id" in stripped, "没有从证据卡自己身上取 id"


def test_the_request_carries_exactly_what_the_screen_shows() -> None:
    """**正向 · 真栈**：发出去的那一发请求里的卡 id 与假设，
    与屏上「本次组合」列的、以及输入框里打的**逐字相同**。

    只判「发出去了」不够：发的是别的卡也会绿，而那在屏上完全看不出来。
    """
    m = _report()["submit"]

    assert m["method"] == "POST", m
    assert str(m["url"]).endswith("/projects/combo"), m
    assert list(m["sentCardIds"]) == list(m["evidenceOnScreen"]), (
        f"发出去的是 {m['sentCardIds']}，屏上列的是 {m['evidenceOnScreen']}")
    assert m["sentHypothesis"] == m["typedHypothesis"], m


# ═════════════════ 四、真答复上屏：说人话、说实话、不转圈


def test_the_screen_repeats_what_the_server_actually_said() -> None:
    """服务端说什么，屏上就说什么——**前端一句拒绝话都不写**。

    ## 这一发的答复变了，而这条判据守的事一个字没变

    本卡写下时，第一段恒 503（`combo` 这一族没配 provider，
    单 `COMBO-FAMILY-HAS-NO-PROVIDER-ANYWHERE.md`）。
    当时这里就写着：「判据钉的不是『503』这个数，而是**屏上那句话 == 服务端那句话**：
    哪天那一族配上了，这条判据仍然在守同一件事。」

    `COMBO-WIRE-01`（第 16 批）把 provider 插上了，于是这一发是 **200**。
    **兑现那句话**：拒绝那一路照旧比 message；成了那一路比的是
    **回执上的 id == 服务端回的 id**——两路判的都是「屏上说的就是服务端说的」。
    """
    m = _report()["submit"]

    if m["status"] != 200:
        assert m["serverMessage"], "服务端这一发没带 message，判据无从比对"
        assert m["serverMessage"] in m["screenText"], (
            f"服务端说的是「{m['serverMessage']}」，屏上是「{m['screenText'][:200]}」")
        return
    assert m["serverProject"], "200 却没回 project_id"
    assert m["receiptProject"] == m["serverProject"], (
        f"服务端建的是 {m['serverProject']}，屏上回执写的是 {m['receiptProject']}")
    assert list(m["receiptTopics"]) == list(m["serverTopics"]), (
        f"服务端回的主题是 {m['serverTopics']}，屏上回执带的是 {m['receiptTopics']}")


def test_the_screen_never_stays_spinning() -> None:
    """答复回来之后**没有任何一处还在转**（`mark_failed` 那一族的病）。

    那一族的病是「失败不写事件、屏上一直转圈」。这一屏两个方向各量一次：
    提交那一刻**在等**（有等待记号），答复之后**等待记号没了**且有终态消息。
    """
    m = _report()["submit"]

    assert m["pendingWhileWaiting"], "提交时屏上没有任何『在等』的表示"
    assert not m["pendingAfterAnswer"], "答复回来了，屏上还在转"
    # **终态 = 最后一条 receipt/failure**，不是最后一条消息（`COMBO-WIRE-01` 之后
    # 成了那一路后面还跟着一条「下一步还没接上」的 `notice`，它既不是成也不是败）。
    assert m["terminalKind"] in ("receipt", "failure"), m["terminalKind"]
    assert "pending" not in m["kinds"], f"等待那条没被换掉：{m['kinds']}"
    assert ("receipt" in m["kinds"]) != ("failure" in m["kinds"]), (
        f"同一次提交既说成了又说败了：{m['kinds']}")


def test_a_failed_step_says_which_step_failed() -> None:
    """终态要说清是**哪一步**，不是笼统一句「生成失败」/「好了」。

    三步链上任何一步都可能失败，而三种失败该做的事完全不同；
    成了的那一路同理——用户要知道刚才成的是**哪一步**，
    因为后两步今天还没接上（屏上那条 `notice` 说的就是这件事）。

    `COMBO-WIRE-01` 之前这条只判失败那一路（那时第一段恒 503）。现在两路都判，
    **各判各该说的那句话**：

    - 失败：步骤名要**在屏上看得见**（「『按你选的卡建项』这一步没成」）；
    - 成了：屏上说的是**产出了什么**（「建好了，生成了 N 条候选主题」），
      而那个 N MUST 等于服务端真回的条数。步骤名此时落在 `data-wb-msg-step` 上
      （`FB-10` A 类脚手架），屏上不印它——**这不是缺陷**：
      成了的那一刻用户要知道的是「拿到了什么」，不是「刚才那步叫什么」。
    """
    m = _report()["submit"]

    assert m["terminalStep"], f"终态消息没点名是哪一步（kind={m['terminalKind']}）"
    if m["terminalKind"] == "failure":
        assert m["failedStep"] == m["terminalStep"]
        assert m["terminalStep"] in m["screenText"], (
            f"失败了却没说是哪一步：{m['screenText'][:120]}")
        return
    count = len(m["serverTopics"])
    assert count > 0, "回执说成了，服务端却一条主题都没回"
    assert str(count) in m["screenText"], (
        f"服务端回了 {count} 条主题，屏上写的是「{m['screenText'][-60:]}」")


def test_the_button_is_only_enabled_when_the_submission_is_actually_valid() -> None:
    """三态各量一次：没选卡 → 禁用；选了而没写假设 → 禁用；两样齐 → 可点。

    数量上下限走既有的 `comboCountValid`（`lib/topicClient.ts`），
    NEVER 在这一屏另写一个 2~5。
    """
    m = _report()["button"]

    assert m["nothingPicked"] == "disabled", m
    assert m["pickedNoHypothesis"] == "disabled", m
    assert m["both"] == "enabled", m
    code = "".join(p.read_text(encoding="utf-8") for p in (PAGE, COMPOSER) if p.exists())
    assert "comboCountValid" in code, "选卡数上下限没走既有的那一处"


def test_the_screen_is_clean_and_inside_the_viewport() -> None:
    """零控制台报错 · 零横向溢出。

    横向那条按 owner 2026-08-12 的口径量：**最右元素的右缘 ≤ 视口宽**。
    文档级 `scrollWidth` 对 `fixed` 元素恒绿——顶栏那次 390 溢出
    （`docs/blocked/NAV-BAR-OVERFLOWS-AT-390.md`）就是这么被判绿一整批的。
    """
    m = _report()

    assert m["errors"] == [], f"有报错：{m['errors'][:2]}"
    # 浏览器给那一发真答复记的那条 console 行**只许说那个状态码**。
    # 这一格是白名单里最容易变成筛子的一种，所以反过来正向断言它的内容。
    for line in list(m["answerNoise"]):
        assert f"status of {m['answerStatus']}" in line, line
    assert int(m["scrollW"]) <= int(m["vw"]) + 1, f"{m['scrollW']} > {m['vw']}"
    assert float(m["rightmostEdge"]) <= float(m["vw"]) + 0.5, (
        f"最右元素右缘 {m['rightmostEdge']} 超出视口 {m['vw']}：{m['rightmostSelector']}")


@pytest.mark.parametrize("theme", ("light", "dark"))
def test_the_screenshot_is_on_disk(theme: str) -> None:
    matches = list(PROBE.glob(f"workbench-generate-*-{theme}.png"))

    assert matches, f"缺这一张：{theme}"
    assert matches[0].stat().st_size > 10_000, (
        f"{matches[0].name} 只有 {matches[0].stat().st_size} 字节")


# ═════════════════ 五、文案：三种态各说各的


def test_the_three_chat_states_are_three_different_sentences() -> None:
    """「在等」「成了」「失败了」三句话互不相同，且都在字典里。

    合并任意两句，用户就分不出「还要等」与「已经结束了」。
    """
    messages = json.loads(MESSAGES.read_text(encoding="utf-8"))
    keys = ("wb.chat.pending", "wb.chat.receipt.project", "wb.chat.failed")

    lines = [messages[k] for k in keys]
    assert len(set(lines)) == 3, f"三句里有两句一样：{lines}"
