"""PERSIST-03：模板表 + `template_solidify` 消费者——最后一个没消费者的作业。

## 实况（开工前实核，不照抄卡面）

- `templates` 表**不存在**（`asyncpg` 实查，`DEC-048` 八张里的第四张）；
- 所以 `flint/api/app.py` 给 design 族注的是 `TemplateRegistry(available=False)`，
  `GET /design/templates` 回 `not_provided`，设计台的「固化为模板」恒置灰；
- `flint/jobs/dispatch.py` 的 `UnwiredKindReason` **只剩 `template_solidify` 这一条**，
  移完**那张表就空了**。

## 表名：`templates`，不是 `template_registry`

`flint/design/templates/registry.py:39` 自述「SQL 实现随 E2 的 `template_registry`
表接入」，而 `DEC-048`（owner 2026-08-09 裁的）点名的是 **`templates`**，
本批的出口判据也是照那八个名字数的。**以 `DEC-048` 为准**——
它是 owner 面的裁决，而那句注释是当时随手写下的一个设想。

## 「没有消费者」与「消费者跑失败」NEVER 合并

`UnwiredKindReason` 存在的意义是让前者**大声**：提交一个没人取的作业，
界面上看到的是「排队中」——永远，而静默丢弃把失败伪装成等待
（`dispatch.py` 文件头原话）。

所以本卡把 `template_solidify` 从那张表移进 `WIREABLE_KINDS` 之后，
**那张表就空了**，而下面有一条判据专门钉住「空了之后这套机制仍然活着」——
空表最容易被下一个人当成「这个机制没用了」而顺手删掉。
"""
from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import asyncpg
import pytest

from flint.domain.models import Principal

pytestmark = pytest.mark.compose

REPO = Path(__file__).resolve().parents[2]
DSN = os.environ.get(
    "FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")
NOW = datetime(2026, 8, 9, 12, 0, 0, tzinfo=UTC)
ME = Principal(kind="user", id="persist03-me")
OTHER = Principal(kind="user", id="persist03-other")

#: 一份最小样板：一个标记区域（会变成插槽）+ 水印（会被剥掉）。
MOCK_HTML = (
    '<div data-mock-watermark="样板"><h1 data-slot="t:title">示例标题</h1></div>'
)


def run(coro: Any) -> Any:
    return asyncio.run(coro)


async def _conn() -> asyncpg.Connection:
    return await asyncpg.connect(DSN)


async def _wipe() -> None:
    conn = await _conn()
    try:
        await conn.execute("DELETE FROM templates")
    finally:
        await conn.close()


@pytest.fixture(autouse=True)
def _clean() -> Any:
    run(_wipe())
    yield
    run(_wipe())


def _registry() -> Any:
    from flint.design.templates.pgregistry import PgTemplateRegistry

    return PgTemplateRegistry(dsn=DSN)


def _record_model() -> Any:
    from contracts_v04.models_v04 import TemplateRecord

    return TemplateRecord


# ───────────────────────── 一、表与迁移号


def test_the_templates_table_exists_now() -> None:
    """实查 `pg_tables`。查迁移文件的话，没跑过的迁移也能骗过判据。"""
    async def _probe() -> Any:
        conn = await _conn()
        try:
            return await conn.fetchval(
                "SELECT to_regclass('public.templates') IS NOT NULL")
        finally:
            await conn.close()

    assert run(_probe()) is True


def test_the_migration_number_leaves_no_gap() -> None:
    """本批四张迁移卡从 0023 起顺序编，**NEVER 跳号也 NEVER 撞号**。

    第一版把本卡编成 `0025`，**给被阻的 `PERSIST-02` 留出 `0024`**。
    那是错的：留号留出来的正是一个跳号，仓里三把尺子当场判红
    （`test_persist_fav_share_prefs` / `test_project_optimistic_lock` /
    `test_cluster_region` 各自的号段判据）——**它们是对的**。

    「四张迁移卡各是哪一号」是 trace 上的记账方便，
    「号段不许有洞」是写死的不变量，两者冲突时后者赢。
    所以这条判据判的是**没有洞**，而不是「本卡是哪一号」。
    """
    import re

    versions = sorted(
        (REPO / "migrations" / "versions").glob("[0-9][0-9][0-9][0-9]_*.py"))
    numbers = [int(p.name[:4]) for p in versions]
    mine = [p for p in versions if p.name.endswith("_templates.py")]

    assert len(mine) == 1, "模板表的迁移不在盘上，或者有两个"
    assert numbers == list(range(1, len(numbers) + 1)), f"号有洞或重号：{numbers}"
    text = mine[0].read_text(encoding="utf-8")
    mine_number = int(mine[0].name[:4])
    chained = re.search(r'down_revision\s*[:=]\s*"(\d{4})"', text)
    assert chained is not None, "模板表的迁移没写 down_revision"
    assert int(chained.group(1)) == mine_number - 1, "没有接在前一号后面"


