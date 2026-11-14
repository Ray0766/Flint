"""BE-10 · 设计工作台端点族（暴露 `flint/design` 的 13 个模块 · v2 屏 2.17）。

v0.4 花 33 张卡建的 `flint/design/` 至今**零 API 出口**。本卡暴露六样：
探索期渲染 / 固化管道 / 模板注册表 / 生产渲染 / 导出闸门 / 陈旧提示，
外加 DEF-02 的 ephemeral 重放语义。

**本卡的承重墙（异见 B5 已判维持）**：生产渲染端点 NEVER 接受任意 html。
判据钉三层——请求模型里没有 html 字段、递进来一个就 422、
模块里再没有第二处调 `ExploreRenderer`。
把这堵墙拆了，两阶段模型（探索期自由 / 固化闸门）就只剩一个说法。
"""
from __future__ import annotations

import ast
import importlib.util
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from flint.api.design import DesignApiDeps, create_design_app
from flint.design.session import ResumePoint
from flint.design.templates.registry import TemplateRegistry

MODULE = Path("flint/api/design.py")

ME = "u-me"
OTHER = "u-other"
NOW = datetime(2026, 7, 8, 9, 10, tzinfo=UTC)

MOCK_HTML = (
    '<div data-mock-watermark="mock">'
    '<h1 data-slot="t:title">示例标题</h1>'
    '<p data-slot="block:b-1">占位正文 XXX%，来源 [来源待补]</p>'
    "</div>"
)


def _contract() -> Any:
    spec = importlib.util.spec_from_file_location(
        "models_v04_be10", Path("contracts_v04/models_v04.py"))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["models_v04_be10"] = module
    spec.loader.exec_module(module)
    return module


def _block(block_id: str = "b-1", *, severity: str | None = None) -> Any:
    """一个块。`severity="blocking"` 才会被既有门禁算成阻断
    （`check_export`：`needs_review and review_severity == "blocking"`）。"""
    from flint.domain.models import Block, ParagraphContent

    # 字段名照冻结件逐字：`section_id` / `type` / `claim_ids` / `fact_ids` /
    # `revision` —— 不是 parent_id / block_type（按记忆写的那两个真件里没有）。
    return Block(
        block_id=block_id, deliverable_id="d-1", section_id="s-1", order=1,
        type="paragraph", content=ParagraphContent(kind="paragraph", spans=[]),
        claim_ids=[], fact_ids=[], author="system", revision=1, locked=False,
        user_modified=False, needs_review=severity is not None,
        review_severity=severity,       # type: ignore[arg-type]
    )


def _app(
    *,
    available: bool = True,
    blocks: list[Any] | None = None,
    edges: list[dict[str, Any]] | None = None,
    changes: list[Any] | None = None,
    session: tuple[ResumePoint, list[Any]] | None = None,
) -> tuple[TestClient, TemplateRegistry]:
    registry = TemplateRegistry(available=available)

    async def load_export_inputs(deliverable_id: str) -> Any:
        if deliverable_id == "d-missing":
            return None
        return (list(blocks or []), list(edges or []))

    async def load_changes() -> list[Any]:
        return list(changes or [])

    async def load_session(job_id: str) -> Any:
        return session

    deps = DesignApiDeps(
        registry=registry,
        now=lambda: NOW,
        load_export_inputs=load_export_inputs,
        load_changes=load_changes if changes is not None else None,
        deliverables_by_graph={"g-1": ["d-1"]},
        load_session=load_session if session is not None else None,
        model=_contract().TemplateRecord,
        event_model=_contract().SolidifyResult,
    )
    return TestClient(create_design_app(deps)), registry


def _solidify(client: TestClient, user: str = ME, **overrides: Any) -> Any:
    body = {"template_id": "tpl-1", "name": "报告样板", "mock_html": MOCK_HTML}
    body.update(overrides)
    return client.post("/design/templates", json=body, headers={"X-User-Id": user})


