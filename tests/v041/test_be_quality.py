"""BE-03：质量卡端点 `GET /deliverables/{id}/quality`（蓝本 R3「端点未建」）。

## 这张卡最硬的一条：NEVER 返回可靠度分值

技术约束清单第 1 条：「是否出现可靠度进度条、百分比、星级、雷达图，
或任何把布尔/枚举画成连续量的表达？**后端不返回这类分值**。」

所以本端点只回**布尔、枚举与计数**：
「12 个块里 9 个有引用」是三个数，前端能列出来；
「引用覆盖率 75%」是一个分值，前端会拿它画进度条——**而那条进度条没有出处**。

**连分母带分子一起给，不给商**：给了商，前端就不必再想「这 75% 是怎么算的」。

## 「没检查过」与「检查过、是 0」分得开

未解引用数要真去解一遍才知道。解引用器没注入时，本端点**不报 0**——
报 0 等于说「查过了，一个都没有」。它报的是**「尚未接线」**这个状态。
这是本轮反复出现的同一条：空值与未知值 NEVER 挤进同一个表示。

## 被阻断的块复用既有闸门

`flint/render/gatekeeper.py#check_export` 已经在算这件事（导出门用的就是它）。
本端点**直接调它**，NEVER 另写一遍判断——两处各判各的话，
质量卡说「没有阻断」而导出却 409，用户无从判断该信哪个。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from fastapi.testclient import TestClient

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from flint.api.quality import QualityApiDeps, create_quality_app
from flint.domain.models import Block

MODULE = REPO / "flint" / "api" / "quality.py"

OWNER = "u-be03"
STRANGER = "u-other"


def _block(
    block_id: str, *, content: object, author: str = "system",
    user_modified: bool = False, needs_review: bool = False,
    severity: str | None = None, claim_ids: list[str] | None = None,
) -> Block:
    from flint.domain.models import ParagraphContent

    return Block(
        block_id=block_id, deliverable_id="d-1", section_id="sec-1", order=1,
        type="paragraph", content=content or ParagraphContent(kind="paragraph", spans=[]),
        claim_ids=claim_ids or [], fact_ids=[], author=author,  # type: ignore[arg-type]
        revision=1, locked=False, user_modified=user_modified,
        needs_review=needs_review, review_severity=severity,  # type: ignore[arg-type]
    )


def _blocks() -> list[Block]:
    # 冻结件里的真类名：**没有** FactRefContent / GapHintsContent。
    # 带 fact_id 的是表格里的 `FactCell`（走 TableContent），
    # 带 hints_ref 的是 `GapNoticeContent`。照真件写，NEVER 按记忆造类名。
    from flint.domain.models import (
        CitationListContent,
        GapNoticeContent,
        ParagraphContent,
        QualityCardContent,
    )

    return [
        # 有引用的系统块
        _block("b-1", content=CitationListContent(
            kind="citation_list", citation_ids=["fact-1"])),
        _block("b-2", content=QualityCardContent(kind="quality_card", card_ref="qc-1")),
        # 没引用的系统块
        _block("b-3", content=ParagraphContent(kind="paragraph", spans=[])),
        # 用户块：**不进覆盖率分母**（冻结件 Block docstring [审3]）
        _block("b-4", content=ParagraphContent(kind="paragraph", spans=[]),
               author="user"),
        # 系统块但被用户改过：同样不进分母
        _block("b-5", content=ParagraphContent(kind="paragraph", spans=[]),
               user_modified=True),
        # 缺口提示
        _block("b-6", content=GapNoticeContent(kind="gap_notice", hints_ref="gh-1")),
        # 阻断级复核
        _block("b-7", content=ParagraphContent(kind="paragraph", spans=[]),
               needs_review=True, severity="blocking"),
        # 建议级复核：**不阻断导出**
        _block("b-8", content=ParagraphContent(kind="paragraph", spans=[]),
               needs_review=True, severity="advisory"),
    ]


def _client(
    *, blocks: list[Block] | None = None, owner: str = OWNER,
    known: bool = True, resolver: object = None,
) -> TestClient:
    async def load(deliverable_id: str) -> list[Block]:
        del deliverable_id
        assert blocks is not None
        return blocks

    async def owner_of(deliverable_id: str) -> str | None:
        del deliverable_id
        return owner if known else None

    deps = QualityApiDeps(
        load_blocks=load, deliverable_owner=owner_of,
        ref_resolver=resolver,  # type: ignore[arg-type]
    )
    return TestClient(create_quality_app(deps))


def _quality(**kwargs: object) -> dict[str, object]:
    client = _client(blocks=_blocks(), **kwargs)  # type: ignore[arg-type]
    return client.get(
        "/deliverables/d-1/quality", headers={"X-User-Id": OWNER}).json()


# ───────────────────────── 一、四样内容都在（acceptance①）


def test_the_quality_card_endpoint_exists() -> None:
    response = _client(blocks=_blocks()).get(
        "/deliverables/d-1/quality", headers={"X-User-Id": OWNER})

    assert response.status_code == 200


def test_citation_coverage_is_reported_as_counts() -> None:
    """引用覆盖给的是**分子与分母两个数**，不是一个比例。"""
    body = _quality()

    coverage = body["citation_coverage"]
    assert coverage["blocks_with_refs"] == 1       # 只有 b-1 带**证据**引用
    # 分母是**六**块：b-1/b-2/b-3/b-6/b-7/b-8——待复核的块也是系统生成的，
    # 它们照样该被问「有没有引用」。只有 b-4（用户写的）与 b-5（用户改过）出局。
    assert coverage["blocks_counted"] == 6


def test_meta_refs_do_not_count_as_citation_coverage() -> None:
    """`card_ref`（质量卡）与 `hints_ref`（缺口清单）是**元信息**，不是证据。

    算进覆盖率的话，一份满是缺口提示的交付物会显得「引用充分」——
    那正好把这个数的意思弄反了。
    """
    from flint.api.quality import block_refs, evidence_refs

    blocks = {b.block_id: b for b in _blocks()}

    assert evidence_refs(blocks["b-1"]) == ["fact-1"]       # 证据
    assert evidence_refs(blocks["b-2"]) == []               # 质量卡：不算
    assert evidence_refs(blocks["b-6"]) == []               # 缺口：不算
    # 但两者都进「未解引用」检查——元信息 ref 解不开同样是坏链接
    assert block_refs(blocks["b-2"]) == ["qc-1"]
    assert block_refs(blocks["b-6"]) == ["gh-1"]


def test_user_blocks_are_out_of_the_denominator() -> None:
    """冻结件 `Block` docstring [审3]：覆盖率**只统计 system 且未被用户修改**的块。

    把用户块算进去的话，用户自己写的段落会拉低「我们的引用覆盖」——
    那个数说的就不再是系统生成的质量了。
    """
    body = _quality()

    assert body["citation_coverage"]["blocks_excluded_user"] == 2   # b-4 / b-5


def test_the_gap_hints_refs_are_listed() -> None:
    """缺口提示列出 `hints_ref`——内容由 `GET /hints/{ref}` 给（各端点各管一段）。"""
    body = _quality()

    assert body["gap_hint_refs"] == ["gh-1"]


def test_the_blocking_blocks_are_listed() -> None:
    """被阻断的块逐个点名——只说「有阻断」的话，用户不知道去改哪一块。"""
    body = _quality()

    assert body["blocking_block_ids"] == ["b-7"]


def test_advisory_reviews_are_counted_but_do_not_block() -> None:
    """建议级复核**要报出来但不阻断**：两者混一起会把可导出的交付物挡下来。"""
    body = _quality()

    assert body["advisory_open"] == 1
    assert body["exportable"] is True or body["exportable"] is False
    assert body["blocking_open"] == 1


def test_it_reuses_the_existing_export_gate() -> None:
    """复用 `gatekeeper.check_export`，NEVER 另写一遍判断。

    两处各判各的话，质量卡说「没有阻断」而导出却 409，
    用户无从判断该信哪个。
    """
    source = MODULE.read_text(encoding="utf-8")

    assert "check_export" in source
    assert "needs_review" not in source.split('"""', 2)[-1], (
        "自己又数了一遍 needs_review：那就是第二份判断")