# ───────────────────────── 二、注册表存得住，且既有三条纪律不倒


def _solidify(registry: Any, *, template_id: str, owner: Principal,
              html: str = MOCK_HTML, name: str = "我的模板") -> Any:
    from contracts_v04.models_v04 import template_checksum
    from flint.design.solidify import to_slots
    from flint.design.templates.registry import register_template

    templated, slots = to_slots(html)
    return register_template(
        registry, template_id=template_id, owner=owner, name=name, slots=slots,
        html=templated, source_deliverable_id=None, now=NOW,
        model=_record_model(), checksum_of=template_checksum)


def test_a_template_survives_a_new_registry_object() -> None:
    """固化一次、换一个 registry 对象——它还在。内存件在这一条上必红。"""
    _solidify(_registry(), template_id="tpl-1", owner=ME)

    rows = _registry().all()

    assert [r.template_id for r in rows] == ["tpl-1"]
    assert rows[0].slots == ("t:title",), "插槽没存住——元组顺序与内容都要还原"
    assert "{{t:title}}" in rows[0].html
    assert "data-mock-watermark" not in rows[0].html, "水印跟着模板进库了"
    assert rows[0].enabled is True


def test_the_same_content_never_makes_a_second_version() -> None:
    """去重按**内容**，不按名字（`registry.py` 文件头原话）——SQL 上再量一次。"""
    _solidify(_registry(), template_id="tpl-1", owner=ME, name="第一次")
    _solidify(_registry(), template_id="tpl-1", owner=ME, name="改了个名字")

    assert len(_registry().all()) == 1


def test_changed_content_appends_a_version_and_never_overwrites() -> None:
    """注册表是 append-only 的版本序列：固化过的东西可能已经被拿去渲染了，
    覆盖它等于让那些产物失去出处。

    upsert 写成「同 template_id 覆盖」的话这条必红——而那正是最省事的写法。
    """
    from flint.design.templates.registry import list_templates

    _solidify(_registry(), template_id="tpl-1", owner=ME)
    _solidify(_registry(), template_id="tpl-1", owner=ME,
              html='<div><h1 data-slot="t:title">另一份示例</h1>'
                   '<p data-slot="block:b1">另一段</p></div>')

    versions = list_templates(_registry(), owner=ME)

    assert [r.version for r in versions] == [1, 2]
    assert len({r.checksum for r in versions}) == 2
    assert versions[0].slots == ("t:title",), "旧版本被新版本覆盖了"


def test_my_templates_never_include_someone_elses() -> None:
    from flint.design.templates.registry import list_templates

    _solidify(_registry(), template_id="tpl-mine", owner=ME)
    _solidify(_registry(), template_id="tpl-theirs", owner=OTHER)

    assert [r.template_id for r in list_templates(_registry(), owner=ME)] == [
        "tpl-mine"]


def test_the_registry_reports_itself_available_when_the_table_is_there() -> None:
    """`available` 是 E6 那条降级线：不可用时**阻断固化与生产渲染，不阻断探索**。

    换成 SQL 之后它不再是一个构造参数，而是一件可以被问出来的事实。
    """
    assert _registry().available is True


# ───────────────────────── 三、分派表：移完那张表就空了


def test_template_solidify_moved_into_the_wired_kinds() -> None:
    """acceptance②：从 `UnwiredKindReason` 移进 `WIREABLE_KINDS`。"""
    from flint.jobs.dispatch import WIREABLE_KINDS, UnwiredKindReason

    assert "template_solidify" in WIREABLE_KINDS
    assert "template_solidify" not in UnwiredKindReason


def test_the_unwired_table_is_empty_now() -> None:
    """**移完那张表就空了**——本卡是最后一条。"""
    from flint.jobs.dispatch import UnwiredKindReason

    assert dict(UnwiredKindReason) == {}


