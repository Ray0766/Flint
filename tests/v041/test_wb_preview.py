"""WB-04：右栏计划书预览（渲染真 Block，八种类型逐一）。

## 复用，NEVER 另写一套渲染

八种块的渲染件本仓**早就有**：`components/BlockTree.tsx` 分节排序、
`components/blocks/BlockView.tsx` 八类各一只读组件 + 三通道 `DerefValue`。
右栏渲染的是同一棵树——另写一份的代价不是重复代码：
`BlockView` 里写着争议记号走几何印记（NEVER emoji）、图表零计算、
保护块标注这些判定面的决定，另写一份会把它们悄悄丢掉。

## 今天拿什么产物来验（`WB-03-b` blocked 的直接后果）

工单原话是「拿 `WB-03` 生成的那份真产物渲染」。`WB-03-b` blocked
（三处断点、两张单），所以拿**库里既有的两份真产物**：

| 产物 | 从哪来 | 有哪几种块 |
|---|---|---|
| `del-job-4d22d6be-…` | 第 12 批那次真跑的 report 作业 | heading ×7 · paragraph ×10 · gap_notice ×5 |
| `del-demo-fixture-report` | 夹具 | **八种各一** |

**这两份都是库里真有的行**（`docker compose exec postgres psql` 实查）。
八种类型只有夹具那份齐全——这不是取巧，是实况：真跑那次的账本是空的
（唯一那条 claim 是 `alignment=partial`，`S2-4` 禁止提升为 Fact），
于是组稿只出得了 heading / paragraph / gap_notice。**这件事本身写进 trace**，
NEVER 用「八种都验过了」一句话盖过去。
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
PROBE = REPO / ".ui-probe" / "wb"
REPORT = PROBE / "preview.json"
PWENV = Path(r"C:\pwenv\Scripts\python.exe")

WEB = REPO / "web"
PREVIEW = WEB / "components" / "workbench" / "WorkbenchPreview.tsx"
CITES = WEB / "components" / "workbench" / "WorkbenchCitations.tsx"
PAGE = WEB / "app" / "workbench" / "page.tsx"
BLOCK_TREE = WEB / "components" / "BlockTree.tsx"
BLOCK_VIEW = WEB / "components" / "blocks" / "BlockView.tsx"
PROBE_TOOL = REPO / "tools" / "ui_probe_wb_preview.py"

#: 冻结件 `Block` 判别联合的八枚（`contracts/models.py#BlockContent`）。
#: 逐字写在这里而不是从代码里读回来——从被判对象身上取判准，判的是它自己。
EIGHT = ("heading", "paragraph", "table", "chart", "declaration",
         "quality_card", "citation_list", "gap_notice")

_INPUTS = (PREVIEW, CITES, PAGE, WEB / "app" / "globals.css", PROBE_TOOL)


def _inputs_stamp() -> str:
    import hashlib

    h = hashlib.sha256()
    for path in _INPUTS:
        h.update(path.read_bytes() if path.exists() else b"")
    return h.hexdigest()[:16]


def _report() -> dict[str, object]:
    if REPORT.exists():
        cached = json.loads(REPORT.read_text(encoding="utf-8"))
        if cached.get("inputs_stamp") == _inputs_stamp():
            return dict(cached)
        REPORT.unlink()
    if not PWENV.exists():
        pytest.skip(f"本机没有 {PWENV}（playwright 恒在项目外）")
    PROBE.mkdir(parents=True, exist_ok=True)
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


# ═════════════════ 一、渲染的是**同一棵树**，NEVER 另写一套


def test_the_preview_renders_the_existing_block_tree() -> None:
    """右栏用的是既有的 `BlockTree` / `BlockView`，不是新写的一份。"""
    code = PREVIEW.read_text(encoding="utf-8")

    assert "BlockTree" in code, "右栏没复用既有的 `BlockTree`"
    # 另写一套的形态：自己按 type 分派。
    stripped = re.sub(r"/\*.*?\*/|//[^\n]*", "", code, flags=re.DOTALL)
    for kind in ("citation_list", "quality_card", "gap_notice"):
        assert f'case "{kind}"' not in stripped, f"右栏自己分派了 {kind}——那是 BlockView 的活"


def test_the_shared_renderer_was_not_touched() -> None:
    """`BlockTree` / `BlockView` **一个字没改**——本卡只是它们的又一个调用方。

    它们是 v0.4 已 verified 的件（`DEC-021` 封版面）：要改得停下报 owner。
    """
    for path in (BLOCK_TREE, BLOCK_VIEW):
        assert "WB-04" not in path.read_text(encoding="utf-8"), (
            f"{path.name} 里出现了本卡的痕迹——它本不该被动")


def test_the_preview_reuses_the_existing_blocks_client() -> None:
    """取数走既有 `fetchBlocks`（`GET /deliverables/{id}/blocks`），NEVER 自己拼 URL。"""
    code = PREVIEW.read_text(encoding="utf-8")
    stripped = re.sub(r"/\*.*?\*/|//[^\n]*", "", code, flags=re.DOTALL)

    assert "fetchBlocks" in code
    assert "/deliverables/" not in stripped, "右栏自己拼了交付物端点"


# ═════════════════ 二、八种类型逐一渲染出了东西（真栈实测）


@pytest.mark.parametrize("kind", EIGHT)
def test_every_one_of_the_eight_block_types_renders_something(kind: str) -> None:
    """**正向 · 逐类型**：八种块各自在屏上渲染出了**有面积的**东西。

    只判 `data-block-type` 在不在不够：一个渲染成 0×0 的块，
    在 DOM 里齐全、在屏上什么都没有。
    """
    rendered = dict(_report()["fixture"]["byType"])  # type: ignore[index,call-overload]

    assert kind in rendered, f"夹具那份产物里没有 {kind} 块——这一类没验到"
    box = rendered[kind]
    assert float(box["w"]) > 0 and float(box["h"]) > 0, f"{kind} 渲染出来是 0 面积：{box}"
    assert str(box["text"]).strip() != "" or kind == "chart", (
        f"{kind} 块屏上一个字都没有")


def test_the_real_generated_product_renders_too() -> None:
    """**真产物**（第 12 批那次真跑的 report 作业产出）也渲染得出来。

    夹具那份验的是「八种都画得出」，这一份验的是「链真的产出的东西画得出」——
    两者缺一：只验夹具的话，真产物里那些形状从没被这一屏见过。
    """
    m = _report()["real"]

    assert int(m["blockCount"]) > 0, "真产物一个块都没渲染出来"
    assert set(m["types"]) <= set(EIGHT), f"出现了冻结件之外的块型：{set(m['types']) - set(EIGHT)}"
    # 真跑那次账本是空的（唯一那条 claim alignment=partial，S2-4 禁止提升），
    # 所以它必然有 gap_notice——「资料不足绝不注水」在真产物上的样子。
    assert "gap_notice" in m["types"], "真产物里没有 gap_notice——那与库里的实况对不上"


def test_an_unknown_block_type_is_reported_not_silently_dropped() -> None:
    """**阴性对照**：塞一种未知类型 → 屏上**显式报出**，NEVER 静默跳过。

    静默跳过的后果：报告少了一段，而屏上、DOM 里、控制台里都没有任何痕迹。
    （既有 `BlockView` 走的是编译期穷尽 + 运行期抛错——抛错会让整屏空白，
    所以未知块在**进 BlockTree 之前**就被挑出来，单独说清。）
    """
    m = _report()["unknown"]

    assert int(m["noticeCount"]) == 1, "未知块没有被显式报出"
    assert m["noticeNamesTheType"], f"报出来了却没说是哪一种：{m['noticeText']}"
    assert int(m["knownStillRendered"]) > 0, "一个未知块把整棵树带没了"


# ═════════════════ 三、数字说得出自己走哪条通道


def test_every_number_names_its_channel() -> None:
    """三通道（`Fact` / `PriceCell` / `ProfileRef`）：**每个数字旁边说得出走哪条**。

    判的是渲染出来的每一个数据格都带且只带一个通道记号——
    带两个等于这个数字有两个出处，那是三通道要防的第一件事。
    """
    m = _report()["fixture"]["channels"]  # type: ignore[index,call-overload]

    assert int(m["cells"]) > 0, "夹具那份产物里没有带出处的数据格——这一条验不到"
    assert m["everyCellHasExactlyOneChannel"], f"有格子的通道不是恰好一个：{m['bad']}"
    assert set(m["kinds"]) <= {"fact", "price", "profile"}, m["kinds"]


def test_the_channel_values_come_from_the_backend_not_the_screen() -> None:
    """屏上那个数 == 后端那条通道回的数（**显示的是不是对的东西**）。

    第 13 批那条补充的形态：不判「有个数字」，判「这个数字与数据源逐字相同」。
    """
    m = _report()["fixture"]["channels"]  # type: ignore[index,call-overload]

    screen = str(m["screenValue"])
    statement = str(m["backendStatement"])

    assert screen, "屏上那一格是空的"
    # 比的是**后端那条 fact 的两样东西都到了屏上**，NEVER 在这里把
    # `DerefValue` 的排版规则再实现一遍去比逐字相等——那样判的是我抄得像不像。
    assert screen.startswith(statement), f"屏上「{screen}」不是以后端那句话开头"
    # 数字在**那句话之后**那一段里找：那句话本身也含数字（「按 12 实例月记账」），
    # 整格里找的话，这条判据会被文案里的数字喂饱而永远绿。
    tail = screen[len(statement):]
    found = {float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", tail)}
    assert float(str(m["backendValue"])) in found, (
        f"屏上那个数是 {found}，后端是 {m['backendValue']}")


# ═════════════════ 四、引用可展开到原文（PRINCIPLES#B10）


def test_citations_expand_to_the_original_text() -> None:
    """引用槽给得出**原文**（`Citation.quote_span`），且与后端逐字相同。

    `B10` 的原话是「译文引用 MUST 可展开到原文」。今天这批引用没有译文槽，
    所以 `QuoteSlot` 显示的就是原文本身（它自己的规矩：无译文数据时只显原文，
    NEVER 摆一个展开出同一段文字的按钮）。判据钉的是**原文到得了屏上**。
    """
    m = _report()["citations"]

    assert int(m["count"]) > 0, "右栏没有列出任何引用"
    assert m["originalOnScreen"], "引用槽里没有原文"
    assert m["originalOnScreen"] == m["backendQuoteSpan"], (
        f"屏上原文与后端 quote_span 不一致：{m['originalOnScreen'][:60]}")


def test_the_citation_panel_reuses_the_existing_quote_slot() -> None:
    """引用槽复用既有 `QuoteSlot`（`I18N-05` 那一个），NEVER 另写一个。"""
    code = CITES.read_text(encoding="utf-8")

    assert "QuoteSlot" in code and "quote-slot/QuoteSlot" in code


# ═════════════════ 五、渐进出现：块是**一块一块到的**


def test_blocks_arrive_one_by_one_over_the_event_stream() -> None:
    """接既有 SSE 那一路（`openJobStream` + `applyEvent` 的 `partial_block`）。

    实测拿一个**真作业**的事件流回放：到达的块 id 与那份产物里的块 id 对得上。
    自己数「渲染了几个」不算——那是屏上的数，不是链上报的数。
    """
    m = _report()["stream"]

    assert int(m["arrived"]) > 0, "事件流里一个 partial_block 都没到"
    assert set(m["arrivedIds"]) <= set(m["deliverableBlockIds"]), (
        f"到的块不在那份产物里：{set(m['arrivedIds']) - set(m['deliverableBlockIds'])}")
    assert m["progressOnScreen"], "屏上看不出块在一块一块地到"


def test_a_dropped_stream_says_so_instead_of_stopping_silently() -> None:
    """断线走既有 `SseDisconnectNotice`（`SSE-DISCONNECT` 的既有纪律）。

    静默停住的话，屏上停在半截而用户以为还在生成——
    那正是 `mark_failed` 那一族的病在流式这一侧的样子。
    """
    code = PREVIEW.read_text(encoding="utf-8")

    assert "SseDisconnectNotice" in code, "断线态没走既有那一件"
    assert "openJobStream" in code and "applyEvent" in code, "自己实现了一套流处理"


# ═════════════════ 六、四种态各说各的 + 屏没坏


def test_the_four_preview_states_are_four_different_things() -> None:
    """还没产出 / 正在取 / 取失败 / 没这一份 —— 四态各有记号，NEVER 合并。"""
    code = PREVIEW.read_text(encoding="utf-8")

    for state in ("empty", "loading", "failed", "not_found"):
        assert f'"{state}"' in code, f"少了 `{state}` 这一态"
    # 四态各有**自己的机器可读记号**（`data-wb-doc-note`），且四句话互不相同。
    # 第一版在这里扫 `data-wb-doc-state="…"`——而那个属性的值是算出来的
    # （`data-wb-doc-state={state}`），源码里根本没有那种字面量：
    # 红的是判据自己，它去源码里找一个只在运行时存在的字符串。
    marks = set(re.findall(r'data-wb-doc-note="(\w+)"', code))
    assert marks == {"empty", "loading", "failed", "not_found"}, marks
    messages = json.loads((WEB / "messages" / "zh.json").read_text(encoding="utf-8"))
    lines = [messages[k] for k in
             ("wb.doc.placeholder", "wb.doc.loading", "wb.doc.failed", "wb.doc.not_found")]
    assert len(set(lines)) == 4, f"四态里有两句话是一样的：{lines}"


#: 这一屏上每一条 4xx 各自是谁、为什么——**逐条点名归属**。
#: 「零控制台报错」在这一屏做不到，而做不到的原因本身是产品事实：
#: 引用了一个真 id 而那类实体没有存储面（前三条，早登记），
#: 或者**根本没有 id**（第四条，本卡逮到的，另立一单）。
#: 把它们并成一句「已知噪声」的代价：下一条真的报错混进来时没有人会发现。
#: 键是**路径前缀**（`/quality` 那条带交付物 id，逐字列不出来）。
KNOWN_404 = {
    "/charts/chart-demo-cost-trend": "docs/blocked/DEMO-REFS-NO-STORAGE-FACE.md",
    "/cards/qc-demo-fixture-01": "docs/blocked/DEMO-REFS-NO-STORAGE-FACE.md",
    "/hints/sec-04-gap-hints": "docs/blocked/DEMO-REFS-NO-STORAGE-FACE.md",
    "/hints/": "docs/blocked/REAL-GAP-NOTICES-HAVE-NO-HINTS-REF.md",
    "/deliverables/": "docs/blocked/QUALITY-FAMILY-HAS-NO-BACKEND.md",
}


def test_every_console_error_on_this_screen_is_one_of_the_named_four() -> None:
    """控制台里那些报错**逐条对得上一张单**，且每张单在盘上。

    多一条 = 有新东西坏了，这里当场红；少一条 = 修好了，来这里删一行。
    """
    m = _report()
    seen = set(m["badPaths"])
    unnamed = {p for p in seen if not any(p.startswith(k) for k in KNOWN_404)}

    assert unnamed == set(), f"出现了没登记的 4xx：{unnamed}"
    for path in seen:
        key = next(k for k in KNOWN_404 if path.startswith(k))
        ticket = REPO / KNOWN_404[key]
        assert ticket.exists(), f"{path} 登记的单子不在盘上：{ticket}"
        # `/deliverables/` 这一条只许是 `quality`——它是那一族没配后端留下的。
        if key == "/deliverables/":
            assert path.endswith("/quality"), f"交付物那一族多出一条 4xx：{path}"
    # 控制台那一侧只许是资源加载行——别的形态（JS 抛错）一条都不许。
    for line in list(m["errors"]):
        assert "Failed to load resource" in line, f"这不是资源加载报错：{line}"


def test_a_source_that_cannot_be_fetched_says_so_on_screen() -> None:
    """**正向**：取不回来的出处，屏上如实说「接口未提供」并留下原 id。

    空白读起来是「这里本来就没东西」——而实况是「这一条有出处，只是取不到」。
    """
    m = _report()["real"]["unavailable"]  # type: ignore[index,call-overload]

    assert int(m["count"]) > 0, "真产物里那几条取不回来的出处，屏上一条都没说"
    assert m["saysSo"], "有一格是空白的"
    # 真产物那 5 个 gap_notice 的 ref 是**空串**（本卡逮到的那条单）。
    assert "hints" in list(m["kinds"]), m["kinds"]


def test_the_screen_is_inside_the_viewport() -> None:
    m = _report()

    assert float(m["rightmostEdge"]) <= float(m["vw"]) + 0.5, (
        f"最右元素右缘 {m['rightmostEdge']} 超出视口：{m['rightmostSelector']}")


@pytest.mark.parametrize("theme", ("light", "dark"))
def test_the_screenshot_is_on_disk(theme: str) -> None:
    matches = list(PROBE.glob(f"workbench-preview-*-{theme}.png"))

    assert matches, f"缺这一张：{theme}"
    assert matches[0].stat().st_size > 10_000, (
        f"{matches[0].name} 只有 {matches[0].stat().st_size} 字节")
