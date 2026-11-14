"""COMBO-ECHO：前端类型描述了一份**不存在的形状**。

## 两边对着虚构达成一致，尺子报绿

`/projects/combo` 的 `card_ids` / `hypothesis` / `n` **一个都不在响应里**——
前两个来自 `runner.submit(payload={…})`（调用方发出去的东西），
`n` 来自 `flint/api/combo.py` 里一个局部计数器 `counter = {"n": 0}`。
而前端 `ComboSubmitEcho` 恰好照着这三个建了类型。

**这比报错更坏：它把「没人核对过」伪装成「核对过、没问题」。**

第 9 批 `SHIP-09` 修对账器时看见了这一处（单据
`PARITY-READS-A-REQUEST-PAYLOAD-AS-A-RESPONSE.md`），当时不在射程；本卡收口。

## 判的是真响应，不是另一份人写的声明

比对的对象是 **`ComboCreateResponse(...).model_dump()` 的键**——
端点最后那一句就是 `JSONResponse(ComboCreateResponse(...).model_dump())`，
所以这些键**字面上就是会走到线上去的那些**。
比对两份声明的话（TS 接口 vs pydantic 类的源码文本），
两边一起写错时判据照样绿——而那正是本卡要治的病。
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TYPES = REPO / "web" / "lib" / "types.ts"
COMBO_API = REPO / "flint" / "api" / "combo.py"
SHEET = REPO / "docs" / "blocked" / "PARITY-READS-A-REQUEST-PAYLOAD-AS-A-RESPONSE.md"


def _interface(name: str) -> set[str]:
    """从 `types.ts` 里取一个接口的字段名。"""
    text = TYPES.read_text(encoding="utf-8")
    hit = re.search(rf"export interface {name}\s*\{{(.*?)\n\}}", text, re.DOTALL)
    assert hit, f"types.ts 里没有 {name}"
    body = "\n".join(
        ln for ln in hit.group(1).splitlines()
        if not ln.strip().startswith(("//", "*", "/*")))
    return set(re.findall(r"^\s*(\w+)\??\s*:", body, re.MULTILINE))


# ───────────────────────── 一、真响应的键 == 前端类型的字段


def test_the_combo_type_matches_what_the_endpoint_really_serialises() -> None:
    """**拿真响应比对**：端点交出去的就是 `model_dump()` 的这些键。"""
    from flint.api.schemas import ComboCreateResponse

    on_the_wire = set(ComboCreateResponse(
        project_id="p-1", topic_ids=["t-1"], degraded=False).model_dump())

    assert _interface("ComboCreateResponse") == on_the_wire, (
        f"前端类型与真响应对不上：类型 {_interface('ComboCreateResponse')} / "
        f"响应 {on_the_wire}")


def test_the_analysis_type_matches_what_that_endpoint_really_serialises() -> None:
    """同一处病的另一半：分析提交的响应**只有 `job_id`**。

    改前它被写成 `{project_id, keywords, locale}`——那三样是**发出去的**东西。
    """
    from flint.api.schemas import AnalysisSubmitResponse

    on_the_wire = set(AnalysisSubmitResponse(job_id="job-1").model_dump())

    assert _interface("AnalysisSubmitResponse") == on_the_wire


# ───────────────────────── 二、虚构的那三格 NEVER 回来


def test_the_three_fictional_fields_are_gone_from_the_frontend_types() -> None:
    """`card_ids` / `n` / `hypothesis` **不再**被声明成 combo 的响应字段。

    它们是请求体与一个局部计数器。留着的话，下一个人会照着它去读响应，
    读到 `undefined` 再去后端「补」——而补上就是让虚构变成事实。
    """
    fields = _interface("ComboCreateResponse")

    assert fields.isdisjoint({"card_ids", "n", "hypothesis"}), fields


def test_the_backend_did_not_grow_the_three_fields_instead() -> None:
    """**NEVER 让虚构变成事实**（acceptance③ 逐字）：后端没被补上那三格。"""
    from flint.api.schemas import ComboCreateResponse

    assert set(ComboCreateResponse.model_fields) == {
        "project_id", "topic_ids", "degraded"}


def test_the_counter_that_fooled_the_ruler_is_still_just_a_counter() -> None:
    """`n` 的出处：`flint/api/combo.py` 里那个局部计数器。

    这条判据钉的是**证据**——它证明「`n` 不是响应字段」不是我说的，是代码说的。
    哪天它真变成响应字段，这条会红，而那时该有人回来改类型。
    """
    code = "\n".join(
        ln for ln in COMBO_API.read_text(encoding="utf-8").splitlines()
        if not ln.strip().startswith("#"))

    assert 'counter = {"n": 0}' in code
    # 而它 NEVER 出现在交出去的那一句里。
    # `rindex` 而不是 `index`：模块里第一句 `return JSONResponse` 在 `_error()` 里，
    # 排在计数器**之前**——用 `index` 切出来的段落把计数器整个圈了进去，
    # 于是判据报「交出去的那句里有 counter」。本轮第二次撞上「锚点选错了那一个」。
    returned = code[code.rindex("return JSONResponse"):]
    assert '"n"' not in returned and "counter" not in returned


# ───────────────────────── 三、旧名字 NEVER 留在盘上


def test_the_fictional_type_names_are_gone_from_the_type_file() -> None:
    """`ComboSubmitEcho` / `AnalysisSubmitEcho` 这两个名字不再是**声明**。

    只判「文件里没有这两个词」会误伤——本文件与 `types.ts` 的注释里
    都写着它们改前叫什么，**而那是记录，不是声明**。
    所以判的是「有没有以这个名字导出的接口」。
    """
    text = TYPES.read_text(encoding="utf-8")

    for gone in ("ComboSubmitEcho", "AnalysisSubmitEcho"):
        assert not re.search(rf"export interface {gone}\b", text), gone


# ───────────────────────── 四、单据按新规矩关


def test_the_sheet_was_closed_by_this_card() -> None:
    """单据留得住痕，且关闭那一节点名本卡。"""
    from tests.v041._sheet_trace import assert_sheet_keeps_its_trace

    state, _day, card = assert_sheet_keeps_its_trace(SHEET)

    assert state == "closed"
    assert card == "COMBO-ECHO"