def test_the_empty_unwired_table_is_still_a_live_mechanism() -> None:
    """空表最容易被下一个人当成「这个机制没用了」而顺手删掉。

    所以这里**造一条**未接线声明，断言整套机制照旧工作：
    它进得了总表、被调到时抛 `JobKindNotWired` 并把理由带出来。
    没有这一条的话，`UnwiredKindReason` 空了之后就没有任何判据在量它，
    而下一个新增的 kind 正需要它——那时静默丢弃会重新出现。
    """
    from flint.jobs.dispatch import JobKindNotWired, _not_wired

    handler = _not_wired("some_future_kind", "假设仓里还没有它的消费者。")

    with pytest.raises(JobKindNotWired, match="还没有它的消费者"):
        run(handler("job-1", {}))


def test_the_dispatch_table_still_covers_every_member_of_the_union() -> None:
    """`IncompleteDispatchTable` 判据不倒（acceptance⑥）。

    移动一条 kind 最容易的失手是「从 Unwired 里删了、忘了加进 WIREABLE」——
    那之后总表少一个成员，而 `build_dispatch_table` 正是为此而建。
    """
    from flint.jobs.dispatch import (
        WIREABLE_KINDS,
        UnwiredKindReason,
        build_dispatch_table,
        known_job_kinds,
    )

    table = build_dispatch_table({k: _noop() for k in WIREABLE_KINDS})

    assert set(table) == set(known_job_kinds())
    assert set(WIREABLE_KINDS) | set(UnwiredKindReason) == set(known_job_kinds())


def _noop() -> Any:
    async def handler(_job_id: str, _payload: Any) -> None:
        return None

    return handler


def test_the_worker_wires_a_real_handler_for_it() -> None:
    """接线**不是把名字挪个位置**：worker 侧要真有一个执行体。

    只改 `dispatch.py` 的话，`build_dispatch_table` 会当场抛
    `IncompleteDispatchTable`（handlers 少一个）——这条判据从 worker 那一侧量。
    """
    from flint.jobs.worker_main import build_handlers

    names = set(build_handlers(_worker_deps()))

    assert "template_solidify" in names


def _worker_deps() -> Any:
    from contracts_v04.models_v04 import UserProfile
    from flint.jobs.worker_main import WorkerDeps

    return WorkerDeps(
        dsn=DSN, redis_url="redis://localhost:56379", repo_root=REPO,
        profile=UserProfile(
            profile_id="p-1", owner=ME, identity={}, research={}, team={},
            assets={}, constraints={}, track_record={}, locale="zh",
            sensitivity_overrides={}, updated_at=NOW),
        now=NOW)


def test_the_handler_says_what_is_missing_instead_of_pretending_to_run() -> None:
    """缺注入件时**点名抛错**，NEVER 假装跑过（既有两个 handler 的同一形状）。

    假装跑过的后果是：作业变成 `done`，而模板一个都没落库——
    用户点了「固化」，列表里什么都没多出来，且没有任何一条错误可查。
    """
    from flint.jobs.worker_main import HandlerDepsMissing, build_handlers

    handler = build_handlers(_worker_deps())["template_solidify"]

    with pytest.raises(HandlerDepsMissing, match="template_solidify_deps"):
        run(handler("job-1", {}))


# ───────────────────────── 四、作业真跑一遍，落真表


def test_running_the_job_solidifies_and_lands_in_the_table() -> None:
    """acceptance③ 的后半：固化成功之后**库里那张表**里看得到。

    只断言作业不抛错的话，一个什么都没做的 handler 也能全绿。
    """
    from flint.jobs.template_solidify import TemplateSolidifyDeps, run_template_solidify

    events: list[Any] = []
    deps = TemplateSolidifyDeps(
        registry=_registry(), now=NOW,
        emit=_collector(events),
    )

    run(run_template_solidify("job-1", {
        "template_id": "tpl-job", "owner": {"kind": "user", "id": ME.id},
        "name": "作业固化出来的", "mock_html": MOCK_HTML,
        "source_deliverable_id": None,
    }, deps))

    rows = _registry().all()
    assert [r.template_id for r in rows] == ["tpl-job"]
    assert events, "一个事件都没发——SSE 那一侧看不到任何进展"
    assert events[-1].kind == "solidify_result"
    assert events[-1].accepted is True


