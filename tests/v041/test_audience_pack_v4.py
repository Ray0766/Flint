r"""AUD-PACK-01：受众选择与 vibe_pack 两屏——补 v4 的说明文字，**其余一个字不重写**。

## 改前实况（先核后动，`stale_premise`）

三条语义**今天已经成立**，不是本卡做的：

| 语义 | 落点 | 谁在守 |
|---|---|---|
| 无默认 | `useState<Audience \| null>(null)` | 本文件 + `test_audience_and_intervention_screens.py` |
| 强制单选 | `type="radio" name="audience"` | 同上 |
| 不选不能提交 | `disabled={audience === null \|\| …}` | 同上 |
| 缺字段即 422 | `flint/api/compose.py` 的 `Literal[...]`（pydantic） | 本文件**真栈实发两次** |

`PackViewer` 也已经是只读清单形态、带 `for_ai_context=false` 标记、
`not_generated` 不冒充空骨架。

**本卡真正补的是三处说明文字**（v4 逐字）：两张受众卡各一句、
未选时按钮上那句、选定后随受众变的两句。

## 「两版互链」那一句没做，且它有单

v4 写着「两版互链（`sibling_deliverable_id`）」。**冻结件里没有这个字段**
（`grep -c sibling contracts/models.py` → 0）——`S2-1` 说了停在这里：
`docs/blocked/SIBLING-DELIVERABLE-ID-IS-NOT-IN-THE-CONTRACTS.md`。
NEVER 在前端编一个出来：编出来的关系没有落点，而屏上会显示成
「两版已互链」这样一句没有任何东西在支撑的话。
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
WEB = REPO / "web"
SCREEN = WEB / "app" / "projects" / "[id]" / "proposal" / "page.tsx"
PACK_VIEWER = WEB / "components" / "pack-viewer" / "PackViewer.tsx"
EXPORT_SCREEN = WEB / "app" / "deliverables" / "[id]" / "export" / "page.tsx"
MESSAGES = WEB / "messages"
DESIGN = REPO / "前端设计" / "应用前端设计需求" / "design-handoff" / "Flint v4.dc.html"
CONTRACTS = REPO / "contracts" / "models.py"
TICKET = REPO / "docs" / "blocked" / "SIBLING-DELIVERABLE-ID-IS-NOT-IN-THE-CONTRACTS.md"
API = "http://127.0.0.1:8000"

#: v4 那三处说明文字（判准取自设计稿原文，见 `test_the_wording_actually_comes_from_the_design_file`）。
V4_KEYS = {
    "proposal.audience.human_reader.blurb": "五套模板（通用",
    "proposal.audience.ai_executor.blurb": "vibe_pack 单一执行包",
    "proposal.submit.unpicked": "选择受众后才能提交",
}


def _zh() -> dict[str, str]:
    return json.loads((MESSAGES / "zh.json").read_text(encoding="utf-8"))


def _post(path: str, body: dict[str, object]) -> int:
    request = urllib.request.Request(
        API + path, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "x-user-id": "demo-user"})
    try:
        with urllib.request.urlopen(request, timeout=30) as res:
            return int(res.status)
    except urllib.error.HTTPError as err:
        return int(err.code)
    except OSError:
        pytest.skip("真栈没起（:8000）——这条判据要实发两次请求")


# ═════════════════ 一、422 是**实测**出来的，不是读出来的


def test_the_endpoint_really_refuses_a_body_without_an_audience() -> None:
    """不带 `audience` 字段发一次 → **实测 422**。

    「受众没有默认值」这句话的服务端形态就是它。读源码读到 `Literal[...]`
    不算证到——那只证明我读对了类型标注。
    """
    assert _post("/projects/proj-demo-fixture/proposal",
                 {"report_id": "del-demo-fixture-report"}) == 422


def test_the_same_endpoint_does_not_refuse_a_body_that_has_one() -> None:
    """带上 `audience` 再发一次 → **不是 422**。

    只断言前一条的话，「这个端点永远 422」也会绿——
    那时受众这一格根本没被读到，而判据看起来很有说服力。
    """
    got = _post("/projects/proj-demo-fixture/proposal",
                {"report_id": "del-demo-fixture-report", "audience": "ai_executor"})

    assert got != 422, f"带了 audience 仍然 422（{got}）——那这条判据证不到东西"


# ═════════════════ 二、v4 的三处说明文字：逐字进词典、两份对称、屏上看得见


@pytest.mark.parametrize("key", sorted(V4_KEYS))
def test_the_v4_wording_landed_verbatim_in_both_locales(key: str) -> None:
    """三处文案逐字照抄进 `zh`，`en` 同时补——两份词典的对称判据管得到它。"""
    zh = _zh()
    en = json.loads((MESSAGES / "en.json").read_text(encoding="utf-8"))

    assert key in zh and key in en, f"{key} 少了一份"
    assert V4_KEYS[key] in zh[key], f"{key} 与 v4 那句对不上：{zh[key]}"


def test_the_wording_actually_comes_from_the_design_file() -> None:
    """判准取自设计稿原文——**在判据里抄一份的话，判的是我抄得对不对**。"""
    src = DESIGN.read_text(encoding="utf-8")
    zh = _zh()

    for key in ("proposal.audience.human_reader.blurb",
                "proposal.audience.ai_executor.blurb"):
        assert zh[key] in src, f"{key} 的文案在设计稿里找不到逐字相同的一句"
    assert "选择受众后才能提交" in src


def test_the_screen_renders_both_blurbs_and_the_button_wording() -> None:
    """三处**到得了屏上**：两张卡各一句 + 按钮文案随受众变。

    只进词典不渲染的话，词典里那三条与「没做」在屏上长得一模一样。
    """
    code = SCREEN.read_text(encoding="utf-8")

    assert "data-audience-blurb" in code, "两张受众卡没有说明那一句"
    assert "proposal.submit.unpicked" in code, "未选时那句没上屏"
    assert "proposal.submit.${audience}" in code, "按钮文案没有随受众变"


def test_the_three_semantics_that_already_held_are_untouched() -> None:
    """三条既有语义**一个字没改**（本卡只补文案）。"""
    code = SCREEN.read_text(encoding="utf-8")

    assert "useState<Audience | null>(null)" in code, "受众有了默认值"
    assert 'type="radio"' in code and 'name="audience"' in code, "不再是强制单选"
    assert "disabled={audience === null" in code, "不选也能提交了"


# ═════════════════ 三、vibe_pack 与报告**长得明显不同**


def test_the_pack_is_a_checklist_in_a_fixed_width_face_not_prose() -> None:
    """技术约束清单第 31 条：vibe_pack 与报告 MUST 长得明显不同。

    三样都判：**清单形态**（`data-pack-layout="checklist"`）·
    **固定宽度字体**（章节正文落在 `<pre>` 里——那是它的字体保证：
    `<pre>` 的默认字体族就是等宽，而报告正文走的是 `--font-body`）·
    **`ai_executor` 那个标记**在屏上印得出来。
    只断言组件渲染成功的话，「它渲染出了一篇散文」也会绿。

    **顺带记一处实况**（本卡没改，写进 trace）：`.pack` 这一族在
    `web/app/globals.css` 里**零 CSS**（`grep -c pack` → 0）。
    今天「等宽」这件事靠的是 `<pre>` 的浏览器默认，不是 `_ds` 的 `--font-mono`。
    这一屏的样式面是空的——`F-09` 记过同一形状的坑（DOM 里有 ≠ 屏幕上有）。
    """
    code = PACK_VIEWER.read_text(encoding="utf-8")

    assert 'data-pack-layout="checklist"' in code, "不是清单形态"
    assert "for-ai-context" in code, "`for_ai_context` 那个标记没上屏"
    assert '<pre className="pack__chapter-body">' in code, (
        "章节正文不在 `<pre>` 里——那它就不是等宽的了")
    assert "pack__chapters" in code and "pack__chapter-title" in code, "九章不是逐条列的"


def test_the_pack_says_not_generated_instead_of_faking_an_empty_skeleton() -> None:
    """`not_generated` 是「还没生成」，NEVER 是 404，也 NEVER 是一个空的九章骨架。"""
    code = PACK_VIEWER.read_text(encoding="utf-8")

    assert 'data-pack-state="not_generated"' in code
    assert "pack.not_generated" in code, "那一态没有自己的文案"


# ═════════════════ 四、v4 那两句「先核后动」的话


def test_the_sibling_link_is_parked_on_a_ticket_because_the_field_does_not_exist() -> None:
    """v4 写着 `sibling_deliverable_id`，而冻结件里没有这个字段 → 开单，NEVER 前端编一个。

    这条判据两个方向各钉一次：字段**确实不在**冻结件里（在的话本单该销）、
    单子在盘上且写清了两种口径。
    """
    assert "sibling" not in CONTRACTS.read_text(encoding="utf-8"), (
        "冻结件里已经有 sibling 了——那这张单该销账，判据也该改")
    assert TICKET.exists(), "矛盾没开单"
    body = TICKET.read_text(encoding="utf-8")
    assert "sibling_deliverable_id" in body and "S2-1" in body
    for code in (WEB / "app").rglob("*.tsx"):
        assert "sibling_deliverable_id" not in code.read_text(encoding="utf-8"), (
            f"{code.name} 里编了一个 sibling_deliverable_id")


def test_the_registry_unavailable_wording_already_has_a_backend_channel() -> None:
    """v4 那句「RegistryValidator 不可用 → 执行包暂缓导出」**后端已经有这条通道**。

    先核后动的结果是「不用动」：`flint/registry/gate.py#registry_pack_gate` 在
    `report.available` 为假时给出 violation 与 `GapHint`（原话点名
    「不可用 ≠ 不存在，不走替换」），`vibe_export_gate` 把它并进 409 的
    `violations`，而导出屏把 `violations` 逐条印出来。

    所以前端**一个字都不用自己写**——那句话的措辞出自后端，
    屏上印的是它原样带回来的东西。
    """
    gate = (REPO / "flint" / "registry" / "gate.py").read_text(encoding="utf-8")
    export_gate = (REPO / "flint" / "spec" / "export_gate.py").read_text(encoding="utf-8")
    screen = EXPORT_SCREEN.read_text(encoding="utf-8")

    assert "validation unavailable" in gate and "不可用 ≠ 不存在" in gate
    assert "registry.violations" in export_gate, "registry 的违规没有并进导出门"
    assert "data-export-violations" in screen, "导出屏没把 violations 逐条印出来"