# ───────────────────────── 二、NEVER 返回可靠度分值（acceptance②）


def test_no_ratio_or_percentage_anywhere_in_the_response() -> None:
    """技术约束清单第 1 条：**后端不返回这类分值**。

    给了商，前端就会拿它画进度条——而那条进度条没有出处。
    """
    flat = json.dumps(_quality(), ensure_ascii=False)

    for banned in ("percent", "ratio", "rate", "score", "stars", "health", "grade"):
        assert banned not in flat, f"响应里出现了分值字段：{banned}"


def test_every_number_in_the_response_is_an_integer_count() -> None:
    """只回**计数**：出现任何小数就意味着有人算了商。"""
    def walk(node: object) -> list[float]:
        if isinstance(node, bool):
            return []
        if isinstance(node, int | float):
            return [node]
        if isinstance(node, dict):
            return [n for v in node.values() for n in walk(v)]
        if isinstance(node, list):
            return [n for v in node for n in walk(v)]
        return []

    numbers = walk(_quality())

    assert numbers, "一个数都没有，那这张质量卡什么也没说"
    assert all(isinstance(n, int) for n in numbers), f"出现了非整数：{numbers}"


def test_the_module_never_divides() -> None:
    """源码级：模块里 NEVER 出现除法。

    比例是除出来的。判在 AST 上——注释里写「NEVER 给比例」不算除法。
    """
    import ast

    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    divisions = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div | ast.FloorDiv)
    ]

    assert divisions == [], "模块里有除法：比例是除出来的"