def test_a_refused_solidify_says_why_and_lands_nothing() -> None:
    """固化被拒时：**一行都不落**，且理由是完整清单不是第一条。

    落一半的后果最坏：模板列表里多出一个「形状不全」的东西，
    而生产渲染只认模板、不再看内容。
    """
    from flint.design.solidify import SolidifyBlocked
    from flint.jobs.template_solidify import TemplateSolidifyDeps, run_template_solidify

    deps = TemplateSolidifyDeps(registry=_registry(), now=NOW, emit=_collector([]))

    with pytest.raises(SolidifyBlocked):
        run(run_template_solidify("job-2", {
            "template_id": "tpl-bad", "owner": {"kind": "user", "id": ME.id},
            "name": "没有插槽", "mock_html": "<div><p>一个槽都没标</p></div>",
            "source_deliverable_id": None,
        }, deps))

    assert _registry().all() == []


def _collector(sink: list[Any]) -> Any:
    async def emit(event: Any) -> None:
        sink.append(event)

    return emit


def test_the_job_never_reaches_the_network() -> None:
    """acceptance⑤：固化这条路**一次外网都不打**。

    `respx` 护栏在这里是阴性对照：固化是纯文本变换 + 落库，
    它一旦开始打网络，那是有人把 LLM 塞进了这条路——
    而模板的形状是确定性的，模型进来就不再可复现（S2-2 第三条铁律）。
    """
    import respx

    from flint.jobs.template_solidify import TemplateSolidifyDeps, run_template_solidify

    deps = TemplateSolidifyDeps(registry=_registry(), now=NOW, emit=_collector([]))

    with respx.mock(assert_all_called=False) as router:
        run(run_template_solidify("job-3", {
            "template_id": "tpl-net", "owner": {"kind": "user", "id": ME.id},
            "name": "不打网络", "mock_html": MOCK_HTML,
            "source_deliverable_id": None,
        }, deps))

        assert router.calls.call_count == 0, "固化这条路打了外网"


# ───────────────────────── 五、端点：not_provided 不再触发，四态不倒


def _client() -> Any:
    from fastapi.testclient import TestClient

    from flint.api.app import create_app

    return TestClient(create_app(dsn=DSN), raise_server_exceptions=False)


def test_the_templates_endpoint_no_longer_answers_not_provided() -> None:
    """接上之后 `GET /design/templates` 回**真列表**（空库时是空列表）。"""
    got = _client().get("/design/templates", headers={"x-user-id": ME.id})

    assert got.status_code == 200, got.text
    body = got.json()
    assert body.get("status") != "not_provided", "still not_provided：注册表没接上"


def test_the_not_provided_seam_is_still_there_for_an_unavailable_registry() -> None:
    """`DESIGN-03` 的四态口径不倒（acceptance④）：
    `not_checked` / `not_provided` / `down` / `ok` **各自成一态**。

    本卡让 `not_provided` 不再被触发，**NEVER 把它删掉**——
    注册表哪天真的不可用时，它仍然是唯一诚实的答复。
    """
    from fastapi.testclient import TestClient

    from flint.api.design import DesignApiDeps, create_design_app
    from flint.design.templates.registry import TemplateRegistry

    app = create_design_app(DesignApiDeps(
        registry=TemplateRegistry(available=False), now=lambda: NOW,
        load_export_inputs=None, model=None, event_model=None,
        deliverables_by_graph={}, load_changes=None, load_session=None))

    got = TestClient(app).get("/design/templates", headers={"x-user-id": ME.id})

    assert got.json()["status"] == "not_provided"


def test_solidifying_through_the_endpoint_lands_in_the_table() -> None:
    """acceptance③ 的前半：「固化为模板」按下去**真落库**。"""
    posted = _client().post("/design/templates", headers={"x-user-id": ME.id}, json={
        "template_id": "tpl-api", "name": "从端点固化", "mock_html": MOCK_HTML})

    assert posted.status_code == 200, posted.text

    async def _count() -> int:
        conn = await _conn()
        try:
            return int(await conn.fetchval(
                "SELECT count(*) FROM templates WHERE template_id = $1", "tpl-api"))
        finally:
            await conn.close()

    assert run(_count()) == 1

    listed = _client().get("/design/templates", headers={"x-user-id": ME.id}).json()
    assert [r["template_id"] for r in listed["items"]] == ["tpl-api"]