def _identifiers() -> set[str]:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    return {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {
        n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}


# ───────────────────────── 一、承重墙：生产渲染 NEVER 收 html（acceptance②）


def test_the_production_render_request_has_no_html_field() -> None:
    """第一层：请求模型里**根本没有** html 这个字段。"""
    from flint.api.design import ProductionRenderRequest

    assert set(ProductionRenderRequest.model_fields) == {"template_id", "slot_values"}


def test_passing_html_to_the_production_render_is_422() -> None:
    """第二层：递进来一个也不收（`extra="forbid"`）。

    插槽**必须全填对**，否则这条判据会因为「缺插槽」而 422——
    看起来绿，其实根本没判到 html 那一层（变异② 就是这么活下来的：
    改成 `extra="ignore"` 后 html 被悄悄丢掉，而缺插槽照样 422）。
    """
    client, _ = _app()
    _solidify(client)
    filled = {"t:title": "真标题", "block:b-1": "真正文"}

    assert client.post(
        "/design/render", json={"template_id": "tpl-1", "slot_values": filled},
        headers={"X-User-Id": ME}).status_code == 200, "先确认这份请求本来会成功"

    response = client.post(
        "/design/render",
        json={"template_id": "tpl-1", "slot_values": filled, "html": "<b>x</b>"},
        headers={"X-User-Id": ME})

    assert response.status_code == 422


def test_the_explore_renderer_is_never_reachable_from_the_production_path() -> None:
    """第三层：模块里 `ExploreRenderer` 只出现在探索那条路上。

    两条路共用一个渲染器的那天，「探索期自由」就变成了「生产期也自由」。
    """
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    handlers = {
        n.name: n for n in ast.walk(tree)
        if isinstance(n, ast.AsyncFunctionDef | ast.FunctionDef)
    }
    production = handlers["production_render"]
    used = {n.id for n in ast.walk(production) if isinstance(n, ast.Name)}
    # 一层调用闭包：处理函数调到的本模块辅助函数（`_renderer`）也算它用到的东西。
    for name in list(used):
        helper = handlers.get(name)
        if helper is not None:
            used |= {n.id for n in ast.walk(helper) if isinstance(n, ast.Name)}

    assert "ExploreRenderer" not in used, "生产那条路够得着探索渲染器"
    assert "ProductionRenderer" in used


def test_the_production_render_fills_the_slots() -> None:
    client, _ = _app()
    _solidify(client)

    response = client.post(
        "/design/render",
        json={"template_id": "tpl-1",
              "slot_values": {"t:title": "真标题", "block:b-1": "真正文"}},
        headers={"X-User-Id": ME})

    assert response.status_code == 200
    assert "真标题" in response.json()["html"]
    assert "{{" not in response.json()["html"]


def test_a_missing_slot_value_is_422_and_never_renders_the_braces() -> None:
    client, _ = _app()
    _solidify(client)

    response = client.post(
        "/design/render",
        json={"template_id": "tpl-1", "slot_values": {"t:title": "只填了一个"}},
        headers={"X-User-Id": ME})

    assert response.status_code == 422
    # 判「没渲染出东西」而不是「文本里没有花括号」：上游那句报错原文里
    # 就写着 `NEVER 把 {{slot}} 原样渲染给客户看`，判文本会被它喂饱。
    assert "html" not in response.json()
    assert "block:b-1" in response.json()["message"]


def test_rendering_someone_elses_template_is_404() -> None:
    """`_lookup` 把「别人的模板」和「不存在」都算成未注册——到 HTTP 边界合成一句 404。"""
    client, _ = _app()
    _solidify(client, user=OTHER)

    response = client.post(
        "/design/render", json={"template_id": "tpl-1", "slot_values": {}},
        headers={"X-User-Id": ME})

    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"


def test_rendering_an_unknown_template_is_404_with_the_same_code() -> None:
    client, _ = _app()
    _solidify(client, user=OTHER)

    unknown = client.post(
        "/design/render", json={"template_id": "tpl-nope", "slot_values": {}},
        headers={"X-User-Id": ME})
    theirs = client.post(
        "/design/render", json={"template_id": "tpl-1", "slot_values": {}},
        headers={"X-User-Id": ME})

    assert unknown.status_code == theirs.status_code == 404
    assert unknown.json()["code"] == theirs.json()["code"]


# ───────────────────────── 二、探索期渲染（acceptance①）


def test_the_explore_render_takes_html_and_needs_no_registry() -> None:
    """探索期几乎无约束（G0/G10）：拿到什么画什么，注册表不可用也照跑。"""
    client, _ = _app(available=False)

    response = client.post(
        "/design/explore/render", json={"html": "<b>试样式</b>"},
        headers={"X-User-Id": ME})

    assert response.status_code == 200
    assert response.json()["html"] == "<b>试样式</b>"


def test_the_explore_render_says_it_is_not_a_deliverable() -> None:
    """探索产物 NEVER 被当成可交付：响应自带 `production: false` 标记。"""
    client, _ = _app()

    body = client.post("/design/explore/render", json={"html": "<b>x</b>"},
                       headers={"X-User-Id": ME}).json()

    assert body["production"] is False


# ───────────────────────── 三、固化管道 + mock 标记（acceptance③）


def test_solidifying_registers_a_template_and_returns_the_event() -> None:
    client, registry = _app()

    body = _solidify(client).json()

    assert body["kind"] == "solidify_result"
    assert body["accepted"] is True
    assert [r.template_id for r in registry.all()] == ["tpl-1"]


def test_a_mock_without_the_watermark_is_rejected() -> None:
    """mock 三件套之一：水印。没有水印的样板**不是样板**，它看起来就是成品。"""
    client, registry = _app()
    without = MOCK_HTML.replace(' data-mock-watermark="mock"', "")

    response = _solidify(client, mock_html=without)

    assert response.status_code == 422
    assert registry.all() == []
    assert "data-mock-watermark" in response.text


def test_the_watermark_is_stripped_from_the_stored_template() -> None:
    """要求它在，是为了确认这是样板；存下来时**必须剥掉**——模板不该带水印。"""
    client, registry = _app()

    _solidify(client)

    assert "data-mock-watermark" not in registry.all()[0].html


def test_a_mock_with_a_concrete_number_is_rejected_with_the_full_list() -> None:
    """示例残留即拒，且给**完整清单**——只报第一条的话，用户改一条再撞一条。

    脏内容要放在 **`data-slot` 标记区之外**：标记区会先被换成 `{{slot}}`，
    里面的东西根本到不了残留检查那一步（那是对的——那块本来就是要填内容的）。
    """
    client, registry = _app()
    dirty = MOCK_HTML.replace(
        "</div>", "<p>营收增长 37%，来源 SRC-1234</p></div>")

    response = _solidify(client, mock_html=dirty)

    assert response.status_code == 422
    assert registry.all() == []
    assert len(response.json()["detail"]["violations"]) >= 2


def test_a_mock_without_any_slot_is_rejected() -> None:
    client, _ = _app()

    response = _solidify(
        client, mock_html='<div data-mock-watermark="mock">静态页</div>')

    assert response.status_code == 422


def test_an_unavailable_registry_blocks_solidify_but_says_exploring_still_works() -> None:
    """E6 降级：报错要说清**还能做什么**，否则用户以为整个设计台挂了。"""
    client, _ = _app(available=False)

    response = _solidify(client)

    assert response.status_code == 503
    assert "探索" in response.json()["message"]


# ───────────────────────── 四、模板注册表（acceptance①⑤）


def test_my_template_list_is_empty_not_404() -> None:
    client, _ = _app()

    response = client.get("/design/templates", headers={"X-User-Id": ME})

    assert response.status_code == 200
    assert response.json()["items"] == []


def test_my_template_list_never_contains_another_owners_template() -> None:
    client, _ = _app()
    _solidify(client, user=OTHER)

    items = client.get("/design/templates", headers={"X-User-Id": ME}).json()["items"]

    assert items == []


def test_the_version_series_is_kept_in_ascending_order() -> None:
    """旧版本 NEVER 被覆盖——「上一版长什么样」是设计台的基本能力。

    第二版必须改**插槽之外**的内容：插槽区里的文字固化时就被换掉了，
    只改那里的话两版 html 逐字相同 → 同内容去重 → 根本不产生第二版。
    """
    client, _ = _app()
    _solidify(client)
    _solidify(client, mock_html=MOCK_HTML.replace("<div ", '<div class="v2" '))

    items = client.get("/design/templates", headers={"X-User-Id": ME}).json()["items"]

    assert [i["version"] for i in items] == [1, 2]


def test_the_listed_template_carries_no_html_and_no_owner() -> None:
    client, _ = _app()
    _solidify(client)

    item = client.get(
        "/design/templates", headers={"X-User-Id": ME}).json()["items"][0]

    assert set(item) == {"template_id", "name", "version", "slots",
                         "source_deliverable_id", "checksum", "solidified_at",
                         "enabled"}


# ───────────────────────── 五、导出闸门（acceptance③）


def test_an_unsolidified_template_blocks_a_production_export() -> None:
    """未固化模板走导出闸门的 blocking 判据（生产格式才管）。"""
    client, _ = _app()

    body = client.post(
        "/design/export-check",
        json={"deliverable_id": "d-1", "export_format": "pdf", "template_id": None},
        headers={"X-User-Id": ME}).json()

    assert body["exportable"] is False
    assert [v["criterion"] for v in body["violations"]] == ["template_not_solidified"]


def test_an_explore_format_is_not_judged_by_the_template_criterion() -> None:
    """探索期导出不受此判据管——否则试个样式都要先固化。"""
    client, _ = _app()

    body = client.post(
        "/design/export-check",
        json={"deliverable_id": "d-1", "export_format": "html", "template_id": None},
        headers={"X-User-Id": ME}).json()

    assert body["exportable"] is True
    assert body["violations"] == []


def test_the_gate_runs_every_criterion_not_just_the_first() -> None:
    """跑完全部判据再回结果：只报第一条的话，用户改一条再撞一条。"""
    client, _ = _app(blocks=[_block(severity="blocking")])

    body = client.post(
        "/design/export-check",
        json={"deliverable_id": "d-1", "export_format": "pdf", "template_id": None},
        headers={"X-User-Id": ME}).json()

    criteria = [v["criterion"] for v in body["violations"]]
    assert "template_not_solidified" in criteria
    assert len(criteria) >= 2


def test_a_solidified_template_passes_the_template_criterion() -> None:
    client, _ = _app()
    _solidify(client)

    body = client.post(
        "/design/export-check",
        json={"deliverable_id": "d-1", "export_format": "pdf",
              "template_id": "tpl-1"},
        headers={"X-User-Id": ME}).json()

    assert body["exportable"] is True


def test_the_export_check_of_an_unknown_deliverable_is_404() -> None:
    client, _ = _app()

    response = client.post(
        "/design/export-check",
        json={"deliverable_id": "d-missing", "export_format": "pdf",
              "template_id": "tpl-1"},
        headers={"X-User-Id": ME})

    assert response.status_code == 404


# ───────────────────────── 六、陈旧提示（acceptance①）


def test_without_a_change_source_the_notices_are_not_checked() -> None:
    """没注入变更源 → 没查过。空列表会被读成「没有任何样板过时」。"""
    client, _ = _app()

    body = client.get("/design/stale-notices", headers={"X-User-Id": ME}).json()

    assert body == {"status": "not_checked"}


def test_no_change_means_an_empty_list_not_404() -> None:
    client, _ = _app(changes=[])

    body = client.get("/design/stale-notices", headers={"X-User-Id": ME}).json()

    assert body == {"status": "checked", "items": []}


def test_a_structural_change_produces_a_notice_with_two_actions() -> None:
    """两条出路：看差异、主动重新生成。**顺序即界面顺序**：先看清再决定。"""
    contract = _contract()
    change = contract.GraphChange(
        kind="edge_added", graph_id="g-1", occurred_at=NOW)
    client, _ = _app(changes=[change])

    items = client.get(
        "/design/stale-notices", headers={"X-User-Id": ME}).json()["items"]

    assert items[0]["stale"] is True
    assert items[0]["actions"] == ["view_diff", "regenerate"]
    assert items[0]["deliverable_id"] == "d-1"


def test_moving_a_node_on_the_canvas_produces_no_notice_at_all() -> None:
    """画布上挪个位置没有改变任何论断。

    把布局变动也算成 stale，会让「陈旧」这个信号迅速失去意义——
    每天挪几下图，满屏都是黄标，然后没人再看它。

    注意这里断的是「**一条都没有**」，不是「有一条但 stale=False」：
    既有 `notices_for_change` 只为受影响的交付物出通知，且出的每一条恒 `stale=True`
    （结构性判定归 `derive_stale`）。所以「不 stale」的形态就是**不出通知**。
    """
    contract = _contract()
    change = contract.GraphChange(
        kind="node_moved", graph_id="g-1", occurred_at=NOW)
    client, _ = _app(changes=[change])

    body = client.get("/design/stale-notices", headers={"X-User-Id": ME}).json()

    assert body == {"status": "checked", "items": []}


def test_the_notice_endpoint_never_regenerates_anything() -> None:
    """通知是**数据，不是动作**：读一次 NEVER 发起一次生成。"""
    identifiers = _identifiers()

    assert "notices_for_change" in identifiers
    assert "regenerate" not in {i for i in identifiers if i != "actions"}


# ───────────────────────── 七、DEF-02 ephemeral 重放（acceptance④）


def test_an_ephemeral_delta_is_never_replayed() -> None:
    """标了 ephemeral 的只走内存，NEVER 进 replay 日志。"""
    contract = _contract()
    events = [
        contract.JobEvent(job_id="j-1", seq=1, ts=NOW, ephemeral=False,
                          payload=contract.DesignDelta(
                              kind="design_delta", seq=1, fragment="持久的")),
        contract.JobEvent(job_id="j-1", seq=2, ts=NOW, ephemeral=True,
                          payload=contract.DesignDelta(
                              kind="design_delta", seq=2, fragment="临时的")),
    ]
    client, _ = _app(session=(ResumePoint(text="", seq=2), events))

    body = client.get("/design/sessions/j-1/replay",
                      headers={"X-User-Id": ME}).json()

    assert "临时的" not in str(body)


def test_a_checkpoint_that_misses_an_ephemeral_event_is_409_not_a_silent_loss() -> None:
    """检查点没盖住 ephemeral → 那几段文字既不在快照里也不在日志里。

    悄悄放过的话，用户重连后看到的是**少了一段**的文字，而且看不出少了。
    """
    contract = _contract()
    events = [
        contract.JobEvent(job_id="j-1", seq=1, ts=NOW, ephemeral=True,
                          payload=contract.DesignDelta(
                              kind="design_delta", seq=1, fragment="会丢的")),
    ]
    client, _ = _app(session=(ResumePoint(text="", seq=0), events))

    response = client.get("/design/sessions/j-1/replay",
                          headers={"X-User-Id": ME})

    assert response.status_code == 409
    assert "1" in response.text


def test_without_a_session_source_the_replay_is_404() -> None:
    client, _ = _app()

    assert client.get("/design/sessions/j-1/replay",
                      headers={"X-User-Id": ME}).status_code == 404


# ───────────────────────── 八、结构判据（acceptance⑤⑥）


def test_identity_is_required_everywhere() -> None:
    client, _ = _app()

    assert client.get("/design/templates").status_code == 422
    assert client.post("/design/explore/render", json={"html": "x"}).status_code == 422
    assert client.post("/design/render",
                       json={"template_id": "t", "slot_values": {}}).status_code == 422


def test_the_module_writes_no_sql_of_its_own() -> None:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    docstrings = {ast.get_docstring(n) for n in ast.walk(tree)
                  if isinstance(n, ast.Module | ast.ClassDef | ast.FunctionDef
                                | ast.AsyncFunctionDef)}
    literals = " ".join(
        node.value for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
        and node.value not in docstrings
    )

    for pattern in (r"INSERT\s+INTO", r"DELETE\s+FROM", r"UPDATE\s+\w+\s+SET",
                    r"DROP\s+(TABLE|COLUMN)", r"ALTER\s+TABLE"):
        assert not re.search(pattern, literals, re.IGNORECASE), f"模块里有 {pattern}"


def test_every_gate_and_pipeline_is_the_existing_one() -> None:
    """六样全部转调既有模块，本模块 NEVER 另写一套判据。"""
    identifiers = _identifiers()

    for name in ("ExploreRenderer", "ProductionRenderer", "solidify_mock",
                 "list_templates", "check_design_export",
                 "check_template_solidified", "notices_for_change",
                 "persisted_events", "resume_text"):
        assert name in identifiers, f"没转调 {name}"


def test_the_module_never_defines_its_own_mock_patterns() -> None:
    """占位语法的唯一真相是 `web/design/mock-identity/mock-syntax.json`。

    在这里再写一个正则，就是第二份表——前端拦住的与后端拦住的会分叉。
    """
    source = MODULE.read_text(encoding="utf-8")

    assert "re.compile" not in source
    assert "SRC-" not in source