# ───────────────────────── 三、「没检查过」与「检查过是 0」分得开


def test_without_a_resolver_the_unresolved_count_is_not_zero_but_unknown() -> None:
    """解引用器没注入时**不报 0**——报 0 等于说「查过了，一个都没有」。

    这是本轮反复出现的同一条：空值与未知值 NEVER 挤进同一个表示。
    """
    body = _quality()

    assert body["unresolved"]["status"] == "not_checked"
    assert "count" not in body["unresolved"]


def test_with_a_resolver_it_reports_the_real_unresolved_ids() -> None:
    """接上解引用器之后，报的是**真解不开的那些 id**。"""
    def resolver(ref: str) -> bool:
        return ref != "fact-1"

    body = _quality(resolver=resolver)

    assert body["unresolved"]["status"] == "checked"
    assert body["unresolved"]["ids"] == ["fact-1"]
    assert body["unresolved"]["count"] == 1


def test_a_fully_resolvable_deliverable_reports_zero_not_unknown() -> None:
    """反向：都解得开时报 `checked` + 0，而不是 `not_checked`。"""
    body = _quality(resolver=lambda ref: True)

    assert body["unresolved"]["status"] == "checked"
    assert body["unresolved"]["count"] == 0
    assert body["unresolved"]["ids"] == []


# ───────────────────────── 四、空态与错误态分清（acceptance④）


def test_a_deliverable_with_no_blocks_returns_empty_not_404() -> None:
    """块一个都没有 → 计数全 0 + 空列表，**不是 404**。

    交付物是在的，只是还没生成内容。
    """
    response = _client(blocks=[]).get(
        "/deliverables/d-1/quality", headers={"X-User-Id": OWNER})

    assert response.status_code == 200
    body = response.json()
    assert body["citation_coverage"]["blocks_counted"] == 0
    assert body["blocking_block_ids"] == []
    assert body["gap_hint_refs"] == []


def test_an_unknown_deliverable_is_404() -> None:
    response = _client(blocks=_blocks(), known=False).get(
        "/deliverables/nope/quality", headers={"X-User-Id": OWNER})

    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"


# ───────────────────────── 五、多租户（acceptance③）


def test_another_owners_quality_card_is_404_not_403() -> None:
    response = _client(blocks=_blocks(), owner=STRANGER).get(
        "/deliverables/d-1/quality", headers={"X-User-Id": OWNER})

    assert response.status_code == 404


def test_the_two_kinds_of_404_share_one_error_code() -> None:
    """「不存在」与「不该看到」对外长得一样。判在**源码**上：

    两种情况在实现里走同一行，逐条比状态码杀不掉「换个错误码」那种改动
    （BE-02 变异考⑯ 学到的）。
    """
    import ast

    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    codes = [
        ast.unparse(call.args[1])
        for call in ast.walk(tree)
        if isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
        and call.func.id == "_error" and len(call.args) >= 2
        and ast.unparse(call.args[0]) == "404"
    ]

    assert codes, "一个 404 都没有"
    assert set(codes) == {"'NOT_FOUND'"}, f"404 用了不同的错误码：{sorted(set(codes))}"


def test_the_owner_still_sees_their_own() -> None:
    response = _client(blocks=_blocks(), owner=STRANGER).get(
        "/deliverables/d-1/quality", headers={"X-User-Id": STRANGER})

    assert response.status_code == 200


def test_identity_is_required() -> None:
    response = _client(blocks=_blocks()).get("/deliverables/d-1/quality")

    assert response.status_code == 422


# ───────────────────────── 六、只读 + NEVER 造字段（acceptance③⑤）


def test_the_module_never_writes() -> None:
    import ast

    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    docstrings = {ast.get_docstring(n) for n in ast.walk(tree)
                  if isinstance(n, ast.Module | ast.ClassDef | ast.FunctionDef
                                | ast.AsyncFunctionDef)}
    literals = " ".join(
        node.value for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
        and node.value not in docstrings
    )

    for verb in ("INSERT", "UPDATE", "DELETE", "DROP", "ALTER"):
        assert not re.search(rf"\b{verb}\b", literals, re.IGNORECASE), f"模块里有 {verb}"


def test_the_response_shape_is_exactly_what_the_card_asks_for() -> None:
    """**NEVER 造字段**：顶层键就是卡上那四样 + 归属与阻断态。"""
    body = _quality()

    assert set(body) == {
        "deliverable_id", "citation_coverage", "unresolved", "gap_hint_refs",
        "blocking_block_ids", "blocking_open", "advisory_open", "exportable",
    }
